import logging
from contextlib import asynccontextmanager
from typing import Optional

import requests
from fastapi import Depends, FastAPI, Form, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import (
    calls_repo,
    config,
    contacts,
    db,
    email_agent,
    emails_repo,
    knowledge_base,
    llm_client,
    phone_agent,
    scheduler,
    settings_repo,
)
from .security import BasicAuthMiddleware, rate_limit, verify_inbound_email_secret
from .twilio_validate import verify_twilio_signature

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if bool(config.APP_USERNAME) != bool(config.APP_PASSWORD):
        logger.warning(
            "Only one of APP_USERNAME/APP_PASSWORD is set -- Basic Auth stays OFF until "
            "both are set. If you meant to password-protect this deployment, it is "
            "currently wide open."
        )
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="Small Business AI Agents", lifespan=lifespan)
app.add_middleware(BasicAuthMiddleware)


# --- Schemas -----------------------------------------------------------

class InboundEmailRequest(BaseModel):
    from_address: str
    subject: str = ""
    body: str = ""
    thread_id: Optional[str] = None


class EmailEditRequest(BaseModel):
    text: Optional[str] = None


class KBEntryRequest(BaseModel):
    question: str
    answer: str
    category: str = "general"


class KBEntryUpdateRequest(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    business_name: Optional[str] = None
    business_hours: Optional[str] = None
    greeting_message: Optional[str] = None
    voice_greeting: Optional[str] = None
    auto_send: Optional[dict] = None


# --- Health / settings ---------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ai_agent_enabled": llm_client.is_available(),
        "smtp_configured": config.smtp_configured(),
        "imap_configured": config.imap_configured(),
        "imap_last_poll": scheduler.last_poll_status() if config.imap_configured() else None,
        "twilio_configured": config.twilio_configured(),
        "inbound_email_secret_configured": bool(config.INBOUND_EMAIL_SECRET),
        "auth_enabled": bool(config.APP_USERNAME and config.APP_PASSWORD),
        "auth_misconfigured": bool(config.APP_USERNAME) != bool(config.APP_PASSWORD),
    }


@app.get("/api/settings")
def get_settings():
    return settings_repo.all_settings()


@app.put("/api/settings")
def update_settings(req: SettingsUpdateRequest):
    values = {k: v for k, v in req.model_dump().items() if v is not None}
    return settings_repo.update_many(values)


# --- Knowledge base --------------------------------------------------------

@app.get("/api/kb")
def list_kb(category: Optional[str] = None):
    return {"entries": knowledge_base.list_entries(category=category)}


@app.post("/api/kb")
def create_kb(req: KBEntryRequest):
    entry_id = knowledge_base.add_entry(req.question, req.answer, req.category)
    return {"id": entry_id}


@app.put("/api/kb/{entry_id}")
def edit_kb(entry_id: int, req: KBEntryUpdateRequest):
    if not knowledge_base.update_entry(entry_id, req.question, req.answer, req.category):
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"updated": entry_id}


@app.delete("/api/kb/{entry_id}")
def remove_kb(entry_id: int):
    if not knowledge_base.delete_entry(entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"deleted": entry_id}


# --- Contacts (derived from email + call history, no separate table) -----

@app.get("/api/contacts")
def list_contacts(limit: int = 100):
    return {"contacts": contacts.list_contacts(limit=limit)}


# --- Email agent -------------------------------------------------------

@app.post("/api/emails/inbound", dependencies=[Depends(rate_limit), Depends(verify_inbound_email_secret)])
def inbound_email(req: InboundEmailRequest):
    return email_agent.process_inbound_email(req.from_address, req.subject, req.body, req.thread_id)


@app.post("/api/emails/simulate", dependencies=[Depends(rate_limit)])
def simulate_inbound_email(req: InboundEmailRequest):
    """Dashboard-only equivalent of /api/emails/inbound, used by the 'Simulate
    an inbound email' panel. Kept separate so the real webhook can require
    INBOUND_EMAIL_SECRET without breaking the in-dashboard demo, and so this
    path stays behind Basic Auth like the rest of the dashboard.
    """
    return email_agent.process_inbound_email(req.from_address, req.subject, req.body, req.thread_id)


@app.get("/api/emails")
def list_emails(status: Optional[str] = None, limit: int = 50):
    return {"emails": emails_repo.list_emails(status=status, limit=limit)}


@app.get("/api/emails/{email_id}")
def get_email(email_id: int):
    row = emails_repo.get_email(email_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return row


@app.post("/api/emails/{email_id}/send", dependencies=[Depends(rate_limit)])
def send_email(email_id: int, req: EmailEditRequest):
    try:
        return email_agent.approve_and_send(email_id, override_text=req.text)
    except ValueError:
        raise HTTPException(status_code=404, detail="Email not found")


@app.post("/api/emails/{email_id}/dismiss")
def dismiss_email(email_id: int):
    if not emails_repo.update_status(email_id, "dismissed"):
        raise HTTPException(status_code=404, detail="Email not found")
    return emails_repo.get_email(email_id)


@app.delete("/api/emails/{email_id}")
def delete_email(email_id: int):
    if not emails_repo.delete_email(email_id):
        raise HTTPException(status_code=404, detail="Email not found")
    return {"deleted": email_id}


@app.post("/api/emails/poll", dependencies=[Depends(rate_limit)])
def poll_mailbox():
    if not config.imap_configured():
        raise HTTPException(status_code=400, detail="IMAP is not configured")
    count = scheduler.poll_mailbox()
    status = scheduler.last_poll_status()
    if not status["success"]:
        raise HTTPException(status_code=502, detail=f"IMAP poll failed: {status['error']}")
    return {"processed": count}


# --- Calls ---------------------------------------------------------------

@app.get("/api/calls")
def list_calls(handled: Optional[bool] = None, limit: int = 50):
    return {"calls": calls_repo.list_calls(handled=handled, limit=limit)}


@app.post("/api/calls/{call_id}/handled")
def mark_call_handled(call_id: int):
    if not calls_repo.mark_handled(call_id, True):
        raise HTTPException(status_code=404, detail="Call not found")
    return {"handled": call_id}


@app.get("/api/calls/{call_id}/recording")
def get_call_recording(call_id: int):
    """Proxies the voicemail audio from Twilio using server-side credentials,
    rather than sending a raw Twilio recording URL (which requires Twilio
    account auth to fetch) to the browser."""
    call = calls_repo.get_call_by_id(call_id)
    if call is None or not call.get("recording_url"):
        raise HTTPException(status_code=404, detail="Recording not found")
    if not config.twilio_configured():
        raise HTTPException(status_code=400, detail="Twilio is not configured")

    try:
        response = requests.get(
            call["recording_url"],
            auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
            timeout=15,
        )
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Failed to fetch recording from Twilio")

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch recording from Twilio")
    return Response(content=response.content, media_type="audio/mpeg")


# --- Twilio voice webhooks (form-encoded). Unauthenticated by design --
# Twilio can't send Basic Auth credentials -- but every route below is
# individually protected by Twilio's own request signature whenever
# TWILIO_AUTH_TOKEN is configured (see twilio_validate.py and
# security.py's _AUTH_EXEMPT_PATHS). ---------------------------------------

_twilio_deps = [Depends(rate_limit), Depends(verify_twilio_signature)]


@app.post("/api/phone/voice", dependencies=_twilio_deps)
def phone_voice(CallSid: str = Form(...), From: str = Form("unknown"), To: str = Form(None)):
    twiml_xml = phone_agent.handle_incoming_call(CallSid, From, To)
    return Response(content=twiml_xml, media_type="application/xml")


@app.post("/api/phone/gather", dependencies=_twilio_deps)
def phone_gather(CallSid: str = Form(...), SpeechResult: str = Form("")):
    twiml_xml = phone_agent.handle_gather(CallSid, SpeechResult)
    return Response(content=twiml_xml, media_type="application/xml")


@app.post("/api/phone/recording", dependencies=_twilio_deps)
def phone_recording(CallSid: str = Form(...), RecordingUrl: str = Form(None)):
    twiml_xml = phone_agent.handle_recording(CallSid, RecordingUrl)
    return Response(content=twiml_xml, media_type="application/xml")


@app.post("/api/phone/transcription", dependencies=_twilio_deps)
def phone_transcription(CallSid: str = Form(...), TranscriptionText: str = Form(None)):
    phone_agent.handle_transcription(CallSid, TranscriptionText)
    return Response(content="", media_type="application/xml")


@app.post("/api/phone/status", dependencies=_twilio_deps)
def phone_status(CallSid: str = Form(...), From: str = Form("unknown"), To: str = Form(None),
                  CallStatus: str = Form("")):
    phone_agent.handle_status_callback(CallSid, From, To, CallStatus)
    return Response(content="", media_type="application/xml")


# --- Phone simulator (dashboard-only, "Try the phone agent") -------------
# Mirrors the Twilio webhooks above but stays behind Basic Auth (it is NOT
# in security.py's exempt path list) instead of a Twilio signature, since
# these calls come from the dashboard's own browser session, not Twilio.

@app.post("/api/phone/simulate/voice", dependencies=[Depends(rate_limit)])
def phone_simulate_voice(CallSid: str = Form(...), From: str = Form("unknown")):
    twiml_xml = phone_agent.handle_incoming_call(CallSid, From, None)
    return Response(content=twiml_xml, media_type="application/xml")


@app.post("/api/phone/simulate/gather", dependencies=[Depends(rate_limit)])
def phone_simulate_gather(CallSid: str = Form(...), SpeechResult: str = Form("")):
    twiml_xml = phone_agent.handle_gather(CallSid, SpeechResult)
    return Response(content=twiml_xml, media_type="application/xml")


app.mount("/", StaticFiles(directory=str(config.BASE_DIR / "frontend"), html=True), name="frontend")
