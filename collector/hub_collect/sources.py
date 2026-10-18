"""Feeds the collector reads: established news outlets (no community aggregators) and AI/tech YouTube channels.
Each feed was fetched by hand on 2026-10-17/18."""
from __future__ import annotations

from dataclasses import dataclass

CATEGORIES = ("invest", "realestate", "tech")


def is_video(url: str) -> bool:
    return url.startswith(("https://www.youtube.com/", "https://youtube.com/", "https://youtu.be/"))


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
    # YouTube (tech/AI): the channel feed lists the 15 newest uploads, shorts included; parse_feed drops the shorts.
    Source("yt_claude", "https://www.youtube.com/feeds/videos.xml?channel_id=UCV03SRZXJEz-hchIAogeJOg", "tech", "en"),
    Source("yt_anthropic", "https://www.youtube.com/feeds/videos.xml?channel_id=UCrDwWp7EBBv4NwvScIpBDOA", "tech", "en"),
    Source("yt_routeai", "https://www.youtube.com/feeds/videos.xml?channel_id=UCDq9_N34UnlMSlFB4kWE15w", "tech", "ko"),
    Source("yt_aiexplained", "https://www.youtube.com/feeds/videos.xml?channel_id=UCNJ1Ymd5yFuUPtn21xtRbbw", "tech", "en"),
    Source("yt_aiengineer", "https://www.youtube.com/feeds/videos.xml?channel_id=UCLKPca3kwwd-B59HNr-_lvA", "tech", "en"),
    Source("yt_mattwolfe", "https://www.youtube.com/feeds/videos.xml?channel_id=UChpleBmo18P08aKCIgti38g", "tech", "en"),
    Source("yt_a16z", "https://www.youtube.com/feeds/videos.xml?channel_id=UC9cn0TuPq4dnbTY-CBsm8XA", "tech", "en"),
    Source("yt_verge", "https://www.youtube.com/feeds/videos.xml?channel_id=UCddiUEpeqJcYeBxX1IVBKvQ", "tech", "en"),
    Source("yt_mkbhd", "https://www.youtube.com/feeds/videos.xml?channel_id=UCBJycsmduvYEL83R_U4JriQ", "tech", "en"),
    Source("yt_svgirl", "https://www.youtube.com/feeds/videos.xml?channel_id=UCiq1FIgtEK7LRAOB1JXTPig", "tech", "en"),
    Source("yt_aiadvantage", "https://www.youtube.com/feeds/videos.xml?channel_id=UCHhYXsLBEVVnbvsq57n1MTQ", "tech", "en"),
    Source("yt_twist", "https://www.youtube.com/feeds/videos.xml?channel_id=UCkkhmBWfS7pILYIk0izkc3A", "tech", "en"),
    Source("yt_allin", "https://www.youtube.com/feeds/videos.xml?channel_id=UCESLZhusAkFfsNsApnjF_Cg", "tech", "en"),
    Source("yt_nateherk", "https://www.youtube.com/feeds/videos.xml?channel_id=UC2ojq-nuP8ceeHqiroeKhBA", "tech", "en"),
    Source("yt_benai", "https://www.youtube.com/feeds/videos.xml?channel_id=UC3KK7ENB_ierAXvrxVNnbZQ", "tech", "en"),
    Source("yt_howiai", "https://www.youtube.com/feeds/videos.xml?channel_id=UCRYY7IEbkHLH_ScJCu9eWDQ", "tech", "en"),
    Source("yt_yc", "https://www.youtube.com/feeds/videos.xml?channel_id=UCcefcZRL2oaA_uBNeo5UOWg", "tech", "en"),
    Source("yt_greg", "https://www.youtube.com/feeds/videos.xml?channel_id=UCPjNBjflYl0-HQtUvOx0Ibw", "tech", "en"),
    Source("yt_lenny", "https://www.youtube.com/feeds/videos.xml?channel_id=UC6t1O76G0jYXOAoYCm153dA", "tech", "en"),
)
