from fastapi.testclient import TestClient

from backend.main import app


def test_health():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["auth_misconfigured"] is False
        assert body["imap_last_poll"] is None


def test_health_flags_partial_auth_config():
    from backend import config

    original_user, original_pass = config.APP_USERNAME, config.APP_PASSWORD
    config.APP_USERNAME = "owner"
    config.APP_PASSWORD = ""
    try:
        with TestClient(app) as client:
            body = client.get("/api/health").json()
            assert body["auth_misconfigured"] is True
            assert body["auth_enabled"] is False
    finally:
        config.APP_USERNAME, config.APP_PASSWORD = original_user, original_pass


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


def test_inbound_email_requires_secret_once_configured():
    from backend import config

    with TestClient(app) as client:
        original = config.INBOUND_EMAIL_SECRET
        config.INBOUND_EMAIL_SECRET = "topsecret"
        try:
            no_header = client.post(
                "/api/emails/inbound",
                json={"from_address": "attacker@example.com", "subject": "hi", "body": "hi"},
            )
            assert no_header.status_code == 403

            wrong_header = client.post(
                "/api/emails/inbound",
                json={"from_address": "attacker@example.com", "subject": "hi", "body": "hi"},
                headers={"X-Inbound-Secret": "wrong"},
            )
            assert wrong_header.status_code == 403

            right_header = client.post(
                "/api/emails/inbound",
                json={"from_address": "real@example.com", "subject": "hi", "body": "hi"},
                headers={"X-Inbound-Secret": "topsecret"},
            )
            assert right_header.status_code == 200
        finally:
            config.INBOUND_EMAIL_SECRET = original


def test_email_simulate_endpoint_ignores_inbound_secret():
    from backend import config

    with TestClient(app) as client:
        original = config.INBOUND_EMAIL_SECRET
        config.INBOUND_EMAIL_SECRET = "topsecret"
        try:
            resp = client.post(
                "/api/emails/simulate",
                json={"from_address": "owner-testing@example.com", "subject": "hi", "body": "hi"},
            )
            assert resp.status_code == 200
        finally:
            config.INBOUND_EMAIL_SECRET = original


def test_inbound_email_dedup_by_thread_id():
    with TestClient(app) as client:
        first = client.post(
            "/api/emails/inbound",
            json={
                "from_address": "dup@example.com",
                "subject": "Hi",
                "body": "hello",
                "thread_id": "msg-123",
            },
        )
        second = client.post(
            "/api/emails/inbound",
            json={
                "from_address": "dup@example.com",
                "subject": "Hi again",
                "body": "hello again",
                "thread_id": "msg-123",
            },
        )
        assert first.json()["id"] == second.json()["id"]

        emails = client.get("/api/emails").json()["emails"]
        assert sum(1 for e in emails if e["thread_id"] == "msg-123") == 1


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


def test_call_recording_proxy(monkeypatch):
    from backend import calls_repo, config

    with TestClient(app) as client:
        client.post("/api/phone/voice", data={"CallSid": "CAREC1", "From": "+15551112222"})
        client.post(
            "/api/phone/recording",
            data={"CallSid": "CAREC1", "RecordingUrl": "https://api.twilio.com/rec1"},
        )
        call = calls_repo.get_call("CAREC1")

        # No recording yet on a call that never got one.
        client.post("/api/phone/voice", data={"CallSid": "CAREC2", "From": "+15551112223"})
        call_no_recording = calls_repo.get_call("CAREC2")
        assert client.get(f"/api/calls/{call_no_recording['id']}/recording").status_code == 404

        # Recording exists but Twilio isn't configured -- nothing to fetch with.
        assert client.get(f"/api/calls/{call['id']}/recording").status_code == 400

        monkeypatch.setattr(config, "TWILIO_ACCOUNT_SID", "ACxxx")
        monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "tok")
        monkeypatch.setattr(config, "TWILIO_FROM_NUMBER", "+15550000000")

        class FakeResponse:
            status_code = 200
            content = b"fake-audio-bytes"

        import backend.main as main_module

        monkeypatch.setattr(main_module.requests, "get", lambda *a, **k: FakeResponse())

        resp = client.get(f"/api/calls/{call['id']}/recording")
        assert resp.status_code == 200
        assert resp.content == b"fake-audio-bytes"
        assert resp.headers["content-type"] == "audio/mpeg"


def test_contacts_endpoint_aggregates_across_channels():
    with TestClient(app) as client:
        client.post(
            "/api/emails/inbound",
            json={"from_address": "Jane <jane@example.com>", "subject": "Hi", "body": "Question"},
        )
        client.post("/api/phone/voice", data={"CallSid": "CACONTACT1", "From": "+15557778888"})

        contacts = client.get("/api/contacts").json()["contacts"]
        identities = {c["identity"] for c in contacts}
        assert "jane@example.com" in identities
        assert "+15557778888" in identities

        jane = next(c for c in contacts if c["identity"] == "jane@example.com")
        assert jane["channels"] == ["email"]
        assert jane["interactions"] == 1
