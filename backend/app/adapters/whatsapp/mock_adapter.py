import re
import uuid
from datetime import datetime, timezone

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError


class MockWhatsAppAdapter(BaseChannelAdapter):
    """
    Mock adapter for WhatsApp Business channel.
    Simulates Cloud API delivery without calling Meta/WhatsApp servers.
    """

    PHONE_REGEX = re.compile(r"^(whatsapp:)?\+?[1-9]\d{6,14}$")

    def validate(self, message):
        recipient = message.get("recipient")
        data = message.get("data", {})

        if not isinstance(recipient, str):
            raise ValueError("WhatsApp recipient must be a phone number or whatsapp: URI string")

        clean_recipient = recipient.strip().replace(" ", "").replace("-", "")
        if not self.PHONE_REGEX.match(clean_recipient):
            raise ValueError(
                f"Invalid WhatsApp recipient '{recipient}'. "
                "Must be a valid international phone number (e.g. '+1234567890' or 'whatsapp:+1234567890')."
            )

        if not isinstance(data, dict):
            raise ValueError("WhatsApp data must be an object")

        content = (
            data.get("text")
            or data.get("message")
            or data.get("content")
            or data.get("body")
            or data.get("media_url")
            or data.get("template")
            or data.get("template_name")
        )
        if not content:
            raise ValueError(
                "WhatsApp message requires text, template, or media content"
            )

        return True

    def format_message(self, message):
        data = message.get("data", {})
        recipient = message["recipient"]
        clean_recipient = recipient if recipient.startswith("whatsapp:") else f"whatsapp:{recipient}"

        formatted = {
            "channel": "whatsapp",
            "to": clean_recipient,
            "type": "template" if data.get("template") or data.get("template_name") else ("media" if data.get("media_url") else "text"),
            "content": data.get("text") or data.get("message") or data.get("content") or data.get("body"),
            "media_url": data.get("media_url"),
            "template": data.get("template") or data.get("template_name")
        }
        for k, v in data.items():
            if k not in formatted:
                formatted[k] = v

        return formatted

    def send(self, message):
        self.validate(message)

        data = message.get("data", {})
        scenario = data.get("mock_scenario", "success")
        retry_count = message.get("retry_count", 0)

        if scenario == "permanent_failure":
            raise ProviderError(
                "Simulated WhatsApp permanent failure: Number not registered on WhatsApp",
                status_code=400,
                retryable=False
            )

        if scenario == "temporary_failure":
            raise ProviderError(
                "Simulated WhatsApp temporary failure: Meta Graph API 503 Service Unavailable",
                status_code=503,
                retryable=True
            )

        if scenario == "temporary_then_success" and retry_count < 2:
            raise ProviderError(
                "Simulated WhatsApp rate limit reached (HTTP 429)",
                status_code=429,
                retryable=True
            )

        if scenario not in [
            "success",
            "permanent_failure",
            "temporary_failure",
            "temporary_then_success"
        ]:
            raise ValueError(f"Unsupported mock scenario: {scenario}")

        return {
            "success": True,
            "status": "SENT",
            "provider": "mock",
            "channel": "whatsapp",
            "provider_message_id": f"mock-wa-{uuid.uuid4()}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_status(self, provider_message_id):
        return {
            "success": True,
            "status": "DELIVERED",
            "provider_message_id": provider_message_id,
            "channel": "whatsapp",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
