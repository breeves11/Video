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
   HTML-only emails are converted to text. Attachment *names* are recorded
   and shown in the inbox; the agent can't read attachment contents, so an
   email with attachments is never auto-sent, and the AI is told not to
   claim it reviewed them. Very long emails are trimmed (`backend/limits.py`)
   rather than rejected.
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
   AI drafts before they send, a call log with transcripts, summaries,
   playable voicemail recordings, and a callback flag, an editable FAQ
   editor, and settings for business info and per-category auto-send
   toggles. Includes built-in simulators (test email, test call) so you
   can try the whole flow without a real email provider or Twilio account
   connected yet -- these post to separate, Basic-Auth-protected endpoints
   (`/api/emails/simulate`, `/api/phone/simulate/*`) so they keep working
   even once the real webhooks are locked down (see Security, below).
5. **Contacts** (Contacts tab; `backend/contacts.py`, `GET /api/contacts`)
   -- everyone who has emailed or called, built automatically from the
   inbox and call log: channels used, interaction count, open items, last
   contact.
6. **AI disclosure** (Settings tab, on by default) -- the phone agent opens
   with "You've reached the automated assistant for <business>", and
   drafted emails end with a one-line AI note. Some jurisdictions require
   telling customers they're dealing with an automated system; switch it
   off only after confirming that's allowed where the business operates.

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

Open http://localhost:8001 (the compose file maps to 8001 so it doesn't
collide with the unrelated app that also lives in this repo, which uses
8000). Data persists in the `smallbiz_data` Docker volume across restarts
(`docker compose down -v` wipes it). The container restarts automatically
after a crash or reboot (`restart: unless-stopped`; enable "start Docker on
login/boot" on the host too).

## Connecting it to real email and phone

**Email -- pick one:**
- *Inbound-parse webhook* (SendGrid, Postmark, Mailgun, etc.): point the
  provider's inbound webhook at `POST /api/emails/inbound` with
  `{from_address, subject, body}` and an `X-Inbound-Secret` header matching
  `INBOUND_EMAIL_SECRET` (see Security, below -- most providers don't speak
  this exact shape natively, so you'll typically need a small relay/mapping
  step in front of it). Fastest to set up, no polling delay.
- *IMAP polling*: set `IMAP_HOST` / `IMAP_USERNAME` / `IMAP_PASSWORD` in
  `.env`. The app polls for unread mail every `IMAP_POLL_INTERVAL_MINUTES`
  (default 5) and processes it the same way. Check the Settings tab's
  integration status panel (or `GET /api/health`) after setup -- it shows
  the timestamp and outcome of the last poll, so a bad password or network
  issue doesn't just fail silently.

Either way, set `SMTP_HOST` / `SMTP_USERNAME` / `SMTP_PASSWORD` so approved
(or auto-sent) replies actually go out. An email's status distinguishes
*why* it didn't send: `queued_send_unconfigured` means SMTP isn't set up
yet, `send_failed` means SMTP is configured but the send itself failed
(bad password, provider outage, etc.) -- worth checking server logs when
you see the latter. Either status can be retried the same way `pending`
can, from the Inbox tab.

**Phone (Twilio):**
1. Buy a number in the [Twilio console](https://console.twilio.com).
2. Deploy this app somewhere with a public URL and set `PUBLIC_BASE_URL`
   to it (e.g. `https://yourapp.onrender.com`).
3. On the Twilio number's configuration page, set:
   - **A call comes in** → Webhook → `<PUBLIC_BASE_URL>/api/phone/voice` (HTTP POST)
   - **Call status changes** → `<PUBLIC_BASE_URL>/api/phone/status` (HTTP POST)
4. Set `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` so
   the missed-call text-back can actually send, and so the webhooks above
   start requiring a valid Twilio signature (see Security, below).

The five `/api/phone/*` webhook routes are exempt from Basic Auth (Twilio
can't send credentials), but each request is independently verified
against Twilio's own request signature once `TWILIO_AUTH_TOKEN` is set --
see Security. The dashboard's "Try the phone agent" simulator posts to a
separate pair of routes (`/api/phone/simulate/voice`, `/api/phone/simulate/gather`)
that stay behind Basic Auth instead, so it keeps working after you lock
the real webhooks down.

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
inbox/call log, trigger AI drafting, or -- worse -- abuse the two webhook
routes that can't use Basic Auth to send real messages on the business's
behalf. Each layer below closes one specific hole; all three matter before
a real customer's Twilio number and mailbox are wired in:

1. **Dashboard + API:** set **both** `APP_USERNAME` and `APP_PASSWORD`.
   This turns on HTTP Basic Auth for the dashboard and every `/api/*`
   route except the six webhook routes below. Setting only one of the two
   leaves auth silently off -- the app logs a startup warning and
   `GET /api/health` reports `auth_misconfigured: true` if that happens.
2. **`/api/phone/*` (the five real Twilio webhooks):** set
   `TWILIO_AUTH_TOKEN` (and `PUBLIC_BASE_URL`, so the app validates against
   the same URL Twilio signed rather than whatever a reverse proxy makes
   the request look like internally). Once set, every request must carry
   a valid `X-Twilio-Signature` or it's rejected with `403` -- this is
   what stops someone from forging a missed-call event to trigger a real,
   billed SMS to an arbitrary number. Leaving it unset is only reasonable
   before you've bought a Twilio number at all.
3. **`/api/emails/inbound` (the real inbound-email webhook):** set
   `INBOUND_EMAIL_SECRET` and configure your email provider to send it
   back as an `X-Inbound-Secret` header. Without this, anyone who finds
   the URL can get the app to auto-send mail to an address of their
   choosing using the business's SMTP account.

As defense in depth on top of all three, the expensive/outbound-messaging
endpoints (including all six webhook routes) are also rate-limited per IP
(`RATE_LIMIT_PER_MINUTE`, default 20/minute) -- note this buckets by
source IP, so a very high call volume through Twilio's shared edge IPs
could in theory hit the same bucket; raise it if a real customer's normal
traffic starts tripping it.

## Going live

**1. Run the preflight check** with the deployment's real environment:

```bash
python scripts/preflight.py          # configuration: auth, secrets, URLs, storage, FAQ
python scripts/preflight.py --live   # + SMTP/IMAP logins, Twilio account, the Twilio
                                     #   number's webhook URLs, public URL, Anthropic key
# in Docker: docker compose exec app python scripts/preflight.py --live
```

It prints PASS/WARN/FAIL per item and exits non-zero on any FAIL, so it
can gate a deploy. `--live` sends no email, SMS, or calls -- it logs in and
reads configuration only. Notably, it confirms the Twilio number's "A call
comes in" and status-callback URLs actually point at this deployment,
which is the easiest setup step to get subtly wrong.

**2. Schedule backups.** The SQLite file is the only copy of every email,
call transcript, and FAQ entry:

```bash
python scripts/backup_db.py --dest /path/on/other/storage --keep 14
# cron, nightly:  15 3 * * * cd /path/to/smallbiz-agents && .venv/bin/python scripts/backup_db.py --dest /mnt/backups
# Docker:         docker compose exec app python scripts/backup_db.py --dest /app/backups   (lands in ./backups on the host)
```

It uses SQLite's online backup API (safe while the app is running) and
prunes old snapshots. A backup on the same disk only protects against
mistakes, not disk loss -- send it somewhere else.

**3. Place a real test call and a real test email** before the business
announces anything: call the number from your own phone, send an email to
the connected inbox, and approve a reply from the dashboard.

**4. Account/ops items** no code can do for you, per business:

- **Twilio A2P 10DLC registration** -- U.S. carriers filter SMS from
  unregistered business use cases, so the missed-call text-back won't
  reliably deliver until it's approved. This can take days: start it first.
- **Email deliverability (SPF/DKIM/DMARC)** for the domain
  `SMTP_FROM_ADDRESS` uses, or AI-drafted replies are likely to land in
  spam -- which looks like the agent is broken when it isn't.
- **AI disclosure** -- on by default (see "What it does"); confirm with
  whoever handles compliance before switching it off.
- **Data retention / privacy** -- there's no automatic retention policy or
  bulk "delete everything for this contact" tool yet; deletion is per
  email/call. Decide what the business's privacy policy commits to before
  customer PII (emails, phone numbers, voicemail transcripts) accumulates.
- **Persistent storage** -- the included `render.yaml` uses Render's free
  plan with the database in `/tmp`, which is wiped on every deploy. For a
  real customer, use a paid instance with the disk block uncommented (or
  any host with a persistent volume).

## API

- `GET    /api/health` -- status + which integrations are active, last IMAP poll outcome, auth misconfiguration warning
- `GET    /api/settings` / `PUT /api/settings` -- business name/hours/greetings, auto-send toggles, `ai_disclosure`
- `GET    /api/kb` / `POST /api/kb` / `PUT /api/kb/{id}` / `DELETE /api/kb/{id}` -- FAQ entries
- `GET    /api/contacts?limit=` -- per-customer rollup derived from email + call history
- `POST   /api/emails/inbound` -- real webhook; requires `X-Inbound-Secret` if `INBOUND_EMAIL_SECRET` is set. `{from_address, subject, body, thread_id?, attachments?: [filename, ...]}` → classify + draft (+ auto-send if enabled and there are no attachments). Deduplicated on `thread_id` when provided. Absurd payloads (e.g. body over 500k chars) get a 422; long-but-real ones are trimmed.
- `POST   /api/emails/simulate` -- same body/behavior, for the dashboard's own test panel; Basic-Auth protected instead of secret-protected
- `GET    /api/emails?status=&limit=` -- inbox listing
- `GET    /api/emails/{id}` -- single email
- `POST   /api/emails/{id}/send` -- `{text?}` approve (optionally edited) and send; resulting status is `sent`, `queued_send_unconfigured`, or `send_failed`
- `POST   /api/emails/{id}/dismiss` -- mark handled without sending
- `DELETE /api/emails/{id}`
- `POST   /api/emails/poll` -- force an immediate IMAP poll (rate-limited; 400 if IMAP isn't configured, 502 if the poll itself failed)
- `GET    /api/calls?handled=&limit=` -- call log
- `POST   /api/calls/{id}/handled` -- mark a call as followed up
- `GET    /api/calls/{id}/recording` -- proxies the voicemail audio from Twilio (server-side credentials, so the browser never needs them)
- `POST   /api/phone/voice`, `/gather`, `/recording`, `/transcription`, `/status` -- real Twilio webhooks (form-encoded); require a valid `X-Twilio-Signature` once `TWILIO_AUTH_TOKEN` is set
- `POST   /api/phone/simulate/voice`, `/api/phone/simulate/gather` -- same behavior, for the dashboard's "Try the phone agent" panel; Basic-Auth protected instead of signature-protected

## Tests

```bash
pytest tests/ -v
```

Tests run fully offline (no Anthropic/SMTP/IMAP/Twilio credentials needed)
by forcing every agent through its deterministic fallback path.
