import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
POLL_INTERVAL_HOURS = float(os.getenv("POLL_INTERVAL_HOURS", "6"))
REVENUE_GOAL_USD = float(os.getenv("REVENUE_GOAL_USD", "5000"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "app.db")))
ASSUMED_VIDEOS_PER_MONTH = int(os.getenv("ASSUMED_VIDEOS_PER_MONTH", "8"))

# Optional HTTP Basic Auth. If either is left blank, auth is disabled (local
# dev default). Set both before deploying somewhere with a public URL.
APP_USERNAME = os.getenv("APP_USERNAME", "").strip()
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()

# Per-IP requests/minute allowed on the expensive endpoints (content
# generation, niche polling) that call paid/quota-limited external APIs.
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
