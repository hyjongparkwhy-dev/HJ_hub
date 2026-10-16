from datetime import datetime, timezone

from hub_collect.fetch import FetchError
from hub_collect.run import collect, format_summary
from hub_collect.sources import Source
from tests.fakes import FakeEmbedder, FakeStore

NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)
A = Source("a", "https://a.test/rss", "invest", "ko")
B = Source("b", "https://b.test/rss", "tech", "en")


def rss(*titles):
    items = "".join(f"<item><title>{t}</title><link>https://x.test/{i}-{t}</link></item>" for i, t in enumerate(titles))
    return f"<rss version='2.0'><channel>{items}</channel></rss>".encode()


def fetcher(pages):
    def fetch(url):
        page = pages[url]
        if isinstance(page, Exception):
            raise page
        return page

    return fetch


def test_one_failing_source_does_not_stop_others():
    store, emb = FakeStore(), FakeEmbedder()
    stats = collect((A, B), fetcher({A.url: FetchError("TimeoutError"), B.url: rss("Secret headline")}), store, emb, NOW)
    assert stats["failed"] == ["a"]
    assert stats["sources"] == {"b": 1}
    assert stats["inserted"] == 1
    assert store.purged_days == [180]
    assert store.runs == [stats]


def test_known_items_are_not_embedded_again():
    store, emb = FakeStore(known_keys={"old"}), FakeEmbedder()
    stats = collect((A,), fetcher({A.url: rss("Old", "New one")}), store, emb, NOW)
    assert stats["new"] == 1
    assert emb.calls == [["New one"]]


def test_nothing_new_skips_embedding():
    store, emb = FakeStore(known_keys={"old"}), FakeEmbedder()
    stats = collect((A,), fetcher({A.url: rss("Old")}), store, emb, NOW)
    assert (stats["new"], stats["inserted"], emb.calls) == (0, 0, [])


def test_database_over_limit_only_purges():
    store, emb = FakeStore(mb=400.0), FakeEmbedder()
    stats = collect((A,), fetcher({A.url: rss("Anything")}), store, emb, NOW)
    assert stats["skipped"] == "db_limit"
    assert store.inserted == [] and emb.calls == []
    assert store.purged_days == [180]


def test_summary_output_has_counts_only():
    store = FakeStore()
    stats = collect((A, B), fetcher({A.url: FetchError("HTTPError"), B.url: rss("Secret headline")}), store, FakeEmbedder(), NOW)
    text = format_summary(stats)
    assert "Secret" not in text and "x.test" not in text
    assert '"inserted": 1' in text and '"failed": ["a"]' in text
