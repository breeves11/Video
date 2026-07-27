# YouTube Niche & Content Engine

An app that helps you find YouTube niches likely to generate views and
revenue, generates ready-to-use video content for them, and tracks your
progress toward a monthly revenue goal (default: $5,000/month).

## What it does

1. **Niche discovery** (`backend/niche_finder.py`) — scores candidate niches
   across 11 content categories (personal finance, AI tools, make-money-online,
   software tutorials, health, pets, travel, careers, sustainability, kids'
   short-form content, etc.) on demand, competition, trend momentum, and
   monetization (RPM), then projects revenue-per-video and how many videos are
   needed to hit the revenue goal. A background job (`backend/scheduler.py`)
   re-polls on an interval (`POLL_INTERVAL_HOURS`, default 6h) so opportunities
   stay fresh.

   Note on kids' content: "Made for Kids" videos get some of the highest view
   counts on YouTube, but COPPA disables personalized ads and comments on them,
   which drags RPM well below every other category in `backend/niche_data.py`.
   The projections reflect that — expect to need much higher video volume to
   hit the same revenue goal in that niche.
2. **Content generation** (`backend/content_generator.py`) — for any niche,
   generates titles, a description, tags, a full script outline, and
   thumbnail text ideas. Uses Claude (`ANTHROPIC_API_KEY`) when available,
   otherwise falls back to a deterministic template generator so the app is
   always usable.
3. **Revenue tracking** (`backend/revenue.py`) — log published videos (views,
   estimated or actual revenue) and see monthly progress toward the goal, plus
   suggestions on which niches to publish more videos in to close the gap.

By default the niche data is a deterministic estimator (no external API
needed). Set `YOUTUBE_API_KEY` to pull real recent-upload stats from the
YouTube Data API v3 instead.

**Note on the $5k/month goal:** this app finds opportunities and produces the
content — actually hitting the revenue number still requires publishing
videos, growing a channel, and YouTube Partner Program monetization approval,
which happen outside this codebase.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optionally add YOUTUBE_API_KEY / ANTHROPIC_API_KEY
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000 for the dashboard.

### Testing on your phone

The dev server above only listens on your computer. To open it from a phone:

- **Same Wi-Fi (fastest):** run `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
  instead, find your computer's LAN IP (e.g. `ipconfig`/`ifconfig`, something
  like `192.168.x.x`), then visit `http://<that-ip>:8000` in your phone's
  browser.
- **Public URL, any network:** deploy it (see below) and open the deployed URL
  on your phone.

### Deploy (public URL)

**Render (no local tooling needed):**
1. Push this repo to GitHub (already done if you're reading this from there).
2. In the Render dashboard: New → Blueprint → connect this repo. Render reads
   `render.yaml` and provisions a free web service automatically.
3. Optionally set `YOUTUBE_API_KEY` / `ANTHROPIC_API_KEY` in the service's
   environment settings for live data / AI-generated content.
4. Open the `*.onrender.com` URL Render gives you — that works from any phone.

Note: the free tier's filesystem is ephemeral, so the SQLite DB (tracked
videos, cached niches) resets on redeploy/restart. Fine for testing; swap in a
persistent disk or external DB for real use.

**Railway / Fly.io:** both auto-detect the included `Dockerfile` — connect the
repo (Railway) or run `fly launch` (Fly) and it builds from that.

## API

- `GET  /api/health` — status + which data/content sources are active
- `GET  /api/niches?limit=15` — ranked niche opportunities
- `POST /api/niches/poll` — force a fresh niche poll
- `POST /api/content/generate` — `{niche_keyword, category, video_topic?}` → titles/description/tags/script/thumbnails
- `GET  /api/content` — previously generated content
- `POST /api/videos` — `{title, niche_keyword?, views?, estimated_revenue_usd?, actual_revenue_usd?}`
- `GET  /api/videos` — tracked videos
- `GET  /api/progress` — current month revenue vs. goal, plus gap-closing suggestions

## Tests

```bash
pytest tests/ -v
```
