"""
SenderX Twilio SMS Adapter
Production-ready SMS integration using Twilio SDK supporting:
- Single and multiple recipient messages
- International E.164 phone numbers
- Unicode and long concatenated SMS (GSM-7 & UCS-2 segmentation)
- Sender ID / from_number / Messaging Service SID
- Delivery status tracking and StatusCallback URL
- Retry classification (429 Rate Limit, 5xx Outages, 401/403 Auth, 2xxxx/3xxxx permanent errors)
- Strict credential protection and sensitive data redaction
- Optional MMS / media attachments
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.adapters.base_adapter import ProviderError
from app.adapters.sms.base_sms_adapter import BaseSMSAdapter
from app.adapters.sms.sms_utils import (
    validate_e164,
    classify_twilio_error,
    normalize_sms_response,
    redact_sensitive,
    calculate_sms_segments
)


class TwilioSMSAdapter(BaseSMSAdapter):
    """Production Twilio SMS Adapter implementing the BaseSMSAdapter interface."""

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: Optional[str] = None,
        messaging_service_sid: Optional[str] = None,
        status_callback_url: Optional[str] = None,
        client: Optional[Any] = None
    ):
        if not account_sid or not isinstance(account_sid, str) or not account_sid.strip():
            raise ValueError("Twilio account_sid is required")
        if not auth_token or not isinstance(auth_token, str) or not auth_token.strip():
            raise ValueError("Twilio auth_token is required")

        self.account_sid = account_sid.strip()
        self.auth_token = auth_token.strip()

        # Validate that at least one sender identifier is provided
        if not from_number and not messaging_service_sid:
            raise ValueError("Twilio requires either 'from_number' or 'messaging_service_sid'")

        self.from_number = from_number.strip() if from_number else None
        self.messaging_service_sid = messaging_service_sid.strip() if messaging_service_sid else None
        self.status_callback_url = status_callback_url.strip() if status_callback_url else None

        # Allow passing an existing client or mock client for tests
        if client is not None:
            self.client = client
        else:
            self.client = Client(self.account_sid, self.auth_token)

    @staticmethod
    def _map_twilio_status(twilio_status: str) -> str:
        """Map Twilio API statuses to SenderX normalized statuses."""
        s = (twilio_status or "").lower()
        if s in ("queued", "accepted", "scheduled"):
            return "ACCEPTED"
        if s in ("sending", "sent"):
            return "SENT"
        if s == "delivered":
            return "DELIVERED"
        if s == "undelivered":
            return "UNDELIVERED"
        if s == "failed":
            return "FAILED"
        return "ACCEPTED"

    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch an SMS message through Twilio REST API."""
        self.validate(message)
        formatted = self.format_message(message)

        data = message.get("data", {})

        # Resolve sender: message override > adapter messaging_service_sid > adapter from_number
        msg_service_sid = data.get("messaging_service_sid") or self.messaging_service_sid
        from_phone = data.get("sender") or data.get("from_number") or self.from_number

        create_kwargs: Dict[str, Any] = {
            "to": formatted["to"],
            "body": formatted["text"]
        }

        if msg_service_sid:
            create_kwargs["messaging_service_sid"] = msg_service_sid
        elif from_phone:
            create_kwargs["from_"] = from_phone
        else:
            raise ValueError("No valid sender (from_number or messaging_service_sid) available for Twilio")

        # Status callback URL for delivery receipts
        callback_url = data.get("status_callback") or data.get("status_callback_url") or self.status_callback_url
        if callback_url:
            create_kwargs["status_callback"] = callback_url

        # MMS media attachments if provided
        media_urls = formatted.get("media_urls") or data.get("media_urls") or data.get("media_url")
        if media_urls:
            if isinstance(media_urls, str):
                media_urls = [media_urls]

            # 1. Enforce recipient MMS support: Twilio MMS is supported for US and Canada (+1) only
            to_number = formatted["to"]
            is_us_ca = to_number.startswith("+1") or (len(to_number) == 11 and to_number.startswith("1"))
            if not is_us_ca:
                raise ValueError(
                    f"Twilio MMS is only supported for US and Canada (+1) phone numbers. Destination '{to_number}' does not support MMS."
                )

            # 2. Verify media URLs meet Twilio's requirements (public HTTP/HTTPS)
            for m_url in media_urls:
                if not isinstance(m_url, str) or not (m_url.startswith("http://") or m_url.startswith("https://")):
                    raise ValueError(f"Twilio MMS requires publicly accessible HTTP/HTTPS media URLs. Invalid URL: '{m_url}'")

            create_kwargs["media_url"] = media_urls

        try:
            resp = self.client.messages.create(**create_kwargs)

            raw_status = getattr(resp, "status", "accepted")
            norm_status = self._map_twilio_status(raw_status)
            provider_message_id = getattr(resp, "sid", None)
            num_segments = getattr(resp, "num_segments", None) or formatted["segmentation"]["segments"]

            return normalize_sms_response(
                success=True,
                provider="twilio",
                channel="sms",
                provider_message_id=provider_message_id,
                status=norm_status,
                timestamp=datetime.now(timezone.utc).isoformat(),
                segments=int(num_segments)
            )

        except TwilioRestException as exc:
            is_retryable, retry_after = classify_twilio_error(
                error_code=exc.code,
                http_status=exc.status,
                error_message=exc.msg
            )

            redacted_msg = redact_sensitive(
                str(exc.msg),
                [self.auth_token, self.account_sid]
            )

            raise ProviderError(
                f"Twilio error {exc.code}: {redacted_msg}",
                status_code=exc.status,
                retryable=is_retryable,
                error_code=exc.code,
                retry_after=retry_after
            )

        except ProviderError:
            raise

        except Exception as exc:
            redacted_msg = redact_sensitive(
                str(exc),
                [self.auth_token, self.account_sid]
            )
            # Default unexpected network or parsing error to retryable 500
            raise ProviderError(
                f"Twilio unexpected error: {redacted_msg}",
                status_code=500,
                retryable=True
            )

    def get_status(self, provider_message_id: str) -> Dict[str, Any]:
        """Fetch message delivery status from Twilio."""
        if not provider_message_id:
            raise ValueError("provider_message_id is required")

        try:
            resp = self.client.messages(provider_message_id).fetch()
            raw_status = getattr(resp, "status", "unknown")
            norm_status = self._map_twilio_status(raw_status)

            return normalize_sms_response(
                success=True,
                provider="twilio",
                channel="sms",
                provider_message_id=provider_message_id,
                status=norm_status,
                error_code=getattr(resp, "error_code", None),
                error_message=getattr(resp, "error_message", None),
                segments=int(getattr(resp, "num_segments", 1) or 1)
            )

        except TwilioRestException as exc:
            is_retryable, _ = classify_twilio_error(exc.code, exc.status, exc.msg)
            redacted = redact_sensitive(str(exc.msg), [self.auth_token, self.account_sid])
            raise ProviderError(
                f"Failed to fetch Twilio message status: {redacted}",
                status_code=exc.status,
                retryable=is_retryable,
                error_code=exc.code
            )
        except Exception as exc:
            redacted = redact_sensitive(str(exc), [self.auth_token, self.account_sid])
            raise ProviderError(
                f"Unexpected error fetching Twilio status: {redacted}",
                status_code=500,
                retryable=True
            )
