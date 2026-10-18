import json
import urllib.error
from datetime import date, datetime, timezone

import pytest

from hub_collect.rank import Candidate
from hub_collect.summarize import Digest
from hub_collect.telegram import Telegram, TelegramError, Vote, format_brief

AT = datetime(2026, 10, 17, tzinfo=timezone.utc)


def cand(id, category="invest", url=None):
    return Candidate(id, "hankyung_economy", category, url or f"https://x.test/{id}?a=1&b=2", "t", "", AT, (1.0,))


class FakePost:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, url, headers, body):
        self.calls.append((url, json.loads(body)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return json.dumps(reply).encode()


def test_format_escapes_html_and_numbers_buttons():
    entries = [(cand(7), Digest("A<B & C", "요약"), "주제: 반도체"), (cand(8, "tech"), Digest("둘째", ""), "")]
    text, keyboard = format_brief(date(2026, 10, 17), entries)
    assert "10월 17일" in text
    assert "A&lt;B &amp; C" in text and 'href="https://x.test/7?a=1&amp;b=2"' in text
    assert "[투자]" in text and "[기술]" in text
    assert "<i>주제: 반도체</i>" in text and text.count("<i>") == 1
    assert keyboard == [
        [
            {"text": "1 👍", "callback_data": "v:7:1"},
            {"text": "1 👎", "callback_data": "v:7:-1"},
            {"text": "2 👍", "callback_data": "v:8:1"},
            {"text": "2 👎", "callback_data": "v:8:-1"},
        ]
    ]


def test_format_drops_summaries_before_exceeding_the_limit():
    from hub_collect.telegram import visible_length

    long_url = "https://x.test/" + "p" * 3000
    entries = [(cand(i, url=long_url), Digest("제목" * 30, "가" * 160), "") for i in range(10)]
    text, _ = format_brief(date(2026, 10, 17), entries, limit=2500)
    assert visible_length(text) <= 2500 < len(text)  # links do not count
    assert text.count("<a href") == 10


def test_only_the_top_ten_carry_summaries():
    from hub_collect.telegram import visible_length

    entries = [(cand(i), Digest(f"제목{i}" * 8, f"요약{i}" + "가" * 150), "주제: 반도체") for i in range(20)]
    text, keyboard = format_brief(date(2026, 10, 17), entries)
    assert visible_length(text) <= 4096
    assert "요약9" in text and "요약10" not in text and "더 볼 기사" in text
    assert text.count("<a href") == 20 and text.count("<i>") == 20
    assert sum(len(row) for row in keyboard) == 40


def test_explorations_get_their_own_labelled_section_with_summaries():
    from hub_collect.telegram import visible_length

    entries = [(cand(i), Digest(f"제목{i}", f"요약{i}" + "가" * 100), "주제: 반도체" if i < 15 else "") for i in range(20)]
    text, keyboard = format_brief(date(2026, 10, 17), entries, explore_from=16)
    assert visible_length(text) <= 4096 and text.count("🧭 새로운 주제") == 1 and text.count("더 볼 기사") == 1
    assert text.index("더 볼 기사") < text.index("🧭 새로운 주제")
    assert "요약10" not in text and "요약17" in text  # the explorations explain themselves
    assert sum(len(row) for row in keyboard) == 40
    trimmed, _ = format_brief(date(2026, 10, 17), entries[:3], explore_from=16)
    assert "🧭" not in trimmed


def test_videos_get_their_own_section_before_the_explorations():
    from hub_collect.telegram import visible_length

    def entry(i, video=False):
        c = cand(i, url=f"https://www.youtube.com/watch?v={i}" if video else None)
        return (c, Digest(f"제목{i}", f"요약{i}" + "가" * 100), "주제: 반도체" if i < 12 else "")

    entries = [entry(i, video=12 <= i < 15) for i in range(20)]
    text, keyboard = format_brief(date(2026, 10, 17), entries, explore_from=16, video_from=13)
    assert visible_length(text) <= 4096
    assert text.index("더 볼 기사") < text.index("▶ 영상") < text.index("🧭 새로운 주제")
    assert text.count("[영상]") == 3 and text.count("▶ 영상") == 1
    assert "요약10" not in text and "요약13" in text and "요약17" in text
    assert sum(len(row) for row in keyboard) == 40


def test_format_drops_trailing_articles_as_a_last_resort():
    from hub_collect.telegram import visible_length

    entries = [(cand(i), Digest("제목" * 40, ""), "") for i in range(10)]
    text, keyboard = format_brief(date(2026, 10, 17), entries, limit=500)
    assert visible_length(text) <= 500 and 0 < text.count("<a href") < 10


def test_send_posts_html_with_keyboard_and_returns_message_id():
    post = FakePost({"ok": True, "result": {"message_id": 55}})
    assert Telegram("tok", "99", post=post).send("hi", [[{"text": "1 👍", "callback_data": "v:1:1"}]]) == 55
    url, body = post.calls[0]
    assert url.endswith("/sendMessage")
    assert body["chat_id"] == "99" and body["parse_mode"] == "HTML"
    assert body["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "v:1:1"


def test_errors_never_carry_the_token():
    err = urllib.error.HTTPError("https://api.telegram.org/botTOKEN123/sendMessage", 401, "Unauthorized", {}, None)
    with pytest.raises(TelegramError) as e:
        Telegram("TOKEN123", "99", post=FakePost(err)).send("hi", [])
    assert "TOKEN123" not in str(e.value) and "401" in str(e.value) and e.value.rejected
    with pytest.raises(TelegramError) as e:
        Telegram("TOKEN123", "99", post=FakePost({"ok": False, "description": "bad"})).send("hi", [])
    assert e.value.rejected


def test_timeouts_and_server_errors_are_not_treated_as_rejections():
    busy = urllib.error.HTTPError("https://api.telegram.org/botT/sendMessage", 502, "Bad Gateway", {}, None)
    for failure in (TimeoutError("timed out"), busy):
        with pytest.raises(TelegramError) as e:
            Telegram("T", "99", post=FakePost(failure)).send("hi", [])
        assert not e.value.rejected


def update(uid, data, chat=99, sender=None):
    query = {"data": data, "from": {"id": chat if sender is None else sender}, "message": {"chat": {"id": chat}}}
    return {"update_id": uid, "callback_query": query}


def test_votes_keep_own_chat_last_press_and_advance_offset():
    post = FakePost(
        {
            "ok": True,
            "result": [
                update(10, "v:7:1"),
                update(11, "v:7:-1"),
                update(12, "v:8:1", chat=1234),  # someone else's chat
                update(16, "v:9:1", sender=555),  # someone else pressing in this chat
                update(13, "junk"),
                update(14, "v:x:1"),
                {"update_id": 15, "message": {"text": "/start"}},
            ],
        }
    )
    votes, offset = Telegram("tok", "99", post=post).votes(5)
    assert votes == [Vote(7, -1)]
    assert offset == 17
    assert post.calls[0][1]["offset"] == 5 and post.calls[0][1]["allowed_updates"] == ["callback_query"]


def test_no_updates_keeps_offset():
    assert Telegram("tok", "99", post=FakePost({"ok": True, "result": []})).votes(5) == ([], 5)
