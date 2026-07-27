import pytest

from backend import config, db, security


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "test.db")
    db.init_db()
    yield


@pytest.fixture(autouse=True)
def isolated_security(monkeypatch):
    monkeypatch.setattr(config, "APP_USERNAME", "")
    monkeypatch.setattr(config, "APP_PASSWORD", "")
    security._rate_buckets.clear()
    yield
