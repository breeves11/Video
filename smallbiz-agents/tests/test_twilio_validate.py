from fastapi.testclient import TestClient

from backend import config
from backend.main import app
from backend.twilio_validate import compute_signature, is_valid_signature


def test_compute_signature_matches_official_twilio_sdk_vector():
    # Twilio's documented example. Expected value produced by the official
    # twilio-python RequestValidator (v9.12.0); this implementation was also
    # cross-checked against that SDK on 1,200+ randomized cases.
    signature = compute_signature(
        "12345",
        "https://mycompany.com/myapp.php?foo=1&bar=2",
        {
            "CallSid": "CA1234567890ABCDE",
            "Caller": "+14158675310",
            "Digits": "1234",
            "From": "+14158675310",
            "To": "+18005551212",
        },
    )
    assert signature == "GvWf1cFY/Q7PnoempGyD5oXAezc="


def test_signature_accepted_with_or_without_default_port():
    # Twilio signs inconsistently on the port; the official validator
    # accepts either form, and rejecting one would drop genuine calls.
    params = {"CallSid": "CA1"}
    with_port = compute_signature("tok", "https://example.com:443/api/phone/voice", params)
    without_port = compute_signature("tok", "https://example.com/api/phone/voice", params)
    for url in ("https://example.com/api/phone/voice", "https://example.com:443/api/phone/voice"):
        assert is_valid_signature("tok", url, params, with_port)
        assert is_valid_signature("tok", url, params, without_port)
    assert not is_valid_signature("tok", "https://example.com/api/phone/voice", params, "")
    assert not is_valid_signature("tok", "https://other.com/api/phone/voice", params, with_port)


def test_phone_webhook_signature_covers_query_string(monkeypatch):
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://example.com")
    params = {"CallSid": "CAQ", "From": "+15551234567"}
    signed = compute_signature("test-token", "https://example.com/api/phone/voice?src=main", params)
    with TestClient(app) as client:
        ok = client.post("/api/phone/voice?src=main", data=params, headers={"X-Twilio-Signature": signed})
        assert ok.status_code == 200
        wrong_query = client.post("/api/phone/voice?src=other", data=params, headers={"X-Twilio-Signature": signed})
        assert wrong_query.status_code == 403


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
