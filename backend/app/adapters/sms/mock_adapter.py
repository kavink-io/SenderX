import re
import uuid
from datetime import datetime, timezone

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError


class MockSMSAdapter(BaseChannelAdapter):
    """
    Mock adapter for SMS channel.
    Simulates carrier SMS gateways without external network calls.
    """

    PHONE_REGEX = re.compile(r"^\+?[1-9]\d{6,14}$")

    def validate(self, message):
        recipient = message.get("recipient")
        data = message.get("data", {})

        if not isinstance(recipient, str):
            raise ValueError("SMS recipient must be a phone number string")

        clean_recipient = recipient.strip().replace(" ", "").replace("-", "")
        if not self.PHONE_REGEX.match(clean_recipient):
            raise ValueError(
                f"Invalid SMS recipient phone number '{recipient}'. "
                "Must be in international E.164 or numeric format (7-15 digits)."
            )

        if not isinstance(data, dict):
            raise ValueError("SMS data must be an object")

        text = (
            data.get("text")
            or data.get("message")
            or data.get("content")
            or data.get("body")
        )
        if not text or not str(text).strip():
            raise ValueError("SMS text message content is required")

        return True

    def format_message(self, message):
        data = message.get("data", {})
        text = (
            data.get("text")
            or data.get("message")
            or data.get("content")
            or data.get("body")
        )
        formatted = {
            "channel": "sms",
            "to_phone": message["recipient"],
            "text": str(text),
            "sender_id": data.get("sender_id", "SenderX"),
            "encoding": data.get("encoding", "GSM-7")
        }
        # Preserve arbitrary metadata
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
                "Simulated SMS permanent failure: Unallocated mobile number",
                status_code=400,
                retryable=False
            )

        if scenario == "temporary_failure":
            raise ProviderError(
                "Simulated SMS temporary failure: Gateway timeout (HTTP 504)",
                status_code=504,
                retryable=True
            )

        if scenario == "temporary_then_success" and retry_count < 2:
            raise ProviderError(
                "Simulated SMS carrier congestion (HTTP 429)",
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
            "channel": "sms",
            "provider_message_id": f"mock-sms-{uuid.uuid4()}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_status(self, provider_message_id):
        return {
            "success": True,
            "status": "DELIVERED",
            "provider_message_id": provider_message_id,
            "channel": "sms",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
