"""Email agent: classifies inbound customer emails, drafts a grounded reply,
and either queues it for human approval or sends it automatically depending
on the business's per-category auto-send settings.
"""

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Optional

from . import classifier, config, emails_repo, knowledge_base, settings_repo

_CATEGORY_LABELS = {
    "faq": "a general question",
    "quote_request": "a pricing/quote request",
    "complaint": "a complaint",
    "scheduling": "a scheduling request",
    "spam": "spam",
    "other": "a general message",
}


@dataclass
class Draft:
    text: str
    source: str  # "llm" or "template"


def _draft_with_llm(subject: str, body: str, category: str, kb_context: str) -> Optional[str]:
    from . import llm_client

    if not llm_client.is_available():
        return None

    business_name = settings_repo.get("business_name")
    system = (
        f"You are a helpful, concise customer-support assistant for a small business called "
        f"'{business_name}'. Write email replies that are warm, professional, and brief "
        "(3-6 sentences). Never invent facts (prices, availability, policies) that aren't "
        "given to you in the knowledge base context -- if you don't know, say a team member "
        "will follow up with specifics. Sign off as 'The " + business_name + " Team'."
    )
    prompt = (
        f"Customer email (classified as {_CATEGORY_LABELS.get(category, 'a message')}):\n"
        f"Subject: {subject}\n\n{body}\n\n"
    )
    if kb_context:
        prompt += f"Relevant knowledge base entries:\n{kb_context}\n\n"
    prompt += "Write the reply email body only, no subject line."

    return llm_client.generate_text(prompt, max_tokens=500, system=system)


def _draft_with_template(subject: str, body: str, category: str, kb_entries: list) -> str:
    business_name = settings_repo.get("business_name")
    greeting = settings_repo.get("greeting_message")

    if category == "spam":
        return "(Flagged as likely spam -- no reply drafted.)"

    if kb_entries:
        answer_lines = "\n\n".join(f"- {e['answer']}" for e in kb_entries[:2])
        return (
            f"Hi,\n\n{greeting}\n\n{answer_lines}\n\n"
            f"Let us know if that answers your question, or if you'd like more detail.\n\n"
            f"The {business_name} Team"
        )

    if category == "quote_request":
        return (
            "Hi,\n\nThanks for your interest! We'd love to put together a quote for you. "
            "A team member will follow up shortly with pricing details once we've confirmed "
            "a few specifics about your request.\n\n"
            f"The {business_name} Team"
        )
    if category == "complaint":
        return (
            "Hi,\n\nWe're sorry to hear about your experience, and we take this seriously. "
            "A team member will personally follow up with you shortly to make this right.\n\n"
            f"The {business_name} Team"
        )
    if category == "scheduling":
        return (
            "Hi,\n\nThanks for reaching out to schedule! A team member will follow up shortly "
            "to confirm a time that works.\n\n"
            f"The {business_name} Team"
        )
    return (
        "Hi,\n\nThanks for reaching out. We've received your message and a team member will "
        "follow up shortly.\n\n"
        f"The {business_name} Team"
    )


def draft_reply(subject: str, body: str, category: str) -> Draft:
    kb_entries = knowledge_base.search(f"{subject}\n{body}", limit=3)
    kb_context = knowledge_base.format_context(kb_entries)

    llm_text = _draft_with_llm(subject, body, category, kb_context)
    if llm_text:
        return Draft(text=llm_text, source="llm")
    return Draft(text=_draft_with_template(subject, body, category, kb_entries), source="template")


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send via SMTP if configured. Returns True on (attempted) success."""
    if not config.smtp_configured():
        return False
    try:
        message = EmailMessage()
        message["From"] = config.SMTP_FROM_ADDRESS or config.SMTP_USERNAME
        message["To"] = to_address
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            if config.SMTP_USE_TLS:
                server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception:
        return False


def process_inbound_email(from_address: str, subject: str, body: str,
                           thread_id: Optional[str] = None) -> dict:
    """Classify + draft a reply for a new inbound email, auto-sending it if
    the category is configured for auto-send. Returns the saved email row.
    """
    contact_name, contact_email = parseaddr(from_address)
    contact_email = contact_email or from_address

    result = classifier.classify(f"{subject}\n{body}", channel="email")
    draft = draft_reply(subject, body, result.category)

    status = "pending"
    email_id = emails_repo.create_email(
        contact_email=contact_email,
        contact_name=contact_name or None,
        subject=subject,
        body=body,
        category=result.category,
        urgency=result.urgency,
        ai_draft=draft.text,
        ai_source=draft.source,
        status=status,
        thread_id=thread_id,
    )

    if result.category != "spam" and settings_repo.is_auto_send(result.category):
        approve_and_send(email_id)

    return emails_repo.get_email(email_id)


def approve_and_send(email_id: int, override_text: Optional[str] = None) -> dict:
    row = emails_repo.get_email(email_id)
    if row is None:
        raise ValueError("email not found")

    reply_text = override_text if override_text is not None else row["ai_draft"]
    reply_subject = f"Re: {row['subject']}" if row["subject"] else "Re: your message"

    sent = send_email(row["contact_email"], reply_subject, reply_text or "")
    new_status = "sent" if sent else "queued_send_unconfigured"
    emails_repo.update_status(email_id, new_status, ai_draft=reply_text, mark_sent=sent)
    return emails_repo.get_email(email_id)
