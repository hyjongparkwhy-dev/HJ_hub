from datetime import date

import pytest

from hub_mcp import stocks
from hub_mcp.db import QueryError
from tests.fakes import FakeDb

TODAY = date(2026, 10, 14)
SAMSUNG = {"symbol": "005930", "market": "KR", "name": "삼성전자"}


def watch_row(**overrides):
    row = {
        "symbol": "005930", "market": "KR", "name": "삼성전자", "is_etf": False,
        "avg_price": 50000.0, "quantity": 10.0,
        "last_close": 60000.0, "last_close_date": "2026-10-13",
        "quote_price": 61000.0, "quote_change_pct": 1.67, "quote_day": "2026-10-14",
        "verdict": "HOLD", "opinion_date": "2026-10-14", "confidence": "MID",
    }
    return {**row, **overrides}


def test_watchlist_prefers_newer_quote_and_computes_pnl():
    db = FakeDb({stocks.WATCHLIST_SQL: [watch_row()]})
    result = stocks.watchlist(db, TODAY)
    item = result["stocks"][0]
    assert item["price"] == 61000.0
    assert item["price_date"] == "2026-10-14"
    assert item["holding"] == {"avg_price": 50000.0, "quantity": 10.0, "pnl_pct": 22.0}
    assert item["latest_opinion"] == {"verdict": "HOLD", "date": "2026-10-14", "confidence": "MID"}


def test_uses_close_when_quote_is_older():
    db = FakeDb({stocks.WATCHLIST_SQL: [watch_row(quote_day="2026-10-10")]})
    item = stocks.watchlist(db, TODAY)["stocks"][0]
    assert (item["price"], item["price_date"]) == (60000.0, "2026-10-13")


def test_not_held_and_no_opinion():
    db = FakeDb({stocks.WATCHLIST_SQL: [watch_row(avg_price=None, quantity=None, verdict=None, opinion_date=None, confidence=None)]})
    item = stocks.watchlist(db, TODAY)["stocks"][0]
    assert item["holding"] is None
    assert item["latest_opinion"] is None


def test_watchlist_events_cover_next_14_days():
    db = FakeDb()
    stocks.watchlist(db, TODAY)
    assert db.params_for(stocks.EVENTS_SQL) == [{"start": TODAY, "end": date(2026, 10, 28), "symbol": None}]


def test_resolve_by_exact_symbol_beats_name_matches():
    db = FakeDb({stocks.RESOLVE_SQL: [SAMSUNG, {"symbol": "005935", "market": "KR", "name": "삼성전자우"}]})
    assert stocks.resolve_stock(db, "005930") == SAMSUNG


def test_ambiguous_name_lists_candidates():
    db = FakeDb({stocks.RESOLVE_SQL: [SAMSUNG, {"symbol": "006400", "market": "KR", "name": "삼성SDI"}]})
    with pytest.raises(QueryError) as info:
        stocks.resolve_stock(db, "삼성")
    assert "삼성전자(005930, KR)" in str(info.value)
    assert "삼성SDI(006400, KR)" in str(info.value)


def test_unknown_stock_points_to_watchlist():
    with pytest.raises(QueryError, match="stock_watchlist"):
        stocks.resolve_stock(FakeDb(), "없는종목")


def test_detail_returns_prices_oldest_first_and_holding_pnl_from_last_close():
    db = FakeDb({
        stocks.RESOLVE_SQL: [SAMSUNG],
        stocks.PRICES_SQL: [{"date": "2026-10-14", "close": 60000.0, "volume": 1}, {"date": "2026-10-13", "close": 58000.0, "volume": 1}],
        stocks.HOLDING_SQL: [{"avg_price": 50000.0, "quantity": 10.0, "bought_at": "2026-01-02"}],
    })
    result = stocks.stock_detail(db, "005930", None, 20, TODAY)
    assert [p["date"] for p in result["prices"]] == ["2026-10-13", "2026-10-14"]
    assert result["holding"] == {"avg_price": 50000.0, "quantity": 10.0, "pnl_pct": 20.0, "bought_at": "2026-01-02"}
    assert result["latest_opinion"] is None
    assert db.params_for(stocks.EVENTS_SQL) == [{"start": TODAY, "end": date(2026, 12, 13), "symbol": "005930"}]


def test_days_are_clamped():
    db = FakeDb({stocks.RESOLVE_SQL: [SAMSUNG]})
    stocks.stock_detail(db, "005930", None, 10000, TODAY)
    assert db.params_for(stocks.PRICES_SQL)[0]["limit"] == 250


def test_news_without_query_reads_everything_since_cutoff():
    db = FakeDb({stocks.NEWS_SQL: [{"title": "t", "summary": None}]})
    result = stocks.stock_news(db, None, 7, 20, TODAY)
    assert result["since"] == "2026-10-07"
    assert result["stock"] is None
    assert db.params_for(stocks.NEWS_SQL) == [{"since": date(2026, 10, 7), "symbol": None, "limit": 20}]
    assert any("null" in note for note in result["notes"])


def test_news_for_one_stock_filters_both_lists_and_clamps():
    db = FakeDb({stocks.RESOLVE_SQL: [SAMSUNG]})
    result = stocks.stock_news(db, "삼성전자", 365, 999, TODAY)
    assert result["stock"] == SAMSUNG
    assert db.params_for(stocks.NEWS_SQL) == [{"since": date(2026, 9, 14), "symbol": "005930", "limit": 50}]
    assert db.params_for(stocks.DISCLOSURES_SQL) == [{"since": date(2026, 9, 14), "symbol": "005930", "limit": 50}]


def test_exact_name_wins_over_longer_names():
    db = FakeDb({stocks.RESOLVE_SQL: [SAMSUNG, {"symbol": "005935", "market": "KR", "name": "삼성전자우"}]})
    assert stocks.resolve_stock(db, "삼성 전자") == SAMSUNG
