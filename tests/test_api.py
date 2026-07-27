from fastapi.testclient import TestClient

from backend.main import app


def test_health():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_niches_endpoint_returns_ranked_list():
    with TestClient(app) as client:
        resp = client.get("/api/niches")
        assert resp.status_code == 200
        niches = resp.json()["niches"]
        assert len(niches) > 0
        assert niches[0]["opportunity_score"] >= niches[-1]["opportunity_score"]


def test_content_generation_endpoint():
    with TestClient(app) as client:
        resp = client.post(
            "/api/content/generate",
            json={"niche_keyword": "budget travel hacks 2026", "category": "budget_travel"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "template"
        assert len(data["titles"]) == 5


def test_video_and_progress_flow():
    with TestClient(app) as client:
        resp = client.post(
            "/api/videos",
            json={"title": "Test Vid", "views": 500, "estimated_revenue_usd": 12.5},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] is not None

        progress_resp = client.get("/api/progress")
        assert progress_resp.status_code == 200
        assert progress_resp.json()["current_revenue_usd"] >= 12.5


def test_video_without_published_at_defaults_to_today_and_counts():
    with TestClient(app) as client:
        client.post("/api/videos", json={"title": "No date given", "estimated_revenue_usd": 50})
        videos = client.get("/api/videos").json()["videos"]
        assert videos[0]["published_at"] is not None

        progress = client.get("/api/progress").json()
        assert progress["current_revenue_usd"] == 50


def test_video_from_a_previous_month_excluded_from_current_progress():
    with TestClient(app) as client:
        client.post(
            "/api/videos",
            json={"title": "Old video", "published_at": "2020-01-15", "estimated_revenue_usd": 999},
        )
        progress = client.get("/api/progress").json()
        assert progress["current_revenue_usd"] == 0
        assert progress["videos_counted"] == 0


def test_negative_values_rejected():
    with TestClient(app) as client:
        resp = client.post("/api/videos", json={"title": "Bad video", "views": -5})
        assert resp.status_code == 422

        resp2 = client.post("/api/videos", json={"title": "Bad video", "estimated_revenue_usd": -1})
        assert resp2.status_code == 422


def test_delete_video():
    with TestClient(app) as client:
        create_resp = client.post("/api/videos", json={"title": "Deletable", "estimated_revenue_usd": 5})
        video_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/videos/{video_id}")
        assert del_resp.status_code == 200

        missing_resp = client.delete(f"/api/videos/{video_id}")
        assert missing_resp.status_code == 404

        videos = client.get("/api/videos").json()["videos"]
        assert all(v["id"] != video_id for v in videos)


def test_get_and_delete_content():
    with TestClient(app) as client:
        gen_resp = client.post(
            "/api/content/generate",
            json={"niche_keyword": "zero waste kitchen swaps", "category": "sustainable_living"},
        )
        content_id = gen_resp.json()["id"]

        list_resp = client.get("/api/content")
        assert list_resp.status_code == 200
        assert any(c["id"] == content_id for c in list_resp.json()["content"])

        del_resp = client.delete(f"/api/content/{content_id}")
        assert del_resp.status_code == 200

        missing_resp = client.delete(f"/api/content/{content_id}")
        assert missing_resp.status_code == 404


def test_niches_endpoint_respects_videos_per_month_override():
    with TestClient(app) as client:
        default_resp = client.get("/api/niches?limit=1&videos_per_month=8")
        override_resp = client.get("/api/niches?limit=1&videos_per_month=20")

        default_niche = default_resp.json()["niches"][0]
        override_niche = override_resp.json()["niches"][0]

        assert override_niche["assumed_videos_per_month"] == 20
        assert override_niche["projected_monthly_revenue_usd"] == round(
            override_niche["projected_revenue_per_video_usd"] * 20, 2
        )
        assert override_niche["projected_monthly_revenue_usd"] > default_niche["projected_monthly_revenue_usd"]
