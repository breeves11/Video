from backend.niche_finder import discover_niches
from backend.niche_data import NICHE_CATEGORIES


def test_discover_niches_returns_ranked_list():
    total_candidates = sum(len(meta["keywords"]) for meta in NICHE_CATEGORIES.values())
    results = discover_niches(limit=total_candidates)

    assert len(results) == total_candidates
    scores = [r.opportunity_score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_discover_niches_respects_limit():
    results = discover_niches(limit=5)
    assert len(results) == 5


def test_niche_fields_are_sane():
    results = discover_niches(limit=3)
    for r in results:
        assert r.avg_views > 0
        assert r.rpm_usd > 0
        assert 0 <= r.opportunity_score <= 100
        assert r.projected_revenue_per_video_usd >= 0
        assert r.videos_needed_for_goal >= 1


def test_discovery_is_deterministic_without_live_api():
    first = discover_niches(limit=5)
    second = discover_niches(limit=5)
    assert [n.keyword for n in first] == [n.keyword for n in second]
    assert [n.avg_views for n in first] == [n.avg_views for n in second]
