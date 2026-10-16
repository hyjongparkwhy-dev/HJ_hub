"""One-off: re-embed every stored item with the current model (sql/004_embeddinggemma.sql). Local use only."""
from __future__ import annotations

import sys
from pathlib import Path

from hub_collect.embed import Embedder
from hub_collect.settings import load_database_url
from hub_collect.store import connect, vector_literal

SQL = Path(__file__).resolve().parents[1] / "sql" / "004_embeddinggemma.sql"
BATCH = 64


def main() -> int:
    step1, step2 = SQL.read_text(encoding="utf-8").split("-- step 2", 1)
    embedder = Embedder()
    with connect(load_database_url()) as conn:
        conn.execute(step1)
        rows = conn.execute("select id, title, coalesce(summary, '') from hub.item where embedding_next is null").fetchall()
        for start in range(0, len(rows), BATCH):
            batch = rows[start : start + BATCH]
            vectors = embedder.vectors([f"{t}. {s}" if s else t for _, t, s in batch])
            with conn.transaction(), conn.cursor() as cur:
                for (item_id, _, _), vector in zip(batch, vectors, strict=True):
                    cur.execute(
                        "update hub.item set embedding_next = %s::extensions.halfvec where id = %s",
                        (vector_literal(vector), item_id),
                    )
            print(f"{min(start + BATCH, len(rows))}/{len(rows)}")
        left = conn.execute("select count(*) from hub.item where embedding_next is null").fetchone()[0]
        if left:
            print(f"{left} rows still missing; not swapping columns", file=sys.stderr)
            return 1
        with conn.transaction():
            conn.execute(step2.split("\n", 1)[1])
    print("swapped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
