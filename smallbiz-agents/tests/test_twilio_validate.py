from fastapi.testclient import TestClient

from backend import config
from backend.main import app
from backend.twilio_validate import compute_signature


def test_compute_signature_is_deterministic_and_order_independent():
    auth_token = "12345"
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    params = {
        "CallSid": "CA1234567890ABCDE",
        "Caller": "+14158675310",
        "Digits": "1234",
        "From": "+14158675310",
        "To": "+18005551212",
    }
    signature = compute_signature(auth_token, url, params)
    # Same params in a different insertion order must produce the same
    # signature (Twilio sorts by key before signing).
    reordered = dict(reversed(list(params.items())))
    assert compute_signature(auth_token, url, reordered) == signature
    # A different auth token must not produce the same signature.
    assert compute_signature("different-token", url, params) != signature
    # A tampered param must not produce the same signature.
    tampered = {**params, "Digits": "9999"}
    assert compute_signature(auth_token, url, tampered) != signature


def test_phone_webhook_open_when_twilio_not_configured():
    with TestClient(app) as client:
        resp = client.post("/api/phone/voice", data={"CallSid": "CA1", "From": "+15551234567"})
        assert resp.status_code == 200
        assert "<Response>" in resp.text


def test_phone_webhook_rejects_missing_signature_once_configured(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-token")
    with TestClient(app) as client:
        resp = client.post("/api/phone/voice", data={"CallSid": "CA1", "From": "+15551234567"})
        assert resp.status_code == 403


def test_phone_webhook_accepts_valid_signature(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://example.com")
    params = {"CallSid": "CA1", "From": "+15551234567"}
    signature = compute_signature("test-token", "https://example.com/api/phone/voice", params)

    with TestClient(app) as client:
        resp = client.post(
            "/api/phone/voice", data=params, headers={"X-Twilio-Signature": signature}
        )
        assert resp.status_code == 200
        assert "<Response>" in resp.text


def test_phone_webhook_rejects_tampered_params(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://example.com")
    signature = compute_signature(
        "test-token", "https://example.com/api/phone/voice", {"CallSid": "CA1", "From": "+15551234567"}
    )

    with TestClient(app) as client:
        # Same signature, different From -- as if someone replayed/edited a
        # captured request.
        resp = client.post(
            "/api/phone/voice",
            data={"CallSid": "CA1", "From": "+19998887777"},
            headers={"X-Twilio-Signature": signature},
        )
        assert resp.status_code == 403


def test_phone_simulate_endpoints_bypass_signature_even_when_twilio_configured(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-token")
    with TestClient(app) as client:
        resp = client.post(
            "/api/phone/simulate/voice", data={"CallSid": "SIM1", "From": "+15550001111"}
        )
        assert resp.status_code == 200
        assert "<Response>" in resp.text
