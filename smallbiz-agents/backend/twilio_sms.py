"""Outbound SMS via Twilio's REST API, used for the missed-call text-back.
Uses `requests` directly against the REST API instead of the `twilio` SDK to
avoid an extra dependency for a single POST call.
"""

import requests

from . import config

_API_BASE = "https://api.twilio.com/2010-04-01"


def send_sms(to_number: str, body: str) -> bool:
    if not config.twilio_configured():
        return False
    url = f"{_API_BASE}/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json"
    try:
        response = requests.post(
            url,
            data={"From": config.TWILIO_FROM_NUMBER, "To": to_number, "Body": body},
            auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
            timeout=10,
        )
        return response.status_code < 300
    except requests.RequestException:
        return False
