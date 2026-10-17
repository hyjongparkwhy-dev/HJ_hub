import re
from datetime import date

import pytest

from hub_mcp import news, stocks
from hub_mcp.db import QueryError
from tests.fakes import FakeDb

# Example stocks only; the owner's watchlist and neighbourhood stay out of this public repository.
BERKSHIRE = {"symbol": "BRK.B", "market": "US", "name": "Berkshire Hathaway Inc. - Class B", "is_etf": False, "held": False}
ARM = {"symbol": "ARM", "market": "US", "name": "Arm Holdings plc", "is_etf": False, "held": True}
HYUNDAI = {"symbol": "005380", "market": "KR", "name": "현대차", "is_etf": False, "held": False}
QQQ = {"symbol": "QQQ", "market": "US", "name": "Invesco QQQ Trust, Series 1", "is_etf": True, "held": False}


def item(id, title, summary=""):
    return {"id": id, "category": "invest", "source": "yna_economy", "title": title, "summary": summary,
            "url": f"https://x.test/{id}", "at_kst": "2026-10-17 09:00", "vote": None}


def test_headline_names_drop_corporate_tails():
    assert news.headline_name("Berkshire Hathaway Inc. - Class B") == "Berkshire Hathaway"
    assert news.headline_name("Arm Holdings plc") == "Arm"
    assert news.headline_name("Overstock.com, Inc.") == "Overstock"
    assert news.headline_name("Microsoft Corporation") == "Microsoft"
    assert news.headline_name("현대차") == "현대차"


def test_latin_terms_stand_alone_and_korean_terms_take_particles():
    arm = re.compile(news.term_pattern("Arm"), re.I)
    assert arm.search("Arm shares jump") and arm.search("암·Arm의 반등")
    assert not arm.search("Alarm sounds") and not arm.search("Army budget")
    assert re.search(news.term_pattern("현대차"), "현대차가 반등")
    assert news.term_pattern("a.b+c") == r"(?<![A-Za-z0-9])a\.b\+c(?![A-Za-z0-9])"


def test_stock_terms_use_aliases_symbols_and_etf_codes():
    aliases = {"BRK.B": ("버크셔",), "005380": ("현대자동차",)}
    assert news.stock_terms(BERKSHIRE, aliases) == ["Berkshire Hathaway", "BRK.B", "버크셔"]
    assert news.stock_terms(HYUNDAI, aliases) == ["현대차", "현대자동차"]
    assert news.stock_terms(QQQ, aliases) == ["QQQ"]


def test_area_words_add_the_home_district():
    assert news.area_words("성남시 분당구", ("판교", "분당")) == ["판교", "분당"]
    assert news.area_words("서울 강남구", ()) == ["강남"]
    assert news.area_words(None, ("판교",)) == ["판교"]


def test_for_stocks_tags_each_article_with_the_stocks_it_names():
    db = FakeDb({news.WATCHED_SQL: [BERKSHIRE, ARM, HYUNDAI],
                 news.MATCH_SQL: [item(1, "버크셔·Arm 실적 발표"), item(2, "현대차가 반등")]})
    result = news.for_stocks(db, None, 3, 30, {"BRK.B": ("버크셔",), "005380": ("현대자동차",)})
    assert [[s["symbol"] for s in i["stocks"]] for i in result["items"]] == [["BRK.B", "ARM"], ["005380"]]
    assert result["items"][0]["stocks"][1]["held"] is True
    params = db.params_for(news.MATCH_SQL)[0]
    assert params["in_summary"] is False and params["category"] is None and len(params["patterns"]) == 6


def test_for_stocks_narrows_to_one_stock_and_clamps():
    db = FakeDb({news.WATCHED_SQL: [BERKSHIRE, HYUNDAI], stocks.RESOLVE_SQL: [{"symbol": "005380", "market": "KR", "name": "현대차"}]})
    result = news.for_stocks(db, "현대차", 99, 999, {})
    assert [s["symbol"] for s in result["stocks"]] == ["005380"]
    params = db.params_for(news.MATCH_SQL)[0]
    assert (params["days"], params["limit"]) == (30, 50)


def test_near_home_reads_the_district_and_searches_summaries_in_real_estate():
    apt = FakeDb({news.HOME_DISTRICT_SQL: [{"name": "성남시 분당구"}]})
    db = FakeDb({news.MATCH_SQL: [item(3, "판교 신축 입주")]})
    result = news.near_home(db, apt, "seq:1-2", ("판교",), 7, 20)
    assert result["words"] == ["판교", "분당"]
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
