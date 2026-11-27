"""
SenderX WhatsApp Business Cloud API Adapter
Production-grade Meta WhatsApp Business Platform integration using the official Cloud API:
- Endpoint: https://graph.facebook.com/{version}/{phone_number_id}/messages
- Supports: Text, Media, Location, Interactive Buttons, Interactive Lists, CTA URL, Meta Templates, Contacts
- Media upload and link processing
- Robust error classification (permanent vs retryable with backoff)
- Credential protection and sensitive token redaction
"""

import json
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional, Tuple, Union
import requests

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError
from app.adapters.whatsapp.models import WhatsAppPayloadValidator
from app.adapters.whatsapp.whatsapp_utils import (
    classify_whatsapp_error,
    normalize_whatsapp_response,
    redact_sensitive,
    validate_media_file,
)

logger = logging.getLogger(__name__)


class WhatsAppCloudAdapter(BaseChannelAdapter):
    """
    Production adapter for Meta's official WhatsApp Business Platform Cloud API.
    Interacts directly with Meta's Graph API.
    """

    GRAPH_BASE_URL = "https://graph.facebook.com"

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        business_account_id: Optional[str] = None,
        graph_api_version: str = "v21.0",
        app_secret: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: int = 30
    ):
        if not access_token or not isinstance(access_token, str) or not access_token.strip():
            raise ValueError("WhatsApp Cloud API 'access_token' is required")
        if not phone_number_id or not isinstance(phone_number_id, str) or not phone_number_id.strip():
            raise ValueError("WhatsApp Cloud API 'phone_number_id' is required")

        self.access_token = access_token.strip()
        self.phone_number_id = phone_number_id.strip()
        self.business_account_id = business_account_id.strip() if business_account_id else None
        self.graph_api_version = (graph_api_version or "v21.0").strip()
        if not self.graph_api_version.startswith("v"):
            self.graph_api_version = f"v{self.graph_api_version}"
        self.app_secret = app_secret.strip() if app_secret else None
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    @property
    def messages_endpoint(self) -> str:
        return f"{self.GRAPH_BASE_URL}/{self.graph_api_version}/{self.phone_number_id}/messages"

    @property
    def media_endpoint(self) -> str:
        return f"{self.GRAPH_BASE_URL}/{self.graph_api_version}/{self.phone_number_id}/media"

    def validate(self, message: Dict[str, Any]) -> bool:
        """Validate WhatsApp payload using strict Pydantic models."""
        WhatsAppPayloadValidator.validate_and_format(message)
        return True

    def format_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert standard SenderX message dict into official Meta Graph API payload."""
        return WhatsAppPayloadValidator.validate_and_format(message)

    def _resolve_and_upload_media_if_needed(self, message: Dict[str, Any]) -> None:
        """
        Detects SenderX centralized media in message data.
        Uploads stored media to Meta Cloud API POST /media endpoint when required.
        Uses the returned Meta media ID in the outgoing payload.
        Never assumes a SenderX media_id is a valid Meta media ID.
        """
        data = message.get("data")
        if not isinstance(data, dict):
            return

        resolved_media_list = data.get("resolved_media", [])
        msg_type = data.get("type")

        # 1. Check if resolved_media is available from message pipeline
        if resolved_media_list and isinstance(resolved_media_list, list) and len(resolved_media_list) > 0:
            first_media = resolved_media_list[0]
            if not msg_type:
                mime = first_media.get("mime_type", "")
                if mime.startswith("image/"):
                    msg_type = "image"
                elif mime.startswith("video/"):
                    msg_type = "video"
                elif mime.startswith("audio/"):
                    msg_type = "audio"
                else:
                    msg_type = "document"
                data["type"] = msg_type

            media_obj = data.get(msg_type)
            if not isinstance(media_obj, dict):
                media_obj = {}
                data[msg_type] = media_obj

            # If no link or numeric Meta ID, upload to Meta
            existing_id = str(media_obj.get("id") or "")
            if not media_obj.get("link") and (not existing_id or "-" in existing_id):
                raw_bytes = first_media.get("raw_bytes")
                if not raw_bytes and first_media.get("storage_key"):
                    try:
                        from app.modules.media.storage import get_storage_backend
                        storage = get_storage_backend()
                        raw_bytes = storage.get_bytes(
                            first_media["storage_key"],
                            organization_id=message.get("organization_id"),
                        )
                    except Exception as e:
                        logger.warning("Could not read media bytes from storage: %s", e)

                if raw_bytes:
                    filename = first_media.get("filename", "media_file")
                    mime_type = first_media.get("mime_type", "application/octet-stream")
                    meta_id = self.upload_media(
                        file_bytes=raw_bytes,
                        filename=filename,
                        mime_type=mime_type,
                        media_type=msg_type
                    )
                    media_obj["id"] = meta_id
                    if "caption" in data and "caption" not in media_obj:
                        media_obj["caption"] = data["caption"]
                    if "filename" not in media_obj:
                        media_obj["filename"] = filename
                    data[msg_type] = media_obj

        # 2. Check if a SenderX UUID was provided directly in data[msg_type]["id"] or data["media_id"]
        elif msg_type in ("image", "video", "audio", "document"):
            media_obj = data.get(msg_type, {})
            current_id = str(media_obj.get("id") or data.get("media_id") or "").strip()
            if current_id and "-" in current_id and not media_obj.get("link"):
                org_id = message.get("organization_id")
                try:
                    from app.modules.media.service import MediaService
                    from app.modules.media.storage import get_storage_backend
                    media_meta = MediaService.get_media(current_id, organization_id=org_id)
                    if media_meta.get("success"):
                        doc = media_meta["data"]
                        storage = get_storage_backend()
                        raw_bytes = storage.get_bytes(doc["storage_key"], organization_id=org_id)
                        meta_id = self.upload_media(
                            file_bytes=raw_bytes,
                            filename=doc["filename"],
                            mime_type=doc["mime_type"],
                            media_type=msg_type
                        )
                        media_obj["id"] = meta_id
                        data[msg_type] = media_obj
                except Exception as exc:
                    logger.warning("Could not auto-upload SenderX media ID to Meta: %s", exc)

    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a validated message via Meta WhatsApp Business Cloud API.
        POST https://graph.facebook.com/{version}/{phone_number_id}/messages
        """
        self._resolve_and_upload_media_if_needed(message)
        payload = self.format_message(message)
        target_url = self.messages_endpoint
        recipient = payload.get("to")

        try:
            resp = self.session.post(
                target_url,
                json=payload,
                headers=self._headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            redacted = redact_sensitive(str(exc), [self.access_token, self.app_secret])
            if isinstance(exc, requests.ConnectTimeout):
                # A connect timeout occurs before an HTTP request is sent and
                # can be retried without risking duplicate delivery.
                logger.warning("Meta WhatsApp Cloud API connect timeout")
                raise ProviderError(
                    "Meta WhatsApp Cloud API connection timed out before dispatch",
                    status_code=503,
                    retryable=True,
                    error_code="CONNECT_TIMEOUT",
                    retry_after=5,
                ) from None
            # A read timeout, reset, or other transport failure can happen
            # after Meta accepted the POST. Fail closed and require status
            # reconciliation before any manual requeue.
            logger.error("Meta WhatsApp Cloud API send outcome is unknown (%s)", type(exc).__name__)
            raise ProviderError(
                f"DELIVERY_OUTCOME_UNKNOWN: Meta WhatsApp request may have been accepted; verify provider status before retry. ({type(exc).__name__})",
                status_code=503,
                retryable=False,
                error_code="DELIVERY_OUTCOME_UNKNOWN",
            ) from None

        # Parse JSON response
        try:
            resp_data = resp.json()
        except ValueError:
            resp_data = {"raw_text": resp.text}

        # Check HTTP status
        if resp.status_code not in (200, 201):
            error_obj = resp_data.get("error", {})
            error_code = error_obj.get("code")
            error_subcode = error_obj.get("error_subcode")
            error_msg = error_obj.get("message") or resp.text

            is_retryable, retry_after = classify_whatsapp_error(
                code=error_code,
                subcode=error_subcode,
                http_status=resp.status_code,
                error_message=error_msg
            )
            if is_retryable:
                provider_retry_after = getattr(resp, "headers", {}).get("Retry-After")
                if provider_retry_after:
                    try:
                        retry_after = max(1, int(provider_retry_after))
                    except (TypeError, ValueError):
                        try:
                            retry_time = parsedate_to_datetime(provider_retry_after)
                            retry_after = max(1, int((retry_time - datetime.now(timezone.utc)).total_seconds()))
                        except (TypeError, ValueError, OverflowError):
                            pass

            logger.warning(
                "WhatsApp Cloud API error HTTP %s: code=%s subcode=%s retryable=%s",
                resp.status_code, error_code, error_subcode, is_retryable
            )

            credential_hint = ""
            if self.access_token and self.access_token in error_msg:
                credential_hint = f" (credential {redact_sensitive(self.access_token, [self.access_token])})"
            elif self.app_secret and self.app_secret in error_msg:
                credential_hint = f" (app secret {redact_sensitive(self.app_secret, [self.app_secret])})"
            raise ProviderError(
                f"WhatsApp Cloud API rejected message (provider code {error_code or resp.status_code}){credential_hint}",
                status_code=resp.status_code,
                retryable=is_retryable,
                error_code=error_code or resp.status_code,
                retry_after=retry_after
            )

        # Extract Meta provider message ID (wamid)
        messages_list = resp_data.get("messages", [])
        provider_message_id = None
        if messages_list and isinstance(messages_list, list):
            provider_message_id = messages_list[0].get("id")

        if not provider_message_id:
            logger.warning("WhatsApp Cloud API response missing message ID")

        return normalize_whatsapp_response(
            success=True,
            provider="meta",
            channel="whatsapp",
            provider_message_id=provider_message_id,
            status="ACCEPTED",
            recipient=recipient,
            timestamp=datetime.now(timezone.utc).isoformat(),
            raw_response=resp_data
        )

    def upload_media(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        media_type: Optional[str] = None
    ) -> str:
        """
        Upload media to Meta WhatsApp servers.
        POST https://graph.facebook.com/{version}/{phone_number_id}/media
        Returns Meta media ID.
        """
        if not file_bytes:
            raise ValueError("Media file content cannot be empty")

        if media_type:
            is_valid, err = validate_media_file(
                media_type=media_type,
                mime_type=mime_type,
                file_size_bytes=len(file_bytes),
                filename=filename
            )
            if not is_valid:
                raise ValueError(err)

        target_url = self.media_endpoint
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        files = {
            "file": (filename, file_bytes, mime_type)
        }
        data = {
            "messaging_product": "whatsapp",
            "type": mime_type
        }

        try:
            resp = self.session.post(
                target_url,
                headers=headers,
                files=files,
                data=data,
                timeout=self.timeout * 2,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            redacted = redact_sensitive(str(exc), [self.access_token, self.app_secret])
            raise ProviderError(
                f"WhatsApp media upload network error: {redacted}",
                status_code=503,
                retryable=True,
                error_code="MEDIA_UPLOAD_NETWORK_ERROR",
                retry_after=5
            )

        try:
            resp_data = resp.json()
        except ValueError:
            resp_data = {"raw_text": resp.text}

        if resp.status_code not in (200, 201):
            error_obj = resp_data.get("error", {})
            error_code = error_obj.get("code")
            raise ProviderError(
                f"WhatsApp media upload failed (provider code {error_code or resp.status_code})",
                status_code=resp.status_code,
                retryable=False,
                error_code=error_code
            )

        media_id = resp_data.get("id")
        if not media_id:
            raise ProviderError("Media upload succeeded but no media ID returned")

        return media_id

    def get_media_url(self, media_id: str) -> Dict[str, Any]:
        """
        Retrieve media URL metadata by Meta media ID.
        GET https://graph.facebook.com/{version}/{media_id}
        """
        if not media_id:
            raise ValueError("Media ID is required")

        target_url = f"{self.GRAPH_BASE_URL}/{self.graph_api_version}/{media_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            resp = self.session.get(target_url, headers=headers, timeout=self.timeout, allow_redirects=False)
            if resp.status_code == 200:
                return resp.json()
            error_obj = resp.json().get("error", {}) if resp.text else {}
            raise ProviderError(
                f"Error retrieving media {media_id}: {error_obj.get('message', resp.text)}",
                status_code=resp.status_code
            )
        except requests.RequestException as exc:
            raise ProviderError(
                f"Network error retrieving media metadata: {str(exc)}",
                status_code=503,
                retryable=True
            )

    def get_status(self, provider_message_id: str) -> Dict[str, Any]:
        """
        Retrieve status for a WhatsApp message.
        Note: WhatsApp Cloud API delivers delivery receipts asynchronously via webhooks.
        This helper returns a normalized query representation.
        """
        if not provider_message_id:
            raise ValueError("Provider message ID is required")

        return normalize_whatsapp_response(
            success=True,
            provider="meta",
            channel="whatsapp",
            provider_message_id=provider_message_id,
            status="UNKNOWN",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
