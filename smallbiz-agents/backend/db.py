import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS kb_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_email TEXT NOT NULL,
    contact_name TEXT,
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'other',
    urgency TEXT NOT NULL DEFAULT 'low',
    ai_draft TEXT,
    ai_source TEXT NOT NULL DEFAULT 'template',
    status TEXT NOT NULL DEFAULT 'pending',
    thread_id TEXT,
    attachments TEXT,
    auto_sent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    sent_at TEXT
);

CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sid TEXT UNIQUE,
    from_number TEXT NOT NULL DEFAULT 'unknown',
    to_number TEXT,
    status TEXT NOT NULL DEFAULT 'in_progress',
    category TEXT NOT NULL DEFAULT 'other',
    urgency TEXT NOT NULL DEFAULT 'low',
    transcript TEXT,
    ai_summary TEXT,
    ai_response TEXT,
    recording_url TEXT,
    callback_requested INTEGER NOT NULL DEFAULT 0,
    handled INTEGER NOT NULL DEFAULT 0,
    handled_at TEXT,
    textback_sent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS
# won't add them to a database created by an older version, so init_db adds
# any that are missing.
_ADDED_COLUMNS = [
    ("emails", "attachments", "TEXT"),
    ("emails", "auto_sent", "INTEGER NOT NULL DEFAULT 0"),
    ("calls", "handled_at", "TEXT"),
    ("calls", "textback_sent", "INTEGER NOT NULL DEFAULT 0"),
]


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        for table, column, decl in _ADDED_COLUMNS:
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


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
