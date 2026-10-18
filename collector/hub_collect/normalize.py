"""Turn raw feed bytes into clean, comparable items."""
from __future__ import annotations

import calendar
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

from hub_collect.sources import Source

SUMMARY_LIMIT = 500
TITLE_LIMIT = 300
TRACKING_KEYS = {"fbclid", "gclid", "cmpid"}


@dataclass(frozen=True)
class Item:
    source_id: str
    category: str
    url: str
    title: str
    title_key: str
    summary: str
    published_at: datetime | None


def _strip_controls(text: str) -> str:
    # Postgres text rejects NUL; other control characters only add noise. Tabs and newlines become spaces later.
    return "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)


def canonical_url(url: str) -> str:
    parts = urlsplit(_strip_controls(url).strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_KEYS
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), ""))


def clean_text(raw: str, limit: int = SUMMARY_LIMIT) -> str:
    text = " ".join(_strip_controls(html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def title_key(title: str) -> str:
    """Letters and digits only, lowercased, so one headline from two feeds compares equal."""
    return "".join(ch for ch in title.lower() if ch.isalnum())


def parse_feed(source: Source, body: bytes, now: datetime) -> list[Item]:
    items = []
    for entry in feedparser.parse(body).entries:
        title = clean_text(entry.get("title", ""), TITLE_LIMIT)
        link = entry.get("link", "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        if "youtube.com/shorts/" in link:  # a few seconds of video and a title: too little to rank or summarize
            continue
        items.append(
            Item(
                source.id,
                source.category,
                canonical_url(link),
                title,
                title_key(title),
                clean_text(entry.get("summary", "")),
                _published(entry, now),
            )
        )
    return items


def _published(entry, now: datetime) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    # Some feeds stamp items in the future; a future date would pin them to the top for days.
    return min(datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc), now)
