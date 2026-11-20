
import uuid
from datetime import datetime, timezone

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError


class MockEmailAdapter(BaseChannelAdapter):

    def validate(self, message):
        recipient = message.get("recipient")
        data = message.get("data", {})

        if not isinstance(recipient, str) or "@" not in recipient:
            raise ValueError("Invalid email recipient: missing '@'")

        if not isinstance(data, dict):
            raise ValueError("Email data must be an object")

        if not data.get("subject"):
            raise ValueError("Email subject is required")

        content = (
            data.get("message")
            or data.get("content")
            or data.get("body")
            or data.get("text")
        )
        if not content:
            raise ValueError("Email content is required")

        return True

    def format_message(self, message):
        data = message.get("data", {})
        content = (
            data.get("message")
            or data.get("content")
            or data.get("body")
            or data.get("text")
        )
        return {
            "channel": "email",
            "to_email": message["recipient"],
            "subject": data["subject"],
            "content": content
        }

    def send(self, message):
        self.validate(message)

        data = message.get("data", {})
        scenario = data.get("mock_scenario", "success")
        retry_count = message.get("retry_count", 0)

        if scenario == "permanent_failure":
            raise ProviderError(
                "Simulated permanent failure: Mailbox does not exist",
                status_code=550,
                retryable=False
            )

        if scenario == "secret_leak_failure":
            secret_msg = data.get(
                "mock_error_message",
                "SendGrid API connection failure: auth header SG.v29skd920skd920skd920.abcdefghijklmnopqrstuvwxyz12345 failed, JWT token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c rejected, password=SuperSecretAdminPass123!"
            )
            raise ProviderError(
                secret_msg,
                status_code=500,
                retryable=False
            )

        if scenario == "temporary_failure":
            raise ProviderError(
                "Simulated temporary failure: SMTP connection timeout",
                status_code=421,
                retryable=True
            )

        if scenario == "temporary_then_success" and retry_count < 2:
            raise ProviderError(
                "Simulated temporary rate limit",
                status_code=429,
                retryable=True
            )

        if scenario not in [
            "success",
            "permanent_failure",
            "secret_leak_failure",
            "temporary_failure",
            "temporary_then_success"
        ]:
            raise ValueError(f"Unsupported mock scenario: {scenario}")

        return {
            "success": True,
            "status": "SENT",
            "provider": "mock",
            "channel": "email",
            "provider_message_id": f"mock-email-{uuid.uuid4()}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_status(self, provider_message_id):
        return {
            "success": True,
            "status": "DELIVERED",
            "provider_message_id": provider_message_id,
            "channel": "email",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

