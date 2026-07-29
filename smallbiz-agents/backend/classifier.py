"""Shared message classification used by both the email and phone agents.

Categories: faq, quote_request, complaint, scheduling, spam, other
Urgency: low, medium, high

Tries the LLM first (structured JSON) and falls back to a deterministic
keyword classifier on any failure or when no API key is configured, so
classification always works.
"""

import json
import re
from dataclasses import dataclass

from . import llm_client

CATEGORIES = ("faq", "quote_request", "complaint", "scheduling", "spam", "other")
URGENCIES = ("low", "medium", "high")

_KEYWORDS = {
    "complaint": [
        "refund", "complain", "unhappy", "disappointed", "terrible", "awful",
        "broken", "damaged", "wrong", "mistake", "unacceptable", "angry",
        "cancel my", "not working", "worst", "furious", "scam",
    ],
    "quote_request": [
        "quote", "estimate", "price", "pricing", "cost", "how much",
        "proposal", "bid", "invoice me", "budget",
    ],
    "scheduling": [
        "schedule", "appointment", "book", "booking", "reschedule",
        "available", "availability", "meet", "meeting", "calendar", "visit",
    ],
    "spam": [
        "unsubscribe", "seo services", "backlink", "crypto", "casino",
        "viagra", "click here to win", "make money fast",
    ],
    "faq": [
        "hours", "open", "location", "address", "website", "do you offer",
        "what is", "how do i", "how does", "policy", "warranty",
    ],
}

_URGENT_WORDS = [
    "urgent", "asap", "emergency", "immediately", "right now", "today",
    "furious", "lawsuit", "lawyer", "unsafe", "leak", "fire", "flood",
    "not working at all", "down", "outage",
]


@dataclass
class Classification:
    category: str
    urgency: str
    source: str  # "llm" or "rules"


def _rule_based(text: str) -> Classification:
    lowered = text.lower()

    best_category = "other"
    best_hits = 0
    for category, words in _KEYWORDS.items():
        hits = sum(1 for w in words if w in lowered)
        if hits > best_hits:
            best_hits = hits
            best_category = category

    urgency = "medium" if any(w in lowered for w in _URGENT_WORDS) else "low"
    if best_category == "complaint" and urgency == "low":
        urgency = "medium"
    if best_category == "complaint" and any(w in lowered for w in ("lawsuit", "lawyer", "unsafe")):
        urgency = "high"
    if best_category == "spam":
        urgency = "low"

    return Classification(category=best_category, urgency=urgency, source="rules")


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found")
    return json.loads(match.group(0))


def classify(text: str, channel: str = "email") -> Classification:
    text = (text or "").strip()
    if not text:
        return Classification(category="other", urgency="low", source="rules")

    if llm_client.is_available():
        prompt = (
            f"Classify this inbound {channel} message from a customer of a small "
            "business. Respond with ONLY a JSON object, no other text, in the form "
            '{"category": "<one of faq|quote_request|complaint|scheduling|spam|other>", '
            '"urgency": "<one of low|medium|high>"}.\n\n'
            f"Message:\n{text[:4000]}"
        )
        raw = llm_client.generate_text(prompt, max_tokens=100)
        if raw:
            try:
                parsed = _extract_json(raw)
                category = str(parsed.get("category", "")).strip().lower()
                urgency = str(parsed.get("urgency", "")).strip().lower()
                if category in CATEGORIES and urgency in URGENCIES:
                    return Classification(category=category, urgency=urgency, source="llm")
            except Exception:
                pass

    return _rule_based(text)
