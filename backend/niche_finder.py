import math
from dataclasses import asdict, dataclass
from typing import List

from . import config
from .niche_data import NICHE_CATEGORIES
from .youtube_client import get_niche_stats

ASSUMED_VIDEOS_PER_MONTH = 8


@dataclass
class NicheOpportunity:
    keyword: str
    category: str
    avg_views: int
    competitor_uploads_per_month: int
    trend_growth_pct: float
    rpm_usd: float
    opportunity_score: float
    projected_revenue_per_video_usd: float
    projected_monthly_revenue_usd: float
    videos_needed_for_goal: int
    data_source: str

    def to_dict(self):
        return asdict(self)


def _normalize(value: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def discover_niches(limit: int = 15, videos_per_month: int = ASSUMED_VIDEOS_PER_MONTH) -> List[NicheOpportunity]:
    """Rank candidate niches by an opportunity score blending demand, how
    saturated the space is, trend momentum, and per-view monetization, then
    project the revenue and posting cadence needed to hit the revenue goal.
    """
    candidates = []
    for category, meta in NICHE_CATEGORIES.items():
        for keyword in meta["keywords"]:
            stats = get_niche_stats(keyword, meta["base_interest"], meta["base_competition"], meta["trend_bias"])
            candidates.append((category, meta, keyword, stats))

    all_views = [c[3].avg_views for c in candidates]
    all_competition = [c[3].competitor_uploads_per_month for c in candidates]
    all_trend = [c[3].trend_growth_pct for c in candidates]
    all_rpm = [c[1]["rpm"] for c in candidates]

    lo_views, hi_views = min(all_views), max(all_views)
    lo_comp, hi_comp = min(all_competition), max(all_competition)
    lo_trend, hi_trend = min(all_trend), max(all_trend)
    lo_rpm, hi_rpm = min(all_rpm), max(all_rpm)

    results = []
    for category, meta, keyword, stats in candidates:
        demand = _normalize(stats.avg_views, lo_views, hi_views)
        openness = 1 - _normalize(stats.competitor_uploads_per_month, lo_comp, hi_comp)
        momentum = _normalize(stats.trend_growth_pct, lo_trend, hi_trend)
        monetization = _normalize(meta["rpm"], lo_rpm, hi_rpm)

        opportunity_score = round((demand * 0.35 + openness * 0.25 + momentum * 0.2 + monetization * 0.2) * 100, 1)

        revenue_per_video = round((stats.avg_views / 1000) * meta["rpm"], 2)
        projected_monthly = round(revenue_per_video * videos_per_month, 2)
        videos_needed = math.ceil(config.REVENUE_GOAL_USD / revenue_per_video) if revenue_per_video > 0 else -1

        results.append(
            NicheOpportunity(
                keyword=keyword,
                category=category,
                avg_views=stats.avg_views,
                competitor_uploads_per_month=stats.competitor_uploads_per_month,
                trend_growth_pct=round(stats.trend_growth_pct, 1),
                rpm_usd=meta["rpm"],
                opportunity_score=opportunity_score,
                projected_revenue_per_video_usd=revenue_per_video,
                projected_monthly_revenue_usd=projected_monthly,
                videos_needed_for_goal=videos_needed,
                data_source=stats.source,
            )
        )

    results.sort(key=lambda r: r.opportunity_score, reverse=True)
    return results[:limit]
