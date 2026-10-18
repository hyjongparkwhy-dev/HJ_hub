import re

from hub_collect.sources import CATEGORIES, SOURCES, is_video


def test_sources_are_unique_https_and_categorised():
    assert len({s.id for s in SOURCES}) == len({s.url for s in SOURCES}) == len(SOURCES) == 46
    assert all(s.url.startswith("https://") for s in SOURCES)
    assert all(s.category in CATEGORIES and s.lang in ("ko", "en") for s in SOURCES)


def test_every_category_has_several_outlets_and_no_community_feeds():
    for category in CATEGORIES:
        assert sum(s.category == category for s in SOURCES) >= 6
    assert not {"geeknews", "hackernews"} & {s.id for s in SOURCES}


def test_youtube_channels_are_tech_feeds_with_ids():
    channels = [s for s in SOURCES if s.id.startswith("yt_")]
    assert len(channels) == 19 and all(s.category == "tech" for s in channels)
    assert all(re.fullmatch(r"https://www\.youtube\.com/feeds/videos\.xml\?channel_id=UC[\w-]{22}", s.url) for s in channels)


def test_is_video_recognises_youtube_links_only():
    assert is_video("https://www.youtube.com/watch?v=abc") and is_video("https://youtu.be/abc")
    assert not is_video("https://x.test/youtube.com/") and not is_video("https://www.hankyung.com/article/1")
