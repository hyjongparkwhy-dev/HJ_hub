"""Real feeds, real model, real database; skipped without HUB_DATABASE_URL. Database writes are rolled back."""
from datetime import datetime, timezone

import pytest

from hub_collect.embed import DIM, Embedder
from hub_collect.fetch import fetch
from hub_collect.normalize import Item, parse_feed
from hub_collect.sources import SOURCES
from hub_collect.store import Store


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s.id)
def test_live_every_source_returns_items(conn, source):
    assert parse_feed(source, fetch(source.url), datetime.now(timezone.utc))


def test_live_embedding_dimension(conn):
    vectors = Embedder().vectors(["기준금리 동결", "Fed holds rates"])
    assert [len(v) for v in vectors] == [DIM, DIM]


def test_live_store_round_trip_is_rolled_back(conn):
    item = Item("test", "tech", "https://hub-test.invalid/1", "Round trip", "roundtrip", "", None)
    with conn.transaction(force_rollback=True):
        store = Store(conn)
        assert store.insert([item], [[0.1] * DIM]) == 1
        assert store.insert([item], [[0.1] * DIM]) == 0  # same url is ignored
        assert store.known([item.url], ["roundtrip"]) == ({item.url}, {"roundtrip"})
        assert store.database_mb() > 0
    assert Store(conn).known([item.url], []) == (set(), set())
