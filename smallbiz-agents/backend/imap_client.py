"""Optional IMAP polling: pulls unread emails from a configured mailbox and
feeds them into the email agent. Purely additive to the inbound-parse
webhook (POST /api/emails/inbound) -- use whichever fits the business's
existing email provider, or both.
"""

import email
import imaplib
import re
from email.header import decode_header
from html.parser import HTMLParser

from . import config, email_agent


def _decode(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = ""
    for text, charset in parts:
        if isinstance(text, bytes):
            decoded += text.decode(charset or "utf-8", errors="replace")
        else:
            decoded += text
    return decoded


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "head"}
    _BREAKS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "blockquote"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html or "")
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _decode_part(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def extract_body(message: email.message.Message) -> str:
    """Prefer the text/plain part; fall back to text/html with tags stripped,
    since plenty of real-world mail (newsletters, many phone mail apps) is
    sent HTML-only and would otherwise arrive with an empty body."""
    parts = message.walk() if message.is_multipart() else [message]
    html_fallback = ""
    for part in parts:
        if part.get_filename() or part.get_content_maintype() == "multipart":
            continue
        content_type = part.get_content_type()
        try:
            if content_type == "text/plain":
                return _decode_part(part)
            if content_type == "text/html" and not html_fallback:
                html_fallback = html_to_text(_decode_part(part))
        except Exception:
            continue
    return html_fallback


def extract_attachments(message: email.message.Message) -> list:
    return [_decode(part.get_filename()) for part in message.walk() if part.get_filename()]


def poll_inbox() -> int:
    """Fetch and process unread messages. Returns the count processed."""
    if not config.imap_configured():
        return 0

    processed = 0
    connection = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
    try:
        connection.login(config.IMAP_USERNAME, config.IMAP_PASSWORD)
        connection.select("INBOX")
        status, data = connection.search(None, "UNSEEN")
        if status != "OK":
            return 0

        for msg_id in data[0].split():
            status, msg_data = connection.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue
            message = email.message_from_bytes(msg_data[0][1])

            email_agent.process_inbound_email(
                _decode(message.get("From", "")),
                _decode(message.get("Subject", "(no subject)")),
                extract_body(message),
                thread_id=message.get("Message-ID"),
                attachments=extract_attachments(message),
            )
            processed += 1
    finally:
        try:
            connection.logout()
        except Exception:
            pass

    return processed
