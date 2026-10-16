"""Morning briefing: collect 👍/👎, rank the last two days, summarize the top 10 once, send one message.

Output is counts only: this repository and its Actions logs are public. `--dry-run` prints the message
locally instead of sending it and refuses to run on Actions."""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

from hub_collect.brief_store import BriefStore
from hub_collect.embed import Embedder
from hub_collect.rank import Signal, pick, score_all
from hub_collect.settings import load_database_url, load_setting
from hub_collect.store import connect
from hub_collect.summarize import GeminiSummarizer, SummaryError, fallback
from hub_collect.telegram import Telegram, TelegramError, format_brief
from hub_collect.topics import TOPICS

KST = timezone(timedelta(hours=9))  # Korea has no daylight saving time
WINDOW_HOURS = 48
BRIEF_SIZE = 10
FEEDBACK_DAYS = 90  # older votes stop steering, so interests can drift
FEEDBACK_LIMIT = 200  # per direction; keeps scoring fast in pure Python


def kst_day(now: datetime) -> date:
    return now.astimezone(KST).date()


def collect_votes(store, telegram, stats: dict) -> None:
    try:
        votes, offset = telegram.votes(store.offset())
    except TelegramError as e:
        # Unread presses stay on Telegram's side for 24 hours; the evening run picks them up.
        stats["votes_error"] = str(e)
        return
    stats["votes"] = store.save_votes(votes)
    store.save_offset(offset)


def brief(store, telegram, summarizer, embedder, now: datetime, dry_run: bool = False) -> tuple[dict, str | None]:
    """A dry run writes nothing: no votes, no digest cache, no briefing."""
    stats: dict = {}
    if not dry_run:
        collect_votes(store, telegram, stats)
    day = kst_day(now)
    if not dry_run and store.briefed(day):
        stats["skipped"] = "already_sent"
        return stats, None
    candidates = store.candidates(WINDOW_HOURS)
    stats["candidates"] = len(candidates)
    if not candidates:
        stats["skipped"] = "no_candidates"
        return stats, None
    seeds = [Signal(f"주제: {t.label}", v) for t, v in zip(TOPICS, embedder.vectors([t.text for t in TOPICS]), strict=True)]
    liked, disliked = store.feedback_signals(FEEDBACK_DAYS, FEEDBACK_LIMIT)
    stats["liked"], stats["disliked"] = len(liked), len(disliked)
    picked = pick(score_all(candidates, seeds, now, liked, disliked), size=BRIEF_SIZE)
    # Digests made earlier today are reused, so a rerun after a failed send does not spend Gemini quota again.
    digests = store.cached_digests(day)
    missing = [s.candidate for s in picked if s.candidate.id not in digests]
    if summarizer is not None and missing:
        try:
            fresh = summarizer.digests(missing)
        except SummaryError as e:
            stats["summary_error"] = str(e)
        else:
            digests |= fresh
            if not dry_run:
                store.save_digests(day, digests)
    stats["summarized"] = sum(s.candidate.id in digests for s in picked)
    entries = [(s.candidate, digests.get(s.candidate.id) or fallback(s.candidate), s.reason) for s in picked]
    text, keyboard = format_brief(day, entries)
    stats["picked"] = len(entries)
    if dry_run:
        return stats, text
    # The rows are written first and committed after the send. A refused send rolls back so a rerun tries
    # again; a timeout or server error may still have delivered, so the record stays and today is not retried
    # (a missed briefing is better than a duplicate).
    uncertain = None
    with store.transaction():
        brief_id = store.save_brief(day, picked, [d for _, d, _ in entries], stats)
        try:
            store.set_message(brief_id, telegram.send(text, keyboard))
        except TelegramError as e:
            if e.rejected:
                raise
            uncertain = e
    if uncertain is not None:
        stats["send_uncertain"] = str(uncertain)
    else:
        stats["sent"] = True
    return stats, None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    dry_run, feedback_only = "--dry-run" in args, "--feedback-only" in args
    if dry_run and feedback_only:
        print("--dry-run and --feedback-only cannot be combined", file=sys.stderr)
        return 2
    if dry_run and os.environ.get("GITHUB_ACTIONS"):
        print("--dry-run prints article titles and is for local use only", file=sys.stderr)
        return 2
    url = load_database_url()
    token, chat_id = load_setting("HUB_TELEGRAM_TOKEN"), load_setting("HUB_TELEGRAM_CHAT_ID")
    required = {"HUB_DATABASE_URL": url}
    if not dry_run:
        required |= {"HUB_TELEGRAM_TOKEN": token, "HUB_TELEGRAM_CHAT_ID": chat_id}
    missing = [name for name, value in required.items() if not value]
    if missing:
        print(json.dumps({"missing": missing}))
        return 2
    telegram = Telegram(token, chat_id) if token and chat_id else None
    key = load_setting("GEMINI_API_KEY")
    # The Gemini quota is shared with other apps: a preview summarizes only when asked to.
    use_gemini = key and (not dry_run or "--summarize" in args)
    summarizer = GeminiSummarizer(key, load_setting("GEMINI_MODEL")) if use_gemini else None
    try:
        with connect(url) as conn:
            store = BriefStore(conn)
            if feedback_only:
                stats: dict = {}
                collect_votes(store, telegram, stats)
                text = None
            else:
                stats, text = brief(
                    store, telegram, summarizer, Embedder(os.environ.get("FASTEMBED_CACHE")), datetime.now(timezone.utc), dry_run
                )
    except TelegramError as e:
        print(json.dumps({"error": str(e)}))  # already token-free: method name and HTTP status only
        return 1
    except Exception as e:
        # Database errors can quote hosts or rows; the public log gets the type only.
        print(json.dumps({"error": type(e).__name__}))
        return 1
    if text is not None:
        print(text)
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    failed = "send_uncertain" in stats or ("votes_error" in stats and feedback_only)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
