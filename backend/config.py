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
