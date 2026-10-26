import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import backup_db  # noqa: E402
import preflight  # noqa: E402

from backend import config, knowledge_base  # noqa: E402


def _status(checks, name_fragment):
    return next(c.status for c in checks if name_fragment in c.name)


def test_preflight_fails_an_unconfigured_deployment():
    checks = preflight.config_checks()
    assert _status(checks, "Dashboard login") == preflight.FAIL
    assert preflight.main([]) == 1


def test_preflight_flags_half_set_auth(monkeypatch):
    monkeypatch.setattr(config, "APP_USERNAME", "owner")
    assert _status(preflight.config_checks(), "Dashboard login") == preflight.FAIL


def test_preflight_requires_inbound_secret_once_smtp_is_configured(monkeypatch):
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_USERNAME", "u")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "p")
    assert _status(preflight.config_checks(), "Inbound email webhook secret") == preflight.FAIL
    monkeypatch.setattr(config, "INBOUND_EMAIL_SECRET", "s3cret")
    assert _status(preflight.config_checks(), "Inbound email webhook secret") == preflight.PASS


def test_preflight_requires_https_public_url_with_twilio(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setattr(config, "TWILIO_FROM_NUMBER", "+15550000000")
    assert _status(preflight.config_checks(), "PUBLIC_BASE_URL") == preflight.FAIL
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "http://insecure.example.com")
    assert _status(preflight.config_checks(), "PUBLIC_BASE_URL") == preflight.FAIL
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://app.example.com")
    assert _status(preflight.config_checks(), "PUBLIC_BASE_URL") == preflight.PASS


def test_preflight_passes_a_fully_configured_deployment(monkeypatch):
    for key, value in {
        "APP_USERNAME": "owner", "APP_PASSWORD": "a-long-password-123",
        "INBOUND_EMAIL_SECRET": "s3cret",
        "SMTP_HOST": "smtp.example.com", "SMTP_USERNAME": "u", "SMTP_PASSWORD": "p",
        "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_AUTH_TOKEN": "tok", "TWILIO_FROM_NUMBER": "+15550000000",
        "PUBLIC_BASE_URL": "https://app.example.com",
    }.items():
        monkeypatch.setattr(config, key, value)
    for i in range(5):
        knowledge_base.add_entry(f"Question {i}?", f"Answer {i}.")

    checks = preflight.config_checks()
    assert not [c for c in checks if c.status == preflight.FAIL]
    assert preflight.main([]) == 0


def test_backup_creates_consistent_snapshot_and_prunes(tmp_path):
    knowledge_base.add_entry("Do you deliver?", "Yes.")
    dest = tmp_path / "backups"
    for i in range(4):
        # Distinct names without sleeping: pre-create older snapshots.
        (dest).mkdir(exist_ok=True)
        (dest / f"app-2020010{i}-000000.db").write_bytes(b"")

    target = backup_db.backup(dest, keep=2)

    snapshots = sorted(p.name for p in dest.glob("app-*.db"))
    assert len(snapshots) == 2
    assert target.name in snapshots
    with sqlite3.connect(target) as conn:
        rows = conn.execute("SELECT question FROM kb_entries").fetchall()
    assert rows == [("Do you deliver?",)]


def test_backup_reports_missing_database(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "nope.db")
    assert backup_db.main(["--dest", str(tmp_path / "b")]) == 1
