from typing import List

from . import db
from .niche_finder import NicheOpportunity


def save_niches(niches: List[NicheOpportunity]) -> None:
    with db.session() as conn:
        for n in niches:
            conn.execute(
                """
                INSERT INTO niches (
                    keyword, category, avg_views, competitor_uploads_per_month, trend_growth_pct,
                    rpm_usd, opportunity_score, projected_revenue_per_video_usd,
                    projected_monthly_revenue_usd, videos_needed_for_goal, data_source, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(keyword) DO UPDATE SET
                    category=excluded.category,
                    avg_views=excluded.avg_views,
                    competitor_uploads_per_month=excluded.competitor_uploads_per_month,
                    trend_growth_pct=excluded.trend_growth_pct,
                    rpm_usd=excluded.rpm_usd,
                    opportunity_score=excluded.opportunity_score,
                    projected_revenue_per_video_usd=excluded.projected_revenue_per_video_usd,
                    projected_monthly_revenue_usd=excluded.projected_monthly_revenue_usd,
                    videos_needed_for_goal=excluded.videos_needed_for_goal,
                    data_source=excluded.data_source,
                    discovered_at=excluded.discovered_at
                """,
                (
                    n.keyword,
                    n.category,
                    n.avg_views,
                    n.competitor_uploads_per_month,
                    n.trend_growth_pct,
                    n.rpm_usd,
                    n.opportunity_score,
                    n.projected_revenue_per_video_usd,
                    n.projected_monthly_revenue_usd,
                    n.videos_needed_for_goal,
                    n.data_source,
                    db.now_iso(),
                ),
            )


def list_niches(limit: int = 15) -> list:
    with db.session() as conn:
        rows = conn.execute(
            "SELECT * FROM niches ORDER BY opportunity_score DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
