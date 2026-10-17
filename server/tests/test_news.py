import re
from datetime import date

import pytest

from hub_mcp import news, stocks
from hub_mcp.db import QueryError
from tests.fakes import FakeDb

ALPHABET = {"symbol": "GOOG", "market": "US", "name": "Alphabet Inc. - Class C Capital Stock", "is_etf": False, "held": False}
META = {"symbol": "META", "market": "US", "name": "Meta Platforms, Inc. - Class A", "is_etf": False, "held": True}
HYNIX = {"symbol": "000660", "market": "KR", "name": "SK하이닉스", "is_etf": False, "held": False}
SOXX = {"symbol": "SOXX", "market": "US", "name": "iShares PHLX SOX Semiconductor Sector Index Fund", "is_etf": True, "held": False}


def item(id, title, summary=""):
    return {"id": id, "category": "invest", "source": "yna_economy", "title": title, "summary": summary,
            "url": f"https://x.test/{id}", "at_kst": "2026-10-17 09:00", "vote": None}


def test_headline_names_drop_corporate_tails():
    assert news.headline_name("Alphabet Inc. - Class C Capital Stock") == "Alphabet"
    assert news.headline_name("Meta Platforms, Inc. - Class A") == "Meta"
    assert news.headline_name("Amazon.com, Inc.") == "Amazon"
    assert news.headline_name("Apple Inc.") == "Apple"
    assert news.headline_name("삼성전자") == "삼성전자"


def test_latin_terms_stand_alone_and_korean_terms_take_particles():
    meta = re.compile(news.term_pattern("Meta"), re.I)
    assert meta.search("Meta shares jump") and meta.search("메타·Meta의 반등")
    assert not meta.search("Metadata leak") and not meta.search("TheMeta")
    assert re.search(news.term_pattern("하이닉스"), "하이닉스가 반등")
    assert news.term_pattern("a.b+c") == r"(?<![A-Za-z0-9])a\.b\+c(?![A-Za-z0-9])"


def test_stock_terms_use_aliases_symbols_and_etf_codes():
    aliases = {"GOOG": ("구글", "알파벳"), "000660": ("하이닉스",)}
    assert news.stock_terms(ALPHABET, aliases) == ["Alphabet", "GOOG", "구글", "알파벳"]
    assert news.stock_terms(HYNIX, aliases) == ["SK하이닉스", "하이닉스"]
    assert news.stock_terms(SOXX, aliases) == ["SOXX"]


def test_area_words_add_the_home_district():
    assert news.area_words("수원시 영통구", ("광교", "영통")) == ["광교", "영통"]
    assert news.area_words("서울 강남구", ()) == ["강남"]
    assert news.area_words(None, ("광교",)) == ["광교"]


def test_for_stocks_tags_each_article_with_the_stocks_it_names():
    db = FakeDb({news.WATCHED_SQL: [ALPHABET, META, HYNIX],
                 news.MATCH_SQL: [item(1, "구글·메타 실적 발표"), item(2, "하이닉스가 반등")]})
    result = news.for_stocks(db, None, 3, 30, {"GOOG": ("구글",), "META": ("메타",), "000660": ("하이닉스",)})
    assert [[s["symbol"] for s in i["stocks"]] for i in result["items"]] == [["GOOG", "META"], ["000660"]]
    assert result["items"][0]["stocks"][1]["held"] is True
    params = db.params_for(news.MATCH_SQL)[0]
    assert params["in_summary"] is False and params["category"] is None and len(params["patterns"]) == 8


def test_for_stocks_narrows_to_one_stock_and_clamps():
    db = FakeDb({news.WATCHED_SQL: [ALPHABET, HYNIX], stocks.RESOLVE_SQL: [{"symbol": "000660", "market": "KR", "name": "SK하이닉스"}]})
    result = news.for_stocks(db, "하이닉스", 99, 999, {})
    assert [s["symbol"] for s in result["stocks"]] == ["000660"]
    params = db.params_for(news.MATCH_SQL)[0]
    assert (params["days"], params["limit"]) == (30, 50)


def test_near_home_reads_the_district_and_searches_summaries_in_real_estate():
    apt = FakeDb({news.HOME_DISTRICT_SQL: [{"name": "수원시 영통구"}]})
    db = FakeDb({news.MATCH_SQL: [item(3, "광교 신축 입주")]})
    result = news.near_home(db, apt, "seq:1-2", ("광교",), 7, 20)
    assert result["words"] == ["광교", "영통"]
    params = db.params_for(news.MATCH_SQL)[0]
    assert params["category"] == "realestate" and params["in_summary"] is True


def test_near_home_without_words_explains_the_setting():
    with pytest.raises(QueryError, match="HUB_NEWS_AREAS"):
        news.near_home(FakeDb(), None, None, (), 7, 20)


def test_brief_defaults_to_the_latest_day():
    db = FakeDb({news.LATEST_BRIEF_SQL: [{"day": date(2026, 10, 17)}], news.BRIEF_SQL: [{"rank": 1}]})
    assert news.brief(db, None)["date"] == date(2026, 10, 17)
    assert db.params_for(news.BRIEF_SQL) == [{"day": date(2026, 10, 17)}]
    with pytest.raises(QueryError, match="브리핑이 없습니다"):
        news.brief(FakeDb(), date(2026, 1, 1))


def test_search_and_similar_clamp_and_report_missing_items():
    db = FakeDb()
    news.search(db, "  ", "tech", 500, 0)
    assert db.params_for(news.SEARCH_SQL) == [{"likes": None, "category": "tech", "days": 90, "limit": 1}]
    with pytest.raises(QueryError, match="찾지 못했습니다"):
        news.similar(FakeDb(), 7, 10)
