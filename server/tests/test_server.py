import json
from datetime import date

import pytest
from mcp.client import Client

from hub_mcp import apts, stocks
from hub_mcp.db import Db
from hub_mcp.server import build_server
from hub_mcp.settings import Settings
from tests.fakes import FakeDb

TODAY = date(2026, 10, 14)
SETTINGS = Settings(None, None, "seq:41135-001", "74")
TOOLS = ["apt_complex", "apt_leaders", "apt_my_home", "apt_records", "apt_search", "stock_detail", "stock_news", "stock_watchlist"]


def make_server(richrich=None, apt=None):
    return build_server(richrich or FakeDb(), apt or FakeDb(), SETTINGS, today=lambda: TODAY)


@pytest.mark.anyio
async def test_lists_eight_read_only_tools_with_descriptions():
    async with Client(make_server()) as client:
        tools = (await client.list_tools()).tools
    assert sorted(t.name for t in tools) == TOOLS
    assert all(t.annotations.read_only_hint for t in tools)
    assert all(t.description and len(t.description) > 40 for t in tools)


@pytest.mark.anyio
async def test_result_is_json_text():
    row = {"symbol": "005930", "market": "KR", "name": "삼성전자", "is_etf": False, "avg_price": None, "quantity": None,
           "last_close": 60000.0, "last_close_date": "2026-10-13", "quote_price": None, "quote_change_pct": None,
           "quote_day": None, "verdict": None, "opinion_date": None, "confidence": None}
    async with Client(make_server(richrich=FakeDb({stocks.WATCHLIST_SQL: [row]}))) as client:
        result = await client.call_tool("stock_watchlist", {})
    assert not result.is_error
    assert json.loads(result.content[0].text)["stocks"][0]["price"] == 60000.0


@pytest.mark.anyio
async def test_query_error_reaches_claude_as_tool_error():
    async with Client(make_server()) as client:
        result = await client.call_tool("stock_detail", {"query": "없는종목"})
    assert result.is_error
    assert "찾지 못했습니다" in result.content[0].text


@pytest.mark.anyio
async def test_missing_database_url_is_explained():
    server = build_server(Db(None, "RichRich", "RICHRICH_DATABASE_URL"), FakeDb(), SETTINGS, today=lambda: TODAY)
    async with Client(server) as client:
        result = await client.call_tool("stock_watchlist", {})
    assert result.is_error
    assert "RICHRICH_DATABASE_URL" in result.content[0].text


@pytest.mark.anyio
async def test_invalid_band_is_rejected_before_query():
    apt = FakeDb()
    async with Client(make_server(apt=apt)) as client:
        result = await client.call_tool("apt_complex", {"complex_id": 7, "band": "99"})
    assert result.is_error
    assert apt.calls == []


@pytest.mark.anyio
async def test_my_home_uses_settings_and_injected_today():
    apt = FakeDb({apts.HOME_ID_SQL: [{"id": 7}], apts.COMPLEX_SQL: [{"id": 7, "sgg_code": "41135"}]})
    async with Client(make_server(apt=apt)) as client:
        home = await client.call_tool("apt_my_home", {})
        recs = await client.call_tool("apt_records", {"days": 30})
    assert not home.is_error and not recs.is_error
    assert apt.params_for(apts.HOME_ID_SQL) == [{"key": "seq:41135-001"}]
    assert json.loads(recs.content[0].text)["since"] == "2026-09-14"


def test_instructions_carry_owner_context_only_from_settings():
    plain = build_server(FakeDb(), FakeDb(), SETTINGS, today=lambda: TODAY)
    personal = build_server(FakeDb(), FakeDb(), Settings(None, None, None, None, "Korean investor in 분당"), today=lambda: TODAY)
    assert "분당" not in plain.instructions
    assert "Owner: Korean investor in 분당." in personal.instructions
