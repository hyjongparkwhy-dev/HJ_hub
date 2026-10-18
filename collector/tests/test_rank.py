from datetime import datetime, timedelta, timezone

from hub_collect.rank import Candidate, Signal, explore_picks, pick, recency, score_all, select
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


def _far(id, topic, source, category="invest", hours=1):
    """Stories about `topic` (an axis other than the interest axis 0), told by one outlet each."""
    vector = [0.1] + [0.0] * 9
    vector[topic] = 1.0
    return cand(id, tuple(vector), source=source, category=category, hours=hours)


def test_explore_picks_covered_stories_far_from_the_interests():
    seeds = [Signal("주제: A", (1.0,) + (0.0,) * 9)]
    near = [cand(i, (1.0,) + (0.0,) * 9, source=f"n{i}") for i in range(1, 7)]
    # topic 3 is told by three outlets, topic 5 by one: the covered one is the better exploration
    far = [_far(10, 3, "x"), _far(11, 3, "y"), _far(12, 3, "z"), _far(13, 5, "w")]
    scored = score_all(near + far, seeds, NOW)
    extra = explore_picks(scored, pick(scored, size=3, per_source=3, per_category=0, duplicate=1.1), 2, NOW, per_category=2)
    assert all(e.explore and e.reason == "" for e in extra)
    assert {e.candidate.id for e in extra} <= {10, 11, 12, 13}
    assert len({e.candidate.id for e in extra} & {10, 11, 12}) == 1  # the same story is never taken twice


def test_explore_never_repeats_picked_or_duplicate_stories_and_spreads_topics():
    seeds = [Signal("주제: A", (1.0,) + (0.0,) * 9)]
    near = [cand(i, (1.0,) + (0.0,) * 9, source=f"n{i}") for i in range(1, 5)]
    far = [_far(20 + i, 2 + i, f"s{i}", category="tech" if i % 2 else "invest") for i in range(6)]
    scored = score_all(near + far, seeds, NOW)
    main = pick(scored, size=4, per_source=3, per_category=0, duplicate=1.1)
    extra = explore_picks(scored, main, 4, NOW, per_category=2)
    ids = [e.candidate.id for e in extra]
    assert len(ids) == 4 and not set(ids) & {p.candidate.id for p in main}
    assert [e.candidate.category for e in extra].count("tech") <= 2 and [e.candidate.category for e in extra].count("invest") <= 2


def test_select_puts_explorations_last_and_falls_back_when_there_are_none():
    def story(topic, strength):  # a distinct story: shares `strength` of the interest axis, the rest is its own topic
        vector = [0.0] * 20
        vector[0], vector[topic] = strength, 1.0
        return tuple(vector)

    seeds = [Signal("주제: A", (1.0,) + (0.0,) * 19)]
    near = [cand(i, story(10 + i, 1.0), source=f"n{i}") for i in range(1, 9)]
    far = [cand(30 + i, story(2 + i, 0.1), source=f"s{i}") for i in range(3)]
    scored = score_all(near + far, seeds, NOW)
    chosen = select(scored, NOW, size=8, explore=3)
    assert len(chosen) == 8 and [c.explore for c in chosen] == [False] * 5 + [True] * 3
    # the only story left over repeats a picked one, so nothing can be explored and the usual picks stand
    echo = [cand(i, story(10 + i, 1.0), source=f"n{i}") for i in range(1, 4)] + [cand(9, story(11, 1.0), source="dup")]
    plain = select(score_all(echo, seeds, NOW), NOW, size=6, explore=3)
    assert len(plain) == 3 and not any(c.explore for c in plain)


def _video(id, topic, channel, hours=1):
    vector = [0.0] * 20
    vector[0], vector[topic] = 0.5, 1.0
    return Candidate(id, channel, "tech", f"https://www.youtube.com/watch?v={id}", f"v{id}", "", NOW - timedelta(hours=hours), tuple(vector))


def test_select_gives_videos_their_own_slots_one_per_channel():
    def story(topic, strength):
        vector = [0.0] * 20
        vector[0], vector[topic] = strength, 1.0
        return tuple(vector)

    seeds = [Signal("주제: A", (1.0,) + (0.0,) * 19)]
    articles = [cand(i, story(10 + i, 1.0), source=f"n{i}") for i in range(1, 10)] + [cand(30 + i, story(2 + i, 0.1), source=f"s{i}") for i in range(3)]
    videos = [_video(50, 14, "chanA"), _video(51, 15, "chanA"), _video(52, 16, "chanB"), _video(53, 17, "chanC"), _video(54, 18, "chanD")]
    chosen = select(score_all(articles + videos, seeds, NOW), NOW, size=10, explore=2, video=3)
    assert len(chosen) == 10
    clips = [c for c in chosen if c.candidate.is_video]
    assert len(clips) == 3 and len({c.candidate.source for c in clips}) == 3  # chanA once
    assert [c.explore for c in chosen] == [False] * 5 + [False] * 3 + [True] * 2
    assert all(c.candidate.is_video for c in chosen[5:8])
    assert not any(c.candidate.is_video for c in chosen if c.explore)
    # with no videos at all, the slots go back to articles
    none = select(score_all(articles, seeds, NOW), NOW, size=10, explore=2, video=3)
    assert len(none) == 10 and not any(c.candidate.is_video for c in none)
