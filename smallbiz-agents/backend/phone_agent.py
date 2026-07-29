"""Phone agent: answers inbound calls with an AI voice assistant grounded on
the business knowledge base, takes voicemail + a transcript/summary for
anything it can't resolve, and auto-texts back missed calls so no lead goes
completely unanswered.
"""

from dataclasses import dataclass
from typing import Optional

from . import calls_repo, classifier, knowledge_base, settings_repo, twiml, twilio_sms

_MISSED_STATUSES = {"no-answer", "busy", "failed"}

# Categories a caller might raise that the AI can fully resolve on the spot
# vs. ones that should always be routed to a human callback.
_RESOLVABLE_ON_CALL = {"faq"}


@dataclass
class SpokenResponse:
    text: str
    source: str


def _draft_spoken_response(speech_text: str, category: str) -> SpokenResponse:
    from . import llm_client

    kb_entries = knowledge_base.search(speech_text, limit=2)
    kb_context = knowledge_base.format_context(kb_entries)
    business_name = settings_repo.get("business_name")

    if llm_client.is_available():
        system = (
            f"You are a friendly phone receptionist AI for a small business called "
            f"'{business_name}'. Reply in 1-3 short spoken sentences, natural to say out "
            "loud. Never invent facts (prices, availability, policies) not given to you -- "
            "if unsure, say a team member will call back with details."
        )
        prompt = f"Caller said: \"{speech_text}\"\n"
        if kb_context:
            prompt += f"\nRelevant knowledge base entries:\n{kb_context}\n"
        prompt += "\nRespond with only what should be spoken to the caller."
        text = llm_client.generate_text(prompt, max_tokens=200, system=system)
        if text:
            return SpokenResponse(text=text, source="llm")

    if kb_entries:
        return SpokenResponse(text=kb_entries[0]["answer"], source="template")

    fallback = {
        "quote_request": "Thanks for asking about pricing! A team member will call you back with a quote.",
        "complaint": "I'm really sorry to hear that. A team member will call you back shortly to make this right.",
        "scheduling": "Happy to help get you scheduled! A team member will call back to confirm a time.",
        "spam": "Thanks for calling.",
        "other": "Thanks for calling! A team member will follow up with you shortly.",
    }
    return SpokenResponse(text=fallback.get(category, fallback["other"]), source="template")


def handle_incoming_call(call_sid: str, from_number: str, to_number: Optional[str]) -> str:
    calls_repo.upsert_call(call_sid, from_number, to_number, status="in_progress")
    greeting = settings_repo.get("voice_greeting")
    action_url = twiml.voice_url("/api/phone/gather")
    return twiml.gather_speech(greeting, action_url)


def handle_gather(call_sid: str, speech_result: str) -> str:
    speech_result = (speech_result or "").strip()
    if not speech_result:
        record_url = twiml.voice_url("/api/phone/recording")
        return twiml.say_and_offer_voicemail(
            "Sorry, I couldn't hear you clearly.", record_url, offer_voicemail=True,
            transcribe_callback_url=twiml.voice_url("/api/phone/transcription"),
        )

    result = classifier.classify(speech_result, channel="phone")
    spoken = _draft_spoken_response(speech_result, result.category)

    calls_repo.update_call(
        call_sid,
        transcript=speech_result,
        category=result.category,
        urgency=result.urgency,
        ai_response=spoken.text,
    )

    resolvable = result.category in _RESOLVABLE_ON_CALL and bool(
        knowledge_base.search(speech_result, limit=1)
    )
    if resolvable:
        calls_repo.update_call(call_sid, handled=1, status="completed")
        return twiml.say_and_offer_voicemail(spoken.text, "", offer_voicemail=False)

    calls_repo.update_call(call_sid, callback_requested=1, status="needs_callback")
    record_url = twiml.voice_url("/api/phone/recording")
    transcribe_url = twiml.voice_url("/api/phone/transcription")
    return twiml.say_and_offer_voicemail(
        spoken.text, record_url, offer_voicemail=True, transcribe_callback_url=transcribe_url
    )


def handle_recording(call_sid: str, recording_url: Optional[str]) -> str:
    if recording_url:
        calls_repo.update_call(call_sid, recording_url=recording_url, status="voicemail")
    return twiml.say_and_hangup("Thanks, we've got your message and will call you back soon.")


def handle_transcription(call_sid: str, transcription_text: Optional[str]) -> None:
    if not transcription_text:
        return
    result = classifier.classify(transcription_text, channel="phone")
    from . import llm_client

    summary = None
    if llm_client.is_available():
        summary = llm_client.generate_text(
            f"Summarize this voicemail transcript for a busy business owner in one short "
            f"sentence:\n\n{transcription_text}",
            max_tokens=120,
        )
    calls_repo.update_call(
        call_sid,
        transcript=transcription_text,
        ai_summary=summary or transcription_text[:200],
        category=result.category,
        urgency=result.urgency,
        callback_requested=1,
    )


def handle_status_callback(call_sid: str, from_number: str, to_number: Optional[str],
                            call_status: str) -> bool:
    """Handle a call-status webhook. Returns True if a missed-call text-back
    was sent."""
    if call_status not in _MISSED_STATUSES:
        return False

    calls_repo.upsert_call(call_sid, from_number, to_number, status="missed")
    calls_repo.update_call(call_sid, status="missed", callback_requested=1)

    business_name = settings_repo.get("business_name")
    business_hours = settings_repo.get("business_hours")
    message = (
        f"Hi, sorry we missed your call to {business_name}! We'll call you back soon. "
        f"Our hours are {business_hours}. Reply here if you'd like to leave a message now."
    )
    return twilio_sms.send_sms(from_number, message)
