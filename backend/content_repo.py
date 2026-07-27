import json

from . import db
from .content_generator import ContentPackage


def save_content(package: ContentPackage) -> int:
    with db.session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO content (niche_keyword, video_topic, titles, description, tags, script, thumbnail_text_ideas, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                package.niche_keyword,
                package.video_topic,
                json.dumps(package.titles),
                package.description,
                json.dumps(package.tags),
                package.script,
                json.dumps(package.thumbnail_text_ideas),
                package.source,
                db.now_iso(),
            ),
        )
        return cursor.lastrowid


def delete_content(content_id: int) -> bool:
    with db.session() as conn:
        cursor = conn.execute("DELETE FROM content WHERE id = ?", (content_id,))
        return cursor.rowcount > 0


def list_content(limit: int = 20) -> list:
    with db.session() as conn:
        rows = conn.execute(
            "SELECT * FROM content ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["titles"] = json.loads(item["titles"])
            item["tags"] = json.loads(item["tags"])
            item["thumbnail_text_ideas"] = json.loads(item["thumbnail_text_ideas"])
            results.append(item)
        return results
