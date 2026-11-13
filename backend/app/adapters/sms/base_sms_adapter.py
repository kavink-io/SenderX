"""
SenderX Base SMS Adapter
Extensible abstract base class for SMS providers (Twilio, future gateways).
Inherits from BaseChannelAdapter and provides common SMS validation and utilities.
"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError
from app.adapters.sms.sms_utils import (
    validate_e164,
    calculate_sms_segments,
    MAX_SMS_CHARACTERS
)


class BaseSMSAdapter(BaseChannelAdapter):
    """
    Abstract base class for all SMS adapters (Twilio, Mock, future gateways).
    Enforces consistent validation, formatting, and status retrieval.
    """

    @abstractmethod
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send an SMS message via the underlying provider."""
        pass

    @abstractmethod
    def get_status(self, provider_message_id: str) -> Dict[str, Any]:
        """Query delivery status from the provider."""
        pass

    def validate_recipient(self, recipient: Any) -> str:
        """Validate single recipient phone number against E.164 format."""
        return validate_e164(recipient)

    def extract_text_content(self, data: Dict[str, Any]) -> str:
        """Extract plain text content from arbitrary message data payload."""
        if not isinstance(data, dict):
            raise ValueError("Message data must be a dictionary")

        text = (
            data.get("message")
            or data.get("text")
            or data.get("body")
            or data.get("content")
            or data.get("plain_text_body")
        )

        if text is None or not str(text).strip():
            raise ValueError("SMS text message content is required (provide 'message', 'text', or 'body')")

        text_str = str(text)
        if len(text_str) > MAX_SMS_CHARACTERS:
            raise ValueError(
                f"SMS text length ({len(text_str)} chars) exceeds maximum allowed {MAX_SMS_CHARACTERS} chars"
            )

        return text_str

    def validate(self, message: Dict[str, Any]) -> bool:
        """Standard validation across all SMS adapters."""
        if not isinstance(message, dict):
            raise ValueError("Message must be a dictionary")

        channel = message.get("channel")
        if channel and channel != "sms":
            raise ValueError(f"Invalid channel '{channel}' for SMS adapter. Expected 'sms'.")

        recipient = message.get("recipient")
        if not recipient:
            raise ValueError("SMS recipient phone number is required")

        self.validate_recipient(recipient)

        data = message.get("data", {})
        self.extract_text_content(data)

        # Validate media_urls if present (for MMS support)
        media_urls = data.get("media_urls") or data.get("media_url")
        if media_urls:
            if isinstance(media_urls, str):
                media_urls = [media_urls]
            if not isinstance(media_urls, list):
                raise ValueError("media_urls must be a list of URL strings or a single URL string")
            for url in media_urls:
                if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
                    raise ValueError(f"Invalid media URL '{url}'. Must be a publicly accessible HTTP/HTTPS URL (start with http:// or https://)")

        return True

    def format_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize message structure and compute segmentation."""
        data = message.get("data", {})
        clean_to = self.validate_recipient(message["recipient"])
        text = self.extract_text_content(data)
        seg_info = calculate_sms_segments(text)

        media_urls = data.get("media_urls") or data.get("media_url")
        if isinstance(media_urls, str):
            media_urls = [media_urls]

        formatted = {
            "channel": "sms",
            "to": clean_to,
            "text": text,
            "sender": data.get("sender") or data.get("from_number") or data.get("from"),
            "media_urls": media_urls or [],
            "segmentation": seg_info
        }

        # Preserve any additional metadata
        for k, v in data.items():
            if k not in formatted:
                formatted[k] = v

        return formatted
