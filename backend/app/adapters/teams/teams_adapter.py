"""
SenderX Microsoft Teams Production Adapter
Implements Microsoft Graph API v1.0 messaging for Microsoft Teams:
- Direct Chat messaging via POST /chats/{chat-id}/messages
- Channel messaging via POST /teams/{team-id}/channels/{channel-id}/messages
- Adaptive Cards (application/vnd.microsoft.card.adaptive)
- Text and HTML message bodies
- File attachments and SharePoint references
- Message importance and subject headers
- Throttling and Retry-After handling
- Token caching and auto-reacquisition
- Strict credential protection and sensitive data redaction
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from app.adapters.base_adapter import BaseChannelAdapter, ProviderError
from app.adapters.teams.graph_client import MicrosoftGraphAuthClient
from app.adapters.teams.models import TeamsPayloadValidator, TeamsRecipientModel
from app.adapters.teams.teams_utils import (
    classify_teams_error,
    normalize_teams_response,
    redact_sensitive,
)

logger = logging.getLogger(__name__)


class MicrosoftTeamsAdapter(BaseChannelAdapter):
    """
    Production adapter for Microsoft Teams using official Microsoft Graph API v1.0.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[float] = None,
        on_token_refresh: Optional[Any] = None,
        default_team_id: Optional[str] = None,
        default_channel_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        credential_loader: Optional[Any] = None,
        allow_local_lock: Optional[bool] = None,
        auth_client: Optional[MicrosoftGraphAuthClient] = None,
        session: Optional[requests.Session] = None,
        timeout: int = 30
    ):
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("Microsoft Teams requires 'tenant_id'")
        if not client_id or not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("Microsoft Teams requires 'client_id'")
        if not client_secret or not isinstance(client_secret, str) or not client_secret.strip():
            raise ValueError("Microsoft Teams requires 'client_secret'")

        self.tenant_id = tenant_id.strip()
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.access_token = access_token.strip() if access_token else None
        self.refresh_token = refresh_token.strip() if refresh_token else None
        self.token_expires_at = token_expires_at
        self.on_token_refresh = on_token_refresh
        self.organization_id = organization_id.strip() if organization_id else None
        self.redis_client = redis_client
        self.credential_loader = credential_loader
        self.allow_local_lock = allow_local_lock
        self.default_team_id = default_team_id.strip() if default_team_id else None
        self.default_channel_id = default_channel_id.strip() if default_channel_id else None
        self.timeout = timeout
        self.session = session or requests.Session()

        # Auth client
        if auth_client is not None:
            self.auth_client = auth_client
        else:
            self.auth_client = MicrosoftGraphAuthClient(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
                access_token=self.access_token,
                refresh_token=self.refresh_token,
                token_expires_at=self.token_expires_at,
                on_token_refresh=self.on_token_refresh,
                organization_id=self.organization_id,
                redis_client=self.redis_client,
                credential_loader=self.credential_loader,
                allow_local_lock=self.allow_local_lock,
                session=self.session,
                timeout=self.timeout
            )

    def validate(self, message: Dict[str, Any]) -> bool:
        """Validate Teams payload and recipient."""
        TeamsPayloadValidator.validate_and_format(message)
        return True

    def format_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Convert standard SenderX message into Microsoft Graph API payload."""
        _, graph_payload = TeamsPayloadValidator.validate_and_format(message)
        return graph_payload

    def _resolve_endpoint(self, target: TeamsRecipientModel) -> str:
        """Construct Microsoft Graph API v1.0 messages endpoint."""
        if target.target_type == "chat":
            if not target.chat_id:
                raise ValueError("Chat ID is required for Teams chat messages")
            return f"{self.GRAPH_BASE_URL}/chats/{target.chat_id}/messages"

        if target.target_type == "channel":
            team_id = target.team_id or self.default_team_id
            channel_id = target.channel_id or self.default_channel_id
            if not team_id or not channel_id:
                raise ValueError("Both team_id and channel_id are required for Teams channel messages")
            return f"{self.GRAPH_BASE_URL}/teams/{team_id}/channels/{channel_id}/messages"

        raise ValueError(f"Unknown Teams target type: {target.target_type}")

    def upload_file_to_sharepoint_or_onedrive(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "application/octet-stream",
        team_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads file to Microsoft OneDrive / SharePoint via Microsoft Graph API v1.0.
        Uses simple PUT for files <= 4MB and uploadSession for files > 4MB up to 250MB.
        Returns driveItem metadata (id, name, webUrl, downloadUrl).
        """
        if not file_bytes:
            raise ValueError("File content cannot be empty for Teams file upload")

        size = len(file_bytes)
        if size > 250 * 1024 * 1024:
            raise ValueError(f"File '{filename}' ({size} bytes) exceeds Microsoft Teams limit of 250 MB")

        token = self.auth_client.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}"
        }

        clean_filename = re.sub(r'[\/:*?"<>|]', "_", filename)
        if team_id:
            base_drive_url = f"{self.GRAPH_BASE_URL}/groups/{team_id}/drive/root:/{clean_filename}"
        else:
            base_drive_url = f"{self.GRAPH_BASE_URL}/me/drive/root:/{clean_filename}"

        # 1. Simple upload for files <= 4 MB (4 * 1024 * 1024 bytes)
        if size <= 4 * 1024 * 1024:
            put_url = f"{base_drive_url}:/content"
            put_headers = dict(headers)
            put_headers["Content-Type"] = mime_type
            try:
                resp = self.session.put(put_url, data=file_bytes, headers=put_headers, timeout=self.timeout * 2)
                if resp.status_code in (200, 201):
                    item = resp.json()
                    return {
                        "id": item.get("id"),
                        "name": item.get("name", clean_filename),
                        "webUrl": item.get("webUrl") or item.get("@microsoft.graph.downloadUrl") or f"https://sharepoint.com/{clean_filename}",
                        "downloadUrl": item.get("@microsoft.graph.downloadUrl")
                    }
                err = resp.json().get("error", {}).get("message") if resp.text else resp.text
                raise ProviderError(f"Teams drive upload error ({resp.status_code}): {err}", status_code=resp.status_code)
            except requests.RequestException as exc:
                raise ProviderError(f"Teams drive upload network error: {exc}", status_code=503)

        # 2. Upload session for files > 4 MB (chunked upload)
        session_url = f"{base_drive_url}:/createUploadSession"
        try:
            session_resp = self.session.post(
                session_url,
                headers=headers,
                json={"item": {"@microsoft.graph.conflictBehavior": "rename", "name": clean_filename}},
                timeout=self.timeout
            )
            if session_resp.status_code not in (200, 201):
                err = session_resp.json().get("error", {}).get("message") if session_resp.text else session_resp.text
                raise ProviderError(f"Failed to create Teams upload session ({session_resp.status_code}): {err}", status_code=session_resp.status_code)
            upload_url = session_resp.json().get("uploadUrl")
            if not upload_url:
                raise ProviderError("Teams upload session returned no uploadUrl")

            chunk_size = 320 * 1024  # 320 KB chunk
            last_item = None
            for offset in range(0, size, chunk_size):
                chunk = file_bytes[offset:offset + chunk_size]
                chunk_len = len(chunk)
                range_header = f"bytes {offset}-{offset + chunk_len - 1}/{size}"
                chunk_headers = {
                    "Content-Length": str(chunk_len),
                    "Content-Range": range_header
                }
                c_resp = self.session.put(upload_url, data=chunk, headers=chunk_headers, timeout=self.timeout * 2)
                if c_resp.status_code in (200, 201):
                    last_item = c_resp.json()
                elif c_resp.status_code != 202:
                    raise ProviderError(f"Teams chunk upload failed ({c_resp.status_code}): {c_resp.text}", status_code=c_resp.status_code)

            if last_item:
                return {
                    "id": last_item.get("id"),
                    "name": last_item.get("name", clean_filename),
                    "webUrl": last_item.get("webUrl") or last_item.get("@microsoft.graph.downloadUrl"),
                    "downloadUrl": last_item.get("@microsoft.graph.downloadUrl")
                }
            raise ProviderError("Teams chunked upload finished without item metadata")
        except requests.RequestException as exc:
            raise ProviderError(f"Teams chunk upload network error: {exc}", status_code=503)

    def _resolve_and_upload_teams_media(self, message: Dict[str, Any], target) -> None:
        """
        Converts media_references into completed Microsoft Teams SharePoint/OneDrive
        reference attachments with webUrl, name, and id.
        """
        data = message.get("data")
        if not isinstance(data, dict):
            return

        media_refs = data.get("media_references", [])
        if not media_refs or not isinstance(media_refs, list):
            return

        current_attachments = data.get("attachments", [])
        if not isinstance(current_attachments, list):
            current_attachments = []

        team_id = getattr(target, "team_id", None)

        for ref in media_refs:
            raw_bytes = ref.get("raw_bytes")
            if not raw_bytes and ref.get("storage_key"):
                try:
                    from app.modules.media.storage import get_storage_backend
                    storage = get_storage_backend()
                    raw_bytes = storage.get_bytes(
                        ref["storage_key"],
                        organization_id=self.organization_id or message.get("organization_id"),
                    )
                except Exception as exc:
                    logger.warning("Could not read Teams media bytes from storage: %s", exc)

            if raw_bytes:
                drive_item = self.upload_file_to_sharepoint_or_onedrive(
                    file_bytes=raw_bytes,
                    filename=ref.get("filename", "attachment.pdf"),
                    mime_type=ref.get("mime_type", "application/octet-stream"),
                    team_id=team_id
                )
                current_attachments.append({
                    "id": drive_item.get("id") or str(uuid.uuid4()),
                    "contentType": "reference",
                    "contentUrl": drive_item.get("webUrl"),
                    "name": drive_item.get("name") or ref.get("filename")
                })
            elif ref.get("contentUrl"):
                current_attachments.append({
                    "id": ref.get("id") or str(uuid.uuid4()),
                    "contentType": "reference",
                    "contentUrl": ref.get("contentUrl"),
                    "name": ref.get("filename", "attachment")
                })

        data["attachments"] = current_attachments

    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatch message to Microsoft Teams via Microsoft Graph API v1.0.
        Supports chats and channels, Adaptive Cards, HTML, and file references.
        """
        # 1. Resolve target and upload media references to SharePoint/OneDrive if needed
        pre_target = TeamsPayloadValidator.resolve_recipient(
            message.get("recipient"),
            message.get("data") if isinstance(message.get("data"), dict) else {}
        )
        self._resolve_and_upload_teams_media(message, pre_target)

        # 2. Validate and format
        target, payload = TeamsPayloadValidator.validate_and_format(message)
        target_url = self._resolve_endpoint(target)

        # 2. Acquire access token
        token = self.auth_client.get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # 3. HTTP POST to Microsoft Graph API
        try:
            resp = self.session.post(
                target_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            # Auto-retry once on 401 (token might have been revoked or expired on server)
            if resp.status_code == 401:
                logger.info("Received HTTP 401 from Microsoft Graph; forcing token refresh and retrying...")
                token = self.auth_client.get_access_token(force_refresh=True)
                headers["Authorization"] = f"Bearer {token}"
                resp = self.session.post(
                    target_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )

        except requests.RequestException as exc:
            redacted = redact_sensitive(str(exc), [self.client_secret])
            logger.error("Microsoft Graph API network error: %s", redacted)
            raise ProviderError(
                f"Microsoft Graph API network error: {redacted}",
                status_code=503,
                retryable=True,
                error_code="GRAPH_NETWORK_ERROR",
                retry_after=5
            )

        # Parse JSON response
        try:
            resp_data = resp.json()
        except ValueError:
            resp_data = {"raw_text": resp.text}

        # 4. Handle HTTP Error Statuses
        if resp.status_code not in (200, 201):
            error_obj = resp_data.get("error", {})
            error_code = error_obj.get("code")
            error_msg = error_obj.get("message") or resp.text

            is_retryable, retry_after = classify_teams_error(
                status_code=resp.status_code,
                error_code=error_code,
                error_message=error_msg,
                headers=dict(resp.headers)
            )

            redacted_msg = redact_sensitive(
                error_msg,
                [self.client_secret]
            )

            logger.warning(
                "Microsoft Graph Teams error HTTP %s: code=%s msg=%s retryable=%s",
                resp.status_code, error_code, redacted_msg, is_retryable
            )

            raise ProviderError(
                f"Microsoft Teams Graph API error {error_code or resp.status_code}: {redacted_msg}",
                status_code=resp.status_code,
                retryable=is_retryable,
                error_code=error_code or resp.status_code,
                retry_after=retry_after
            )

        # 5. Extract Microsoft Graph Message ID
        provider_message_id = resp_data.get("id")
        if not provider_message_id:
            logger.warning("Microsoft Graph returned 201 Created but no message ID found: %s", resp_data)
            provider_message_id = f"teams_msg_{uuid.uuid4().hex[:16]}"

        return normalize_teams_response(
            success=True,
            provider="teams",
            channel="microsoft_teams",
            provider_message_id=str(provider_message_id),
            status="ACCEPTED",
            recipient=message.get("recipient"),
            target_type=target.target_type,
            chat_id=target.chat_id,
            team_id=target.team_id,
            channel_id=target.channel_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            raw_response=resp_data
        )

    def get_status(self, provider_message_id: str) -> Dict[str, Any]:
        """Query message delivery status representation."""
        if not provider_message_id:
            raise ValueError("Provider message ID is required")

        return normalize_teams_response(
            success=True,
            provider="teams",
            channel="microsoft_teams",
            provider_message_id=provider_message_id,
            status="UNKNOWN",
            timestamp=datetime.now(timezone.utc).isoformat()
        )


class MockTeamsAdapter(BaseChannelAdapter):
    """
    Mock adapter for Microsoft Teams channel.
    Simulates Microsoft Graph delivery without calling Microsoft servers.
    """

    def validate(self, message: Dict[str, Any]) -> bool:
        recipient = message.get("recipient")
        data = message.get("data", {})

        if not recipient and not data.get("chat_id") and not (data.get("team_id") and data.get("channel_id")):
            raise ValueError("Teams recipient (chat_id or team_id/channel_id) is required")

        content = (
            data.get("text")
            or data.get("message")
            or data.get("html")
            or data.get("body")
            or data.get("adaptive_card")
            or data.get("card")
            or data.get("attachments")
        )
        if not content:
            raise ValueError("Teams message requires text, HTML, or card content")

        return True

    def format_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        target, payload = TeamsPayloadValidator.validate_and_format(message)
        return {
            "channel": "microsoft_teams",
            "target_type": target.target_type,
            "target": target.chat_id if target.target_type == "chat" else f"{target.team_id}:{target.channel_id}",
            "payload": payload
        }

    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        self.validate(message)
        data = message.get("data", {})
        scenario = data.get("mock_scenario", "success")
        retry_count = message.get("retry_count", 0)

        if scenario == "permanent_failure":
            raise ProviderError(
                "Simulated Teams permanent failure: 403 Forbidden - Application lacks Chat.ReadWrite.All permission",
                status_code=403,
                retryable=False,
                error_code="Forbidden"
            )

        if scenario == "temporary_failure":
            raise ProviderError(
                "Simulated Teams temporary failure: 503 Service Unavailable",
                status_code=503,
                retryable=True,
                error_code="ServiceUnavailable",
                retry_after=5
            )

        if scenario == "temporary_then_success" and retry_count < 2:
            raise ProviderError(
                "Simulated Teams throttling: 429 Too Many Requests",
                status_code=429,
                retryable=True,
                error_code="ThrottledRequest",
                retry_after=10
            )

        mock_id = f"mock_teams_{uuid.uuid4().hex[:12]}"
        return normalize_teams_response(
            success=True,
            provider="mock",
            channel="microsoft_teams",
            provider_message_id=mock_id,
            status="ACCEPTED",
            recipient=message.get("recipient"),
            raw_response={"mock": True, "id": mock_id}
        )

    def get_status(self, provider_message_id: str) -> Dict[str, Any]:
        return normalize_teams_response(
            success=True,
            provider="mock",
            channel="microsoft_teams",
            provider_message_id=provider_message_id,
            status="DELIVERED"
        )
