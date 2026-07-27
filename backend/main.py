from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, content_repo, db, llm_client, niches_repo, revenue, scheduler
from .content_generator import generate_content
from .security import BasicAuthMiddleware, rate_limit


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if not niches_repo.list_niches(limit=1):
        scheduler.poll_niches()
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="YouTube Niche & Content Engine", lifespan=lifespan)
app.add_middleware(BasicAuthMiddleware)


class ContentRequest(BaseModel):
    niche_keyword: str
    category: str = "general"
    video_topic: Optional[str] = None


class VideoRequest(BaseModel):
    title: str
    niche_keyword: Optional[str] = None
    published_at: Optional[str] = None
    views: int = Field(default=0, ge=0)
    estimated_revenue_usd: float = Field(default=0.0, ge=0)
    actual_revenue_usd: Optional[float] = Field(default=None, ge=0)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "youtube_live_data": bool(config.YOUTUBE_API_KEY),
        "ai_content_generation": llm_client.is_available(),
        "revenue_goal_usd": config.REVENUE_GOAL_USD,
        "assumed_videos_per_month": config.ASSUMED_VIDEOS_PER_MONTH,
        "auth_enabled": bool(config.APP_USERNAME and config.APP_PASSWORD),
    }


@app.get("/api/niches")
def get_niches(limit: int = 15, videos_per_month: Optional[int] = None):
    niches = niches_repo.list_niches(limit=limit, videos_per_month=videos_per_month)
    if not niches:
        scheduler.poll_niches()
        niches = niches_repo.list_niches(limit=limit, videos_per_month=videos_per_month)
    return {"niches": niches}


@app.post("/api/niches/poll", dependencies=[Depends(rate_limit)])
def poll_niches():
    count = scheduler.poll_niches()
    return {"polled": count, "niches": niches_repo.list_niches(limit=15)}


@app.post("/api/content/generate", dependencies=[Depends(rate_limit)])
def create_content(req: ContentRequest):
    package = generate_content(req.niche_keyword, req.category, req.video_topic)
    content_id = content_repo.save_content(package)
    result = package.to_dict()
    result["id"] = content_id
    return result


@app.get("/api/content")
def get_content(limit: int = 20):
    return {"content": content_repo.list_content(limit=limit)}


@app.delete("/api/content/{content_id}")
def remove_content(content_id: int):
    if not content_repo.delete_content(content_id):
        raise HTTPException(status_code=404, detail="Content not found")
    return {"deleted": content_id}


@app.post("/api/videos")
def create_video(req: VideoRequest):
    video_id = revenue.add_video(
        title=req.title,
        niche_keyword=req.niche_keyword,
        published_at=req.published_at,
        views=req.views,
        estimated_revenue_usd=req.estimated_revenue_usd,
        actual_revenue_usd=req.actual_revenue_usd,
    )
    if video_id is None:
        raise HTTPException(status_code=500, detail="Failed to save video")
    return {"id": video_id}


@app.get("/api/videos")
def get_videos():
    return {"videos": revenue.list_videos()}


@app.delete("/api/videos/{video_id}")
def remove_video(video_id: int):
    if not revenue.delete_video(video_id):
        raise HTTPException(status_code=404, detail="Video not found")
    return {"deleted": video_id}


@app.get("/api/progress")
def get_progress():
    return revenue.get_progress()


app.mount("/", StaticFiles(directory=str(config.BASE_DIR / "frontend"), html=True), name="frontend")
