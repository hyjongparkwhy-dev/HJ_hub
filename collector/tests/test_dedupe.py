from hub_collect.dedupe import unique_items
from hub_collect.normalize import Item


def item(url, key, source="a"):
    return Item(source, "invest", url, key, key, "", None)


def test_unique_items_drop_same_url_and_same_title_keeping_first():
    items = [item("https://a/1", "fed"), item("https://a/1", "other"), item("https://b/2", "fed", "b"), item("https://c/3", "cpi")]
    assert [i.url for i in unique_items(items)] == ["https://a/1", "https://c/3"]


def test_unique_items_never_match_on_empty_title_key():
    assert len(unique_items([item("https://a/1", ""), item("https://a/2", "")])) == 2
