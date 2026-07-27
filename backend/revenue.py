import math
from datetime import datetime, timezone
from typing import Optional

from . import config, db


def _current_month_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def add_video(
    title: str,
    niche_keyword: Optional[str] = None,
    published_at: Optional[str] = None,
    views: int = 0,
    estimated_revenue_usd: float = 0.0,
    actual_revenue_usd: Optional[float] = None,
) -> int:
    if not published_at:
        published_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with db.session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO videos (title, niche_keyword, published_at, views, estimated_revenue_usd, actual_revenue_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, niche_keyword, published_at, views, estimated_revenue_usd, actual_revenue_usd, db.now_iso()),
        )
        return cursor.lastrowid


def list_videos() -> list:
    with db.session() as conn:
        rows = conn.execute("SELECT * FROM videos ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def delete_video(video_id: int) -> bool:
    with db.session() as conn:
        cursor = conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        return cursor.rowcount > 0


def get_progress(goal: Optional[float] = None) -> dict:
    goal = goal if goal is not None else config.REVENUE_GOAL_USD
    month_prefix = _current_month_prefix()

    with db.session() as conn:
        rows = conn.execute("SELECT * FROM videos").fetchall()
        top_niches = conn.execute(
            "SELECT * FROM niches ORDER BY opportunity_score DESC LIMIT 3"
        ).fetchall()

    total_revenue = 0.0
    total_views = 0
    counted_videos = 0
    for row in rows:
        published_at = row["published_at"]
        if published_at and not published_at.startswith(month_prefix):
            continue
        revenue = row["actual_revenue_usd"] if row["actual_revenue_usd"] is not None else row["estimated_revenue_usd"]
        total_revenue += revenue or 0.0
        total_views += row["views"] or 0
        counted_videos += 1

    total_revenue = round(total_revenue, 2)
    remaining = round(max(goal - total_revenue, 0), 2)
    percent_to_goal = round(min(total_revenue / goal * 100, 100), 1) if goal else 0.0

    gap_closing_suggestions = []
    for niche in top_niches:
        per_video = niche["projected_revenue_per_video_usd"]
        if per_video > 0:
            videos_needed = math.ceil(remaining / per_video)
        else:
            videos_needed = None
        gap_closing_suggestions.append(
            {
                "keyword": niche["keyword"],
                "category": niche["category"],
                "opportunity_score": niche["opportunity_score"],
                "projected_revenue_per_video_usd": per_video,
                "additional_videos_needed_to_close_gap": videos_needed,
            }
        )

    return {
        "month": month_prefix,
        "goal_usd": goal,
        "current_revenue_usd": total_revenue,
        "remaining_usd": remaining,
        "percent_to_goal": percent_to_goal,
        "videos_counted": counted_videos,
        "views_counted": total_views,
        "gap_closing_suggestions": gap_closing_suggestions,
    }
