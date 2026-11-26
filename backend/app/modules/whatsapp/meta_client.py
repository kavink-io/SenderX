"""
SenderX Meta WhatsApp Cloud API Client
Dedicated client for interacting with the Meta Graph API to verify
WhatsApp Business Accounts (WABA) and Phone Numbers.

Security Controls:
- All external calls use HTTPS (https://graph.facebook.com).
- Authentication uses 'Authorization: Bearer <token>' headers only.
- Access tokens are NEVER included in URL parameters, logs, or exception messages.
- HTTP redirects are disabled (allow_redirects=False) to prevent token leakage.
- Strict connection and read timeouts prevent worker hanging.
- Safe error classification distinguishing:
  * INVALID_CREDENTIALS
  * INSUFFICIENT_PERMISSIONS
  * PHONE_NUMBER_MISMATCH
  * META_API_UNAVAILABLE
  * VERIFICATION_FAILED
"""

from enum import Enum
import logging
import re
import json
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class WhatsAppVerificationErrorCode(str, Enum):
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    PHONE_NUMBER_MISMATCH = "PHONE_NUMBER_MISMATCH"
    META_API_UNAVAILABLE = "META_API_UNAVAILABLE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


class WhatsAppVerificationError(Exception):
    """
    Raised when Meta Graph API credential or WABA verification fails.
    Never exposes raw tokens in error messages or string representations.
    """

    def __init__(
        self,
        message: str,
        error_code: WhatsAppVerificationErrorCode = WhatsAppVerificationErrorCode.VERIFICATION_FAILED,
        meta_code: Optional[int] = None,
        meta_subcode: Optional[int] = None,
        fbtrace_id: Optional[str] = None,
        http_status: Optional[int] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.meta_code = meta_code
        self.meta_subcode = meta_subcode
        self.fbtrace_id = fbtrace_id
        self.http_status = http_status

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "error_code": self.error_code.value,
            "message": self.message,
        }
        if self.meta_code is not None:
            res["meta_code"] = self.meta_code
        if self.fbtrace_id:
            res["fbtrace_id"] = self.fbtrace_id
        return res


class MetaWhatsAppClient:
    """
    Client for Meta WhatsApp Business Platform Graph API verification.
    """

    DEFAULT_BASE_URL = "https://graph.facebook.com"
    DEFAULT_GRAPH_VERSION = "v21.0"
    DEFAULT_CONNECT_TIMEOUT = 5.0
    DEFAULT_READ_TIMEOUT = 15.0

    def __init__(
        self,
        base_url: Optional[str] = None,
        graph_api_version: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: Optional[tuple] = None,
    ):
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        ver = (graph_api_version or self.DEFAULT_GRAPH_VERSION).strip()
        if not ver.startswith("v"):
            ver = f"v{ver}"
        self.graph_api_version = ver
        self.session = session or requests.Session()
        self.timeout = timeout or (self.DEFAULT_CONNECT_TIMEOUT, self.DEFAULT_READ_TIMEOUT)

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        if not access_token or not isinstance(access_token, str) or not access_token.strip():
            raise WhatsAppVerificationError(
                "Access token is required and cannot be empty",
                error_code=WhatsAppVerificationErrorCode.INVALID_CREDENTIALS,
            )
        return {
            "Authorization": f"Bearer {access_token.strip()}",
            "Accept": "application/json",
            "User-Agent": "SenderX-WhatsApp-Client/1.0",
        }

    def request_graph(self, method: str, path: str, access_token: str, *, params=None, json_body=None, data=None, files=None):
        """Make a bounded, redirect-disabled Graph API request without exposing credentials."""
        clean_path = str(path or "").strip().strip("/")
        if not clean_path or "?" in clean_path or "#" in clean_path or ".." in clean_path:
            raise ValueError("Invalid Meta Graph API path")
        url = f"{self.base_url}/{self.graph_api_version}/{clean_path}"
        try:
            response = self.session.request(
                str(method).upper(), url, headers=self._get_headers(access_token),
                params=params, json=json_body, data=data, files=files,
                timeout=self.timeout, allow_redirects=False,
            )
        except requests.exceptions.Timeout as exc:
            raise WhatsAppVerificationError("Meta Graph API request timed out.", WhatsAppVerificationErrorCode.META_API_UNAVAILABLE) from exc
        except requests.exceptions.RequestException as exc:
            raise WhatsAppVerificationError("Meta Graph API is unreachable.", WhatsAppVerificationErrorCode.META_API_UNAVAILABLE) from exc
        try:
            result = response.json()
        except (ValueError, json.JSONDecodeError):
            result = {}
        if response.status_code >= 300:
            error = result.get("error", {}) if isinstance(result, dict) else {}
            raise self._classify_meta_error(response.status_code, error if isinstance(error, dict) else {})
        return result

    def _classify_meta_error(
        self, status_code: int, error_obj: Dict[str, Any]
    ) -> WhatsAppVerificationError:
        """
        Classifies Meta Graph API error codes into precise, safe verification exceptions.
        Never interpolates access tokens into error text.
        """
        meta_code = error_obj.get("code")
        meta_subcode = error_obj.get("error_subcode")
        raw_msg = str(error_obj.get("message", "Meta Graph API error"))
        fbtrace_id = error_obj.get("fbtrace_id")
        error_type = error_obj.get("type", "")

        # 1. Invalid or expired credentials (Code 190, 102, or 401 status)
        if status_code == 401 or meta_code in (190, 102) or error_type == "OAuthException" and "token" in raw_msg.lower():
            if meta_subcode in (463, 467) or "expired" in raw_msg.lower():
                msg = "WhatsApp access token has expired. Please generate a new access token."
            else:
                msg = "Invalid WhatsApp access token. The token is invalid, revoked, or malformed."
            return WhatsAppVerificationError(
                message=msg,
                error_code=WhatsAppVerificationErrorCode.INVALID_CREDENTIALS,
                meta_code=meta_code,
                meta_subcode=meta_subcode,
                fbtrace_id=fbtrace_id,
                http_status=status_code,
            )

        # 2. Insufficient permissions (Code 10, 200, 298, or 403 status with permission text)
        if (
            status_code == 403
            or meta_code in (10, 200, 298)
            or "permission" in raw_msg.lower()
            or "not authorized" in raw_msg.lower()
        ):
            return WhatsAppVerificationError(
                message="Access token has insufficient permissions for this WhatsApp Business Account or Phone Number.",
                error_code=WhatsAppVerificationErrorCode.INSUFFICIENT_PERMISSIONS,
                meta_code=meta_code,
                meta_subcode=meta_subcode,
                fbtrace_id=fbtrace_id,
                http_status=status_code,
            )

        # 3. Rate limiting / Throttling (Code 4, 17, 32, 613, 80007, or HTTP 429)
        if status_code == 429 or meta_code in (4, 17, 32, 613, 80007):
            return WhatsAppVerificationError(
                message="Meta Graph API rate limit exceeded. Please wait a moment before trying again.",
                error_code=WhatsAppVerificationErrorCode.META_API_UNAVAILABLE,
                meta_code=meta_code,
                meta_subcode=meta_subcode,
                fbtrace_id=fbtrace_id,
                http_status=status_code,
            )

        # 4. Meta service errors (HTTP 5xx)
        if status_code >= 500:
            return WhatsAppVerificationError(
                message="Meta Graph API service is temporarily unavailable. Please try again later.",
                error_code=WhatsAppVerificationErrorCode.META_API_UNAVAILABLE,
                meta_code=meta_code,
                meta_subcode=meta_subcode,
                fbtrace_id=fbtrace_id,
                http_status=status_code,
            )

        # 5. Invalid Object ID (WABA or Phone ID does not exist)
        if meta_code == 100 and ("does not exist" in raw_msg.lower() or "unsupported get request" in raw_msg.lower()):
            return WhatsAppVerificationError(
                message="The specified WhatsApp Business Account ID or Phone Number ID does not exist in Meta.",
                error_code=WhatsAppVerificationErrorCode.INVALID_CREDENTIALS,
                meta_code=meta_code,
                meta_subcode=meta_subcode,
                fbtrace_id=fbtrace_id,
                http_status=status_code,
            )

        # 6. Fallback general verification failure
        safe_msg = f"Meta Graph API verification failed: {raw_msg}"
        return WhatsAppVerificationError(
            message=safe_msg,
            error_code=WhatsAppVerificationErrorCode.VERIFICATION_FAILED,
            meta_code=meta_code,
            meta_subcode=meta_subcode,
            fbtrace_id=fbtrace_id,
            http_status=status_code,
        )

    def verify_and_fetch_metadata(
        self,
        waba_id: str,
        phone_number_id: str,
        access_token: str,
        graph_api_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the two-step verification against the Meta Graph API:
        1. Verify that the requested Phone Number ID belongs to the specified WABA:
           GET /{WABA_ID}/phone_numbers
        2. Retrieve phone number details:
           GET /{PHONE_NUMBER_ID}?fields=id,display_phone_number,verified_name,quality_rating,platform_type,code_verification_status

        Returns normalized phone number metadata if verification succeeds.
        Raises WhatsAppVerificationError if any check fails.
        """
        # Validate format
        if not waba_id or not isinstance(waba_id, str) or not waba_id.strip():
            raise WhatsAppVerificationError(
                "WhatsApp Business Account ID (waba_id) is required",
                error_code=WhatsAppVerificationErrorCode.INVALID_CREDENTIALS,
            )
        clean_waba_id = waba_id.strip()
        if not re.match(r"^[a-zA-Z0-9_\-]+$", clean_waba_id):
            raise WhatsAppVerificationError(
                "Invalid WABA ID format. Only alphanumeric characters, dashes, and underscores are allowed.",
                error_code=WhatsAppVerificationErrorCode.INVALID_CREDENTIALS,
            )

        if not phone_number_id or not isinstance(phone_number_id, str) or not phone_number_id.strip():
            raise WhatsAppVerificationError(
                "Meta Phone Number ID (phone_number_id) is required",
                error_code=WhatsAppVerificationErrorCode.INVALID_CREDENTIALS,
            )
        clean_phone_id = phone_number_id.strip()
        if not re.match(r"^[a-zA-Z0-9_\-]+$", clean_phone_id):
            raise WhatsAppVerificationError(
                "Invalid Phone Number ID format. Only alphanumeric characters, dashes, and underscores are allowed.",
                error_code=WhatsAppVerificationErrorCode.INVALID_CREDENTIALS,
            )

        if not access_token or not isinstance(access_token, str) or len(access_token.strip()) < 10:
            raise WhatsAppVerificationError(
                "A valid WhatsApp access token is required (minimum 10 characters).",
                error_code=WhatsAppVerificationErrorCode.INVALID_CREDENTIALS,
            )
        clean_token = access_token.strip()

        version = (graph_api_version or self.graph_api_version).strip()
        if not version.startswith("v"):
            version = f"v{version}"

        headers = self._get_headers(clean_token)

        # ------------------------------------------------------------------
        # Step 1: Verify WABA ownership of the phone number
        # GET https://graph.facebook.com/{version}/{waba_id}/phone_numbers
        # ------------------------------------------------------------------
        waba_phone_numbers_url = f"{self.base_url}/{version}/{clean_waba_id}/phone_numbers"
        params_waba = {
            "fields": "id,display_phone_number,verified_name,quality_rating,code_verification_status,platform_type",
            "limit": 100,
        }

        try:
            resp_waba = self.session.get(
                waba_phone_numbers_url,
                headers=headers,
                params=params_waba,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout as exc:
            logger.warning("Meta API timeout while verifying WABA phone numbers: %s", type(exc).__name__)
            raise WhatsAppVerificationError(
                "Meta API request timed out while verifying WhatsApp Business Account.",
                error_code=WhatsAppVerificationErrorCode.META_API_UNAVAILABLE,
            ) from exc
        except requests.exceptions.RequestException as exc:
            logger.warning("Meta API connection error while verifying WABA: %s", type(exc).__name__)
            raise WhatsAppVerificationError(
                "Meta API is unreachable. Please check network connectivity.",
                error_code=WhatsAppVerificationErrorCode.META_API_UNAVAILABLE,
            ) from exc

        if resp_waba.status_code != 200:
            try:
                err_data = resp_waba.json().get("error", {})
            except Exception:
                err_data = {"message": resp_waba.text[:200]}
            raise self._classify_meta_error(resp_waba.status_code, err_data)

        try:
            waba_data = resp_waba.json()
        except Exception as exc:
            raise WhatsAppVerificationError(
                "Malformed response received from Meta Graph API for WABA phone numbers.",
                error_code=WhatsAppVerificationErrorCode.VERIFICATION_FAILED,
            ) from exc

        phone_list = waba_data.get("data")
        if not isinstance(phone_list, list):
            raise WhatsAppVerificationError(
                "Unexpected response format from Meta Graph API: 'data' array missing.",
                error_code=WhatsAppVerificationErrorCode.VERIFICATION_FAILED,
            )

        # Check if requested clean_phone_id exists in the WABA's phone numbers
        matched_waba_record = None
        for item in phone_list:
            if str(item.get("id")).strip() == clean_phone_id:
                matched_waba_record = item
                break

        if not matched_waba_record:
            raise WhatsAppVerificationError(
                f"Phone Number ID '{clean_phone_id}' does not belong to WhatsApp Business Account '{clean_waba_id}'.",
                error_code=WhatsAppVerificationErrorCode.PHONE_NUMBER_MISMATCH,
            )

        # ------------------------------------------------------------------
        # Step 2: Retrieve Phone Number Details
        # GET https://graph.facebook.com/{version}/{phone_number_id}
        # ------------------------------------------------------------------
        phone_url = f"{self.base_url}/{version}/{clean_phone_id}"
        params_phone = {
            "fields": "id,display_phone_number,verified_name,quality_rating,platform_type,code_verification_status",
        }

        try:
            resp_phone = self.session.get(
                phone_url,
                headers=headers,
                params=params_phone,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout as exc:
            logger.warning("Meta API timeout while fetching phone details: %s", type(exc).__name__)
            raise WhatsAppVerificationError(
                "Meta API request timed out while retrieving phone number details.",
                error_code=WhatsAppVerificationErrorCode.META_API_UNAVAILABLE,
            ) from exc
        except requests.exceptions.RequestException as exc:
            logger.warning("Meta API connection error while fetching phone details: %s", type(exc).__name__)
            raise WhatsAppVerificationError(
                "Meta API is unreachable while retrieving phone number details.",
                error_code=WhatsAppVerificationErrorCode.META_API_UNAVAILABLE,
            ) from exc

        if resp_phone.status_code != 200:
            try:
                err_data = resp_phone.json().get("error", {})
            except Exception:
                err_data = {"message": resp_phone.text[:200]}
            raise self._classify_meta_error(resp_phone.status_code, err_data)

        try:
            phone_details = resp_phone.json()
        except Exception as exc:
            raise WhatsAppVerificationError(
                "Malformed response received from Meta Graph API for phone number details.",
                error_code=WhatsAppVerificationErrorCode.VERIFICATION_FAILED,
            ) from exc

        # Merge metadata with preference to direct phone details, fallback to matched WABA record
        display_phone_number = (
            phone_details.get("display_phone_number")
            or matched_waba_record.get("display_phone_number")
        )
        verified_name = (
            phone_details.get("verified_name")
            or matched_waba_record.get("verified_name")
        )
        quality_rating = (
            phone_details.get("quality_rating")
            or matched_waba_record.get("quality_rating")
            or "UNKNOWN"
        )
        platform_type = (
            phone_details.get("platform_type")
            or matched_waba_record.get("platform_type")
            or "CLOUD_API"
        )
        code_verification_status = (
            phone_details.get("code_verification_status")
            or matched_waba_record.get("code_verification_status")
            or "VERIFIED"
        )

        if not display_phone_number:
            raise WhatsAppVerificationError(
                "Meta did not return a valid display_phone_number for this phone number ID.",
                error_code=WhatsAppVerificationErrorCode.VERIFICATION_FAILED,
            )

        return {
            "verified": True,
            "waba_id": clean_waba_id,
            "phone_number_id": clean_phone_id,
            "display_phone_number": str(display_phone_number).strip(),
            "verified_name": str(verified_name).strip() if verified_name else None,
            "quality_rating": str(quality_rating).strip().upper() if quality_rating else "UNKNOWN",
            "platform_type": str(platform_type).strip().upper() if platform_type else "CLOUD_API",
            "code_verification_status": str(code_verification_status).strip().upper() if code_verification_status else "VERIFIED",
        }
