"""Runs the real SQL against the real databases (read-only, so safe on production). Skipped without URLs."""
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import StdioServerParameters
from mcp.client import Client

from hub_mcp import apts, stocks
from hub_mcp.server import kst_today

SERVER_DIR = Path(__file__).resolve().parents[1]


def test_live_watchlist_detail_and_news(richrich_db):
    result = stocks.watchlist(richrich_db, kst_today())
    assert isinstance(result["stocks"], list)
    if result["stocks"]:
        first = result["stocks"][0]
        detail = stocks.stock_detail(richrich_db, first["symbol"], first["market"], 5, kst_today())
        assert detail["stock"]["symbol"] == first["symbol"]
        assert len(detail["prices"]) <= 5
        news = stocks.stock_news(richrich_db, first["symbol"], 7, 5, kst_today())
        assert len(news["news"]) <= 5
    assert isinstance(stocks.stock_news(richrich_db, None, 3, 5, kst_today())["news"], list)


def test_live_my_home(apt_db, settings):
    home = apts.my_home(apt_db, settings.apt_home_key, settings.apt_home_band)
    assert home["complex"]["apt_name"]
    assert home["band"] == settings.apt_home_band
    assert home["series"] == sorted(home["series"], key=lambda s: s["ym"])
    # The auto rank must agree with what apt_leaders shows for the same district.
    ranked = apts.leaders(apt_db, home["complex"]["sgg_name"], "auto", 30)["leaders"]
    shown = next((r["rank"] for r in ranked if r["complex_id"] == home["complex"]["id"]), None)
    assert home["district_rank"]["auto"] == shown


def test_live_search_finds_home(apt_db, settings):
    home = apts.my_home(apt_db, settings.apt_home_key, settings.apt_home_band)
    found = apts.search(apt_db, home["complex"]["apt_name"], None, 20)["complexes"]
    assert home["complex"]["id"] in [c["id"] for c in found]


def test_live_leaders_and_records(apt_db):
    ranked = apts.leaders(apt_db, "분당구", "auto", 5)
    assert ranked["district"]["code"] == "41135"
    assert [r["rank"] for r in ranked["leaders"]] == sorted(r["rank"] for r in ranked["leaders"])
    recs = apts.records(apt_db, 92, None, 10, kst_today())["records"]
    assert len(recs) <= 10
    assert [r["contract_date"] for r in recs] == sorted((r["contract_date"] for r in recs), reverse=True)


@pytest.mark.anyio
async def test_live_stdio_entrypoint(settings):
    if not settings.apt_database_url:
        pytest.skip("APT_DATABASE_URL not set")
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "hub_mcp"], env={**os.environ, "PYTHONPATH": str(SERVER_DIR)}
    )
    async with Client(params) as client:
        tools = (await client.list_tools()).tools
        home = await client.call_tool("apt_my_home", {})
        brief = await client.call_tool("news_brief", {})
    assert len(tools) == 13
    assert not home.is_error and not brief.is_error
    assert json.loads(home.content[0].text)["is_home"] is True


def test_live_news_tools(richrich_db, apt_db, settings):
    from hub_mcp import news

    latest = news.brief(richrich_db, None)
    assert 1 <= len(latest["items"]) <= 20
    found = news.search(richrich_db, None, "tech", 3, 5)["items"]
    assert len(found) <= 5 and all(i["category"] == "tech" for i in found)
    if found:
        near = news.similar(richrich_db, found[0]["id"], 3)
        assert len(near["similar"]) <= 3 and all(0 <= s["similarity"] <= 100 for s in near["similar"])
    stocks_news = news.for_stocks(richrich_db, None, 7, 10, dict(settings.news_aliases))
    assert all(i["stocks"] for i in stocks_news["items"])  # SQL and Python agree on every match
    home = news.near_home(richrich_db, apt_db, settings.apt_home_key, settings.news_areas, 30, 5)
    assert home["words"] and all(i["category"] == "realestate" for i in home["items"])
