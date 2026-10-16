"""News feeds the collector reads; each one was fetched by hand on 2026-10-16."""
from __future__ import annotations

from dataclasses import dataclass

CATEGORIES = ("invest", "realestate", "tech")


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    category: str
    lang: str


SOURCES = (
    Source("hankyung_economy", "https://www.hankyung.com/feed/economy", "invest", "ko"),
    Source("hankyung_realestate", "https://www.hankyung.com/feed/realestate", "realestate", "ko"),
    Source("yna_economy", "https://www.yna.co.kr/rss/economy.xml", "invest", "ko"),
    Source("geeknews", "https://news.hada.io/rss/news", "tech", "ko"),
    Source("hackernews", "https://hnrss.org/frontpage?points=200", "tech", "en"),
    Source("bloomberg_markets", "https://feeds.bloomberg.com/markets/news.rss", "invest", "en"),
    Source("cnbc_top", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "invest", "en"),
)
