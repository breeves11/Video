"""Optional IMAP polling: pulls unread emails from a configured mailbox and
feeds them into the email agent. Purely additive to the inbound-parse
webhook (POST /api/emails/inbound) -- use whichever fits the business's
existing email provider, or both.
"""

import email
import imaplib
from email.header import decode_header

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


def _extract_body(message: email.message.Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                try:
                    return part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
                except Exception:
                    continue
        return ""
    try:
        return message.get_payload(decode=True).decode(
            message.get_content_charset() or "utf-8", errors="replace"
        )
    except Exception:
        return str(message.get_payload())


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
            raw = msg_data[0][1]
            message = email.message_from_bytes(raw)

            from_address = _decode(message.get("From", ""))
            subject = _decode(message.get("Subject", "(no subject)"))
            thread_id = message.get("Message-ID")
            body = _extract_body(message)

            email_agent.process_inbound_email(from_address, subject, body, thread_id=thread_id)
            processed += 1
    finally:
        try:
            connection.logout()
        except Exception:
            pass

    return processed
