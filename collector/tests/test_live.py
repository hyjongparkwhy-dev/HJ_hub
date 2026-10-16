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


def test_live_brief_store_round_trip_is_rolled_back(conn):
    from datetime import date

    from hub_collect.brief_store import BriefStore
    from hub_collect.rank import Scored
    from hub_collect.summarize import Digest
    from hub_collect.telegram import Vote

    item = Item("test", "tech", "https://hub-test.invalid/brief", "Brief trip", "brieftrip", "", None)
    day = date(1999, 1, 1)
    with conn.transaction(force_rollback=True):
        Store(conn).insert([item], [[0.1] * DIM])
        store = BriefStore(conn)
        cand = next(c for c in store.candidates(1) if c.url == item.url)
        assert len(cand.vector) == DIM and cand.at is not None
        assert not store.briefed(day)
        brief_id = store.save_brief(day, [Scored(cand, 0.5, 0.5, ())], [Digest("제목", "")], {"picked": 1})
        store.set_message(brief_id, 1)
        assert store.briefed(day)
        assert all(c.id != cand.id for c in store.candidates(1))  # briefed items are not offered again
        assert store.save_votes([Vote(cand.id, 1), Vote(cand.id, -1), Vote(-5, 1)]) == 2
        assert conn.execute("select vote from hub.feedback where item_id = %s", (cand.id,)).fetchone()[0] == -1
        store.save_offset(42)
        assert store.offset() == 42


def test_live_web_roles_cannot_read_briefing_tables(conn):
    for table in ("hub.brief", "hub.brief_item", "hub.feedback", "hub.state"):
        for role in ("anon", "authenticated"):
            ok = conn.execute(f"select has_table_privilege('{role}', '{table}', 'select')").fetchone()[0]
            assert ok is False, (role, table)


def test_live_digest_cache_is_per_day_and_rolled_back(conn):
    from datetime import date

    from hub_collect.brief_store import BriefStore
    from hub_collect.summarize import Digest

    with conn.transaction(force_rollback=True):
        store = BriefStore(conn)
        store.save_digests(date(1999, 1, 1), {7: Digest("t", "s")})
        assert store.cached_digests(date(1999, 1, 1)) == {7: Digest("t", "s")}
        assert store.cached_digests(date(1999, 1, 2)) == {}
