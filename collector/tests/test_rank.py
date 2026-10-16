from datetime import datetime, timedelta, timezone

from hub_collect.rank import Candidate, Signal, pick, recency, score_all
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
    seeds = [Signal("주제: A", (1.0, 0.0, 0.0)), Signal("주제: B", (0.0, 1.0, 0.0))]
    scored = score_all([cand(1, (0.0, 1.0, 0.0)), cand(2, (0.0, 0.0, 1.0)), cand(3, (0.0, 2.0, 0.0), hours=24)], seeds, NOW)
    assert [s.candidate.id for s in scored] == [1, 3, 2]
    assert abs(scored[0].relevance - 1.0) < 1e-9
    assert abs(scored[1].score - 0.85) < 1e-9  # relevance 1 x (0.7 + 0.3 x 0.5)
    assert scored[0].reason == "주제: B"


def test_topics_have_short_labels():
    assert all(0 < len(t.label) <= 12 for t in TOPICS)


def test_liked_articles_add_a_bonus_and_name_the_reason():
    seeds = [Signal("주제: A", (1.0, 0.0, 0.0))]
    liked = [Signal("👍 비슷: 예전 기사", (0.0, 1.0, 0.0))]
    near_like, plain = cand(1, (0.5, 0.8, 0.0)), cand(2, (0.6, 0.0, 0.8))  # seed match 0.53 vs 0.6
    assert [s.candidate.id for s in score_all([near_like, plain], seeds, NOW)] == [2, 1]
    learned = score_all([near_like, plain], seeds, NOW, liked=liked)
    assert [s.candidate.id for s in learned] == [1, 2]  # like match 0.85 adds 0.5 x 0.35
    assert learned[0].reason == "주제: A · 👍 비슷: 예전 기사" and learned[1].reason == "주제: A"


def test_a_like_never_replaces_the_topics():
    seeds = [Signal("주제: A", (1.0, 0.0, 0.0))]
    liked = [Signal("👍", (0.0, 1.0, 0.0))]
    off_topic, on_topic = cand(1, (0.0, 1.0, 0.0)), cand(2, (0.6, 0.0, 0.8))
    by_id = {s.candidate.id: s for s in score_all([off_topic, on_topic], seeds, NOW, liked=liked)}
    assert by_id[1].relevance < by_id[2].relevance  # identical to a liked story, but 0.25 bonus < 0.6 topic match


def test_disliked_articles_push_close_candidates_down_but_ignore_distant_ones():
    seeds = [Signal("주제: A", (1.0, 0.0, 0.0))]
    disliked = [Signal("👎", (0.8, 0.6, 0.0))]
    close, far = cand(1, (0.8, 0.6, 0.0)), cand(2, (0.6, 0.0, 0.8))
    by_id = {s.candidate.id: s for s in score_all([close, far], seeds, NOW, disliked=disliked)}
    assert abs(by_id[1].relevance - (0.8 - 0.5 * 0.5)) < 1e-9  # 1.0 dislike match is 0.5 past the floor
    assert abs(by_id[2].relevance - 0.6) < 1e-9  # dislike similarity 0.48 stays under the floor


def test_notice_board_and_people_items_are_never_scored():
    def titled(id, title):
        return Candidate(id, "a", "invest", f"https://x.test/{id}", title, "", NOW, (1.0,))

    cands = [titled(1, "[게시판] 증권사 기부"), titled(2, "【인사】 금융위"), titled(3, "[특징주] 반도체 강세"), titled(4, "[속보] 금리 동결")]
    assert [s.candidate.id for s in score_all(cands, [Signal("주제: A", (1.0,))], NOW)] == [3, 4]


def test_pick_limits_each_source():
    seeds = [Signal("주제: A", (1.0, 0.0))]
    cands = [cand(i, (1.0, 0.1 * i), source="a") for i in range(5)] + [cand(9, (0.5, 1.0), source="b")]
    picked = pick(score_all(cands, seeds, NOW), size=4, per_source=3, per_category=0, duplicate=1.1)
    assert [p.candidate.source for p in picked].count("a") == 3
    assert 9 in [p.candidate.id for p in picked]


def test_pick_skips_near_duplicates():
    seeds = [Signal("주제: A", (1.0, 0.0))]
    cands = [cand(1, (1.0, 0.0), source="a"), cand(2, (1.0, 0.01), source="b"), cand(3, (0.6, 0.8), source="c")]
    picked = pick(score_all(cands, seeds, NOW), size=2, per_source=3, per_category=0, duplicate=0.85)
    assert [p.candidate.id for p in picked] == [1, 3]


def test_pick_reserves_a_minimum_per_category():
    seeds = [Signal("주제: A", (1.0, 0.0))]
    cands = [cand(i, (1.0, 0.0), source=f"s{i}") for i in range(4)] + [cand(9, (0.1, 1.0), category="tech", source="t")]
    picked = pick(score_all(cands, seeds, NOW), size=3, per_source=3, per_category=1, duplicate=1.1)
    assert 9 in [p.candidate.id for p in picked]
    assert [p.score for p in picked] == sorted((p.score for p in picked), reverse=True)


def test_pick_returns_fewer_when_candidates_run_out():
    assert pick(score_all([cand(1, (1.0,))], [Signal("주제: A", (1.0,))], NOW), size=10) != []
    assert pick([], size=10) == []
