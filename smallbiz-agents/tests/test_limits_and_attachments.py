import email
import sqlite3
from email.message import EmailMessage

from fastapi.testclient import TestClient

from backend import config, db, email_agent, emails_repo, imap_client
from backend.limits import MAX_STORED_BODY_CHARS, MAX_SUBJECT_CHARS, clip
from backend.main import app


def test_clip_leaves_short_text_alone_and_marks_truncation():
    assert clip("hello", 10) == "hello"
    clipped = clip("x" * 100, 40)
    assert len(clipped) == 40
    assert clipped.endswith("[... truncated]")


def test_long_email_is_trimmed_not_rejected():
    row = email_agent.process_inbound_email(
        "long@example.com", "S" * 5_000, "B" * (MAX_STORED_BODY_CHARS * 3)
    )
    assert len(row["subject"]) == MAX_SUBJECT_CHARS
    assert len(row["body"]) == MAX_STORED_BODY_CHARS
    assert row["body"].endswith("[... truncated]")


def test_api_rejects_absurd_payloads():
    with TestClient(app) as client:
        too_big = client.post(
            "/api/emails/simulate",
            json={"from_address": "a@example.com", "body": "x" * 500_001},
        )
        assert too_big.status_code == 422

        bad_kb = client.post("/api/kb", json={"question": "q" * 1_001, "answer": "a"})
        assert bad_kb.status_code == 422

        bad_toggle = client.put("/api/settings", json={"auto_send": {"faq": "yes please"}})
        assert bad_toggle.status_code == 422


def test_email_with_attachments_is_never_auto_sent():
    # FAQ is auto-send by default -- the attachment must override that.
    row = email_agent.process_inbound_email(
        "pics@example.com", "Hours?", "What are your hours?", attachments=["damage.jpg"]
    )
    assert row["category"] == "faq"
    assert row["status"] == "pending"
    assert row["attachments"] == ["damage.jpg"]


def test_webhook_accepts_attachment_names():
    with TestClient(app) as client:
        resp = client.post(
            "/api/emails/inbound",
            json={"from_address": "a@example.com", "subject": "Quote", "body": "See attached",
                  "attachments": ["plans.pdf", "site.jpg"]},
        )
        assert resp.status_code == 200
        assert resp.json()["attachments"] == ["plans.pdf", "site.jpg"]
        listed = client.get("/api/emails").json()["emails"][0]
        assert listed["attachments"] == ["plans.pdf", "site.jpg"]


def test_email_without_attachments_reports_empty_list():
    row = email_agent.process_inbound_email("a@example.com", "Hi", "Hello")
    assert row["attachments"] == []


def _multipart(plain=None, html=None, attachment=None):
    msg = EmailMessage()
    msg["From"] = "Jane <jane@example.com>"
    msg["Subject"] = "Test"
    if plain is not None:
        msg.set_content(plain)
        if html is not None:
            msg.add_alternative(html, subtype="html")
    elif html is not None:
        msg.set_content(html, subtype="html")
    if attachment:
        msg.add_attachment(b"%PDF-1.4", maintype="application", subtype="pdf", filename=attachment)
    return email.message_from_bytes(msg.as_bytes())


def test_imap_prefers_plain_text():
    msg = _multipart(plain="Plain version", html="<p>HTML version</p>")
    assert imap_client.extract_body(msg).strip() == "Plain version"


def test_imap_falls_back_to_html_when_no_plain_part():
    html = (
        "<html><head><style>p{color:red}</style></head><body>"
        "<p>Hi there,</p><p>Do you open on <b>Saturdays</b>?</p>"
        "<script>track()</script></body></html>"
    )
    body = imap_client.extract_body(_multipart(html=html))
    assert "Do you open on Saturdays?" in body
    assert "color:red" not in body
    assert "track()" not in body
    assert "<p>" not in body


def test_imap_extracts_attachment_names_and_skips_them_as_body():
    msg = _multipart(plain="See the quote attached.", attachment="quote.pdf")
    assert imap_client.extract_attachments(msg) == ["quote.pdf"]
    assert "PDF" not in imap_client.extract_body(msg)


def test_init_db_adds_attachments_column_to_older_database(tmp_path, monkeypatch):
    old_db = tmp_path / "old.db"
    monkeypatch.setattr(config, "DATABASE_PATH", old_db)
    with sqlite3.connect(old_db) as conn:
        conn.execute(
            "CREATE TABLE emails (id INTEGER PRIMARY KEY AUTOINCREMENT, contact_email TEXT NOT NULL, "
            "contact_name TEXT, subject TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '', "
            "category TEXT NOT NULL DEFAULT 'other', urgency TEXT NOT NULL DEFAULT 'low', ai_draft TEXT, "
            "ai_source TEXT NOT NULL DEFAULT 'template', status TEXT NOT NULL DEFAULT 'pending', "
            "thread_id TEXT, created_at TEXT NOT NULL, sent_at TEXT)"
        )
        conn.execute(
            "INSERT INTO emails (contact_email, created_at) VALUES ('before@example.com', '2026-01-01')"
        )

    db.init_db()
    db.init_db()  # idempotent

    rows = emails_repo.list_emails()
    assert rows[0]["contact_email"] == "before@example.com"
    assert rows[0]["attachments"] == []
