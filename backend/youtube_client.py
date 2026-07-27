"""Data source for niche demand/competition/trend signals.

Uses the real YouTube Data API when YOUTUBE_API_KEY is configured, and falls
back to a deterministic estimator otherwise (or if the live call fails) so the
rest of the app always has data to rank against.
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from . import config

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class NicheStats:
    def __init__(self, avg_views: int, competitor_uploads_per_month: int, trend_growth_pct: float, source: str):
        self.avg_views = avg_views
        self.competitor_uploads_per_month = competitor_uploads_per_month
        self.trend_growth_pct = trend_growth_pct
        self.source = source

    def to_dict(self):
        return {
            "avg_views": self.avg_views,
            "competitor_uploads_per_month": self.competitor_uploads_per_month,
            "trend_growth_pct": round(self.trend_growth_pct, 1),
            "source": self.source,
        }


def _seeded_random(keyword: str) -> random.Random:
    seed = int(hashlib.md5(keyword.encode("utf-8")).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _mock_stats(keyword: str, base_interest: int, base_competition: int, trend_bias: float) -> NicheStats:
    rng = _seeded_random(keyword)
    avg_views = int(base_interest * rng.uniform(500, 2200))
    competitor_uploads = int(base_competition * rng.uniform(0.3, 0.9))
    trend_growth = trend_bias + rng.uniform(-8, 22)
    return NicheStats(avg_views, max(competitor_uploads, 1), trend_growth, source="estimated")


def _thirty_days_ago_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _live_stats(keyword: str) -> Optional[NicheStats]:
    try:
        search_resp = requests.get(
            YOUTUBE_SEARCH_URL,
            params={
                "key": config.YOUTUBE_API_KEY,
                "q": keyword,
                "part": "id",
                "type": "video",
                "order": "date",
                "maxResults": 25,
                "publishedAfter": _thirty_days_ago_iso(),
            },
            timeout=10,
        )
        search_resp.raise_for_status()
        video_ids = [
            item["id"]["videoId"]
            for item in search_resp.json().get("items", [])
            if item.get("id", {}).get("videoId")
        ]
        if not video_ids:
            return None

        videos_resp = requests.get(
            YOUTUBE_VIDEOS_URL,
            params={"key": config.YOUTUBE_API_KEY, "id": ",".join(video_ids), "part": "statistics"},
            timeout=10,
        )
        videos_resp.raise_for_status()
        view_counts = [int(item["statistics"].get("viewCount", 0)) for item in videos_resp.json().get("items", [])]
        if not view_counts:
            return None

        avg_views = sum(view_counts) // len(view_counts)
        uploads_per_month = len(video_ids)

        midpoint = len(view_counts) // 2
        recent_half = view_counts[:midpoint] or view_counts
        older_half = view_counts[midpoint:] or view_counts
        recent_avg = sum(recent_half) / len(recent_half)
        older_avg = sum(older_half) / len(older_half)
        trend_growth = ((recent_avg / older_avg) - 1) * 100 if older_avg else 0.0

        return NicheStats(avg_views, uploads_per_month, trend_growth, source="youtube_api")
    except (requests.RequestException, KeyError, ValueError, ZeroDivisionError):
        return None


def get_niche_stats(keyword: str, base_interest: int, base_competition: int, trend_bias: float) -> NicheStats:
    if config.YOUTUBE_API_KEY:
        live = _live_stats(keyword)
        if live is not None:
            return live
    return _mock_stats(keyword, base_interest, base_competition, trend_bias)
