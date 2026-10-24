"""Interest ranking: seed similarity weighted by freshness, then a diverse top N."""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime

from hub_collect.sources import CATEGORIES, SOURCES, is_video

HALF_LIFE_HOURS = 24.0
FRESHNESS_WEIGHT = 0.3
# Measured with EmbeddingGemma on 2026-10-16 (336 items): the best seed topic match is 0.32 at the median and
# 0.63 at most, unrelated article pairs stay under 0.36 for 95% of pairs, and one story told by two outlets
# (or in two languages) scores 0.74-0.93. Votes add or subtract half of what passes FEEDBACK_FLOOR, so a
# follow-up of a 👍 story (~0.87) gains about as much as the spread between a median and a top topic match.
FEEDBACK_FLOOR = 0.5
FEEDBACK_WEIGHT = 0.5
SAME_STORY = 0.75
# Exploration slots come from the least interesting half of the candidates, so a 👍 there can reveal a new interest.
# Another outlet telling the same story (0.74-0.93 apart, see above) is the quality signal; freshness breaks ties.
EXPLORE_SIZE = 5
VIDEO_SIZE = 3  # one per channel, ranked among videos only so they never compete with articles
# Relative weights of the usual article picks per category. Scores alone cannot set the mix: votes made 부동산 score
# 70-80 while tech tops out near 50, so the weights decide how many slots each category gets.
CATEGORY_SHARE = {"tech": 5, "invest": 4, "realestate": 3}
EXPLORE_SKIP = ("realestate",)  # a known interest is not a new one; explorations come from the other fields
EXPLORE_POOL = 100  # newest candidates compared; keeps the pure-Python similarity count to a few seconds
COVERED = 0.7
COVERAGE_CAP = 3
# Price-move headlines (특징주, 장초반, 마감) of one stock on different days score 0.66-0.87 (measured 2026-10-23), often
# under SAME_STORY; moves of related stocks reach 0.68-0.74, so a pair of them over this line counts as one story.
MARKET_MOVE = re.compile(r"특징주|장\s?초반|마감|급등|급락|반등|강세|약세|[↑↓]")
SAME_MARKET_MOVE = 0.65
# A Korean and an English report of one event score only 0.67-0.75; Korean-English pairs at 0.67-0.70 were the same
# event or a tightly linked one (2 days of items, measured 2026-10-23).
SAME_STORY_ACROSS_LANGUAGES = 0.67
LANGUAGE = {s.id: s.lang for s in SOURCES}
# Two reports of one event often share a name few other titles use (SK하이퍼, HD현대, Moderna) yet score 0.65-0.75.
# On 48 hours of candidates (2026-10-24), pairs over 0.65 sharing a word found in at most 5 titles were the same
# event 85-90% of the time; the rest were close relatives (one district's record sales, one person's remarks).
SAME_STORY_SHARED_NAME = 0.65
RARE_WORD_MAX = 5
WORD = re.compile(r"[0-9A-Za-z가-힣]+")
HANGUL = re.compile(r"[가-힣]")
PARTICLE = re.compile(r"(으로|에서|에게|까지|부터|은|는|이|가|을|를|의|에|도|로|와|과|만)$")
NUMBER_WORD = re.compile(r"^\d+[가-힣]*$")  # dates and amounts: 10월, 463조, 2026년
# Notice boards, appointments, obituaries and photo captions match finance seeds by vocabulary alone.
NOISE_TITLE = re.compile(r"^\s*[\[【](게시판|인사|부고|프로필|포토|사진|화보)[\]】]")


@dataclass(frozen=True)
class Candidate:
    id: int
    source: str
    category: str
    url: str
    title: str
    summary: str
    at: datetime
    vector: Sequence[float]

    @property
    def is_video(self) -> bool:
        return is_video(self.url)


@dataclass(frozen=True)
class Signal:
    """A seed topic or a voted article: the label explains a match, e.g. "주제: 반도체"."""

    label: str
    vector: Sequence[float]


@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    score: float
    relevance: float
    unit: tuple[float, ...] = field(repr=False)
    reason: str = ""
    explore: bool = False


def _unit(vector: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return tuple(v / norm for v in vector)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def title_words(title: str) -> frozenset[str]:
    """Words long enough to name something: Korean 3+ syllables without a trailing particle, other words 4+ letters."""
    words = set()
    for word in WORD.findall(title):
        if NUMBER_WORD.match(word):
            continue
        if HANGUL.search(word):
            word = PARTICLE.sub("", word)
            if len(word) >= 3:
                words.add(word.lower())
        elif len(word) >= 4:
            words.add(word.lower())
    return frozenset(words)


def rare_words(scored: Sequence[Scored]) -> dict[int, frozenset[str]]:
    """Each candidate's words that at most RARE_WORD_MAX candidate titles use."""
    words = {s.candidate.id: title_words(s.candidate.title) for s in scored}
    counts = Counter(w for ws in words.values() for w in ws)
    return {i: frozenset(w for w in ws if counts[w] <= RARE_WORD_MAX) for i, ws in words.items()}


def is_market_move(title: str) -> bool:
    return bool(MARKET_MOVE.search(title))


def _same_story(a: Scored, b: Scored, duplicate: float, rare: Mapping[int, frozenset[str]]) -> bool:
    similarity = _dot(a.unit, b.unit)
    if similarity >= duplicate:
        return True
    lang_a, lang_b = LANGUAGE.get(a.candidate.source), LANGUAGE.get(b.candidate.source)
    if lang_a and lang_b and lang_a != lang_b and similarity >= min(duplicate, SAME_STORY_ACROSS_LANGUAGES):
        return True
    shared = rare.get(a.candidate.id, frozenset()) & rare.get(b.candidate.id, frozenset())
    if shared and similarity >= min(duplicate, SAME_STORY_SHARED_NAME):
        return True
    both_moves = is_market_move(a.candidate.title) and is_market_move(b.candidate.title)
    return both_moves and similarity >= min(duplicate, SAME_MARKET_MOVE)


def recency(at: datetime, now: datetime) -> float:
    hours = max((now - at).total_seconds() / 3600, 0.0)
    return 0.5 ** (hours / HALF_LIFE_HOURS)


def _best(unit: Sequence[float], signals: Sequence[tuple[str, tuple[float, ...]]]) -> tuple[float, str]:
    return max(((_dot(unit, v), label) for label, v in signals), default=(0.0, ""))


def score_all(
    candidates: Sequence[Candidate],
    seeds: Sequence[Signal],
    now: datetime,
    liked: Sequence[Signal] = (),
    disliked: Sequence[Signal] = (),
) -> list[Scored]:
    """Relevance is the closest seed topic, plus a bonus for a close 👍 article and minus a penalty for a close
    👎 one. The reason names the topic and, when it added anything, the 👍 article."""
    seed_units = [(s.label, _unit(s.vector)) for s in seeds]
    liked_units = [(s.label, _unit(s.vector)) for s in liked]
    disliked_units = [(s.label, _unit(s.vector)) for s in disliked]
    scored = []
    for c in candidates:
        if NOISE_TITLE.match(c.title):
            continue
        unit = _unit(c.vector)
        relevance, reason = _best(unit, seed_units)
        like_sim, like_label = _best(unit, liked_units)
        if like_sim > FEEDBACK_FLOOR:
            relevance += FEEDBACK_WEIGHT * (like_sim - FEEDBACK_FLOOR)
            reason = f"{reason} · {like_label}"
        relevance -= FEEDBACK_WEIGHT * max(0.0, _best(unit, disliked_units)[0] - FEEDBACK_FLOOR)
        score = relevance * (1 - FRESHNESS_WEIGHT + FRESHNESS_WEIGHT * recency(c.at, now))
        scored.append(Scored(c, score, relevance, unit, reason))
    return sorted(scored, key=lambda s: s.score, reverse=True)


def category_quotas(size: int, share: Mapping[str, int] = CATEGORY_SHARE) -> dict[str, int]:
    """Splits `size` slots in proportion to `share`; the largest remainders get the leftover slots."""
    total = sum(share.values())
    quotas = {c: size * w // total for c, w in share.items()}
    by_remainder = sorted(share, key=lambda c: (size * share[c] % total, share[c]), reverse=True)
    for c in by_remainder[: size - sum(quotas.values())]:
        quotas[c] += 1
    return quotas


def pick(
    scored: Sequence[Scored],
    size: int = 10,
    per_source: int = 2,
    per_category: int = 2,
    duplicate: float = SAME_STORY,
    quota: Mapping[str, int] | None = None,
) -> list[Scored]:
    """Greedy top `size` from score order. Each category first gets its `quota` slots (default: `per_category`
    for every category) so one busy field cannot fill the whole briefing; slots a category cannot fill go to the
    best of the rest. One story covered by several outlets counts once."""
    picked: list[Scored] = []
    rare = rare_words(scored)
    limits = quota if quota is not None else dict.fromkeys(CATEGORIES, per_category)

    def fits(s: Scored) -> bool:
        if any(p is s for p in picked) or sum(p.candidate.source == s.candidate.source for p in picked) >= per_source:
            return False
        return not any(_same_story(s, p, duplicate, rare) for p in picked)

    for category in CATEGORIES:
        taken = 0
        for s in scored:
            if taken >= limits.get(category, 0) or len(picked) >= size:
                break
            if s.candidate.category == category and fits(s):
                picked.append(s)
                taken += 1
    for s in scored:
        if len(picked) >= size:
            break
        if fits(s):
            picked.append(s)
    return sorted(picked, key=lambda s: s.score, reverse=True)


def explore_picks(
    scored: Sequence[Scored],
    picked: Sequence[Scored],
    count: int,
    now: datetime,
    per_source: int = 2,
    per_category: int = 2,
    duplicate: float = SAME_STORY,
    skip_categories: Collection[str] = (),
) -> list[Scored]:
    """`count` fresh stories from outside the owner's usual interests, each told by other outlets too."""
    if count <= 0 or not scored:
        return []
    chosen = {p.candidate.id for p in picked}
    median = sorted(s.relevance for s in scored)[len(scored) // 2]
    pool = [s for s in scored if s.candidate.id not in chosen and s.relevance <= median and s.candidate.category not in skip_categories]
    pool.sort(key=lambda s: recency(s.candidate.at, now), reverse=True)

    def coverage(s: Scored) -> int:
        return min(COVERAGE_CAP, sum(1 for o in scored if o is not s and _dot(s.unit, o.unit) >= COVERED))

    ranked = sorted(
        ((coverage(s), recency(s.candidate.at, now), s) for s in pool[:EXPLORE_POOL]), key=lambda t: t[:2], reverse=True
    )
    rare = rare_words(scored)
    taken = list(picked)
    extra: list[Scored] = []
    for category_cap in (per_category, count):  # first spread over topics, then fill what is left
        per_category_count = Counter(e.candidate.category for e in extra)
        for _, _, s in ranked:
            if len(extra) >= count:
                break
            if any(s is e for e in extra):
                continue
            if sum(t.candidate.source == s.candidate.source for t in taken) >= per_source:
                continue
            if per_category_count[s.candidate.category] >= category_cap:
                continue
            if any(_same_story(s, t, min(duplicate, COVERED), rare) for t in taken):
                continue
            extra.append(replace(s, explore=True, reason=""))
            taken.append(s)
            per_category_count[s.candidate.category] += 1
    return extra


def select(
    scored: Sequence[Scored], now: datetime, size: int, explore: int = EXPLORE_SIZE, video: int = VIDEO_SIZE
) -> list[Scored]:
    """Usual article picks, then `video` videos (best from different channels), then `explore` articles from outside
    the usual interests. A slot with nothing to fill it goes back to the usual picks."""
    articles = [s for s in scored if not s.candidate.is_video]
    clips = pick([s for s in scored if s.candidate.is_video], size=video, per_source=1, per_category=0)
    main_size = size - explore - len(clips)
    main = pick(articles, size=main_size, quota=category_quotas(main_size))
    extra = explore_picks(articles, main, explore, now, skip_categories=EXPLORE_SKIP)
    if len(extra) < explore:
        taken = {e.candidate.id for e in extra}
        main_size = size - len(extra) - len(clips)
        main = pick([s for s in articles if s.candidate.id not in taken], size=main_size, quota=category_quotas(main_size))
    return main + clips + extra
