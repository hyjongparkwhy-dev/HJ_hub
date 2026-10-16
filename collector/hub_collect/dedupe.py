"""Drop repeats inside one run: same canonical URL, or same headline from another feed."""
from __future__ import annotations

from hub_collect.normalize import Item


def unique_items(items: list[Item]) -> list[Item]:
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()
    kept = []
    for item in items:
        if item.url in seen_urls or (item.title_key and item.title_key in seen_keys):
            continue
        seen_urls.add(item.url)
        if item.title_key:
            seen_keys.add(item.title_key)
        kept.append(item)
    return kept
