"""Go-live preflight: checks a deployment's configuration before a real
customer's email and phone traffic is pointed at it.

    python scripts/preflight.py          # configuration checks only
    python scripts/preflight.py --live   # also log in to SMTP/IMAP, check the
                                         # Twilio account and number webhooks,
                                         # the public URL, and the Anthropic key

Run it with the same environment as the app (same .env / host env vars).
Exits non-zero if anything FAILs, so it can gate a deploy script.
Nothing here sends an email, SMS, or call.
"""

import argparse
import imaplib
import os
import smtplib
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config  # noqa: E402

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass
class Check:
    status: str
    name: str
    detail: str = ""


def config_checks() -> list:
    checks = []

    def add(status, name, detail=""):
        checks.append(Check(status, name, detail))

    # Dashboard auth
    if config.APP_USERNAME and config.APP_PASSWORD:
        add(PASS, "Dashboard login (APP_USERNAME/APP_PASSWORD)")
        if len(config.APP_PASSWORD) < 12:
            add(WARN, "Dashboard password strength", "use 12+ characters on a public deploy")
    elif config.APP_USERNAME or config.APP_PASSWORD:
        add(FAIL, "Dashboard login", "only one of APP_USERNAME/APP_PASSWORD is set -- auth is OFF")
    else:
        add(FAIL, "Dashboard login", "APP_USERNAME/APP_PASSWORD not set -- anyone with the URL can use the dashboard")

    # Inbound email webhook. The endpoint exists whether or not the business
    # uses it, so an unset secret is an open door either way -- and a real
    # open relay once SMTP is configured.
    if config.INBOUND_EMAIL_SECRET:
        add(PASS, "Inbound email webhook secret (INBOUND_EMAIL_SECRET)")
    elif config.smtp_configured():
        add(FAIL, "Inbound email webhook secret", "not set while SMTP is configured -- anyone can trigger auto-sent mail")
    else:
        add(WARN, "Inbound email webhook secret", "not set -- set it before connecting a mail provider")

    # Outbound email
    if config.smtp_configured():
        add(PASS, "Outbound email (SMTP)")
        if not os.getenv("SMTP_FROM_ADDRESS", "").strip():
            add(WARN, "SMTP_FROM_ADDRESS", "not set -- replies will come from the SMTP username")
    else:
        add(WARN, "Outbound email (SMTP)", "not configured -- replies are drafted but never sent")

    if config.imap_configured():
        add(PASS, "Inbound email polling (IMAP)")

    # Phone
    twilio_any = any([config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN, config.TWILIO_FROM_NUMBER])
    if twilio_any:
        if config.twilio_configured():
            add(PASS, "Twilio credentials")
        else:
            add(FAIL, "Twilio credentials", "set all of TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER")
        if not config.PUBLIC_BASE_URL:
            add(FAIL, "PUBLIC_BASE_URL", "required with Twilio -- signature checks and callbacks depend on it")
        elif not config.PUBLIC_BASE_URL.startswith("https://"):
            add(FAIL, "PUBLIC_BASE_URL", "must be an https:// URL")
        else:
            add(PASS, "PUBLIC_BASE_URL", config.PUBLIC_BASE_URL)
    else:
        add(WARN, "Phone (Twilio)", "not configured -- phone agent only works in the dashboard simulator")

    # AI
    if config.ANTHROPIC_API_KEY:
        add(PASS, "AI drafting (ANTHROPIC_API_KEY)")
    else:
        add(WARN, "AI drafting", "no ANTHROPIC_API_KEY -- template replies only")

    # Storage
    db_path = config.DATABASE_PATH.resolve()
    if str(db_path).startswith("/tmp"):
        add(WARN, "Database location", f"{db_path} is ephemeral on most hosts -- data is lost on restart")
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        probe = db_path.parent / ".preflight-write-test"
        probe.write_text("ok")
        probe.unlink()
        add(PASS, "Database directory writable", str(db_path.parent))
    except OSError as exc:
        add(FAIL, "Database directory writable", f"{db_path.parent}: {exc}")

    # Business content (only if the DB already exists -- don't create one)
    if db_path.exists():
        from backend import knowledge_base, settings_repo

        kb_count = len(knowledge_base.list_entries())
        if kb_count >= 5:
            add(PASS, "Knowledge base", f"{kb_count} entries")
        else:
            add(WARN, "Knowledge base", f"only {kb_count} entries -- add the business's common questions")
        if settings_repo.get("business_name") == settings_repo.DEFAULTS["business_name"]:
            add(WARN, "Business name", "still the placeholder 'Your Business' (Settings tab)")
    else:
        add(WARN, "Knowledge base / settings", "no database yet -- start the app once and fill these in")

    return checks


def live_checks() -> list:
    import requests

    checks = []

    def add(status, name, detail=""):
        checks.append(Check(status, name, detail))

    if config.smtp_configured():
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
                if config.SMTP_USE_TLS:
                    server.starttls()
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            add(PASS, "SMTP login")
        except Exception as exc:
            add(FAIL, "SMTP login", str(exc))

    if config.imap_configured():
        try:
            conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
            conn.login(config.IMAP_USERNAME, config.IMAP_PASSWORD)
            conn.logout()
            add(PASS, "IMAP login")
        except Exception as exc:
            add(FAIL, "IMAP login", str(exc))

    if config.twilio_configured():
        auth = (config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        base = f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}"
        try:
            account = requests.get(f"{base}.json", auth=auth, timeout=15)
            if account.status_code != 200:
                add(FAIL, "Twilio account", f"HTTP {account.status_code} -- check SID/auth token")
            else:
                add(PASS, "Twilio account", account.json().get("friendly_name", ""))
                numbers = requests.get(
                    f"{base}/IncomingPhoneNumbers.json",
                    params={"PhoneNumber": config.TWILIO_FROM_NUMBER},
                    auth=auth, timeout=15,
                ).json().get("incoming_phone_numbers", [])
                if not numbers:
                    add(FAIL, "Twilio number", f"{config.TWILIO_FROM_NUMBER} is not on this account")
                else:
                    number = numbers[0]
                    expected_voice = f"{config.PUBLIC_BASE_URL}/api/phone/voice"
                    expected_status = f"{config.PUBLIC_BASE_URL}/api/phone/status"
                    for label, actual, expected in (
                        ("Twilio 'A call comes in' webhook", number.get("voice_url"), expected_voice),
                        ("Twilio call status callback", number.get("status_callback"), expected_status),
                    ):
                        if actual == expected:
                            add(PASS, label, actual)
                        else:
                            add(FAIL, label, f"is {actual or '(empty)'!r}, should be {expected!r}")
        except requests.RequestException as exc:
            add(FAIL, "Twilio API", str(exc))

    if config.PUBLIC_BASE_URL:
        try:
            auth = (config.APP_USERNAME, config.APP_PASSWORD) if config.APP_USERNAME else None
            health = requests.get(f"{config.PUBLIC_BASE_URL}/api/health", auth=auth, timeout=15)
            if health.status_code == 200:
                add(PASS, "Public URL reachable", f"{config.PUBLIC_BASE_URL}/api/health")
            else:
                add(FAIL, "Public URL reachable", f"HTTP {health.status_code}")
        except requests.RequestException as exc:
            add(FAIL, "Public URL reachable", str(exc))

    if config.ANTHROPIC_API_KEY:
        from backend import llm_client

        reply = llm_client.generate_text("Reply with the single word: ok", max_tokens=5)
        if reply:
            add(PASS, "Anthropic API key", f"model {llm_client.AGENT_MODEL}")
        else:
            add(FAIL, "Anthropic API key", "request failed -- check the key and AGENT_MODEL")

    return checks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="also test credentials against the real services")
    args = parser.parse_args(argv)

    checks = config_checks() + (live_checks() if args.live else [])
    for check in checks:
        line = f"[{check.status}] {check.name}"
        print(f"{line} -- {check.detail}" if check.detail else line)

    fails = sum(c.status == FAIL for c in checks)
    warns = sum(c.status == WARN for c in checks)
    print(f"\n{fails} failing, {warns} warnings" + ("" if args.live else " (run with --live to test credentials)"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
