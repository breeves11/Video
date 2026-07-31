import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "app.db")))

# Optional HTTP Basic Auth. If either is left blank, auth is disabled (local
# dev default). Set both before deploying somewhere with a public URL --
# these agents can send email/SMS on the business's behalf, so an
# unauthenticated public deploy is a real risk.
APP_USERNAME = os.getenv("APP_USERNAME", "").strip()
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()

# Per-IP requests/minute allowed on endpoints that call paid/quota-limited
# external APIs (LLM drafting, outbound SMS/email).
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))

# --- Outbound email (SMTP) -------------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM_ADDRESS = os.getenv("SMTP_FROM_ADDRESS", SMTP_USERNAME).strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() != "false"

# Shared secret required on the inbound-email webhook (POST /api/emails/inbound)
# once set. Configure your email provider's inbound-parse webhook to send it
# as an `X-Inbound-Secret` header. Left blank, the endpoint accepts any
# caller -- fine for local testing, a real security gap on a public deploy.
INBOUND_EMAIL_SECRET = os.getenv("INBOUND_EMAIL_SECRET", "").strip()

# --- Inbound email (IMAP polling), optional --------------------------------
# Leave blank to rely solely on the inbound-parse webhook
# (POST /api/emails/inbound) instead of polling a mailbox.
IMAP_HOST = os.getenv("IMAP_HOST", "").strip()
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USERNAME = os.getenv("IMAP_USERNAME", "").strip()
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "").strip()
IMAP_POLL_INTERVAL_MINUTES = float(os.getenv("IMAP_POLL_INTERVAL_MINUTES", "5"))

# --- Twilio (phone calls + SMS text-back), optional -------------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
# Base public URL of this deployment (e.g. https://yourapp.onrender.com),
# used to build the <Record>/<Gather> action callback URLs Twilio calls back.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")


def twilio_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER)


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD)


def imap_configured() -> bool:
    return bool(IMAP_HOST and IMAP_USERNAME and IMAP_PASSWORD)
