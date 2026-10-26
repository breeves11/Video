from fastapi.testclient import TestClient

from backend import email_agent, phone_agent, settings_repo
from backend.main import app


def test_ai_disclosure_on_by_default_in_email_drafts():
    draft = email_agent.draft_reply("Hours?", "When are you open?", "faq")
    assert draft.text.endswith(email_agent.AI_DISCLOSURE_FOOTER)


def test_no_disclosure_on_spam_placeholder():
    draft = email_agent.draft_reply("WIN", "casino crypto", "spam")
    assert email_agent.AI_DISCLOSURE_FOOTER not in draft.text


def test_ai_disclosure_spoken_at_start_of_call():
    settings_repo.set("business_name", "Acme Plumbing")
    twiml = phone_agent.handle_incoming_call("CADISC1", "+15550001111", None)
    assert "automated assistant for Acme Plumbing" in twiml


def test_disclosure_can_be_switched_off():
    settings_repo.set("ai_disclosure", False)
    draft = email_agent.draft_reply("Hours?", "When are you open?", "faq")
    assert email_agent.AI_DISCLOSURE_FOOTER not in draft.text
    twiml = phone_agent.handle_incoming_call("CADISC2", "+15550001111", None)
    assert "automated assistant" not in twiml


def test_disclosure_toggle_via_settings_api():
    with TestClient(app) as client:
        assert client.get("/api/settings").json()["ai_disclosure"] is True
        resp = client.put("/api/settings", json={"ai_disclosure": False})
        assert resp.json()["ai_disclosure"] is False
