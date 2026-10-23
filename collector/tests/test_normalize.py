from datetime import datetime, timezone

from hub_collect.normalize import canonical_url, category_for, clean_text, parse_feed, title_key
from hub_collect.sources import Source

NOW = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)
SOURCE = Source("test", "https://example.com/rss", "invest", "ko")
RSS = """<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>t</title>
<item><title>기준금리 &amp; 동결</title><link>https://Example.com/a?utm_source=rss&amp;id=3#top</link>
<description>&lt;p&gt;한국은행이   금리를&lt;/p&gt; 동결</description><pubDate>Thu, 15 Oct 2026 21:00:00 +0900</pubDate></item>
<item><title></title><link>https://example.com/no-title</link></item>
<item><title>No link</title></item>
<item><title>Future</title><link>https://example.com/f</link><pubDate>Sat, 31 Dec 2050 00:00:00 GMT</pubDate></item>
<item><title>Undated</title><link>https://example.com/u</link></item>
</channel></rss>""".encode("utf-8")


def test_canonical_url_drops_tracking_and_fragment():
    assert canonical_url("https://Example.com/A?utm_source=x&id=3&fbclid=z#top") == "https://example.com/A?id=3"


def test_clean_text_strips_tags_and_caps_length():
    assert clean_text("<b>a</b>&nbsp; b\n c") == "a b c"
    assert clean_text("x" * 600) == "x" * 499 + "…"


def test_title_key_ignores_case_and_punctuation():
    assert title_key("Fed Holds Rates!") == title_key("fed holds rates")
    assert title_key("기준금리, 동결") == "기준금리동결"


def test_parse_feed_cleans_fields_and_skips_broken_entries():
    items = parse_feed(SOURCE, RSS, NOW)
    assert [i.title for i in items] == ["기준금리 & 동결", "Future", "Undated"]
    first = items[0]
    assert first.url == "https://example.com/a?id=3"
    assert first.summary == "한국은행이 금리를 동결"
    assert first.published_at == datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
    assert (first.source_id, first.category) == ("test", "invest")


def test_parse_feed_clamps_future_dates_and_keeps_missing_ones_null():
    items = {i.title: i for i in parse_feed(SOURCE, RSS, NOW)}
    assert items["Future"].published_at == NOW
    assert items["Undated"].published_at is None


def test_nul_and_control_characters_are_removed():
    assert clean_text("a\x00b\x07c\td") == "abc d"
    assert canonical_url("https://example.com/a\x00b") == "https://example.com/ab"


def test_youtube_shorts_are_dropped_and_videos_kept():
    from datetime import datetime, timezone

    from hub_collect.normalize import parse_feed
    from hub_collect.sources import Source

    xml = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
    <entry><title>A short</title><link rel="alternate" href="https://www.youtube.com/shorts/abc"/><updated>2026-10-18T00:00:00+00:00</updated></entry>
    <entry><title>A full video</title><link rel="alternate" href="https://www.youtube.com/watch?v=xyz"/><updated>2026-10-18T00:00:00+00:00</updated></entry></feed>"""
    items = parse_feed(Source("yt_x", "https://www.youtube.com/feeds/videos.xml?channel_id=x", "tech", "en"), xml, datetime(2026, 10, 18, tzinfo=timezone.utc))
    assert [i.title for i in items] == ["A full video"]


def test_housing_headlines_from_invest_feeds_count_as_real_estate():
    assert category_for(SOURCE, "서울 아파트 매매가격 상승세 3주만에 둔화…0.13%↑") == "realestate"
    assert category_for(SOURCE, "1∼9월 서울 전세 거래 28% 급감") == "realestate"
    assert category_for(SOURCE, "US Housing Starts Fall to One of the Worst Paces Since Pandemic") == "realestate"
    assert category_for(SOURCE, "[특징주] 삼성전자, 장초반 4%대 반등") == "invest"


def test_lookalike_words_keep_the_feed_category():
    # 공모주 청약 is an IPO subscription and 전세기 a charter flight, not housing.
    assert category_for(SOURCE, "인도 지오 플랫폼스, IPO 공모주 청약 30배 몰려") == "invest"
    assert category_for(SOURCE, "후티 공격에 사우디 전세기 요금 급등") == "invest"
    assert category_for(SOURCE, "전세계 증시 동반 하락") == "invest"


def test_only_invest_feeds_are_reclassified():
    tech = Source("t", "https://example.com/rss", "tech", "ko")
    assert category_for(tech, "홍콩 부동산 재벌의 황당한 저출생 해법") == "tech"


def test_parse_feed_applies_the_title_category():
    rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>강남 아파트 실거래가지수 하락 전환</title><link>https://example.com/h</link></item>
</channel></rss>""".encode("utf-8")
    assert [i.category for i in parse_feed(SOURCE, rss, NOW)] == ["realestate"]
