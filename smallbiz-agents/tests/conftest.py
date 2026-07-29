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


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch):
    """Keep tests hermetic: no LLM key, no SMTP/IMAP/Twilio configured, so
    every agent exercises its deterministic fallback path."""
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "SMTP_HOST", "")
    monkeypatch.setattr(config, "IMAP_HOST", "")
    monkeypatch.setattr(config, "TWILIO_ACCOUNT_SID", "")
    yield
