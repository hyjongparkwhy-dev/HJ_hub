from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytest

from hub_collect.brief import brief, kst_day, main
from hub_collect.rank import Candidate
from hub_collect.summarize import Digest, SummaryError
from hub_collect.telegram import TelegramError, Vote

NOW = datetime(2026, 10, 17, 0, 5, tzinfo=timezone.utc)  # 09:05 KST


def cand(id, category="invest", source=None):
    # Each article shares the seed direction plus one of its own, so no two look like the same story.
    vector = tuple(1.0 if d in (0, id) else 0.0 for d in range(32))
    return Candidate(id, source or f"s{id}", category, f"https://x.test/{id}", f"Secret title {id}", "desc", NOW - timedelta(hours=id), vector)


class FakeBriefStore:
    def __init__(self, candidates=(), briefed=False, offset=0, digests=None):
        self._candidates, self._briefed, self._offset = list(candidates), briefed, offset
        self.briefs, self.messages, self.votes, self.offsets, self.committed = [], [], [], [], 0
        self.digests, self.saved_digests = dict(digests or {}), []
        self.liked = []

    def feedback_signals(self, days, limit):
        assert (days, limit) == (90, 200)
        return list(self.liked), []

    def cached_digests(self, day):
        return dict(self.digests)

    def save_digests(self, day, digests):
        self.saved_digests.append(dict(digests))

    @contextmanager
    def transaction(self):
        saved = len(self.briefs)
        try:
            yield
        except Exception:
            del self.briefs[saved:]
            raise
        self.committed += 1

    def candidates(self, hours):
        assert hours == 48
        return self._candidates

    def briefed(self, day):
        return self._briefed

    def save_brief(self, day, picked, digests, stats):
        self.briefs.append((day, [s.candidate.id for s in picked], list(digests)))
        return 1

    def set_message(self, brief_id, message_id):
        self.messages.append((brief_id, message_id))

    def save_votes(self, votes):
        self.votes.extend(votes)
        return len(votes)

    def offset(self):
        return self._offset

    def save_offset(self, offset):
        self.offsets.append(offset)


class FakeTelegram:
    def __init__(self, votes=(), next_offset=9, fail_send=False, fail_votes=False, send_error=None):
        self._votes, self._next, self.fail_send, self.fail_votes = list(votes), next_offset, fail_send, fail_votes
        self.sent, self.send_error = [], send_error

    def votes(self, offset):
        if self.fail_votes:
            raise TelegramError("getUpdates failed with HTTP 502")
        return self._votes, self._next

    def send(self, text, keyboard):
        if self.fail_send:
            raise TelegramError("sendMessage failed with HTTP 400", rejected=True)
        if self.send_error:
            raise self.send_error
        self.sent.append((text, keyboard))
        return 77


class FakeEmbedder:
    def vectors(self, texts):
        return [tuple(1.0 if d == 0 else 0.0 for d in range(32)) for _ in texts]


class FakeSummarizer:
    def __init__(self, fail=False):
        self.fail, self.asked = fail, []

    def digests(self, items):
        self.asked.append([c.id for c in items])
        if self.fail:
            raise SummaryError("Gemini failed after 3 attempts (HTTPError)")
        return {c.id: Digest(f"요약 제목 {c.id}", "요약") for c in items[:2]}


def test_kst_day_rolls_over_at_midnight_korea_time():
    assert kst_day(datetime(2026, 10, 16, 14, 59, tzinfo=timezone.utc)) == date(2026, 10, 16)
    assert kst_day(datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)) == date(2026, 10, 17)


def test_full_run_collects_votes_then_sends_and_records_once():
    store, tg = FakeBriefStore([cand(i) for i in range(1, 26)], offset=4), FakeTelegram([Vote(3, 1)], next_offset=9)
    stats, text = brief(store, tg, FakeSummarizer(), FakeEmbedder(), NOW)
    assert text is None
    assert store.votes == [Vote(3, 1)] and store.offsets == [9]
    assert len(tg.sent) == 1 and store.messages == [(1, 77)] and store.committed == 1
    day, ids, digests = store.briefs[0]
    assert day == date(2026, 10, 17) and len(ids) == 20
    assert sum(d.title.startswith("요약 제목") for d in digests) == 2  # the rest fall back to feed text
    assert stats == {"votes": 1, "candidates": 25, "liked": 0, "disliked": 0, "summarized": 2, "picked": 20, "explore": 5, "sent": True}
    assert "<i>주제: " in tg.sent[0][0]  # every pick says why


def test_digests_from_an_earlier_run_today_are_reused():
    store = FakeBriefStore([cand(1), cand(2)], digests={1: Digest("캐시", "요약")})
    summarizer = FakeSummarizer()
    stats, _ = brief(store, FakeTelegram(), summarizer, FakeEmbedder(), NOW)
    assert summarizer.asked == [[2]]
    assert store.saved_digests[0].keys() == {1, 2}
    assert stats["summarized"] == 2


def test_uncertain_send_keeps_the_record_so_today_is_not_sent_twice():
    store = FakeBriefStore([cand(1)])
    stats, _ = brief(store, FakeTelegram(send_error=TelegramError("sendMessage failed (TimeoutError)")), None, FakeEmbedder(), NOW)
    assert stats["send_uncertain"] == "sendMessage failed (TimeoutError)" and "sent" not in stats
    assert len(store.briefs) == 1 and store.committed == 1 and store.messages == []


def test_already_sent_today_sends_nothing_but_still_collects_votes():
    store, tg = FakeBriefStore([cand(1)], briefed=True), FakeTelegram([Vote(1, -1)])
    stats, _ = brief(store, tg, FakeSummarizer(), FakeEmbedder(), NOW)
    assert stats["skipped"] == "already_sent" and tg.sent == [] and store.votes == [Vote(1, -1)]


def test_failed_send_leaves_no_record():
    store = FakeBriefStore([cand(1)])
    with pytest.raises(TelegramError):
        brief(store, FakeTelegram(fail_send=True), None, FakeEmbedder(), NOW)
    assert store.briefs == [] and store.committed == 0


def test_summary_and_vote_failures_do_not_stop_the_briefing():
    store, tg = FakeBriefStore([cand(1), cand(2)]), FakeTelegram(fail_votes=True)
    stats, _ = brief(store, tg, FakeSummarizer(fail=True), FakeEmbedder(), NOW)
    assert stats["sent"] and stats["summarized"] == 0
    assert "HTTP" in stats["summary_error"] and "502" in stats["votes_error"]
    assert store.offsets == []  # nothing read, nothing confirmed


def test_no_candidates_is_reported():
    stats, _ = brief(FakeBriefStore([]), FakeTelegram(), None, FakeEmbedder(), NOW)
    assert stats["skipped"] == "no_candidates"


def test_dry_run_returns_text_without_sending_or_saving():
    store, tg, summarizer = FakeBriefStore([cand(1)], briefed=True), FakeTelegram([Vote(1, 1)]), FakeSummarizer()
    stats, text = brief(store, tg, summarizer, FakeEmbedder(), NOW, dry_run=True)
    assert "요약 제목 1" in text and store.briefs == [] and "votes" not in stats
    assert store.votes == [] and store.offsets == [] and store.saved_digests == []
    assert summarizer.asked == [[1]]


def test_main_reports_missing_settings_by_name(monkeypatch, capsys):
    from hub_collect import brief as module

    monkeypatch.setattr(module, "load_database_url", lambda: "postgresql://unused")
    monkeypatch.setattr(module, "load_setting", lambda name: None)
    assert main([]) == 2
    assert capsys.readouterr().out.strip() == '{"missing": ["HUB_TELEGRAM_TOKEN", "HUB_TELEGRAM_CHAT_ID"]}'


def test_main_refuses_dry_run_on_actions(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert main(["--dry-run"]) == 2


def test_main_refuses_dry_run_with_feedback_only():
    assert main(["--dry-run", "--feedback-only"]) == 2


def test_main_prints_only_counts_and_error_types(monkeypatch, capsys):
    import psycopg

    from hub_collect import brief as module

    def broken_connect(url):
        raise psycopg.OperationalError('connection to "aws-0.pooler.supabase.com" failed for user "postgres.secretref"')

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(module, "load_database_url", lambda: "postgresql://unused")
    monkeypatch.setattr(module, "load_setting", lambda name: "x")
    monkeypatch.setattr(module, "connect", broken_connect)
    assert main([]) == 1
    out = capsys.readouterr()
    assert out.out.strip() == '{"error": "OperationalError"}'
    assert "secretref" not in out.out + out.err
