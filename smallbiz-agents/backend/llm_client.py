"""Thin wrapper around the Anthropic API. Returns None on any failure or when
no API key is configured, so callers can fall back to deterministic,
template/rule-based behavior -- the app stays fully usable without an API
key, just less fluent.
"""

import os
from typing import Optional

from . import config

AGENT_MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-5")

_client = None


def _get_client():
    global _client
    if _client is None and config.ANTHROPIC_API_KEY:
        import anthropic

        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def is_available() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def generate_text(prompt: str, max_tokens: int = 800, system: Optional[str] = None) -> Optional[str]:
    client = _get_client()
    if client is None:
        return None
    try:
        kwargs = dict(
            model=AGENT_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)
        return "".join(block.text for block in response.content if block.type == "text").strip()
    except Exception:
        return None
