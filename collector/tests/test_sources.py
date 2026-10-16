from hub_collect.sources import CATEGORIES, SOURCES


def test_sources_are_unique_https_and_categorised():
    assert len({s.id for s in SOURCES}) == len(SOURCES) == 7
    assert all(s.url.startswith("https://") for s in SOURCES)
    assert all(s.category in CATEGORIES and s.lang in ("ko", "en") for s in SOURCES)
