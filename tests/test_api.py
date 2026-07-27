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
