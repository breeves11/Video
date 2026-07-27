# YouTube Niche & Content Engine

![Tests](https://github.com/breeves11/video/actions/workflows/tests.yml/badge.svg)

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
3. **Revenue tracking** (`backend/revenue.py`) — log published videos (title,
   publish date, views, estimated or actual revenue) and see progress for the
   *current calendar month* toward the goal, plus suggestions on which niches
   to publish more videos in to close the gap. Entries are currently manual —
   there's no automatic pull from YouTube Analytics/AdSense (that would need
   its own OAuth app and a monetization-scoped consent flow per channel,
   which is out of scope here; revenue numbers are only as accurate as what
   you enter).

By default the niche data is a deterministic estimator (no external API
needed). Set `YOUTUBE_API_KEY` to pull real recent-upload stats from the
YouTube Data API v3 instead. The assumed posting cadence used to project
monthly revenue defaults to 8 videos/month (`ASSUMED_VIDEOS_PER_MONTH`) and
can be overridden per-request via `?videos_per_month=` on `GET /api/niches`,
or live in the dashboard.

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

### Securing a public deploy

Once this is reachable from the internet, anyone with the link can call
`/api/content/generate` (burns your `ANTHROPIC_API_KEY` usage) or
`/api/niches/poll` (burns `YOUTUBE_API_KEY` quota — the default free quota is
10,000 units/day and a single poll uses roughly 130). Before sharing the URL
around, set **both** `APP_USERNAME` and `APP_PASSWORD` in the environment —
this turns on HTTP Basic Auth for the whole app (dashboard included). Leaving
either blank disables auth entirely, which is the default for local dev.

As defense in depth even with auth on, `/api/content/generate` and
`/api/niches/poll` are also rate-limited per IP (`RATE_LIMIT_PER_MINUTE`,
default 10/minute).

## API

- `GET    /api/health` — status + which data/content sources are active
- `GET    /api/niches?limit=15&videos_per_month=8` — ranked niche opportunities
- `POST   /api/niches/poll` — force a fresh niche poll (rate-limited)
- `POST   /api/content/generate` — `{niche_keyword, category, video_topic?}` → titles/description/tags/script/thumbnails (rate-limited)
- `GET    /api/content` — previously generated content
- `DELETE /api/content/{id}` — remove a generated-content entry
- `POST   /api/videos` — `{title, niche_keyword?, published_at?, views?, estimated_revenue_usd?, actual_revenue_usd?}` (`published_at` defaults to today; numeric fields must be ≥ 0)
- `GET    /api/videos` — tracked videos
- `DELETE /api/videos/{id}` — remove a tracked video
- `GET    /api/progress` — current calendar month's revenue vs. goal, plus gap-closing suggestions

## Tests

```bash
pytest tests/ -v
```
