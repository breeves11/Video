"""The results report: what the agents did for the business over a period,
compared with the period before and with the owner's own "before" numbers.

Each period is a cohort: the emails and calls that *arrived* in it, plus
what happened to them (replied? how fast? called back?). Nothing is counted
twice across periods, and a period's numbers don't shift because of
activity on older messages.

Every figure is measured from stored data -- no estimates or assumed
minutes-saved, so the numbers hold up when shown to the business owner.
"""

import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import config, db, settings_repo

WAITING_EMAIL_STATUSES = ("pending", "queued_send_unconfigured", "send_failed")
SEND_HOUR_LOCAL = 8
_LAST_SENT_KEY = "weekly_report_last_sent_week"  # internal; not an editable setting


def _parse(ts: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(ts) if ts else None


def _minutes(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() / 60)


def _median(values: list) -> Optional[float]:
    return round(statistics.median(values), 1) if values else None


def _pct(part: int, whole: int) -> Optional[int]:
    return round(100 * part / whole) if whole else None


def _load(conn, table: str, since: datetime) -> list:
    # Coarse filter on the date prefix in SQL (timestamps are UTC ISO
    # strings), exact comparison after parsing.
    rows = conn.execute(f"SELECT * FROM {table} WHERE created_at >= ?", (since.date().isoformat(),))
    items = []
    for row in rows:
        item = dict(row)
        item["_created"] = _parse(item["created_at"])
        items.append(item)
    return items


def _window(items: list, start: datetime, end: datetime) -> list:
    return [i for i in items if start <= i["_created"] < end]


def email_metrics(rows: list) -> dict:
    replied = [r for r in rows if r["status"] == "sent" and r["sent_at"]]
    reply_minutes = [_minutes(r["_created"], _parse(r["sent_at"])) for r in replied]
    auto = sum(1 for r in replied if r["auto_sent"])
    categories = Counter(r["category"] for r in rows)
    return {
        "received": len(rows),
        "replied": len(replied),
        "auto_replied": auto,
        "owner_replied": len(replied) - auto,
        "dismissed": sum(1 for r in rows if r["status"] == "dismissed"),
        "spam": categories.get("spam", 0),
        "median_reply_minutes": _median(reply_minutes),
        "replied_within_hour_pct": _pct(sum(m <= 60 for m in reply_minutes), len(reply_minutes)),
        "by_category": dict(categories),
    }


def call_metrics(rows: list) -> dict:
    missed = [r for r in rows if r["status"] == "missed"]
    needed_callback = [r for r in rows if r["callback_requested"]]
    called_back = [r for r in needed_callback if r["handled"]]
    callback_minutes = [
        _minutes(r["_created"], _parse(r["handled_at"])) for r in called_back if r["handled_at"]
    ]
    return {
        "total": len(rows),
        "answered_by_ai": len(rows) - len(missed),
        "resolved_on_call": sum(1 for r in rows if r["handled"] and not r["callback_requested"]),
        "voicemails": sum(1 for r in rows if r["recording_url"]),
        "callbacks_needed": len(needed_callback),
        "callbacks_done": len(called_back),
        "median_callback_minutes": _median(callback_minutes),
        "missed": len(missed),
        "missed_texted_back": sum(1 for r in missed if r["textback_sent"]),
        "missed_followed_up": sum(1 for r in missed if r["textback_sent"] or r["handled"]),
    }


def _open_items(conn, now: datetime) -> dict:
    placeholders = ",".join("?" * len(WAITING_EMAIL_STATUSES))
    waiting = conn.execute(
        f"SELECT created_at FROM emails WHERE status IN ({placeholders}) AND category != 'spam'",
        WAITING_EMAIL_STATUSES,
    ).fetchall()
    oldest = min((_parse(r["created_at"]) for r in waiting), default=None)
    callbacks = conn.execute(
        "SELECT COUNT(*) AS n FROM calls WHERE callback_requested = 1 AND handled = 0"
    ).fetchone()["n"]
    return {
        "emails_waiting": len(waiting),
        "oldest_email_waiting_minutes": round(_minutes(oldest, now)) if oldest else None,
        "callbacks_waiting": callbacks,
    }


def build_report(days: int = 7, weeks: int = 8, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    previous_start = start - timedelta(days=days)
    earliest = min(previous_start, now - timedelta(weeks=weeks))

    with db.session() as conn:
        emails = _load(conn, "emails", earliest)
        calls = _load(conn, "calls", earliest)
        open_items = _open_items(conn, now)

    current = {
        "emails": email_metrics(_window(emails, start, now)),
        "calls": call_metrics(_window(calls, start, now)),
    }
    previous = {
        "emails": email_metrics(_window(emails, previous_start, start)),
        "calls": call_metrics(_window(calls, previous_start, start)),
    }

    weekly = []
    for i in reversed(range(weeks)):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(weeks=1)
        weekly.append({
            "start": week_start.isoformat(),
            "end": week_end.isoformat(),
            "emails": len(_window(emails, week_start, week_end)),
            "calls": len(_window(calls, week_start, week_end)),
        })

    baseline_missed = settings_repo.get("baseline_missed_calls_per_week")
    baseline_reply_hours = settings_repo.get("baseline_email_reply_hours")
    median_reply = current["emails"]["median_reply_minutes"]
    return {
        "period": {"start": start.isoformat(), "end": now.isoformat(), "days": days},
        "current": current,
        "previous": previous,
        "open": open_items,
        "weekly": weekly,
        "baseline": {
            "missed_calls_per_week": baseline_missed,
            "email_reply_hours": baseline_reply_hours,
            # Normalised to per-week so a 30-day view compares like for like.
            "missed_calls_per_week_now": round(current["calls"]["missed"] * 7 / days, 1),
            "email_reply_hours_now": round(median_reply / 60, 2) if median_reply is not None else None,
        },
    }


# --- Email rendering -------------------------------------------------------

def humanize_minutes(minutes: Optional[float]) -> str:
    if minutes is None:
        return "--"
    if minutes < 60:
        return f"{round(minutes)} min"
    hours = minutes / 60
    if hours < 48:
        return f"{hours:.1f} h".replace(".0 h", " h")
    return f"{round(hours / 24)} days"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def render_email(report: dict) -> tuple:
    business = settings_repo.get("business_name")
    calls, emails, open_items = report["current"]["calls"], report["current"]["emails"], report["open"]
    tz = _business_tz()  # dates as the owner reads them, not UTC
    start = _parse(report["period"]["start"]).astimezone(tz)
    end = _parse(report["period"]["end"]).astimezone(tz)

    subject = (
        f"{business}: {_plural(calls['answered_by_ai'], 'call')} answered, "
        f"{_plural(emails['replied'], 'email')} replied this week"
    )

    lines = [f"Your AI front desk, {start:%b} {start.day} - {end:%b} {end.day}", ""]

    lines += ["PHONE",
              f"  {_plural(calls['answered_by_ai'], 'call')} answered by the AI assistant",
              f"  {calls['resolved_on_call']} resolved on the call, no callback needed"]
    if calls["callbacks_needed"]:
        lines.append(
            f"  {calls['callbacks_needed']} needed a callback: {calls['callbacks_done']} done"
            + (f" (median {humanize_minutes(calls['median_callback_minutes'])} after the call)"
               if calls["median_callback_minutes"] is not None else "")
        )
    if calls["missed"]:
        lines.append(
            f"  {_plural(calls['missed'], 'missed call')}: {calls['missed_followed_up']} followed up "
            f"({calls['missed_texted_back']} texted back automatically)"
        )
    else:
        lines.append("  No missed calls")

    lines += ["", "EMAIL",
              f"  {emails['received']} received, {emails['replied']} replied "
              f"({emails['auto_replied']} automatically, {emails['owner_replied']} approved by you)"]
    if emails["median_reply_minutes"] is not None:
        lines.append(
            f"  Typical reply time: {humanize_minutes(emails['median_reply_minutes'])}"
            f" ({emails['replied_within_hour_pct']}% within an hour)"
        )

    lines += ["", "WAITING FOR YOU NOW"]
    if open_items["emails_waiting"] or open_items["callbacks_waiting"]:
        if open_items["emails_waiting"]:
            lines.append(
                f"  {_plural(open_items['emails_waiting'], 'email')} to review "
                f"(oldest {humanize_minutes(open_items['oldest_email_waiting_minutes'])})"
            )
        if open_items["callbacks_waiting"]:
            lines.append(f"  {_plural(open_items['callbacks_waiting'], 'caller')} waiting for a callback")
    else:
        lines.append("  Nothing -- you're all caught up")

    baseline = report["baseline"]
    comparisons = []
    if baseline["missed_calls_per_week"] is not None:
        comparisons.append(
            f"  Missed calls per week: {baseline['missed_calls_per_week']:g} before -> "
            f"{baseline['missed_calls_per_week_now']:g} now"
        )
    if baseline["email_reply_hours"] is not None and baseline["email_reply_hours_now"] is not None:
        comparisons.append(
            f"  Email reply time: {humanize_minutes(baseline['email_reply_hours'] * 60)} before -> "
            f"{humanize_minutes(baseline['email_reply_hours_now'] * 60)} now"
        )
    if comparisons:
        lines += ["", "BEFORE VS NOW"] + comparisons

    if config.PUBLIC_BASE_URL:
        lines += ["", f"Open your dashboard: {config.PUBLIC_BASE_URL}"]
    return subject, "\n".join(lines) + "\n"


# --- Sending -----------------------------------------------------------------

def send_report(recipient: str) -> str:
    """Email the last 7 days' report. Returns sent / unconfigured / failed."""
    from . import email_agent

    subject, body = render_email(build_report(days=7))
    return email_agent.send_email(recipient, subject, body)


def _business_tz():
    try:
        return ZoneInfo(settings_repo.get("timezone") or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def _week_key(moment: datetime) -> str:
    year, week, _ = moment.isocalendar()
    return f"{year}-W{week:02d}"


def maybe_send_weekly(now: Optional[datetime] = None) -> bool:
    """Called hourly. Sends once per week, at the first check after Monday
    08:00 in the business's timezone. If the app was down on Monday it
    catches up later that week -- but a freshly configured recipient waits
    for the next Monday instead of getting a surprise mid-week email.
    """
    recipient = settings_repo.get("weekly_report_email")
    if not recipient or not config.smtp_configured():
        return False

    local = (now or datetime.now(timezone.utc)).astimezone(_business_tz())
    this_week = _week_key(local)
    last_sent = settings_repo.get(_LAST_SENT_KEY)
    if last_sent == this_week:
        return False

    monday_morning = local.weekday() == 0 and local.hour >= SEND_HOUR_LOCAL
    catching_up = local.weekday() > 0 and last_sent == _week_key(local - timedelta(weeks=1))
    if not (monday_morning or catching_up):
        return False

    if send_report(recipient) != "sent":
        return False
    settings_repo.set(_LAST_SENT_KEY, this_week)
    return True
