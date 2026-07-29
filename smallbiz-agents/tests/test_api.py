from fastapi.testclient import TestClient

from backend.main import app


def test_health():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_kb_crud_flow():
    with TestClient(app) as client:
        create = client.post(
            "/api/kb", json={"question": "Do you deliver?", "answer": "Yes, locally.", "category": "faq"}
        )
        assert create.status_code == 200
        entry_id = create.json()["id"]

        listing = client.get("/api/kb").json()["entries"]
        assert any(e["id"] == entry_id for e in listing)

        edit = client.put(f"/api/kb/{entry_id}", json={"answer": "Yes, within 10 miles."})
        assert edit.status_code == 200

        delete = client.delete(f"/api/kb/{entry_id}")
        assert delete.status_code == 200
        assert client.delete(f"/api/kb/{entry_id}").status_code == 404


def test_inbound_email_flow_and_send():
    with TestClient(app) as client:
        client.post("/api/kb", json={"question": "hours", "answer": "9-5 Mon-Fri", "category": "faq"})
        inbound = client.post(
            "/api/emails/inbound",
            json={"from_address": "test@example.com", "subject": "Hours", "body": "What are your hours?"},
        )
        assert inbound.status_code == 200
        email_id = inbound.json()["id"]

        emails = client.get("/api/emails").json()["emails"]
        assert any(e["id"] == email_id for e in emails)

        send = client.post(f"/api/emails/{email_id}/send", json={})
        assert send.status_code == 200
        assert send.json()["status"] in ("sent", "queued_send_unconfigured")


def test_dismiss_and_delete_email_endpoints():
    with TestClient(app) as client:
        inbound = client.post(
            "/api/emails/inbound",
            json={"from_address": "someone@example.com", "subject": "Hi", "body": "Random complaint, refund"},
        )
        email_id = inbound.json()["id"]

        dismiss = client.post(f"/api/emails/{email_id}/dismiss")
        assert dismiss.status_code == 200
        assert dismiss.json()["status"] == "dismissed"

        delete = client.delete(f"/api/emails/{email_id}")
        assert delete.status_code == 200
        assert client.get(f"/api/emails/{email_id}").status_code == 404


def test_settings_update_roundtrip():
    with TestClient(app) as client:
        resp = client.put("/api/settings", json={"business_name": "Acme Plumbing"})
        assert resp.status_code == 200
        assert resp.json()["business_name"] == "Acme Plumbing"

        fetched = client.get("/api/settings").json()
        assert fetched["business_name"] == "Acme Plumbing"


def test_phone_voice_and_gather_webhooks_return_twiml():
    with TestClient(app) as client:
        voice_resp = client.post(
            "/api/phone/voice", data={"CallSid": "CATEST1", "From": "+15551230000"}
        )
        assert voice_resp.status_code == 200
        assert "<Response>" in voice_resp.text

        gather_resp = client.post(
            "/api/phone/gather", data={"CallSid": "CATEST1", "SpeechResult": "What are your hours?"}
        )
        assert gather_resp.status_code == 200
        assert "<Response>" in gather_resp.text

        calls = client.get("/api/calls").json()["calls"]
        assert any(c["call_sid"] == "CATEST1" for c in calls)


def test_phone_status_webhook_logs_missed_call():
    with TestClient(app) as client:
        resp = client.post(
            "/api/phone/status",
            data={"CallSid": "CATEST2", "From": "+15559998888", "CallStatus": "no-answer"},
        )
        assert resp.status_code == 200
        calls = client.get("/api/calls").json()["calls"]
        missed = next(c for c in calls if c["call_sid"] == "CATEST2")
        assert missed["status"] == "missed"
        assert missed["callback_requested"] == 1


def test_missing_email_returns_404():
    with TestClient(app) as client:
        assert client.get("/api/emails/9999").status_code == 404
        assert client.post("/api/emails/9999/send", json={}).status_code == 404
