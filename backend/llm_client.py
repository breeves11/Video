"""Thin wrapper around the Anthropic API. Returns None on any failure or when
no API key is configured, so callers can fall back to the template generator.
"""

import os
from typing import Optional

from . import config

CONTENT_MODEL = os.getenv("CONTENT_MODEL", "claude-sonnet-5")

_client = None


def _get_client():
    global _client
    if _client is None and config.ANTHROPIC_API_KEY:
        import anthropic

        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def is_available() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def generate_text(prompt: str, max_tokens: int = 1500) -> Optional[str]:
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.messages.create(
            model=CONTENT_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()
    except Exception:
        return None
