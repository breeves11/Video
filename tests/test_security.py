import base64

from fastapi.testclient import TestClient

from backend import config
from backend.main import app


def _basic_auth_header(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_no_auth_required_when_unconfigured():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200


def test_auth_required_when_configured(monkeypatch):
    monkeypatch.setattr(config, "APP_USERNAME", "admin")
    monkeypatch.setattr(config, "APP_PASSWORD", "secret")

    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers

        wrong = client.get("/api/health", headers=_basic_auth_header("admin", "wrong"))
        assert wrong.status_code == 401

        right = client.get("/api/health", headers=_basic_auth_header("admin", "secret"))
        assert right.status_code == 200


def test_rate_limit_blocks_after_threshold(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_MINUTE", 2)

    with TestClient(app) as client:
        payload = {"niche_keyword": "budget travel hacks 2026", "category": "budget_travel"}
        first = client.post("/api/content/generate", json=payload)
        second = client.post("/api/content/generate", json=payload)
        third = client.post("/api/content/generate", json=payload)

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
