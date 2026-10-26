"""Size limits shared by every inbound path (webhook, IMAP, phone).

Two tiers on purpose: the JSON API rejects absurd payloads outright (see the
Pydantic constraints in main.py), while anything that gets past that is
*trimmed* here rather than rejected -- a genuine but very long customer
email should still land in the inbox, not bounce back to a provider that
retries and eventually drops it.
"""

MAX_SUBJECT_CHARS = 998          # RFC 5322 line-length limit
MAX_STORED_BODY_CHARS = 50_000   # what we keep in the DB / show in the inbox
MAX_LLM_INPUT_CHARS = 6_000      # what we send to the model per message
MAX_ATTACHMENTS = 50
MAX_FILENAME_CHARS = 255

_TRUNCATION_MARKER = "\n[... truncated]"


def clip(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - len(_TRUNCATION_MARKER))] + _TRUNCATION_MARKER


def clip_attachments(names) -> list:
    cleaned = [clip(str(n).strip(), MAX_FILENAME_CHARS) for n in (names or []) if str(n).strip()]
    return cleaned[:MAX_ATTACHMENTS]
