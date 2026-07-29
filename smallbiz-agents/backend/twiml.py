"""Minimal TwiML (Twilio Markup Language) response builder. Hand-rolled XML
string building instead of the `twilio` SDK to keep this app's dependency
footprint small -- TwiML is a tiny, stable XML vocabulary and Twilio calls
these webhooks over plain HTTP POST, so no SDK is required to speak it.
"""

from xml.sax.saxutils import escape

from . import config


def _say(text: str) -> str:
    return f"<Say>{escape(text)}</Say>"


def gather_speech(prompt: str, action_url: str, timeout: int = 5) -> str:
    """Greet the caller and collect a spoken response."""
    no_input_message = _say("Sorry, we didn't catch that.")
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<Response>"
        f'<Gather input="speech" action="{escape(action_url)}" method="POST" '
        f'speechTimeout="auto" timeout="{timeout}">'
        f"{_say(prompt)}"
        "</Gather>"
        f"{no_input_message}"
        f'<Redirect method="POST">{escape(action_url)}</Redirect>'
        "</Response>"
    )


def say_and_offer_voicemail(response_text: str, record_action_url: str,
                             offer_voicemail: bool, transcribe_callback_url: str = "") -> str:
    parts = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "<Response>", _say(response_text)]
    if offer_voicemail:
        parts.append(_say(
            "If you'd like us to call you back, please leave your name and a brief message "
            "after the tone."
        ))
        transcribe_attr = ""
        if transcribe_callback_url:
            transcribe_attr = f' transcribe="true" transcribeCallback="{escape(transcribe_callback_url)}"'
        parts.append(
            f'<Record action="{escape(record_action_url)}" method="POST" '
            f'maxLength="120" playBeep="true"{transcribe_attr}/>'
        )
    else:
        parts.append(_say("Thanks for calling, have a great day!"))
        parts.append("<Hangup/>")
    parts.append("</Response>")
    return "".join(parts)


def say_and_hangup(text: str) -> str:
    return f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response>{_say(text)}<Hangup/></Response>"


def empty_response() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def voice_url(path: str) -> str:
    """Build an absolute callback URL for Twilio to POST back to, using the
    configured public base URL. Falls back to a relative path (works fine
    for local testing where Twilio isn't actually calling back)."""
    if config.PUBLIC_BASE_URL:
        return f"{config.PUBLIC_BASE_URL}{path}"
    return path
