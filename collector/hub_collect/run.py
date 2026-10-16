"""Daily collection. Output is counts and source ids only: this repository and its Actions logs are public."""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from hub_collect.dedupe import unique_items
from hub_collect.embed import Embedder, embedding_text
from hub_collect.fetch import FetchError, fetch
from hub_collect.normalize import parse_feed
from hub_collect.settings import load_database_url
from hub_collect.sources import SOURCES, Source
from hub_collect.store import Store, connect

DB_LIMIT_MB = 400
RETENTION_DAYS = 180


def collect(sources: Sequence[Source], fetch: Callable[[str], bytes], store, embedder, now: datetime) -> dict:
    stats: dict = {"db_mb": round(store.database_mb(), 1), "sources": {}, "failed": [], "new": 0, "inserted": 0}
    if stats["db_mb"] >= DB_LIMIT_MB:
        stats["skipped"] = "db_limit"
    else:
        items = []
        for source in sources:
            try:
                parsed = parse_feed(source, fetch(source.url), now)
            except FetchError:
                stats["failed"].append(source.id)
                continue
            stats["sources"][source.id] = len(parsed)
            items.extend(parsed)
        fresh = unique_items(items)
        known_urls, known_keys = store.known([i.url for i in fresh], [i.title_key for i in fresh if i.title_key])
        new = [i for i in fresh if i.url not in known_urls and i.title_key not in known_keys]
        stats["new"] = len(new)
        if new:
            stats["inserted"] = store.insert(new, embedder.vectors([embedding_text(i) for i in new]))
    stats["purged"] = store.purge(RETENTION_DAYS)
    store.record_run(stats)
    return stats


def format_summary(stats: dict) -> str:
    return json.dumps(stats, ensure_ascii=False, sort_keys=True)


def main() -> int:
    url = load_database_url()
    if not url:
        print("HUB_DATABASE_URL is not set", file=sys.stderr)
        return 2
    with connect(url) as conn:
        stats = collect(
            SOURCES, fetch, Store(conn), Embedder(os.environ.get("FASTEMBED_CACHE")), datetime.now(timezone.utc)
        )
    print(format_summary(stats))
    return 1 if len(stats["failed"]) == len(SOURCES) else 0
