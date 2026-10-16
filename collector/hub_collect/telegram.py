"""The briefing message, its 👍/👎 buttons, and reading the presses back with getUpdates (no webhook).

The bot token is part of every request URL, so errors keep only the HTTP status or exception type."""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from hub_collect.rank import Candidate
from hub_collect.summarize import Digest

API = "https://api.telegram.org/bot{token}/{method}"
MESSAGE_LIMIT = 4096
TIMEOUT_SECONDS = 30
LABELS = {"invest": "투자", "realestate": "부동산", "tech": "기술"}
VOTE_DATA = re.compile(r"^v:(\d+):(-?1)$")

Post = Callable[[str, dict, bytes], bytes]


class TelegramError(Exception):
    def __init__(self, message: str, rejected: bool = False):
        super().__init__(message)
        # True only when Telegram answered and refused; a timeout or dropped connection may still have delivered.
        self.rejected = rejected


@dataclass(frozen=True)
class Vote:
    item_id: int
    vote: int


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def visible_length(text: str) -> int:
    """Telegram counts the limit on the text left after parsing the HTML, so tags and links are free."""
    return len(html.unescape(re.sub(r"<[^>]+>", "", text)))


def _render(day: date, entries: Sequence[tuple[Candidate, Digest]], summary_limit: int) -> str:
    lines = [f"<b>📰 {day.month}월 {day.day}일 아침 브리핑</b>"]
    for n, (c, d) in enumerate(entries, 1):
        lines.append("")
        lines.append(f'<b>{n}.</b> [{LABELS.get(c.category, c.category)}] <a href="{escape(c.url)}">{escape(d.title)}</a>')
        summary = d.summary[:summary_limit]
        if summary:
            lines.append(escape(summary))
    return "\n".join(lines)


def format_brief(
    day: date, entries: Sequence[tuple[Candidate, Digest]], limit: int = MESSAGE_LIMIT
) -> tuple[str, list[list[dict]]]:
    """Summaries shrink, then go, then trailing articles go, before the message would pass the length limit."""
    entries = list(entries)
    for summary_limit in (160, 80, 0):
        text = _render(day, entries, summary_limit)
        if visible_length(text) <= limit:
            break
    while visible_length(text) > limit and len(entries) > 1:
        entries.pop()
        text = _render(day, entries, 0)
    buttons = []
    for n, (c, _) in enumerate(entries, 1):
        buttons += [{"text": f"{n} 👍", "callback_data": f"v:{c.id}:1"}, {"text": f"{n} 👎", "callback_data": f"v:{c.id}:-1"}]
    # Two articles per row keeps ten articles to five rows of buttons.
    return text, [buttons[i : i + 4] for i in range(0, len(buttons), 4)]


def _urllib_post(url: str, headers: dict, body: bytes) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


class Telegram:
    def __init__(self, token: str, chat_id: str, post: Post = _urllib_post):
        self._token = token
        self._chat_id = str(chat_id)
        self._post = post

    def send(self, text: str, keyboard: list[list[dict]]) -> int:
        result = self._call(
            "sendMessage",
            {
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return int(result["message_id"])

    def votes(self, offset: int) -> tuple[list[Vote], int]:
        """Presses since `offset`, last press per article wins. Passing the returned offset next time tells
        Telegram these updates are handled; unhandled ones are kept for only 24 hours."""
        updates = self._call("getUpdates", {"offset": offset, "timeout": 0, "allowed_updates": ["callback_query"]})
        latest: dict[int, int] = {}
        next_offset = offset
        for u in updates:
            next_offset = max(next_offset, int(u["update_id"]) + 1)
            query = u.get("callback_query") or {}
            chat = ((query.get("message") or {}).get("chat") or {}).get("id")
            sender = (query.get("from") or {}).get("id")
            match = VOTE_DATA.match(str(query.get("data") or ""))
            # In a private chat the chat id is the owner's user id; checking both keeps group members out.
            if match and str(chat) == self._chat_id and str(sender) == self._chat_id:
                item_id = int(match.group(1))
                latest.pop(item_id, None)  # re-insert so the order follows the last press
                latest[item_id] = int(match.group(2))
        return [Vote(i, v) for i, v in latest.items()], next_offset

    def _call(self, method: str, payload: dict):
        url = API.format(token=self._token, method=method)
        try:
            reply = json.loads(self._post(url, {"Content-Type": "application/json"}, json.dumps(payload).encode()))
        except urllib.error.HTTPError as e:
            # 4xx means Telegram refused the request; 5xx may come after it already acted.
            raise TelegramError(f"{method} failed with HTTP {e.code}", rejected=e.code < 500) from None
        except Exception as e:
            raise TelegramError(f"{method} failed ({type(e).__name__})") from None
        if not reply.get("ok"):
            raise TelegramError(f"{method} was rejected", rejected=True)
        return reply["result"]
