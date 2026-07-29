from typing import Optional

from . import db


def create_email(contact_email: str, contact_name: Optional[str], subject: str, body: str,
                  category: str, urgency: str, ai_draft: Optional[str], ai_source: str,
                  status: str, thread_id: Optional[str] = None) -> int:
    with db.session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO emails (contact_email, contact_name, subject, body, category, urgency,
                                 ai_draft, ai_source, status, thread_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (contact_email, contact_name, subject, body, category, urgency, ai_draft, ai_source,
             status, thread_id, db.now_iso()),
        )
        return cursor.lastrowid


def get_email(email_id: int) -> Optional[dict]:
    with db.session() as conn:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
        return dict(row) if row else None


def list_emails(status: Optional[str] = None, limit: int = 50) -> list:
    with db.session() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM emails WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM emails ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]


def update_status(email_id: int, status: str, ai_draft: Optional[str] = None,
                   mark_sent: bool = False) -> bool:
    fields, values = ["status = ?"], [status]
    if ai_draft is not None:
        fields.append("ai_draft = ?")
        values.append(ai_draft)
    if mark_sent:
        fields.append("sent_at = ?")
        values.append(db.now_iso())
    values.append(email_id)
    with db.session() as conn:
        cursor = conn.execute(f"UPDATE emails SET {', '.join(fields)} WHERE id = ?", values)
        return cursor.rowcount > 0


def delete_email(email_id: int) -> bool:
    with db.session() as conn:
        cursor = conn.execute("DELETE FROM emails WHERE id = ?", (email_id,))
        return cursor.rowcount > 0
