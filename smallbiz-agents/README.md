# Small Business AI Agents

![Tests](https://github.com/breeves11/video/actions/workflows/smallbiz-agents-tests.yml/badge.svg)

An AI front-desk for small businesses: agents that triage and respond to
customer **emails** and **phone calls** so nothing sits unanswered. Runs
fully offline with deterministic fallbacks (no API keys required to try
it), and gets noticeably sharper once you add Claude, SMTP/IMAP, and
Twilio.

## The problems it targets

- **Slow email replies.** Every inbound email is classified (FAQ / quote
  request / complaint / scheduling / spam / other) and gets an AI-drafted
  reply immediately. Simple FAQs can auto-send; anything sensitive (a
  complaint, a quote, a scheduling request) is queued for a human to
  review and approve in one click.
- **Missed calls = lost leads.** The phone agent answers calls with a
  voice AI grounded on your FAQ, can resolve simple questions on the
  spot, and takes a voicemail (with transcript + AI summary) for anything
  that needs a human. If a call goes unanswered, it automatically texts
  the caller back so they're not left hanging.
- **Repeating the same answers.** A shared knowledge base (business FAQ)
  grounds both agents so answers stay consistent and don't hallucinate
  policies/prices you haven't actually entered.
- **After-hours coverage.** Both channels work around the clock without
  anyone on staff, and everything left for a human lands in one unified
  dashboard.

## What it does

1. **Email agent** (`backend/email_agent.py`) -- classifies inbound
   emails (`backend/classifier.py`), drafts a grounded reply
   (`backend/knowledge_base.py` for context, Claude when available,
   deterministic templates otherwise), and either auto-sends (SMTP) or
   queues it for approval based on per-category settings. Emails come in
   via a webhook (`POST /api/emails/inbound` -- compatible with inbound-
   parse providers like SendGrid/Postmark/Mailgun) or by polling a
   mailbox directly over IMAP (`backend/imap_client.py`,
   `backend/scheduler.py`), whichever fits your existing email setup.
2. **Phone agent** (`backend/phone_agent.py`) -- answers Twilio voice
   webhooks with TwiML (`backend/twiml.py`): greets the caller, listens
   for speech, classifies + answers using the same knowledge base, and
   either resolves simple FAQs on the spot or takes a voicemail (with
   Twilio's built-in transcription) for a callback. A call-status webhook
   detects missed calls (no-answer/busy/failed) and auto-texts the caller
   back (`backend/twilio_sms.py`) so a missed call isn't a lost lead.
3. **Knowledge base** (`backend/knowledge_base.py`) -- a simple FAQ store
   with keyword-overlap retrieval that grounds both agents' answers so
   they don't invent prices, policies, or hours you haven't told them.
4. **Dashboard** (`frontend/`) -- a unified inbox to review/edit/approve
   AI drafts before they send, a call log with transcripts/summaries and
   a callback flag, an FAQ editor, and settings for business info and
   per-category auto-send toggles. Includes built-in simulators (test
   email, test call) so you can try the whole flow without a real email
   provider or Twilio account connected yet.

Everything works with zero external services configured -- classification
falls back to keyword rules, replies fall back to templates grounded on
your FAQ, and sending is simply skipped (marked `queued_send_unconfigured`)
until you add SMTP/Twilio credentials.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optionally add ANTHROPIC_API_KEY / SMTP / IMAP / Twilio
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000 for the dashboard. Add a few FAQ entries, then
use the "Simulate an inbound email" and "Try the phone agent" panels to see
both agents in action immediately.

## Run with Docker (local)

```bash
cp .env.example .env
docker compose up --build
```

Open http://localhost:8000. Data persists in the `smallbiz_data` Docker
volume across restarts (`docker compose down -v` wipes it).

## Connecting it to real email and phone

**Email -- pick one:**
- *Inbound-parse webhook* (SendGrid, Postmark, Mailgun, etc.): point the
  provider's inbound webhook at `POST /api/emails/inbound` with
  `{from_address, subject, body}`. Fastest to set up, no polling delay.
- *IMAP polling*: set `IMAP_HOST` / `IMAP_USERNAME` / `IMAP_PASSWORD` in
  `.env`. The app polls for unread mail every `IMAP_POLL_INTERVAL_MINUTES`
  (default 5) and processes it the same way.

Either way, set `SMTP_HOST` / `SMTP_USERNAME` / `SMTP_PASSWORD` so approved
(or auto-sent) replies actually go out -- without SMTP configured, replies
are drafted and queued but marked `queued_send_unconfigured` since there's
nowhere to send them.

**Phone (Twilio):**
1. Buy a number in the [Twilio console](https://console.twilio.com).
2. Deploy this app somewhere with a public URL and set `PUBLIC_BASE_URL`
   to it (e.g. `https://yourapp.onrender.com`).
3. On the Twilio number's configuration page, set:
   - **A call comes in** → Webhook → `<PUBLIC_BASE_URL>/api/phone/voice` (HTTP POST)
   - **Call status changes** → `<PUBLIC_BASE_URL>/api/phone/status` (HTTP POST)
4. Set `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` so
   the missed-call text-back can actually send.

The `/api/phone/*` webhook endpoints are intentionally exempt from Basic
Auth (Twilio/inbound-parse providers can't send credentials) -- they only
ever create records or return TwiML, never expose existing data.

### Deploy (public URL)

**Render (no local tooling needed):** New → Blueprint → connect this repo;
Render reads `render.yaml` and provisions a free web service. Set the env
vars above (Anthropic/SMTP/IMAP/Twilio/auth) in the service's environment
settings, note the `*.onrender.com` URL it gives you, and use that as
`PUBLIC_BASE_URL` for the Twilio webhooks above.

**Railway / Fly.io:** both auto-detect the included `Dockerfile`.

Note: the free tier's filesystem is ephemeral, so the SQLite DB (inbox,
call log, FAQ, settings) resets on redeploy/restart. Fine for testing;
swap in a persistent disk or external DB for real use.

### Securing a public deploy

Once reachable from the internet, anyone with the link could read the
inbox/call log or trigger AI drafting. Set **both** `APP_USERNAME` and
`APP_PASSWORD` before sharing the URL around -- this turns on HTTP Basic
Auth for the dashboard and all `/api/*` routes except the Twilio/inbound-
email webhooks (which can't authenticate). As defense in depth, the
expensive/outbound-messaging endpoints are also rate-limited per IP
(`RATE_LIMIT_PER_MINUTE`, default 20/minute).

## API

- `GET    /api/health` -- status + which integrations are active
- `GET    /api/settings` / `PUT /api/settings` -- business name/hours/greetings, auto-send toggles
- `GET    /api/kb` / `POST /api/kb` / `PUT /api/kb/{id}` / `DELETE /api/kb/{id}` -- FAQ entries
- `POST   /api/emails/inbound` -- `{from_address, subject, body}` → classify + draft (+ auto-send if enabled)
- `GET    /api/emails?status=&limit=` -- inbox listing
- `GET    /api/emails/{id}` -- single email
- `POST   /api/emails/{id}/send` -- `{text?}` approve (optionally edited) and send
- `POST   /api/emails/{id}/dismiss` -- mark handled without sending
- `DELETE /api/emails/{id}`
- `POST   /api/emails/poll` -- force an immediate IMAP poll (rate-limited; 400 if IMAP isn't configured)
- `GET    /api/calls?handled=&limit=` -- call log
- `POST   /api/calls/{id}/handled` -- mark a call as followed up
- `POST   /api/phone/voice`, `/gather`, `/recording`, `/transcription`, `/status` -- Twilio webhooks (form-encoded)

## Tests

```bash
pytest tests/ -v
```

Tests run fully offline (no Anthropic/SMTP/IMAP/Twilio credentials needed)
by forcing every agent through its deterministic fallback path.
