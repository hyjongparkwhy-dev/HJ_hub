from datetime import datetime, timezone

from hub_collect.normalize import canonical_url, clean_text, parse_feed, title_key
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
