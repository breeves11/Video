from backend import revenue
from backend.niche_finder import discover_niches
from backend.niches_repo import save_niches


def test_add_and_list_videos():
    revenue.add_video("My First Video", niche_keyword="ai coding assistant comparison", views=1000, estimated_revenue_usd=14.0)
    videos = revenue.list_videos()
    assert len(videos) == 1
    assert videos[0]["title"] == "My First Video"
    assert videos[0]["estimated_revenue_usd"] == 14.0


def test_progress_with_no_videos_is_zero():
    progress = revenue.get_progress(goal=5000)
    assert progress["current_revenue_usd"] == 0
    assert progress["percent_to_goal"] == 0
    assert progress["remaining_usd"] == 5000


def test_progress_accumulates_revenue_and_caps_percent():
    revenue.add_video("Video A", estimated_revenue_usd=2000)
    revenue.add_video("Video B", estimated_revenue_usd=4000)
    progress = revenue.get_progress(goal=5000)
    assert progress["current_revenue_usd"] == 6000
    assert progress["percent_to_goal"] == 100.0
    assert progress["remaining_usd"] == 0


def test_actual_revenue_overrides_estimated():
    revenue.add_video("Video C", estimated_revenue_usd=10.0, actual_revenue_usd=25.0)
    progress = revenue.get_progress(goal=5000)
    assert progress["current_revenue_usd"] == 25.0


def test_gap_closing_suggestions_use_top_niches():
    niches = discover_niches(limit=3)
    save_niches(niches)
    revenue.add_video("Video D", estimated_revenue_usd=100)
    progress = revenue.get_progress(goal=5000)
    assert len(progress["gap_closing_suggestions"]) == 3
    for s in progress["gap_closing_suggestions"]:
        assert s["additional_videos_needed_to_close_gap"] is None or s["additional_videos_needed_to_close_gap"] >= 1
