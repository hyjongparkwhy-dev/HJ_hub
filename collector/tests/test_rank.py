from datetime import datetime, timedelta, timezone

from hub_collect.rank import Candidate, pick, recency, score_all
from hub_collect.topics import TOPICS

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


def cand(id, vector, source="a", category="invest", hours=0):
    return Candidate(id, source, category, f"https://x.test/{id}", f"t{id}", "", NOW - timedelta(hours=hours), vector)


def test_topics_cover_every_category():
    assert {t.category for t in TOPICS} == {"invest", "realestate", "tech"}
    assert all(t.text.strip() for t in TOPICS)


def test_recency_halves_every_day_and_ignores_future():
    assert recency(NOW, NOW) == 1.0
    assert abs(recency(NOW - timedelta(hours=24), NOW) - 0.5) < 1e-9
    assert recency(NOW + timedelta(hours=3), NOW) == 1.0


def test_score_uses_best_matching_seed_and_freshness():
    seeds = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    scored = score_all([cand(1, (0.0, 1.0, 0.0)), cand(2, (0.0, 0.0, 1.0)), cand(3, (0.0, 2.0, 0.0), hours=24)], seeds, NOW)
    assert [s.candidate.id for s in scored] == [1, 3, 2]
    assert abs(scored[0].relevance - 1.0) < 1e-9
    assert abs(scored[1].score - 0.85) < 1e-9  # relevance 1 x (0.7 + 0.3 x 0.5)


def test_notice_board_and_people_items_are_never_scored():
    def titled(id, title):
        return Candidate(id, "a", "invest", f"https://x.test/{id}", title, "", NOW, (1.0,))

    cands = [titled(1, "[게시판] 증권사 기부"), titled(2, "【인사】 금융위"), titled(3, "[특징주] 반도체 강세"), titled(4, "[속보] 금리 동결")]
    assert [s.candidate.id for s in score_all(cands, [(1.0,)], NOW)] == [3, 4]


def test_pick_limits_each_source():
    seeds = [(1.0, 0.0)]
    cands = [cand(i, (1.0, 0.1 * i), source="a") for i in range(5)] + [cand(9, (0.5, 1.0), source="b")]
    picked = pick(score_all(cands, seeds, NOW), size=4, per_source=3, per_category=0, duplicate=1.1)
    assert [p.candidate.source for p in picked].count("a") == 3
    assert 9 in [p.candidate.id for p in picked]


def test_pick_skips_near_duplicates():
    seeds = [(1.0, 0.0)]
    cands = [cand(1, (1.0, 0.0), source="a"), cand(2, (1.0, 0.01), source="b"), cand(3, (0.6, 0.8), source="c")]
    picked = pick(score_all(cands, seeds, NOW), size=2, per_source=3, per_category=0, duplicate=0.85)
    assert [p.candidate.id for p in picked] == [1, 3]


def test_pick_reserves_a_minimum_per_category():
    seeds = [(1.0, 0.0)]
    cands = [cand(i, (1.0, 0.0), source=f"s{i}") for i in range(4)] + [cand(9, (0.1, 1.0), category="tech", source="t")]
    picked = pick(score_all(cands, seeds, NOW), size=3, per_source=3, per_category=1, duplicate=1.1)
    assert 9 in [p.candidate.id for p in picked]
    assert [p.score for p in picked] == sorted((p.score for p in picked), reverse=True)


def test_pick_returns_fewer_when_candidates_run_out():
    assert pick(score_all([cand(1, (1.0,))], [(1.0,)], NOW), size=10) != []
    assert pick([], size=10) == []
