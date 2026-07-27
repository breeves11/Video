import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS niches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    category TEXT NOT NULL,
    avg_views INTEGER NOT NULL,
    competitor_uploads_per_month INTEGER NOT NULL,
    trend_growth_pct REAL NOT NULL,
    rpm_usd REAL NOT NULL,
    opportunity_score REAL NOT NULL,
    projected_revenue_per_video_usd REAL NOT NULL,
    projected_monthly_revenue_usd REAL NOT NULL,
    videos_needed_for_goal INTEGER NOT NULL,
    data_source TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    UNIQUE(keyword)
);

CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    niche_keyword TEXT NOT NULL,
    video_topic TEXT NOT NULL,
    titles TEXT NOT NULL,
    description TEXT NOT NULL,
    tags TEXT NOT NULL,
    script TEXT NOT NULL,
    thumbnail_text_ideas TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    niche_keyword TEXT,
    published_at TEXT,
    views INTEGER NOT NULL DEFAULT 0,
    estimated_revenue_usd REAL NOT NULL DEFAULT 0,
    actual_revenue_usd REAL,
    created_at TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
