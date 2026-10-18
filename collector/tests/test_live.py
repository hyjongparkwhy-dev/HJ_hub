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
        liked, disliked = store.feedback_signals(90, 200)
        assert any(len(s.vector) == DIM for s in disliked)
        assert all(s.label.startswith("👍 비슷: ") for s in liked)
        assert conn.execute("select count(*) from hub.daily_feedback where brief_date = %s", (day,)).fetchone()[0] == 1
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


def test_live_voted_items_are_not_candidates(conn):
    from hub_collect.brief_store import BriefStore
    from hub_collect.telegram import Vote

    item = Item("test", "tech", "https://hub-test.invalid/voted", "Voted", "votedtrip", "", None)
    with conn.transaction(force_rollback=True):
        Store(conn).insert([item], [[0.1] * DIM])
        store = BriefStore(conn)
        cand = next(c for c in store.candidates(1) if c.url == item.url)
        store.save_votes([Vote(cand.id, 1)])
        assert all(c.id != cand.id for c in store.candidates(1))


def test_live_purge_keeps_voted_items(conn):
    from hub_collect.brief_store import BriefStore
    from hub_collect.telegram import Vote

    old = [Item("test", "tech", f"https://hub-test.invalid/old-{n}", f"Old {n}", f"oldtrip{n}", "", None) for n in (1, 2)]
    with conn.transaction(force_rollback=True):
        Store(conn).insert(old, [[0.1] * DIM] * 2)
        conn.execute("update hub.item set fetched_at = now() - interval '100 days' where url like 'https://hub-test.invalid/old-%'")
        voted_id = conn.execute("select id from hub.item where url = %s", (old[0].url,)).fetchone()[0]
        BriefStore(conn).save_votes([Vote(voted_id, 1)])
        Store(conn).purge(90)
        left = {r[0] for r in conn.execute("select url from hub.item where url like 'https://hub-test.invalid/old-%'")}
        assert left == {old[0].url}


def test_live_telegram_votes_do_not_overwrite_web_votes(conn):
    from hub_collect.brief_store import BriefStore
    from hub_collect.telegram import Vote

    items = [Item("test", "tech", f"https://hub-test.invalid/src-{n}", f"Src {n}", f"srctrip{n}", "", None) for n in (1, 2)]
    with conn.transaction(force_rollback=True):
        Store(conn).insert(items, [[0.1] * DIM] * 2)
        web_id, tg_id = (conn.execute("select id from hub.item where url = %s", (i.url,)).fetchone()[0] for i in items)
        conn.execute("insert into hub.feedback (item_id, vote, source) values (%s, -1, 'web')", (web_id,))
        store = BriefStore(conn)
        store.save_votes([Vote(tg_id, 1)])
        store.save_votes([Vote(web_id, 1), Vote(tg_id, -1)])
        votes = dict(conn.execute("select item_id, vote from hub.feedback where item_id = any(%s)", ([web_id, tg_id],)).fetchall())
        assert votes == {web_id: -1, tg_id: -1}


def test_live_brief_items_record_explorations(conn):
    from datetime import date

    from hub_collect.brief_store import BriefStore
    from hub_collect.rank import Scored

    item = Item("test", "tech", "https://hub-test.invalid/explore", "Explore", "exploretrip", "", None)
    with conn.transaction(force_rollback=True):
        Store(conn).insert([item], [[0.1] * DIM])
        item_id = conn.execute("select id from hub.item where url = %s", (item.url,)).fetchone()[0]
        from hub_collect.rank import Candidate
        from hub_collect.summarize import Digest

        cand = Candidate(item_id, "test", "tech", item.url, "Explore", "", datetime(2026, 10, 18, tzinfo=timezone.utc), (1.0,))
        BriefStore(conn).save_brief(date(1999, 1, 3), [Scored(cand, 0.1, 0.1, (1.0,), "", True)], [Digest("t", "s")], {})
        assert conn.execute("select explore from hub.brief_item where item_id = %s", (item_id,)).fetchone()[0] is True
