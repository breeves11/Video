from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend import calls_repo, config, db, email_agent, phone_agent, reports, settings_repo
from backend.main import app

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)  # a Monday


def _ago(**kwargs) -> str:
    return (NOW - timedelta(**kwargs)).isoformat()


def _email(created, status="pending", sent=None, auto=0, category="faq"):
    with db.session() as conn:
        conn.execute(
            "INSERT INTO emails (contact_email, subject, body, category, urgency, ai_source, status, "
            "auto_sent, created_at, sent_at) VALUES ('c@example.com', 's', 'b', ?, 'low', 'template', ?, ?, ?, ?)",
            (category, status, auto, created, sent),
        )


def _call(created, status="completed", callback=0, handled=0, handled_at=None, textback=0, recording=None):
    with db.session() as conn:
        conn.execute(
            "INSERT INTO calls (call_sid, from_number, status, callback_requested, handled, handled_at, "
            "textback_sent, recording_url, created_at, updated_at) VALUES (?, '+15550000000', ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"CA{created}", status, callback, handled, handled_at, textback, recording, created, created),
        )


def test_email_metrics_cohort_reply_times_and_auto_split():
    _email(_ago(days=1), "sent", sent=_ago(days=1, minutes=-10), auto=1)       # 10 min, auto
    _email(_ago(days=2), "sent", sent=_ago(days=2, minutes=-30))               # 30 min, owner
    _email(_ago(days=3), "sent", sent=_ago(days=3, minutes=-180))              # 3 h, owner
    _email(_ago(days=4), "pending")
    _email(_ago(days=5), "pending", category="spam")
    _email(_ago(days=6), "dismissed")
    _email(_ago(days=10), "sent", sent=_ago(days=10, minutes=-5))              # previous period

    report = reports.build_report(days=7, now=NOW)
    emails = report["current"]["emails"]
    assert emails["received"] == 6
    assert emails["replied"] == 3
    assert emails["auto_replied"] == 1
    assert emails["owner_replied"] == 2
    assert emails["dismissed"] == 1
    assert emails["spam"] == 1
    assert emails["median_reply_minutes"] == 30.0
    assert emails["replied_within_hour_pct"] == 67
    assert report["previous"]["emails"]["received"] == 1

    # Waiting-now excludes spam and is not period-bound.
    assert report["open"]["emails_waiting"] == 1
    assert report["open"]["oldest_email_waiting_minutes"] == 4 * 24 * 60


def test_call_metrics_missed_followup_and_callback_time():
    _call(_ago(days=1), "completed", handled=1, handled_at=_ago(days=1))                      # resolved by AI
    _call(_ago(days=2), "voicemail", callback=1, handled=1, handled_at=_ago(days=2, minutes=-40),
          recording="https://r/1")                                                             # called back in 40 min
    _call(_ago(days=2, hours=1), "needs_callback", callback=1)                                 # still waiting
    _call(_ago(days=3), "missed", callback=1, textback=1)                                      # texted back
    _call(_ago(days=4), "missed", callback=1, handled=1, handled_at=_ago(days=4, minutes=-90)) # called back, no text
    _call(_ago(days=5), "missed", callback=1)                                                  # not followed up

    calls = reports.build_report(days=7, now=NOW)["current"]["calls"]
    assert calls["total"] == 6
    assert calls["answered_by_ai"] == 3
    assert calls["resolved_on_call"] == 1
    assert calls["voicemails"] == 1
    assert calls["callbacks_needed"] == 5
    assert calls["callbacks_done"] == 2
    assert calls["median_callback_minutes"] == 65.0
    assert calls["missed"] == 3
    assert calls["missed_texted_back"] == 1
    assert calls["missed_followed_up"] == 2


def test_weekly_series_and_baseline_normalisation():
    _email(_ago(days=1))
    _email(_ago(days=8))
    _email(_ago(days=8))
    _call(_ago(days=1), "missed", callback=1)
    settings_repo.set("baseline_missed_calls_per_week", 14)
    settings_repo.set("baseline_email_reply_hours", 6)

    report = reports.build_report(days=7, weeks=3, now=NOW)
    assert [w["emails"] for w in report["weekly"]] == [0, 2, 1]   # oldest -> newest
    assert [w["calls"] for w in report["weekly"]] == [0, 0, 1]
    assert report["baseline"]["missed_calls_per_week"] == 14
    assert report["baseline"]["missed_calls_per_week_now"] == 1

    thirty = reports.build_report(days=30, now=NOW)
    assert thirty["baseline"]["missed_calls_per_week_now"] == round(1 * 7 / 30, 1)


def test_empty_report_is_well_formed():
    report = reports.build_report(now=NOW)
    assert report["current"]["emails"]["median_reply_minutes"] is None
    assert report["current"]["emails"]["replied_within_hour_pct"] is None
    assert report["baseline"]["email_reply_hours_now"] is None
    subject, body = reports.render_email(report)
    assert "0 calls answered" in subject
    assert "No missed calls" in body
    assert "all caught up" in body


def test_agents_record_report_facts():
    # Auto-sent FAQ marks auto_sent only when the send actually succeeds.
    row = email_agent.process_inbound_email("a@example.com", "Hours?", "What are your hours?")
    assert row["auto_sent"] == 0  # SMTP unconfigured -> not actually sent

    phone_agent.handle_incoming_call("CAR1", "+15551112222", None)
    calls_repo.update_call("CAR1", callback_requested=1)
    call = calls_repo.get_call("CAR1")
    calls_repo.mark_handled(call["id"])
    first = calls_repo.get_call("CAR1")["handled_at"]
    assert first is not None
    calls_repo.mark_handled(call["id"])
    assert calls_repo.get_call("CAR1")["handled_at"] == first  # re-marking keeps the first time
    calls_repo.mark_handled(call["id"], handled=False)
    assert calls_repo.get_call("CAR1")["handled_at"] is None


def test_textback_recorded_when_sms_sends(monkeypatch):
    monkeypatch.setattr(phone_agent.twilio_sms, "send_sms", lambda to, body: True)
    phone_agent.handle_status_callback("CAMISS", "+15553334444", None, "no-answer")
    assert calls_repo.get_call("CAMISS")["textback_sent"] == 1


def test_render_email_includes_before_and_after():
    settings_repo.set("business_name", "Acme Plumbing")
    settings_repo.set("baseline_missed_calls_per_week", 14)
    settings_repo.set("baseline_email_reply_hours", 6)
    _email(_ago(days=1), "sent", sent=_ago(days=1, minutes=-12), auto=1)
    _call(_ago(days=1), "completed", handled=1, handled_at=_ago(days=1))

    subject, body = reports.render_email(reports.build_report(now=NOW))
    assert subject == "Acme Plumbing: 1 call answered, 1 email replied this week"
    assert "Missed calls per week: 14 before -> 0 now" in body
    assert "Email reply time: 6 h before -> 12 min now" in body


def test_render_email_dates_use_business_timezone():
    # 2026-10-26 03:00 UTC is still Oct 25 in Chicago.
    late_sunday = datetime(2026, 10, 26, 3, 0, tzinfo=timezone.utc)
    settings_repo.set("timezone", "America/Chicago")
    _, body = reports.render_email(reports.build_report(now=late_sunday))
    assert body.startswith("Your AI front desk, Oct 18 - Oct 25")


def test_humanize_minutes():
    assert reports.humanize_minutes(None) == "--"
    assert reports.humanize_minutes(12.4) == "12 min"
    assert reports.humanize_minutes(90) == "1.5 h"
    assert reports.humanize_minutes(360) == "6 h"
    assert reports.humanize_minutes(3 * 24 * 60) == "3 days"


# --- Weekly send schedule -----------------------------------------------------

def _enable_email(monkeypatch, sent_log):
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(config, "SMTP_USERNAME", "u")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "p")
    settings_repo.set("weekly_report_email", "owner@example.com")
    settings_repo.set("timezone", "America/Chicago")
    monkeypatch.setattr(reports, "send_report", lambda to: sent_log.append(to) or "sent")


def test_weekly_email_sends_once_after_monday_8am_local(monkeypatch):
    sent = []
    _enable_email(monkeypatch, sent)
    # Monday 2026-10-26: 12:59 UTC = 07:59 Chicago (CDT) -> too early.
    assert not reports.maybe_send_weekly(datetime(2026, 10, 26, 12, 59, tzinfo=timezone.utc))
    # 13:00 UTC = 08:00 Chicago -> send.
    assert reports.maybe_send_weekly(datetime(2026, 10, 26, 13, 0, tzinfo=timezone.utc))
    # Later the same week -> already sent.
    assert not reports.maybe_send_weekly(datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc))
    # Next Monday morning -> send again.
    assert reports.maybe_send_weekly(datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc))
    assert sent == ["owner@example.com", "owner@example.com"]


def test_weekly_email_catches_up_after_downtime_but_not_on_first_setup(monkeypatch):
    sent = []
    _enable_email(monkeypatch, sent)
    # Freshly configured on a Wednesday: wait for Monday, no surprise email.
    assert not reports.maybe_send_weekly(datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc))
    # Sent normally one Monday...
    assert reports.maybe_send_weekly(datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc))
    # ...app down all of the next Monday, back on Tuesday -> catch up.
    assert reports.maybe_send_weekly(datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc))
    assert len(sent) == 2


def test_weekly_email_not_marked_sent_when_send_fails(monkeypatch):
    sent = []
    _enable_email(monkeypatch, sent)
    monkeypatch.setattr(reports, "send_report", lambda to: "failed")
    monday = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)
    assert not reports.maybe_send_weekly(monday)
    monkeypatch.setattr(reports, "send_report", lambda to: "sent")
    assert reports.maybe_send_weekly(monday + timedelta(hours=1))  # retried next hour


def test_weekly_email_off_without_recipient_or_smtp(monkeypatch):
    monday = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)
    assert not reports.maybe_send_weekly(monday)  # nothing configured
    settings_repo.set("weekly_report_email", "owner@example.com")
    assert not reports.maybe_send_weekly(monday)  # no SMTP


# --- API --------------------------------------------------------------------

def test_report_api_and_settings_validation():
    with TestClient(app) as client:
        body = client.get("/api/report?days=30").json()
        assert body["period"]["days"] == 30
        assert len(body["weekly"]) == 8
        assert client.get("/api/report?days=0").status_code == 422

        ok = client.put("/api/settings", json={
            "timezone": "America/Chicago",
            "weekly_report_email": "owner@example.com",
            "baseline_missed_calls_per_week": 14,
            "baseline_email_reply_hours": 6,
        })
        assert ok.status_code == 200
        assert ok.json()["timezone"] == "America/Chicago"

        assert client.put("/api/settings", json={"timezone": "Mars/Olympus"}).status_code == 422
        assert client.put("/api/settings", json={"weekly_report_email": "not-an-email"}).status_code == 422
        assert client.put("/api/settings", json={"baseline_missed_calls_per_week": -1}).status_code == 422

        # Baselines can be cleared with an explicit null; other fields ignore nulls.
        cleared = client.put("/api/settings", json={"baseline_missed_calls_per_week": None,
                                                    "business_name": None}).json()
        assert cleared["baseline_missed_calls_per_week"] is None
        assert cleared["business_name"] != None  # noqa: E711


def test_send_report_endpoint(monkeypatch):
    with TestClient(app) as client:
        assert client.post("/api/report/send").status_code == 400  # no recipient
        client.put("/api/settings", json={"weekly_report_email": "owner@example.com"})
        resp = client.post("/api/report/send")
        assert resp.status_code == 400 and "SMTP" in resp.json()["detail"]

        monkeypatch.setattr(reports, "send_report", lambda to: "sent")
        assert client.post("/api/report/send").json() == {"sent_to": "owner@example.com"}
