"""News feeds the collector reads: established news outlets only (no community aggregators).
Each feed was fetched by hand on 2026-10-17."""
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
    # invest
    Source("hankyung_economy", "https://www.hankyung.com/feed/economy", "invest", "ko"),
    Source("hankyung_finance", "https://www.hankyung.com/feed/finance", "invest", "ko"),
    Source("yna_economy", "https://www.yna.co.kr/rss/economy.xml", "invest", "ko"),
    Source("yna_market", "https://www.yna.co.kr/rss/market.xml", "invest", "ko"),
    Source("chosunbiz_stock", "https://biz.chosun.com/arc/outboundfeeds/rss/category/stock/?outputType=xml", "invest", "ko"),
    Source("bloomberg_markets", "https://feeds.bloomberg.com/markets/news.rss", "invest", "en"),
    Source("bloomberg_economics", "https://feeds.bloomberg.com/economics/news.rss", "invest", "en"),
    Source("cnbc_top", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "invest", "en"),
    Source("wsj_markets", "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain", "invest", "en"),
    Source("ft_markets", "https://www.ft.com/markets?format=rss", "invest", "en"),
    # realestate
    Source("hankyung_realestate", "https://www.hankyung.com/feed/realestate", "realestate", "ko"),
    Source("heraldcorp_realestate", "https://biz.heraldcorp.com/rss/google/realestate", "realestate", "ko"),
    Source("sedaily_realestate", "https://www.sedaily.com/rss/realestate", "realestate", "ko"),
    Source("mk_realestate", "https://www.mk.co.kr/rss/50300009/", "realestate", "ko"),
    Source("asiae_realestate", "https://www.asiae.co.kr/rss/realestate.htm", "realestate", "ko"),
    Source(
        "chosunbiz_realestate",
        "https://biz.chosun.com/arc/outboundfeeds/rss/category/real_estate/?outputType=xml",
        "realestate",
        "ko",
    ),
    # tech
    Source("etnews", "https://rss.etnews.com/Section901.xml", "tech", "ko"),
    Source("zdnet_kr", "https://feeds.feedburner.com/zdkorea", "tech", "ko"),
    Source("hankyung_it", "https://www.hankyung.com/feed/it", "tech", "ko"),
    Source("theverge", "https://www.theverge.com/rss/index.xml", "tech", "en"),
    Source("techcrunch", "https://techcrunch.com/feed/", "tech", "en"),
    Source("arstechnica", "https://feeds.arstechnica.com/arstechnica/index", "tech", "en"),
    Source("wired", "https://www.wired.com/feed/rss", "tech", "en"),
    Source("mit_techreview", "https://www.technologyreview.com/feed/", "tech", "en"),
    Source("bloomberg_tech", "https://feeds.bloomberg.com/technology/news.rss", "tech", "en"),
    Source("cnbc_tech", "https://www.cnbc.com/id/19854910/device/rss/rss.html", "tech", "en"),
    Source("engadget", "https://www.engadget.com/rss.xml", "tech", "en"),
)
