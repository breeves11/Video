from typing import Optional

from . import db


def upsert_call(call_sid: str, from_number: str, to_number: Optional[str] = None,
                 status: str = "in_progress") -> dict:
    with db.session() as conn:
        row = conn.execute("SELECT * FROM calls WHERE call_sid = ?", (call_sid,)).fetchone()
        if row:
            return dict(row)
        now = db.now_iso()
        conn.execute(
            """
            INSERT INTO calls (call_sid, from_number, to_number, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (call_sid, from_number, to_number, status, now, now),
        )
        row = conn.execute("SELECT * FROM calls WHERE call_sid = ?", (call_sid,)).fetchone()
        return dict(row)


def update_call(call_sid: str, **fields) -> Optional[dict]:
    if not fields:
        with db.session() as conn:
            row = conn.execute("SELECT * FROM calls WHERE call_sid = ?", (call_sid,)).fetchone()
            return dict(row) if row else None

    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(db.now_iso())
    values.append(call_sid)
    with db.session() as conn:
        conn.execute(
            f"UPDATE calls SET {columns}, updated_at = ? WHERE call_sid = ?", values
        )
        row = conn.execute("SELECT * FROM calls WHERE call_sid = ?", (call_sid,)).fetchone()
        return dict(row) if row else None


def get_call(call_sid: str) -> Optional[dict]:
    with db.session() as conn:
        row = conn.execute("SELECT * FROM calls WHERE call_sid = ?", (call_sid,)).fetchone()
        return dict(row) if row else None


def get_call_by_id(call_id: int) -> Optional[dict]:
    with db.session() as conn:
        row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
        return dict(row) if row else None


def list_calls(handled: Optional[bool] = None, limit: int = 50) -> list:
    with db.session() as conn:
        if handled is None:
            rows = conn.execute(
                "SELECT * FROM calls ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM calls WHERE handled = ? ORDER BY created_at DESC LIMIT ?",
                (1 if handled else 0, limit),
            ).fetchall()
        return [dict(row) for row in rows]


def mark_handled(call_id: int, handled: bool = True) -> bool:
    """`handled_at` keeps the first time a call was followed up (re-marking
    doesn't move it), so time-to-callback in the report stays honest."""
    now = db.now_iso()
    with db.session() as conn:
        if handled:
            cursor = conn.execute(
                "UPDATE calls SET handled = 1, handled_at = COALESCE(handled_at, ?), updated_at = ? "
                "WHERE id = ?",
                (now, now, call_id),
            )
        else:
            cursor = conn.execute(
                "UPDATE calls SET handled = 0, handled_at = NULL, updated_at = ? WHERE id = ?",
                (now, call_id),
            )
        return cursor.rowcount > 0
