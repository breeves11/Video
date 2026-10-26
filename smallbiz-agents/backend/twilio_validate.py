"""Validates that a webhook request actually came from Twilio, using
Twilio's request-signing scheme (HMAC-SHA1 of the full URL + sorted POST
params, keyed by the account auth token). Implemented by hand instead of
pulling in the `twilio` SDK for one check.

Without this, anyone who finds a deployment's URL could POST directly to
the phone webhooks -- e.g. faking a missed-call status to trigger a real,
billed SMS text-back to an arbitrary number.
"""

import base64
import hashlib
import hmac
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, Request

from . import config


def compute_signature(auth_token: str, url: str, params: dict) -> str:
    data = url + "".join(f"{key}{value}" for key, value in sorted(params.items()))
    digest = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def _webhook_url(request: Request) -> str:
    # Prefer the configured public URL over the request's own view of
    # itself: behind a reverse proxy (Render, Railway, etc.) the app
    # typically sees plain http even though Twilio signed the https URL
    # you configured in the console, which would otherwise make every
    # signature check fail.
    if config.PUBLIC_BASE_URL:
        query = f"?{request.url.query}" if request.url.query else ""
        return f"{config.PUBLIC_BASE_URL}{request.url.path}{query}"
    return str(request.url)


def _url_variants(url: str) -> list:
    """The URL with and without its default port. Twilio doesn't sign
    consistently on this point, so its official validator accepts either --
    checking only one form would reject some genuine calls."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        return [url, urlunsplit(parts._replace(netloc=host))]
    default_port = 443 if parts.scheme == "https" else 80
    return [url, urlunsplit(parts._replace(netloc=f"{parts.netloc}:{default_port}"))]


def is_valid_signature(auth_token: str, url: str, params: dict, signature: str) -> bool:
    if not signature:
        return False
    return any(
        hmac.compare_digest(compute_signature(auth_token, variant, params), signature)
        for variant in _url_variants(url)
    )


async def verify_twilio_signature(request: Request) -> None:
    if not config.TWILIO_AUTH_TOKEN:
        # No real Twilio integration configured -- nothing to validate
        # against, and no real webhook URL has been given to Twilio for
        # an attacker to have found either.
        return

    signature = request.headers.get("x-twilio-signature", "")
    form = await request.form()
    if not is_valid_signature(config.TWILIO_AUTH_TOKEN, _webhook_url(request), dict(form), signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
