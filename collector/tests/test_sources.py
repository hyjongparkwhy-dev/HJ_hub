from hub_collect.sources import CATEGORIES, SOURCES


def test_sources_are_unique_https_and_categorised():
    assert len({s.id for s in SOURCES}) == len({s.url for s in SOURCES}) == len(SOURCES) == 27
    assert all(s.url.startswith("https://") for s in SOURCES)
    assert all(s.category in CATEGORIES and s.lang in ("ko", "en") for s in SOURCES)


def test_every_category_has_several_outlets_and_no_community_feeds():
    for category in CATEGORIES:
        assert sum(s.category == category for s in SOURCES) >= 6
    assert not {"geeknews", "hackernews"} & {s.id for s in SOURCES}
