import uuid
from datetime import datetime, timezone

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError


class MockTelegramAdapter(BaseChannelAdapter):
    """
    Mock adapter for Telegram Bot API channel.
    Simulates Telegram Bot messaging without hitting live Telegram Bot servers.
    """

    def validate(self, message):
        recipient = message.get("recipient")
        data = message.get("data", {})

        if recipient is None or str(recipient).strip() == "":
            raise ValueError("Telegram recipient (chat_id or @username) is required")

        rec_str = str(recipient).strip()
        # Valid telegram recipients: numeric chat ID (including negative for supergroups/channels) or @channel_username
        is_numeric_chat_id = rec_str.lstrip("-").isdigit()
        is_username = rec_str.startswith("@") and len(rec_str) >= 2

        if not (is_numeric_chat_id or is_username):
            raise ValueError(
                f"Invalid Telegram recipient '{recipient}'. "
                "Must be a numeric chat_id (e.g. '123456789', '-100123456789') or a channel/user handle starting with '@'."
            )

        if not isinstance(data, dict):
            raise ValueError("Telegram data must be an object")

        content = (
            data.get("text")
            or data.get("message")
            or data.get("content")
            or data.get("body")
            or data.get("caption")
            or data.get("photo")
            or data.get("document")
            or data.get("media")
        )
        if not content:
            raise ValueError("Telegram message content (text, caption, or media) is required")

        return True

    def format_message(self, message):
        data = message.get("data", {})
        content = (
            data.get("text")
            or data.get("message")
            or data.get("content")
            or data.get("body")
        )
        formatted = {
            "channel": "telegram",
            "chat_id": str(message["recipient"]).strip(),
            "text": str(content) if content else None,
            "parse_mode": data.get("parse_mode", "HTML"),
            "photo": data.get("photo"),
            "document": data.get("document")
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
                "Simulated Telegram permanent failure: Bot was blocked by user or Chat not found",
                status_code=403,
                retryable=False
            )

        if scenario == "temporary_failure":
            raise ProviderError(
                "Simulated Telegram temporary failure: Flood control exceeded (Retry-After)",
                status_code=429,
                retryable=True
            )

        if scenario == "temporary_then_success" and retry_count < 2:
            raise ProviderError(
                "Simulated Telegram gateway timeout (HTTP 504)",
                status_code=504,
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
            "channel": "telegram",
            "provider_message_id": f"mock-tg-{uuid.uuid4()}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_status(self, provider_message_id):
        return {
            "success": True,
            "status": "DELIVERED",
            "provider_message_id": provider_message_id,
            "channel": "telegram",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
