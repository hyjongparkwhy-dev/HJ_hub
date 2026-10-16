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
class Scored:
    candidate: Candidate
    score: float
    relevance: float
    unit: tuple[float, ...] = field(repr=False)


def _unit(vector: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return tuple(v / norm for v in vector)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def recency(at: datetime, now: datetime) -> float:
    hours = max((now - at).total_seconds() / 3600, 0.0)
    return 0.5 ** (hours / HALF_LIFE_HOURS)


def score_all(candidates: Sequence[Candidate], seeds: Sequence[Sequence[float]], now: datetime) -> list[Scored]:
    units = [_unit(s) for s in seeds]
    scored = []
    for c in candidates:
        if NOISE_TITLE.match(c.title):
            continue
        unit = _unit(c.vector)
        relevance = max(_dot(unit, s) for s in units)
        score = relevance * (1 - FRESHNESS_WEIGHT + FRESHNESS_WEIGHT * recency(c.at, now))
        scored.append(Scored(c, score, relevance, unit))
    return sorted(scored, key=lambda s: s.score, reverse=True)


def pick(
    scored: Sequence[Scored], size: int = 10, per_source: int = 3, per_category: int = 2, duplicate: float = 0.85
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
