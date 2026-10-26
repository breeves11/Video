import json
from typing import Optional

from . import db


def _to_dict(row) -> Optional[dict]:
    if row is None:
        return None
    item = dict(row)
    item["attachments"] = json.loads(item["attachments"]) if item.get("attachments") else []
    return item


def create_email(contact_email: str, contact_name: Optional[str], subject: str, body: str,
                  category: str, urgency: str, ai_draft: Optional[str], ai_source: str,
                  status: str, thread_id: Optional[str] = None,
                  attachments: Optional[list] = None) -> int:
    with db.session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO emails (contact_email, contact_name, subject, body, category, urgency,
                                 ai_draft, ai_source, status, thread_id, attachments, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (contact_email, contact_name, subject, body, category, urgency, ai_draft, ai_source,
             status, thread_id, json.dumps(attachments) if attachments else None, db.now_iso()),
        )
        return cursor.lastrowid


def get_email(email_id: int) -> Optional[dict]:
    with db.session() as conn:
        return _to_dict(conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone())


def get_by_thread_id(thread_id: str) -> Optional[dict]:
    with db.session() as conn:
        return _to_dict(conn.execute(
            "SELECT * FROM emails WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
            (thread_id,),
        ).fetchone())


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
        return [_to_dict(row) for row in rows]


def update_status(email_id: int, status: str, ai_draft: Optional[str] = None,
                   mark_sent: bool = False, auto_sent: Optional[bool] = None) -> bool:
    fields, values = ["status = ?"], [status]
    if ai_draft is not None:
        fields.append("ai_draft = ?")
        values.append(ai_draft)
    if mark_sent:
        fields.append("sent_at = ?")
        values.append(db.now_iso())
    if auto_sent is not None:
        fields.append("auto_sent = ?")
        values.append(1 if auto_sent else 0)
    values.append(email_id)
    with db.session() as conn:
        cursor = conn.execute(f"UPDATE emails SET {', '.join(fields)} WHERE id = ?", values)
        return cursor.rowcount > 0


def delete_email(email_id: int) -> bool:
    with db.session() as conn:
        cursor = conn.execute("DELETE FROM emails WHERE id = ?", (email_id,))
        return cursor.rowcount > 0
