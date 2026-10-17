import json
from datetime import datetime, timezone

import pytest

from hub_collect.rank import Candidate
from hub_collect.summarize import Digest, GeminiSummarizer, SummaryError, fallback

AT = datetime(2026, 10, 17, tzinfo=timezone.utc)


def cand(id, title="Fed holds rates", summary="The Fed kept rates."):
    return Candidate(id, "a", "invest", f"https://x.test/{id}", title, summary, AT, (1.0,))


def gemini_reply(rows):
    return json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(rows)}]}}]}).encode()


class FakePost:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, url, headers, body):
        self.calls.append((url, headers, json.loads(body)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_one_call_maps_rows_back_to_items_and_keeps_the_key_out_of_the_url():
    post = FakePost(gemini_reply([{"id": 0, "title": "연준 금리 동결", "summary": "연준이 금리를 유지했다."}]))
    out = GeminiSummarizer("k-secret", post=post, retry_wait=0).digests([cand(41)])
    assert out == {41: Digest("Fed holds rates", "연준이 금리를 유지했다.")}  # the headline is never translated
    url, headers, body = post.calls[0]
    assert "k-secret" not in url and headers["x-goog-api-key"] == "k-secret"
    assert "gemini-3.5-flash" in url
    assert "https://x.test" not in json.dumps(body)  # only title and description leave the machine


def test_bad_rows_are_dropped():
    rows = [{"id": 0, "summary": ""}, {"id": 5, "summary": "b"}, {"id": 1, "summary": "c"}, "junk"]
    out = GeminiSummarizer("k", post=FakePost(gemini_reply(rows)), retry_wait=0).digests([cand(1), cand(2)])
    assert out == {2: Digest("Fed holds rates", "c")}


def test_malformed_answers_are_retried_only_once():
    post = FakePost(b"not json", gemini_reply({"not": "a list"}), gemini_reply([]))
    with pytest.raises(SummaryError, match="after 2 attempts"):
        GeminiSummarizer("k", post=post, retry_wait=0).digests([cand(1)])
    assert len(post.calls) == 2


def test_retries_then_raises_with_type_only():
    post = FakePost(OSError("boom k"), OSError("boom k"), gemini_reply({"not": "a list"}))
    with pytest.raises(SummaryError) as e:
        GeminiSummarizer("k", post=post, retry_wait=0).digests([cand(1)])
    assert len(post.calls) == 3
    assert [c[0].rsplit("/", 1)[1] for c in post.calls] == [
        "gemini-3.5-flash:generateContent",
        "gemini-3.5-flash:generateContent",
        "gemini-3.5-flash-lite:generateContent",
    ]
    assert "boom" not in str(e.value)


def test_http_status_is_reported_and_thought_parts_are_skipped():
    import urllib.error

    busy = urllib.error.HTTPError("https://g.test", 503, "Unavailable", {}, None)
    with pytest.raises(SummaryError, match="HTTP 503"):
        GeminiSummarizer("k", post=FakePost(busy, busy, busy), retry_wait=0).digests([cand(1)])
    rows = [{"id": 0, "summary": "요약"}]
    reply = {"candidates": [{"content": {"parts": [{"text": "thinking", "thought": True}, {"text": json.dumps(rows)}]}}]}
    out = GeminiSummarizer("k", post=FakePost(json.dumps(reply).encode()), retry_wait=0).digests([cand(1)])
    assert out == {1: Digest("Fed holds rates", "요약")}


def test_empty_input_makes_no_call():
    post = FakePost()
    assert GeminiSummarizer("k", post=post, retry_wait=0).digests([]) == {}
    assert post.calls == []


def test_fallback_uses_title_and_a_short_description():
    d = fallback(cand(1, title="원제목", summary="가" * 300))
    assert d.title == "원제목" and len(d.summary) <= 160 and d.summary.endswith("…")
    assert fallback(cand(2, summary="")).summary == ""
