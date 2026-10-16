"""One Gemini call per briefing: Korean titles and short summaries for the picked items.

Plain REST over urllib keeps the collector free of an SDK. The key travels in a header, never in the URL."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hub_collect.normalize import clean_text
from hub_collect.rank import Candidate

DEFAULT_MODEL = "gemini-3.5-flash"  # RichRich keeps its own use of this model paused, so the quota is free
# Flash answers 503 "high demand" at busy hours; the last attempt goes to the lighter model instead.
FALLBACK_MODEL = "gemini-3.5-flash-lite"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ATTEMPTS = 3
TIMEOUT_SECONDS = 60
TITLE_LIMIT = 80
SUMMARY_LIMIT = 160

PROMPT = (
    "아래는 아침 뉴스 브리핑에 넣을 기사 목록이다. 각 항목마다 한국어로 써라.\n"
    "- title: 기사 제목. 영어면 자연스러운 한국어로 옮기고, 한국어면 그대로 두되 50자 안팎으로 다듬는다.\n"
    "- summary: 핵심을 1~2문장(120자 안팎)으로. 설명(description)이 비어 있으면 제목만 보고 1문장.\n"
    "기사에 없는 수치나 사실을 만들지 마라. 매수·매도를 권하는 표현은 쓰지 마라. 입력의 id를 그대로 돌려줘라.\n\n"
)

SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {"id": {"type": "INTEGER"}, "title": {"type": "STRING"}, "summary": {"type": "STRING"}},
        "required": ["id", "title", "summary"],
    },
}

Post = Callable[[str, dict, bytes], bytes]


class SummaryError(Exception):
    pass


@dataclass(frozen=True)
class Digest:
    title: str
    summary: str


def fallback(c: Candidate) -> Digest:
    return Digest(c.title, clean_text(c.summary, SUMMARY_LIMIT))


def _urllib_post(url: str, headers: dict, body: bytes) -> bytes:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


class GeminiSummarizer:
    def __init__(self, api_key: str, model: str | None = None, post: Post = _urllib_post, retry_wait: float = 10.0):
        self._key = api_key
        primary = ENDPOINT.format(model=model or DEFAULT_MODEL)
        self._urls = [primary] * (ATTEMPTS - 1) + [ENDPOINT.format(model=FALLBACK_MODEL)]
        self._post = post
        self._retry_wait = retry_wait

    def digests(self, items: Sequence[Candidate]) -> dict[int, Digest]:
        if not items:
            return {}
        # Only the public headline and feed description go out; links and ids stay local.
        payload = [{"id": n, "title": c.title, "description": c.summary[:600]} for n, c in enumerate(items)]
        rows = self._call(PROMPT + json.dumps(payload, ensure_ascii=False))
        return {items[n].id: digest for n, digest in _valid(rows, len(items)).items()}

    def _call(self, prompt: str) -> list:
        body = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA},
            }
        ).encode()
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._key}
        problem, answered, tries = "unknown", 0, 0
        for attempt, url in enumerate(self._urls):
            # A malformed answer was still generated and counted against the shared quota: retry it only once.
            if answered >= 2:
                break
            if attempt:
                time.sleep(self._retry_wait * attempt)
            tries += 1
            try:
                raw = self._post(url, headers, body)
            except urllib.error.HTTPError as e:
                problem = f"HTTP {e.code}"  # 429 quota and 503 overload are the usual ones
                continue
            except Exception as e:
                # Exception text can echo request details; keep only the type.
                problem = type(e).__name__
                continue
            answered += 1
            try:
                parts = json.loads(raw)["candidates"][0]["content"]["parts"]
                rows = json.loads("".join(p.get("text", "") for p in parts if not p.get("thought")))
            except Exception as e:
                problem = type(e).__name__
                continue
            if isinstance(rows, list):
                return rows
            problem = "not a list"
        raise SummaryError(f"Gemini failed after {tries} attempts ({problem})")


def _valid(rows: list, size: int) -> dict[int, Digest]:
    valid: dict[int, Digest] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), int):
            continue
        n = row["id"]
        title = clean_text(str(row.get("title") or ""), TITLE_LIMIT)
        summary = clean_text(str(row.get("summary") or ""), SUMMARY_LIMIT)
        if 0 <= n < size and n not in valid and title and summary:
            valid[n] = Digest(title, summary)
    return valid
