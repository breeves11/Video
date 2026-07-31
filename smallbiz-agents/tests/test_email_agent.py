from backend import email_agent, emails_repo, knowledge_base, settings_repo


def test_process_inbound_faq_auto_sends_by_default():
    knowledge_base.add_entry("What are your hours?", "We're open Mon-Fri 9am-5pm.")
    row = email_agent.process_inbound_email(
        "Jane Doe <jane@example.com>", "Hours?", "What time do you open?"
    )
    assert row["category"] == "faq"
    assert row["ai_draft"]
    # SMTP isn't configured in tests, so auto-send attempts but can't
    # actually deliver -- status reflects that rather than silently
    # pretending it sent.
    assert row["status"] == "queued_send_unconfigured"


def test_process_inbound_complaint_stays_pending():
    row = email_agent.process_inbound_email(
        "angry@example.com", "Refund", "This is unacceptable, I want a refund now."
    )
    assert row["category"] == "complaint"
    assert row["status"] == "pending"


def test_approve_and_send_with_override_text():
    row = email_agent.process_inbound_email("someone@example.com", "Quote", "How much for a quote?")
    assert row["status"] == "pending"

    updated = email_agent.approve_and_send(row["id"], override_text="Custom reply text")
    assert updated["ai_draft"] == "Custom reply text"
    assert updated["status"] == "queued_send_unconfigured"


def test_dismiss_and_delete_email():
    row = email_agent.process_inbound_email("someone@example.com", "Hi", "Just saying hello")
    assert emails_repo.update_status(row["id"], "dismissed")
    assert emails_repo.get_email(row["id"])["status"] == "dismissed"
    assert emails_repo.delete_email(row["id"])
    assert emails_repo.get_email(row["id"]) is None


def test_auto_send_toggle_off_keeps_faq_pending():
    settings_repo.set("auto_send", {**settings_repo.DEFAULTS["auto_send"], "faq": False})
    row = email_agent.process_inbound_email("someone@example.com", "Hours?", "What are your hours?")
    assert row["category"] == "faq"
    assert row["status"] == "pending"


def test_draft_uses_knowledge_base_when_available():
    knowledge_base.add_entry("Do you ship internationally?", "Yes, worldwide shipping is available.")
    draft = email_agent.draft_reply("Shipping", "Do you ship internationally?", "faq")
    assert "worldwide shipping" in draft.text.lower()
    assert draft.source == "template"


def test_send_email_distinguishes_failed_from_unconfigured(monkeypatch):
    from backend import config

    assert email_agent.send_email("someone@example.com", "Subject", "Body") == "unconfigured"

    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_USERNAME", "user")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "pass")

    class ExplodingSMTP:
        def __init__(self, *args, **kwargs):
            raise OSError("connection refused")

    monkeypatch.setattr(email_agent.smtplib, "SMTP", ExplodingSMTP)
    assert email_agent.send_email("someone@example.com", "Subject", "Body") == "failed"


def test_approve_and_send_maps_failed_status(monkeypatch):
    from backend import config

    row = email_agent.process_inbound_email("someone@example.com", "Hi", "How much does it cost?")

    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_USERNAME", "user")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "pass")

    class ExplodingSMTP:
        def __init__(self, *args, **kwargs):
            raise OSError("connection refused")

    monkeypatch.setattr(email_agent.smtplib, "SMTP", ExplodingSMTP)
    updated = email_agent.approve_and_send(row["id"])
    assert updated["status"] == "send_failed"


def test_process_inbound_email_dedups_by_thread_id():
    first = email_agent.process_inbound_email(
        "dup@example.com", "Hi", "hello", thread_id="msg-abc"
    )
    second = email_agent.process_inbound_email(
        "dup@example.com", "Hi again", "different body", thread_id="msg-abc"
    )
    assert first["id"] == second["id"]
    assert len(emails_repo.list_emails(limit=50)) == 1
