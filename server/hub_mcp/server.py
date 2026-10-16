"""MCP server that lets Claude read the owner's RichRich and apt-leader data (never writes)."""
from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from hub_mcp import apts, stocks
from hub_mcp.db import Db, QueryError, Reader
from hub_mcp.settings import Settings, load_settings

KST = datetime.timezone(datetime.timedelta(hours=9))
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

Market = Literal["KR", "US"]
Band = Literal["59", "74", "84", "large"]
Mode = Literal["auto", "59", "74", "84", "large"]

INSTRUCTIONS = (
    "Personal data of the owner. "
    "stock_* tools read RichRich: the owner's watchlist, holdings, rule-based opinions, news and DART filings. "
    "apt_* tools read apt-leader: 수도권 apartment trades, per-district 대장 아파트 rankings and 내 집 (apt_my_home). "
    "Every result carries `notes` explaining units; prices of apartments are in 만원. "
    "Opinions are mechanical scores, not advice: report them, do not turn them into buy/sell recommendations. "
    "Answer the owner in Korean."
)


def kst_today() -> datetime.date:
    return datetime.datetime.now(KST).date()


def _answer(produce: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return produce()
    except QueryError as e:
        raise ToolError(str(e)) from e


def build_server(
    richrich: Reader, apt: Reader, settings: Settings, today: Callable[[], datetime.date] = kst_today
) -> MCPServer:
    instructions = INSTRUCTIONS if not settings.owner_context else f"{INSTRUCTIONS} Owner: {settings.owner_context}."
    server = MCPServer("my-hub", instructions=instructions)

    @server.tool(annotations=READ_ONLY)
    def stock_watchlist() -> dict:
        """List every stock on the owner's RichRich watchlist with current price, latest opinion
        (BUY/HOLD/SELL/REDUCE/WITHHELD), holding with profit % if owned, and market events in the next 14 days."""
        return _answer(lambda: stocks.watchlist(richrich, today()))

    @server.tool(annotations=READ_ONLY)
    def stock_detail(query: str, market: Market | None = None, days: int = 20) -> dict:
        """One watchlist stock by ticker (005930, AAPL) or Korean/English name: latest opinion with per-principle
        scores and reasons, the last `days` daily closes (max 250), holding, latest fundamentals, events in 60 days."""
        return _answer(lambda: stocks.stock_detail(richrich, query, market, days, today()))

    @server.tool(annotations=READ_ONLY)
    def stock_news(query: str | None = None, days: int = 7, limit: int = 20) -> dict:
        """Recent news (summary, sentiment, important flag) and Korean DART filings collected by RichRich.
        Pass `query` (ticker or name) for one stock, or omit it for everything. `days` max 30, `limit` max 50."""
        return _answer(lambda: stocks.stock_news(richrich, query, days, limit, today()))

    @server.tool(annotations=READ_ONLY)
    def apt_my_home() -> dict:
        """The owner's own apartment (내 집): price per 평, recent median price, 1/3/6/12-month change, distance from the
        2021-22 peak (전고점), rank among its district's 대장 아파트, 24-month trend, recent trades, district summary."""
        return _answer(lambda: apts.my_home(apt, settings.apt_home_key, settings.apt_home_band))

    @server.tool(annotations=READ_ONLY)
    def apt_search(name: str, district: str | None = None, limit: int = 10) -> dict:
        """Find 수도권 apartment complexes by name (spaces ignored; every word must match), optionally within a
        district such as '분당구' or '서울 강남구'. Returns complex ids for apt_complex. `limit` max 20."""
        return _answer(lambda: apts.search(apt, name, district, limit))

    @server.tool(annotations=READ_ONLY)
    def apt_complex(complex_id: int, band: Band | None = None, months: int = 24) -> dict:
        """Details of one complex (id from apt_search or apt_leaders) for a size band (전용 59/74/84/large; default:
        the band with most trades): price metrics, 전고점 대비, district rank, monthly trend (`months` max 60), recent trades."""
        return _answer(lambda: apts.complex_detail(apt, complex_id, band, months))

    @server.tool(annotations=READ_ONLY)
    def apt_leaders(district: str, mode: Mode = "auto", limit: int = 10) -> dict:
        """대장 아파트 ranking of one 수도권 district (e.g. '분당구', '수지구', '서울 강남구') by price per 평.
        mode 'auto' ranks each complex by its main size band; or fix a band. `limit` max 30."""
        return _answer(lambda: apts.leaders(apt, district, mode, limit))

    @server.tool(annotations=READ_ONLY)
    def apt_records(days: int = 30, district: str | None = None, limit: int = 30) -> dict:
        """Recent record-high trades (신고가: above every earlier trade of the same complex and size, floors 4+)
        by contract date, newest first, optionally for one district. `days` max 92, `limit` max 50."""
        return _answer(lambda: apts.records(apt, days, district, limit, today()))

    return server


def main() -> None:
    settings = load_settings()
    richrich = Db(settings.richrich_database_url, "RichRich", "RICHRICH_DATABASE_URL")
    apt = Db(settings.apt_database_url, "apt-leader", "APT_DATABASE_URL")
    build_server(richrich, apt, settings).run("stdio")
