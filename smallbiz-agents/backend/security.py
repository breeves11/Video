"""Optional HTTP Basic Auth (for public deploys) and a simple per-IP rate
limiter for endpoints that call paid/quota-limited external APIs or send
messages on the business's behalf.

Both are process-local and intended for a single-instance deployment, which
matches the rest of the app's scaling assumptions (in-memory scheduler,
SQLite).
"""

import base64
import secrets
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from . import config

# Webhook endpoints (Twilio, inbound-email parse providers) can't send Basic
# Auth credentials, so they're exempted from the auth middleware. Each is
# independently authenticated another way instead: the /api/phone/* routes
# here are exactly the ones protected by Twilio's own request signature
# (see twilio_validate.py), and /api/emails/inbound is protected by
# INBOUND_EMAIL_SECRET. Listed as an exact set (not a prefix) so that any
# *other* route added under /api/phone/ or /api/emails/ in the future --
# e.g. the dashboard's own /api/phone/simulate/* test-call endpoints --
# stays behind Basic Auth by default rather than silently inheriting the
# exemption.
_AUTH_EXEMPT_PATHS = {
    "/api/phone/voice",
    "/api/phone/gather",
    "/api/phone/recording",
    "/api/phone/transcription",
    "/api/phone/status",
    "/api/emails/inbound",
}


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not config.APP_USERNAME or not config.APP_PASSWORD:
            return await call_next(request)

        if request.url.path in _AUTH_EXEMPT_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if header.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
                username, _, password = decoded.partition(":")
            except Exception:
                username, password = "", ""

            if secrets.compare_digest(username, config.APP_USERNAME) and secrets.compare_digest(
                password, config.APP_PASSWORD
            ):
                return await call_next(request)

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Small Business AI Agents"'},
        )


_rate_buckets: dict = defaultdict(deque)


def rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_buckets[client_ip]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= config.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded, try again in a minute")
    bucket.append(now)


def verify_inbound_email_secret(request: Request) -> None:
    """Guards POST /api/emails/inbound, the one endpoint that's both
    unauthenticated (a provider webhook can't send Basic Auth) and capable
    of triggering an outbound send -- without this, anyone who finds the
    URL could get the app to auto-send mail to an arbitrary address using
    the business's SMTP account.
    """
    if not config.INBOUND_EMAIL_SECRET:
        return
    provided = request.headers.get("x-inbound-secret", "")
    if not secrets.compare_digest(provided, config.INBOUND_EMAIL_SECRET):
        raise HTTPException(status_code=403, detail="Invalid or missing inbound secret")
