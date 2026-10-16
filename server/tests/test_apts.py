from datetime import date

import pytest

from hub_mcp import apts
from hub_mcp.db import QueryError
from tests.fakes import FakeDb

TODAY = date(2026, 10, 14)
HOME = {"id": 7, "key": "seq:41135-001", "apt_name": "테스트단지", "umd_name": "정자동", "jibun": "1",
        "sgg_name": "경기도 성남시 분당구", "sgg_code": "41135", "build_year": 2015, "households": 500, "dong_count": 8}
BUNDANG = {"code": "41135", "name": "경기도 성남시 분당구"}


def metric(band, trades):
    return {"band": band, "recent_ppp": 3000.0, "recent_price": 70000, "ppp_3m": 3000.0, "price_3m": 70000,
            "trades_12m": trades, "chg_1m": 0.01, "chg_3m": 0.02, "chg_6m": 0.03, "chg_12m": 0.05,
            "peak_price": 80000, "peak_ym": "2021-10", "from_peak": -0.125, "as_of_ym": "2026-10"}


def test_detail_defaults_to_busiest_band():
    db = FakeDb({
        apts.COMPLEX_SQL: [HOME],
        apts.METRICS_SQL: [metric("84", 12), metric("74", 5)],
        apts.RANK_SQL: [{"mode": "84", "rank": 3}, {"mode": "auto", "rank": 4}],
        apts.SERIES_SQL: [{"ym": "2026-10"}, {"ym": "2026-09"}],
    })
    result = apts.complex_detail(db, 7, None, 24)
    assert result["band"] == "84"
    assert result["metric"]["trades_12m"] == 12
    assert result["bands_with_data"] == ["84", "74"]
    assert result["district_rank"] == {"band": 3, "auto": 4}
    assert db.params_for(apts.RANK_SQL) == [{"id": 7, "band": "84"}]
    assert [s["ym"] for s in result["series"]] == ["2026-09", "2026-10"]
    assert db.params_for(apts.SERIES_SQL) == [{"id": 7, "band": "84", "months": 24}]


def test_band_without_metric_still_returns_complex():
    db = FakeDb({apts.COMPLEX_SQL: [HOME], apts.METRICS_SQL: [metric("84", 12)], apts.TRADES_SQL: [{"price_manwon": 1}]})
    result = apts.complex_detail(db, 7, "74", 24)
    assert result["band"] == "74"
    assert result["metric"] is None
    assert result["district_rank"] == {"band": None, "auto": None}
    assert result["recent_trades"] == [{"price_manwon": 1}]


def test_complex_with_no_metrics_skips_band_queries():
    db = FakeDb({apts.COMPLEX_SQL: [HOME]})
    result = apts.complex_detail(db, 7, None, 24)
    assert result["band"] is None
    assert result["series"] == []
    assert db.params_for(apts.RANK_SQL) == [{"id": 7, "band": None}]
    assert db.params_for(apts.TRADES_SQL) == [{"id": 7, "band": None}]


def test_unknown_complex_points_to_search():
    with pytest.raises(QueryError, match="apt_search"):
        apts.complex_detail(FakeDb(), 999, None, 24)


def test_months_are_clamped():
    db = FakeDb({apts.COMPLEX_SQL: [HOME], apts.METRICS_SQL: [metric("74", 5)]})
    apts.complex_detail(db, 7, None, 500)
    assert db.params_for(apts.SERIES_SQL)[0]["months"] == 60


def test_my_home_uses_configured_key_and_band():
    db = FakeDb({
        apts.HOME_ID_SQL: [{"id": 7}],
        apts.COMPLEX_SQL: [HOME],
        apts.METRICS_SQL: [metric("84", 12), metric("74", 5)],
        apts.SGG_STAT_SQL: [{"leader_ppp": 4000.0}],
    })
    result = apts.my_home(db, "seq:41135-001", "74")
    assert result["is_home"] is True
    assert result["band"] == "74"
    assert result["district_stat"] == {"leader_ppp": 4000.0}
    assert db.params_for(apts.HOME_ID_SQL) == [{"key": "seq:41135-001"}]
    assert db.params_for(apts.SGG_STAT_SQL) == [{"sgg": "41135"}]


def test_my_home_without_key_explains_setting():
    with pytest.raises(QueryError, match="APT_HOME_KEY"):
        apts.my_home(FakeDb(), None, "74")


def test_my_home_key_not_in_data():
    with pytest.raises(QueryError, match="찾지 못했습니다"):
        apts.my_home(FakeDb(), "seq:0-0", "74")


def test_search_passes_word_patterns_and_clamps():
    db = FakeDb({apts.SEARCH_SQL: [{"id": 7}]})
    result = apts.search(db, "판교 테스트", None, 100)
    assert result == {"complexes": [{"id": 7}]}
    assert db.params_for(apts.SEARCH_SQL) == [{"likes": ["%판교%", "%테스트%"], "district_likes": None, "limit": 20}]


def test_search_with_district():
    db = FakeDb()
    apts.search(db, "자이", "분당", 10)
    assert db.params_for(apts.SEARCH_SQL)[0]["district_likes"] == ["%분당%"]


def test_ambiguous_district_lists_candidates():
    db = FakeDb({apts.DISTRICT_SQL: [{"code": "11140", "name": "서울특별시 중구"}, {"code": "28110", "name": "인천광역시 중구"}]})
    with pytest.raises(QueryError) as info:
        apts.resolve_district(db, "중구")
    assert "서울특별시 중구" in str(info.value)
    assert "인천광역시 중구" in str(info.value)


def test_unknown_district():
    with pytest.raises(QueryError, match="시군구"):
        apts.resolve_district(FakeDb(), "없는구")


def test_leaders_for_district():
    db = FakeDb({apts.DISTRICT_SQL: [BUNDANG], apts.LEADERS_SQL: [{"rank": 1}], apts.SGG_STAT_SQL: [{"leader_n": 20}]})
    result = apts.leaders(db, "분당구", "auto", 99)
    assert result["district"] == BUNDANG
    assert result["leaders"] == [{"rank": 1}]
    assert result["district_stat"] == {"leader_n": 20}
    assert db.params_for(apts.LEADERS_SQL) == [{"sgg": "41135", "mode": "auto", "limit": 30}]


def test_records_with_and_without_district():
    db = FakeDb({apts.DISTRICT_SQL: [BUNDANG]})
    apts.records(db, 30, None, 30, TODAY)
    apts.records(db, 500, "분당구", 500, TODAY)
    assert db.params_for(apts.RECORDS_SQL) == [
        {"since": date(2026, 9, 14), "sgg": None, "limit": 30},
        {"since": date(2026, 7, 14), "sgg": "41135", "limit": 50},
    ]
