from datetime import datetime, timedelta, timezone

from hub_collect.rank import (
    Candidate,
    Signal,
    category_quotas,
    explore_picks,
    is_market_move,
    pick,
    recency,
    score_all,
    select,
    title_words,
)
from hub_collect.topics import TOPICS

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


def cand(id, vector, source="a", category="invest", hours=0, title=None):
    return Candidate(
        id, source, category, f"https://x.test/{id}", title or f"t{id}", "", NOW - timedelta(hours=hours), vector
    )


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


def test_pick_keeps_one_market_move_story_per_stock():
    # Measured 2026-10-23: one stock's rebound and next-day fall scored 0.70, under SAME_STORY.
    seeds = [Signal("주제: A", (1.0, 0.0))]
    cands = [
        cand(1, (1.0, 0.0), source="a", title="[특징주] 삼성전자, 장초반 4%대 반등 중…SK하이닉스도 5.6%↑"),
        cand(2, (0.7, 0.714), source="b", title="[특징주] 삼전·닉스, AI 투자 수익성 의혹 지속에 4∼5%대 하락(종합)"),
        cand(3, (0.0, 1.0), source="c", title="[특징주] 현대로템, 해외 수주 불확실성에 10%대 급락"),
    ]
    picked = pick(score_all(cands, seeds, NOW), size=3, per_source=3, per_category=0)
    assert [p.candidate.id for p in picked] == [1, 3]


def test_ordinary_stories_as_close_as_a_market_move_pair_are_both_kept():
    seeds = [Signal("주제: A", (1.0, 0.0))]
    cands = [
        cand(1, (1.0, 0.0), source="a", title="한은, 기준금리 동결"),
        cand(2, (0.7, 0.714), source="b", title="정부, 내년 예산안 국회 제출"),
    ]
    picked = pick(score_all(cands, seeds, NOW), size=2, per_source=3, per_category=0)
    assert [p.candidate.id for p in picked] == [1, 2]


def test_one_story_in_two_languages_counts_once():
    # Measured 2026-10-23: Korean and English reports of one event scored 0.67-0.75.
    seeds = [Signal("주제: A", (1.0, 0.0))]
    cands = [
        cand(1, (1.0, 0.0), source="zdnet_kr", title="유전자 변형 개, 미군의 차세대 비밀병기 될까"),
        cand(2, (0.72, 0.694), source="engadget", title="A startup called Warhound is genetically engineering dogs"),
        cand(3, (0.72, 0.694), source="etnews", title="SK하이퍼, 글로벌 투자 유치 착수"),
    ]
    picked = pick(score_all(cands, seeds, NOW), size=3, per_source=3, per_category=0)
    assert [p.candidate.id for p in picked] == [1, 3]


def test_stories_sharing_a_rare_name_count_once():
    # Measured 2026-10-24: two Korean reports of SK하이퍼's funding scored 0.68, under SAME_STORY.
    seeds = [Signal("주제: A", (1.0, 0.0))]
    cands = [
        cand(1, (1.0, 0.0), source="a", title="SK하이퍼, 국내에 463조 규모…초대형 AI 데이터센터 짓는다"),
        cand(2, (0.68, 0.733), source="b", title="SK하이퍼, 글로벌 투자 유치 착수…내년 첫 매출 목표"),
        cand(3, (0.68, 0.733), source="c", title="미국 전력 수요 급증 전망"),
    ]
    picked = pick(score_all(cands, seeds, NOW), size=3, per_source=3, per_category=0)
    assert [p.candidate.id for p in picked] == [1, 3]


def test_a_name_many_stories_mention_does_not_join_them():
    seeds = [Signal("주제: A", (1.0, 0.0, 0.0))]
    cands = [
        cand(1, (1.0, 0.0, 0.0), source="a", title="스타링크, 우크라이나 속도 제한 해제"),
        cand(2, (0.68, 0.733, 0.0), source="b", title="스타링크 대체재 찾는 유럽"),
    ] + [cand(10 + i, (0.0, 0.0, 1.0), source=f"s{i}", title=f"스타링크 소식 {i}") for i in range(4)]
    picked = pick(score_all(cands, seeds, NOW), size=2, per_source=3, per_category=0)
    assert [p.candidate.id for p in picked] == [1, 2]


def test_title_words_keep_names_and_drop_particles_numbers_and_short_words():
    assert title_words("SK하이퍼가 463조 규모 AI 데이터센터를 짓는다") == {"sk하이퍼", "데이터센터", "짓는다"}
    assert title_words("Moderna shares plunge on leak") == {"moderna", "shares", "plunge", "leak"}
    assert "10월" not in title_words("2026년 10월 22일자 지표")


def test_is_market_move_spots_price_move_headlines():
    assert is_market_move("[특징주] 엘리스그룹, 코스닥 상장 첫날 29% 급락")
    assert is_market_move("삼성전자, 낙폭 키워 3% 하락 마감…SK하이닉스도 4.2%↓(종합)")
    assert not is_market_move("삼성바이오 3분기 영업이익 6천401억원")
    assert not is_market_move("서울 아파트 실거래가 1년 새 15.5% 상승")


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


def test_explore_takes_one_story_per_cluster_of_coverage():
    # Measured 2026-10-24: two Starlink stories 0.72 apart were both explorations; COVERED (0.7) treats them as one.
    seeds = [Signal("주제: A", (1.0,) + (0.0,) * 9)]
    near = [cand(i, (1.0,) + (0.0,) * 9, source=f"n{i}") for i in range(1, 7)]
    close = (0.1, 0.0, 0.0, 0.72, 0.694) + (0.0,) * 5
    far = [_far(10, 3, "x"), cand(11, close, source="y", hours=1), _far(13, 5, "w")]
    scored = score_all(near + far, seeds, NOW)
    extra = explore_picks(scored, [s for s in scored if s.candidate.id < 10], 2, NOW, per_category=2)
    assert len({e.candidate.id for e in extra} & {10, 11}) == 1
    assert 13 in {e.candidate.id for e in extra}


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


def test_category_quotas_follow_the_shares_and_always_sum_to_the_size():
    assert category_quotas(12) == {"tech": 5, "invest": 4, "realestate": 3}
    assert category_quotas(6) == {"tech": 3, "invest": 2, "realestate": 1}
    for size in range(0, 30):
        assert sum(category_quotas(size).values()) == size
    assert category_quotas(13)["tech"] == 6  # the largest remainder goes to the heaviest share


def _mixed():
    """Real estate scores far above tech, like the owner's votes made it: one axis per story, none a duplicate."""
    seeds = [Signal("주제: A", (1.0,) + (0.0,) * 29)]

    def story(topic, strength, category, source):
        vector = [0.0] * 30
        vector[0], vector[topic] = strength, 1.0
        return cand(100 * (topic + 1), tuple(vector), source=source, category=category)

    realestate = [story(1 + i, 1.5, "realestate", f"r{i}") for i in range(8)]
    invest = [story(10 + i, 1.0, "invest", f"i{i}") for i in range(8)]
    tech = [story(20 + i, 0.2, "tech", f"t{i}") for i in range(8)]
    return seeds, realestate + invest + tech


def test_quota_gives_tech_its_slots_although_real_estate_scores_higher():
    seeds, cands = _mixed()
    scored = score_all(cands, seeds, NOW)
    picked = pick(scored, size=12, per_source=2, quota=category_quotas(12))
    mix = {c: sum(p.candidate.category == c for p in picked) for c in ("tech", "invest", "realestate")}
    assert mix == {"tech": 5, "invest": 4, "realestate": 3}
    by_score = pick(scored, size=12, per_source=2, per_category=0)  # without quotas real estate fills the list
    assert sum(p.candidate.category == "realestate" for p in by_score) > 3


def test_a_category_that_cannot_fill_its_quota_hands_the_slots_to_the_rest():
    seeds, cands = _mixed()
    no_tech = [c for c in cands if c.category != "tech"]
    picked = pick(score_all(no_tech, seeds, NOW), size=12, per_source=2, quota=category_quotas(12))
    assert len(picked) == 12 and not any(p.candidate.category == "tech" for p in picked)


def test_explorations_skip_real_estate_and_select_applies_the_mix():
    seeds, cands = _mixed()
    chosen = select(score_all(cands, seeds, NOW), NOW, size=20, explore=5, video=0)
    usual = [c for c in chosen if not c.explore]
    assert {c: sum(u.candidate.category == c for u in usual) for c in ("tech", "invest", "realestate")} == {"tech": 6, "invest": 5, "realestate": 4}
    explored = [c for c in chosen if c.explore]
    assert explored and all(c.candidate.category != "realestate" for c in explored)
