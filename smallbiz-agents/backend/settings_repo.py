"""Runtime-editable business settings (name, hours, greeting, per-category
auto-send toggles) backed by a simple key/value table. Separate from
backend/config.py, which holds deploy-time secrets (API keys, SMTP/Twilio
credentials) that only change via environment variables.
"""

import json
from typing import Any

from . import db

DEFAULTS = {
    "business_name": "Your Business",
    "business_hours": "Mon-Fri 9am-5pm",
    "greeting_message": "Thanks for reaching out! Here's what I found:",
    "voice_greeting": "Thanks for calling. How can I help you today?",
    # Tell customers they're dealing with an AI (spoken at the start of a
    # call, and a footer on drafted emails). On by default: some
    # jurisdictions require it for automated customer interactions, so the
    # business should only switch it off after confirming that's allowed
    # where they operate.
    "ai_disclosure": True,
    # The weekly report. Baselines are the owner's own numbers from before
    # the agents went live (None = not entered yet); the report compares
    # against them. The timezone decides when "Monday morning" is.
    "timezone": "UTC",
    "weekly_report_email": "",
    "baseline_missed_calls_per_week": None,
    "baseline_email_reply_hours": None,
    # Categories where the AI-drafted reply/response is sent automatically
    # without human review. Off by default for everything except plain FAQs
    # -- complaints, quotes, and scheduling requests usually need a human
    # to actually look at them before anything goes out.
    "auto_send": {
        "faq": True,
        "quote_request": False,
        "complaint": False,
        "scheduling": False,
        "spam": False,
        "other": False,
    },
}


def _get_raw(key: str, default: Any) -> Any:
    with db.session() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (TypeError, ValueError):
            return default


def get(key: str) -> Any:
    return _get_raw(key, DEFAULTS.get(key))


def set(key: str, value: Any) -> None:
    with db.session() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


def all_settings() -> dict:
    return {key: get(key) for key in DEFAULTS}


def update_many(values: dict) -> dict:
    for key, value in values.items():
        if key in DEFAULTS:
            set(key, value)
    return all_settings()


def is_auto_send(category: str) -> bool:
    auto_send = get("auto_send") or {}
    return bool(auto_send.get(category, False))
