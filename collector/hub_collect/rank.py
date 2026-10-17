"""Interest ranking: seed similarity weighted by freshness, then a diverse top N."""
from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from hub_collect.sources import CATEGORIES

HALF_LIFE_HOURS = 24.0
FRESHNESS_WEIGHT = 0.3
# Measured with EmbeddingGemma on 2026-10-16 (336 items): the best seed topic match is 0.32 at the median and
# 0.63 at most, unrelated article pairs stay under 0.36 for 95% of pairs, and one story told by two outlets
# (or in two languages) scores 0.74-0.93. Votes add or subtract half of what passes FEEDBACK_FLOOR, so a
# follow-up of a 👍 story (~0.87) gains about as much as the spread between a median and a top topic match.
FEEDBACK_FLOOR = 0.5
FEEDBACK_WEIGHT = 0.5
SAME_STORY = 0.75
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


def _unit(vector: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return tuple(v / norm for v in vector)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


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


def pick(
    scored: Sequence[Scored], size: int = 10, per_source: int = 2, per_category: int = 2, duplicate: float = SAME_STORY
) -> list[Scored]:
    """Greedy top `size` from score order. Each category first gets up to `per_category` slots so one busy
    field cannot fill the whole briefing; one story covered by several outlets counts once."""
    picked: list[Scored] = []

    def fits(s: Scored) -> bool:
        if any(p is s for p in picked) or sum(p.candidate.source == s.candidate.source for p in picked) >= per_source:
            return False
        return all(_dot(s.unit, p.unit) < duplicate for p in picked)

    for category in CATEGORIES:
        taken = 0
        for s in scored:
            if taken >= per_category or len(picked) >= size:
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
