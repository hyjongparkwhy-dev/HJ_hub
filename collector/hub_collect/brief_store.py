"""Briefing reads and writes in the `hub` schema."""
from __future__ import annotations

import json
from collections.abc import Sequence
from contextlib import AbstractContextManager
from datetime import date

import psycopg

from hub_collect.rank import Candidate, Scored
from hub_collect.summarize import Digest
from hub_collect.telegram import Vote

OFFSET_KEY = "telegram_offset"
DIGESTS_KEY = "brief_digests"

CANDIDATES_SQL = """
select i.id, i.source, i.category, i.url, i.title, coalesce(i.summary, ''),
       coalesce(i.published_at, i.fetched_at), i.embedding::text
from hub.item i
where i.fetched_at > now() - make_interval(hours => %(hours)s)
  and not exists (select 1 from hub.brief_item b where b.item_id = i.id)
"""
BRIEFED_SQL = "select 1 from hub.brief where brief_date = %(day)s"
BRIEF_SQL = "insert into hub.brief (brief_date, stats) values (%(day)s, %(stats)s::jsonb) returning id"
BRIEF_ITEM_SQL = """
insert into hub.brief_item (brief_id, rank, item_id, score, title, summary)
values (%(brief_id)s, %(rank)s, %(item_id)s, %(score)s, %(title)s, %(summary)s)
"""
MESSAGE_SQL = "update hub.brief set message_id = %(message_id)s where id = %(id)s"
# Presses on articles already purged by retention are dropped instead of failing the foreign key.
VOTE_SQL = """
insert into hub.feedback (item_id, vote)
select %(item_id)s, %(vote)s where exists (select 1 from hub.item where id = %(item_id)s)
on conflict (item_id) do update set vote = excluded.vote, voted_at = now()
"""
GET_STATE_SQL = "select value from hub.state where key = %(key)s"
SET_STATE_SQL = """
insert into hub.state (key, value) values (%(key)s, %(value)s::jsonb)
on conflict (key) do update set value = excluded.value
"""


class BriefStore:
    def __init__(self, conn: psycopg.Connection):
        self._conn = conn

    def transaction(self) -> AbstractContextManager:
        return self._conn.transaction()

    def candidates(self, hours: int) -> list[Candidate]:
        rows = self._conn.execute(CANDIDATES_SQL, {"hours": hours}).fetchall()
        return [Candidate(r[0], r[1], r[2], r[3], r[4], r[5], r[6], json.loads(r[7])) for r in rows]

    def briefed(self, day: date) -> bool:
        return self._conn.execute(BRIEFED_SQL, {"day": day}).fetchone() is not None

    def save_brief(self, day: date, picked: Sequence[Scored], digests: Sequence[Digest], stats: dict) -> int:
        brief_id = self._conn.execute(BRIEF_SQL, {"day": day, "stats": json.dumps(stats)}).fetchone()[0]
        with self._conn.cursor() as cur:
            for rank, (s, d) in enumerate(zip(picked, digests, strict=True), 1):
                cur.execute(
                    BRIEF_ITEM_SQL,
                    {
                        "brief_id": brief_id,
                        "rank": rank,
                        "item_id": s.candidate.id,
                        "score": s.score,
                        "title": d.title,
                        "summary": d.summary or None,
                    },
                )
        return brief_id

    def set_message(self, brief_id: int, message_id: int) -> None:
        self._conn.execute(MESSAGE_SQL, {"id": brief_id, "message_id": message_id})

    def save_votes(self, votes: Sequence[Vote]) -> int:
        saved = 0
        with self._conn.transaction(), self._conn.cursor() as cur:
            for v in votes:
                cur.execute(VOTE_SQL, {"item_id": v.item_id, "vote": v.vote})
                saved += cur.rowcount
        return saved

    def cached_digests(self, day: date) -> dict[int, Digest]:
        row = self._conn.execute(GET_STATE_SQL, {"key": DIGESTS_KEY}).fetchone()
        if not row or row[0].get("day") != day.isoformat():
            return {}
        return {int(i): Digest(t, s) for i, (t, s) in row[0]["items"].items()}

    def save_digests(self, day: date, digests: dict[int, Digest]) -> None:
        value = {"day": day.isoformat(), "items": {str(i): [d.title, d.summary] for i, d in digests.items()}}
        self._conn.execute(SET_STATE_SQL, {"key": DIGESTS_KEY, "value": json.dumps(value, ensure_ascii=False)})

    def offset(self) -> int:
        row = self._conn.execute(GET_STATE_SQL, {"key": OFFSET_KEY}).fetchone()
        return int(row[0]) if row else 0

    def save_offset(self, offset: int) -> None:
        self._conn.execute(SET_STATE_SQL, {"key": OFFSET_KEY, "value": json.dumps(offset)})
