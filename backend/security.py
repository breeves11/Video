"""Optional HTTP Basic Auth (for public deploys) and a simple per-IP rate
limiter for the endpoints that call paid/quota-limited external APIs.

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


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not config.APP_USERNAME or not config.APP_PASSWORD:
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
            headers={"WWW-Authenticate": 'Basic realm="YouTube Niche Engine"'},
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
