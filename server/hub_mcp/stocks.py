"""Read-only questions about the RichRich database (public schema)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from hub_mcp.db import QueryError, Reader, clamp, like_tokens

PRICE_NOTE = "가격은 각 시장 통화(KR=원, US=달러) 기준이고 pnl_pct는 평균 매입가 대비 등락률(%)입니다. 환율은 반영하지 않습니다."
OPINION_NOTE = "verdict는 RichRich 원칙 엔진의 기계적 채점 결과이며 투자 권유가 아닙니다."
SUMMARY_NOTE = "summary·plain_explanation이 null인 항목은 아직 AI 요약 전입니다(RichRich의 Gemini가 꺼져 있을 수 있음)."

WATCHLIST_SQL = """
select w.symbol, w.market, w.name, w.is_etf,
       h.avg_price, h.quantity,
       p.close as last_close, p.date as last_close_date,
       q.price as quote_price, q.change_pct as quote_change_pct, q.day as quote_day,
       o.verdict, o.date as opinion_date, o.confidence
from watchlist w
left join holdings h on h.symbol = w.symbol and h.market = w.market
left join quote_snapshots q on q.symbol = w.symbol and q.market = w.market
left join lateral (
  select d.close, d.date from prices_daily d
  where d.symbol = w.symbol and d.market = w.market
  order by d.date desc limit 1
) p on true
left join lateral (
  select o.verdict, o.date, o.confidence from opinions o
  where o.symbol = w.symbol and o.market = w.market
  order by o.date desc, o.id desc limit 1
) o on true
order by w.market, w.symbol
"""

EVENTS_SQL = """
select date, type, symbol, title from events
where date between %(start)s and %(end)s
  and (%(symbol)s::text is null or symbol = %(symbol)s)
order by date, type
limit 40
"""

RESOLVE_SQL = """
select symbol, market, name from watchlist
where (upper(symbol) = upper(%(q)s) or replace(name, ' ', '') ilike all(%(likes)s))
  and (%(market)s::text is null or market = %(market)s)
order by upper(symbol) = upper(%(q)s) desc, market, symbol
limit 10
"""

OPINION_SQL = """
select date, verdict, total_score, confidence, scores, narrative, note, target_weight,
       vol_annual, vol_rank, price_date, config_version
from opinions
where symbol = %(symbol)s and market = %(market)s
order by date desc, id desc
limit 1
"""

PRICES_SQL = """
select date, close, volume from prices_daily
where symbol = %(symbol)s and market = %(market)s
order by date desc
limit %(limit)s
"""

HOLDING_SQL = """
select avg_price, quantity, bought_at from holdings
where symbol = %(symbol)s and market = %(market)s
"""

FUNDAMENTALS_SQL = """
select as_of, data from fundamentals
where symbol = %(symbol)s and market = %(market)s
order by as_of desc
limit 1
"""

NEWS_SQL = """
select title, source, url, published_at, summary, sentiment, important, symbols
from news_items
where published_at >= %(since)s
  and (%(symbol)s::text is null or %(symbol)s = any(symbols))
order by published_at desc nulls last
limit %(limit)s
"""

DISCLOSURES_SQL = """
select rcept_no, symbol, corp_name, title, filed_on, importance, plain_explanation, impact
from disclosures
where filed_on >= %(since)s
  and (%(symbol)s::text is null or symbol = %(symbol)s)
order by filed_on desc, rcept_no desc
limit %(limit)s
"""


def resolve_stock(db: Reader, query: str, market: str | None = None) -> dict[str, Any]:
    q = query.strip()
    rows = db.all(RESOLVE_SQL, {"q": q, "likes": like_tokens(q), "market": market})
    if not rows:
        raise QueryError(f"관심 종목에서 '{q}'을(를) 찾지 못했습니다. stock_watchlist로 목록을 확인해 주세요.")
    exact = [r for r in rows if r["symbol"].upper() == q.upper()]
    # "삼성전자" must not be blocked by "삼성전자우" on the same watchlist.
    same_name = [r for r in rows if _compact(r["name"]) == _compact(q)]
    candidates = exact or same_name or rows
    if len(candidates) > 1:
        names = ", ".join(f"{r['name']}({r['symbol']}, {r['market']})" for r in candidates)
        raise QueryError(f"'{q}'에 해당하는 종목이 여러 개입니다: {names}. 종목 코드나 market으로 좁혀 주세요.")
    return candidates[0]


def watchlist(db: Reader, today: date) -> dict[str, Any]:
    rows = db.all(WATCHLIST_SQL)
    events = db.all(EVENTS_SQL, {"start": today, "end": today + timedelta(days=14), "symbol": None})
    return {"stocks": [_watch_item(r) for r in rows], "upcoming_events": events, "notes": [PRICE_NOTE, OPINION_NOTE]}


def stock_detail(db: Reader, query: str, market: str | None, days: int, today: date) -> dict[str, Any]:
    stock = resolve_stock(db, query, market)
    key = {"symbol": stock["symbol"], "market": stock["market"]}
    prices = list(reversed(db.all(PRICES_SQL, {**key, "limit": clamp(days, 1, 250)})))
    holding_row = db.one(HOLDING_SQL, key)
    last_close = prices[-1]["close"] if prices else None
    holding = None
    if holding_row is not None:
        holding = {**_holding(holding_row["avg_price"], holding_row["quantity"], last_close), "bought_at": holding_row["bought_at"]}
    return {
        "stock": stock,
        "latest_opinion": db.one(OPINION_SQL, key),
        "prices": prices,
        "holding": holding,
        "fundamentals": db.one(FUNDAMENTALS_SQL, key),
        "upcoming_events": db.all(EVENTS_SQL, {"start": today, "end": today + timedelta(days=60), "symbol": stock["symbol"]}),
        "notes": [PRICE_NOTE, OPINION_NOTE],
    }


def stock_news(db: Reader, query: str | None, days: int, limit: int, today: date) -> dict[str, Any]:
    stock = resolve_stock(db, query) if query and query.strip() else None
    since = today - timedelta(days=clamp(days, 1, 30))
    params = {"since": since, "symbol": stock["symbol"] if stock else None, "limit": clamp(limit, 1, 50)}
    return {
        "since": since.isoformat(),
        "stock": stock,
        "news": db.all(NEWS_SQL, params),
        "disclosures": db.all(DISCLOSURES_SQL, params),
        "notes": [SUMMARY_NOTE],
    }


def _compact(text: str) -> str:
    return "".join(text.split()).upper()


def _watch_item(r: dict[str, Any]) -> dict[str, Any]:
    price, price_date = _current_price(r)
    opinion = None if r["verdict"] is None else {"verdict": r["verdict"], "date": r["opinion_date"], "confidence": r["confidence"]}
    return {
        "symbol": r["symbol"],
        "market": r["market"],
        "name": r["name"],
        "is_etf": r["is_etf"],
        "price": price,
        "price_date": price_date,
        "latest_opinion": opinion,
        "holding": _holding(r["avg_price"], r["quantity"], price),
    }


def _current_price(r: dict[str, Any]) -> tuple[float | None, str | None]:
    """Intraday quote when it is at least as new as the last daily close (ISO dates compare as strings)."""
    quote_day, close_day = r["quote_day"], r["last_close_date"]
    if r["quote_price"] is not None and (close_day is None or quote_day >= close_day):
        return r["quote_price"], quote_day
    return r["last_close"], close_day


def _holding(avg_price: float | None, quantity: float | None, price: float | None) -> dict[str, Any] | None:
    if avg_price is None:
        return None
    pnl = None if price is None else round((price / avg_price - 1) * 100, 2)
    return {"avg_price": avg_price, "quantity": quantity, "pnl_pct": pnl}
