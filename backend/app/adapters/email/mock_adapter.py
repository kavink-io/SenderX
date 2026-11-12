
import uuid

from app.adapters.base_adapter import BaseChannelAdapter
from app.adapters.email.sendgrid_adapter import ProviderError


class MockEmailAdapter(BaseChannelAdapter):

    def validate(self, message):
        recipient = message.get("recipient")
        data = message.get("data", {})

        if not isinstance(recipient, str) or "@" not in recipient:
            raise ValueError("Invalid email recipient")

        if not isinstance(data, dict):
            raise ValueError("Email data must be an object")

        if not data.get("subject"):
            raise ValueError("Email subject is required")

        if not data.get("message") and not data.get("content"):
            raise ValueError("Email content is required")

        return True

    def format_message(self, message):
        return {
            "to_email": message["recipient"],
            "subject": message["data"]["subject"],
            "content": (
                message["data"].get("message")
                or message["data"].get("content")
            )
        }

    def send(self, message):
        self.validate(message)

        data = message.get("data", {})
        scenario = data.get("mock_scenario", "success")
        retry_count = message.get("retry_count", 0)

        if scenario == "permanent_failure":
            raise ValueError("Simulated permanent failure")

        if scenario == "temporary_failure":
            raise ProviderError(
                "Simulated temporary network failure",
                status_code=None,
                retryable=True
            )

        if scenario == "temporary_then_success" and retry_count < 2:
            raise ProviderError(
                "Simulated temporary network failure",
                status_code=None,
                retryable=True
            )

        if scenario not in [
            "success",
            "permanent_failure",
            "temporary_failure",
            "temporary_then_success"
        ]:
            raise ValueError("Unsupported mock scenario")

        return {
            "success": True,
            "status": "SENT",
            "provider": "mock",
            "provider_message_id": f"mock-{uuid.uuid4()}"
        }

    def get_status(self, provider_message_id):
        return {
            "success": True,
            "status": "DELIVERED",
            "provider_message_id": provider_message_id
        }
