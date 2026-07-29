from backend import calls_repo, knowledge_base, phone_agent


def test_incoming_call_creates_record_and_gathers_speech():
    twiml = phone_agent.handle_incoming_call("CA123", "+15551234567", "+15559999999")
    assert "<Gather" in twiml
    assert "<Response>" in twiml

    call = calls_repo.get_call("CA123")
    assert call is not None
    assert call["from_number"] == "+15551234567"
    assert call["status"] == "in_progress"


def test_gather_faq_with_kb_match_resolves_without_voicemail():
    knowledge_base.add_entry("What are your hours?", "We're open 9am-5pm Monday to Friday.")
    phone_agent.handle_incoming_call("CA200", "+15551112222", None)

    twiml = phone_agent.handle_gather("CA200", "What are your hours?")
    assert "<Record" not in twiml
    assert "<Hangup" in twiml

    call = calls_repo.get_call("CA200")
    assert call["category"] == "faq"
    assert call["handled"] == 1


def test_gather_complaint_offers_voicemail_and_flags_callback():
    phone_agent.handle_incoming_call("CA300", "+15553334444", None)
    twiml = phone_agent.handle_gather("CA300", "This is unacceptable, I want a refund, terrible service")

    assert "<Record" in twiml
    call = calls_repo.get_call("CA300")
    assert call["category"] == "complaint"
    assert call["callback_requested"] == 1
    assert call["status"] == "needs_callback"


def test_gather_empty_speech_offers_voicemail():
    phone_agent.handle_incoming_call("CA400", "+15550000000", None)
    twiml = phone_agent.handle_gather("CA400", "")
    assert "<Record" in twiml


def test_recording_stores_url_and_hangs_up():
    phone_agent.handle_incoming_call("CA500", "+15551239876", None)
    twiml = phone_agent.handle_recording("CA500", "https://api.twilio.com/recording123.mp3")
    assert "<Hangup" in twiml
    call = calls_repo.get_call("CA500")
    assert call["recording_url"] == "https://api.twilio.com/recording123.mp3"
    assert call["status"] == "voicemail"


def test_transcription_stores_summary_and_flags_callback():
    phone_agent.handle_incoming_call("CA600", "+15559990000", None)
    phone_agent.handle_transcription("CA600", "Please call me back about scheduling a repair visit")
    call = calls_repo.get_call("CA600")
    assert call["transcript"] == "Please call me back about scheduling a repair visit"
    assert call["callback_requested"] == 1
    assert call["ai_summary"]


def test_missed_call_status_marks_missed_and_attempts_textback():
    sent = phone_agent.handle_status_callback("CA700", "+15551110000", "+15552220000", "no-answer")
    # Twilio isn't configured in tests, so the text-back can't actually go
    # out, but the call must still be logged as missed with a callback flag.
    assert sent is False
    call = calls_repo.get_call("CA700")
    assert call["status"] == "missed"
    assert call["callback_requested"] == 1


def test_completed_call_status_is_not_treated_as_missed():
    sent = phone_agent.handle_status_callback("CA800", "+15551110000", "+15552220000", "completed")
    assert sent is False
    assert calls_repo.get_call("CA800") is None
