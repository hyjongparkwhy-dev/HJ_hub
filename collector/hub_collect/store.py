"""Writes to the `hub` schema in the RichRich database."""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence

import psycopg

from hub_collect.normalize import Item

SIZE_SQL = "select pg_database_size(current_database()) / 1048576.0 as mb"
KNOWN_SQL = """
select url, title_key from hub.item
where url = any(%(urls)s)
   or (title_key = any(%(keys)s) and fetched_at > now() - interval '7 days')
"""
INSERT_SQL = """
insert into hub.item (url, source, category, title, title_key, summary, published_at, embedding)
values (%(url)s, %(source)s, %(category)s, %(title)s, %(title_key)s, %(summary)s, %(published_at)s,
        %(embedding)s::extensions.vector)
on conflict (url) do nothing
"""
PURGE_SQL = "delete from hub.item where fetched_at < now() - make_interval(days => %(days)s)"
RUN_SQL = "insert into hub.run (stats) values (%(stats)s::jsonb)"


def vector_literal(values: Iterable[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


def connect(url: str) -> psycopg.Connection:
    # prepare_threshold=None because Supabase's pooler cannot keep prepared statements.
    return psycopg.connect(url, autocommit=True, prepare_threshold=None, connect_timeout=10)


class Store:
    def __init__(self, conn: psycopg.Connection):
        self._conn = conn

    def database_mb(self) -> float:
        return float(self._conn.execute(SIZE_SQL).fetchone()[0])

    def known(self, urls: Sequence[str], keys: Sequence[str]) -> tuple[set[str], set[str]]:
        rows = self._conn.execute(KNOWN_SQL, {"urls": list(urls), "keys": list(keys)}).fetchall()
        wanted_urls, wanted_keys = set(urls), set(keys)
        return {r[0] for r in rows if r[0] in wanted_urls}, {r[1] for r in rows if r[1] in wanted_keys}

    def insert(self, items: Sequence[Item], vectors: Sequence[Sequence[float]]) -> int:
        inserted = 0
        with self._conn.transaction(), self._conn.cursor() as cur:
            for item, vector in zip(items, vectors, strict=True):
                cur.execute(
                    INSERT_SQL,
                    {
                        "url": item.url,
                        "source": item.source_id,
                        "category": item.category,
                        "title": item.title,
                        "title_key": item.title_key,
                        "summary": item.summary or None,
                        "published_at": item.published_at,
                        "embedding": vector_literal(vector),
                    },
                )
                inserted += cur.rowcount
        return inserted

    def purge(self, days: int) -> int:
        return self._conn.execute(PURGE_SQL, {"days": days}).rowcount

    def record_run(self, stats: dict) -> None:
        self._conn.execute(RUN_SQL, {"stats": json.dumps(stats)})
