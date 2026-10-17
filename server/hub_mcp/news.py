"""Read-only questions about the news curator (the `hub` schema in the RichRich database)."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from hub_mcp.db import QueryError, Reader, clamp, like_tokens
from hub_mcp.stocks import resolve_stock

CATEGORY_NOTE = "category: invest=투자, realestate=부동산, tech=기술. at_kst는 기사 시각(없으면 수집 시각, 한국 시간)입니다."
VOTE_NOTE = "vote는 주인이 누른 👍(1)/👎(-1), 없으면 null입니다."
POOL_NOTE = "기사 풀은 언론사 27곳 RSS를 4시간마다 모은 것으로 최근 90일치만 남아 있습니다. summary는 RSS 설명이며 비어 있을 수 있습니다."
MATCH_NOTE = (
    "제목에 종목 이름·별칭이 나온 기사만 고릅니다(뜻으로 찾지 않음). 미국 종목은 my-hub/.env의 HUB_NEWS_ALIASES에 "
    "한국어 별칭(예: GOOG:구글)이 있어야 한국어 기사를 찾습니다."
)

ITEM_COLUMNS = """
i.id, i.category, i.source, i.title, i.summary, i.url,
to_char(coalesce(i.published_at, i.fetched_at) at time zone 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') as at_kst, f.vote
"""

LATEST_BRIEF_SQL = "select max(brief_date) as day from hub.brief"

BRIEF_SQL = f"""
select bi.rank, round(bi.score * 100)::int as relevance, bi.reason, bi.title as brief_title, bi.summary as brief_summary,
       {ITEM_COLUMNS}
from hub.brief b
join hub.brief_item bi on bi.brief_id = b.id
join hub.item i on i.id = bi.item_id
left join hub.feedback f on f.item_id = i.id
where b.brief_date = %(day)s
order by bi.rank
"""

SEARCH_SQL = f"""
select {ITEM_COLUMNS}
from hub.item i
left join hub.feedback f on f.item_id = i.id
where coalesce(i.published_at, i.fetched_at) > now() - make_interval(days => %(days)s)
  and (%(likes)s::text[] is null or i.title ilike all(%(likes)s))
  and (%(category)s::text is null or i.category = %(category)s)
order by coalesce(i.published_at, i.fetched_at) desc
limit %(limit)s
"""

ITEM_SQL = f"""
select {ITEM_COLUMNS}
from hub.item i left join hub.feedback f on f.item_id = i.id
where i.id = %(id)s
"""

# The <=> operator lives in the extensions schema; qualifying it keeps the query independent of search_path.
SIMILAR_SQL = f"""
select round((1 - (i.embedding operator(extensions.<=>) b.embedding)) * 100)::int as similarity, {ITEM_COLUMNS}
from hub.item i
cross join (select embedding from hub.item where id = %(id)s) b
left join hub.feedback f on f.item_id = i.id
where i.id <> %(id)s
order by i.embedding operator(extensions.<=>) b.embedding
limit %(limit)s
"""

WATCHED_SQL = """
select w.symbol, w.market, w.name, w.is_etf, h.symbol is not null as held
from watchlist w
left join holdings h on h.symbol = w.symbol and h.market = w.market
order by w.market, w.symbol
"""

MATCH_SQL = f"""
select {ITEM_COLUMNS}
from hub.item i
left join hub.feedback f on f.item_id = i.id
where coalesce(i.published_at, i.fetched_at) > now() - make_interval(days => %(days)s)
  and (%(category)s::text is null or i.category = %(category)s)
  and (i.title ~* any(%(patterns)s) or (%(in_summary)s and coalesce(i.summary, '') ~* any(%(patterns)s)))
order by coalesce(i.published_at, i.fetched_at) desc
limit %(limit)s
"""

HOME_DISTRICT_SQL = """
select s.name from apt.complex c join apt.sgg s on s.code = c.sgg_code where c.key = %(key)s
"""

# Corporate tails that never appear in headlines: "Meta Platforms, Inc." is "Meta", "Amazon.com, Inc." is "Amazon".
_NAME_TAIL = re.compile(
    r"(\s+-\s+.*$)|(\.com\b)|([,\s]+(inc|corp|corporation|co|ltd|plc|holdings|group|platforms|company)\.?)+$", re.I
)
_REGEX_SPECIAL = re.compile(r"([\\.^$|?*+()\[\]{}])")
_LATIN = re.compile(r"[A-Za-z]")


def headline_name(name: str) -> str:
    previous = None
    while previous != name:
        previous, name = name, _NAME_TAIL.sub("", name).strip()
    return name


def term_pattern(term: str) -> str:
    """A pattern Postgres (~*) and Python (re.I) read the same way. Latin words must stand alone, so "Meta" skips
    "metadata"; Korean names match inside words because particles attach to them ("삼성전자가")."""
    literal = _REGEX_SPECIAL.sub(r"\\\1", term)
    if _LATIN.search(term):
        return f"(?<![A-Za-z0-9]){literal}(?![A-Za-z0-9])"
    return literal


def stock_terms(stock: Mapping[str, Any], aliases: Mapping[str, Sequence[str]]) -> list[str]:
    symbol = stock["symbol"].upper()
    if stock["is_etf"]:
        terms = [symbol]  # fund names ("iShares PHLX SOX ...") never appear in headlines
    else:
        terms = [headline_name(stock["name"])]
        if stock["market"] == "US":
            terms.append(symbol)
    terms.extend(aliases.get(symbol, ()))
    return list(dict.fromkeys(t for t in terms if len(t) >= 2))


def area_words(district: str | None, extra: Sequence[str]) -> list[str]:
    """'수원시 영통구' adds '영통'; articles name the neighbourhood, not the administrative district."""
    words = list(extra)
    if district:
        last = district.split()[-1]
        words.append(last[:-1] if len(last) > 2 and last[-1] in "구시군" else last)
    return list(dict.fromkeys(w for w in words if w))


def brief(db: Reader, day: date | None) -> dict[str, Any]:
    target = day or (db.one(LATEST_BRIEF_SQL) or {}).get("day")
    if target is None:
        raise QueryError("아직 브리핑이 없습니다. 매일 오전 9시에 만들어집니다.")
    rows = db.all(BRIEF_SQL, {"day": target})
    if not rows:
        raise QueryError(f"{target} 브리핑이 없습니다. date를 비우면 가장 최근 브리핑을 봅니다.")
    return {
        "date": target,
        "items": rows,
        "notes": [
            "relevance는 관심 주제·투표와 비슷한 정도를 0~100으로 나타낸 순위 점수입니다. "
            "brief_title·brief_summary는 브리핑에 실린 제목과 Gemini 한국어 요약입니다.",
            CATEGORY_NOTE,
            VOTE_NOTE,
        ],
    }


def search(db: Reader, query: str | None, category: str | None, days: int, limit: int) -> dict[str, Any]:
    likes = like_tokens(query) if query and query.strip() else None
    params = {"likes": likes, "category": category, "days": clamp(days, 1, 90), "limit": clamp(limit, 1, 50)}
    return {"query": query, "items": db.all(SEARCH_SQL, params), "notes": [POOL_NOTE, CATEGORY_NOTE, VOTE_NOTE]}


def similar(db: Reader, item_id: int, limit: int) -> dict[str, Any]:
    base = db.one(ITEM_SQL, {"id": item_id})
    if base is None:
        raise QueryError(f"기사 {item_id}를 찾지 못했습니다. 90일이 지나 지워졌을 수 있습니다.")
    return {
        "base": base,
        "similar": db.all(SIMILAR_SQL, {"id": item_id, "limit": clamp(limit, 1, 20)}),
        "notes": ["similarity는 내용이 비슷한 정도(0~100, 100에 가까울수록 같은 이야기)입니다.", CATEGORY_NOTE],
    }


def for_stocks(
    db: Reader, query: str | None, days: int, limit: int, aliases: Mapping[str, Sequence[str]]
) -> dict[str, Any]:
    watched = db.all(WATCHED_SQL)
    if query and query.strip():
        chosen = resolve_stock(db, query)
        watched = [w for w in watched if (w["symbol"], w["market"]) == (chosen["symbol"], chosen["market"])]
    if not watched:
        raise QueryError("RichRich 관심 종목이 비어 있습니다.")
    stocks = [{**w, "terms": stock_terms(w, aliases)} for w in watched]
    patterns = [term_pattern(t) for s in stocks for t in s["terms"]]
    params = {"days": clamp(days, 1, 30), "limit": clamp(limit, 1, 50), "category": None, "patterns": patterns, "in_summary": False}
    matchers = [(s, re.compile("|".join(term_pattern(t) for t in s["terms"]), re.I)) for s in stocks]
    items = []
    for row in db.all(MATCH_SQL, params):
        hits = [s for s, rx in matchers if rx.search(row["title"])]
        items.append({**row, "stocks": [{"symbol": s["symbol"], "name": s["name"], "held": s["held"]} for s in hits]})
    return {
        "stocks": [{k: s[k] for k in ("symbol", "market", "name", "held", "terms")} for s in stocks],
        "items": items,
        "notes": [MATCH_NOTE, "held는 RichRich holdings에 등록된 보유 종목인지입니다.", POOL_NOTE, CATEGORY_NOTE],
    }


def near_home(
    news_db: Reader, apt_db: Reader | None, home_key: str | None, extra: Sequence[str], days: int, limit: int
) -> dict[str, Any]:
    district = None
    if apt_db is not None and home_key:
        try:
            district = (apt_db.one(HOME_DISTRICT_SQL, {"key": home_key}) or {}).get("name")
        except QueryError:
            district = None  # the configured words still work without apt-leader
    words = area_words(district, extra)
    if not words:
        raise QueryError("동네 단어가 없습니다. my-hub/.env에 HUB_NEWS_AREAS(예: 광교,영통)를 넣어 주세요.")
    params = {
        "days": clamp(days, 1, 90),
        "limit": clamp(limit, 1, 50),
        "category": "realestate",
        "patterns": [term_pattern(w) for w in words],
        "in_summary": True,
    }
    return {
        "words": words,
        "items": news_db.all(MATCH_SQL, params),
        "notes": ["부동산 기사 중 제목이나 요약에 동네 단어가 나온 것만 고릅니다.", POOL_NOTE, VOTE_NOTE],
    }
