"""
SenderX WhatsApp Business Cloud API Utilities
Includes:
- Media MIME type and file size validation
- HMAC-SHA256 signature verification for Meta webhooks
- Meta Graph API error classification (retryable vs permanent)
- Sensitive credential redaction
- Response normalization
"""

import hashlib
import hmac
import mimetypes
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Supported media types and size limits per official Meta WhatsApp Cloud API
WHATSAPP_MEDIA_LIMITS: Dict[str, Dict[str, Any]] = {
    "image": {
        "max_bytes": 5 * 1024 * 1024,  # 5 MB
        "mimes": {"image/jpeg", "image/png"},
        "extensions": {".jpg", ".jpeg", ".png"}
    },
    "video": {
        "max_bytes": 16 * 1024 * 1024,  # 16 MB
        "mimes": {"video/mp4", "video/3gpp"},
        "extensions": {".mp4", ".3gp"}
    },
    "audio": {
        "max_bytes": 16 * 1024 * 1024,  # 16 MB
        "mimes": {"audio/aac", "audio/mp4", "audio/mpeg", "audio/amr", "audio/ogg"},
        "extensions": {".aac", ".m4a", ".mp3", ".amr", ".ogg", ".opus"}
    },
    "document": {
        "max_bytes": 100 * 1024 * 1024,  # 100 MB
        "mimes": {
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/plain",
            "application/zip",
            "application/octet-stream"
        },
        "extensions": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".zip"}
    },
    "sticker": {
        "max_bytes": 500 * 1024,  # 500 KB for animated, 100 KB for static
        "mimes": {"image/webp"},
        "extensions": {".webp"}
    }
}

# Meta WhatsApp Graph API Error Code Catalog
# Permanent errors (non-retryable)
PERMANENT_ERROR_CODES = {
    190: "Invalid or expired OAuth token",
    100: "Invalid parameter or malformed request",
    131008: "Required parameter missing",
    131009: "Parameter value is invalid",
    131016: "Service unavailable due to payment/credit issue",
    131026: "Message undeliverable: recipient unavailable or unreachable",
    131030: "Recipient phone number is not on allowed list or not registered on WhatsApp",
    131047: "Re-engagement message: 24h conversation window closed; must use approved template",
    131051: "Unsupported message type",
    131052: "Media download error on Meta server",
    131053: "Media upload error or unsupported media format",
    132000: "Template does not exist or has not been approved",
    132001: "Template format does not match",
    132005: "Template hydration failed or variable count mismatch",
    132007: "Template is paused or rejected",
    132015: "Template content paused due to low quality",
    133000: "Incompatible client version",
}

# Retryable errors
RETRYABLE_ERROR_CODES = {
    130429: ("Cloud API rate limit hit", 10),
    131056: ("Pairing rate limit hit", 15),
    131000: ("Internal Meta service error; please retry", 5),
    2: ("Temporary Meta service downtime", 5),
    1: ("Temporary unknown Meta server error", 5),
    80007: ("Rate limit exceeded", 10),
}


def validate_media_file(
    media_type: str,
    mime_type: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    filename: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate media against Meta WhatsApp size and MIME constraints.
    Returns (is_valid, error_message).
    """
    mtype = (media_type or "").lower().strip()
    if mtype not in WHATSAPP_MEDIA_LIMITS:
        return False, f"Unsupported media type '{media_type}'. Must be one of: {list(WHATSAPP_MEDIA_LIMITS.keys())}"

    limits = WHATSAPP_MEDIA_LIMITS[mtype]

    # 1. Size check
    if file_size_bytes is not None:
        if file_size_bytes > limits["max_bytes"]:
            max_mb = limits["max_bytes"] / (1024 * 1024)
            actual_mb = file_size_bytes / (1024 * 1024)
            return False, f"{mtype.capitalize()} exceeds maximum allowed size of {max_mb:.1f} MB (got {actual_mb:.2f} MB)"

    # 2. MIME type check
    resolved_mime = mime_type
    if not resolved_mime and filename:
        guessed_type, _ = mimetypes.guess_type(filename)
        if guessed_type:
            resolved_mime = guessed_type

    if resolved_mime:
        clean_mime = resolved_mime.lower().split(";")[0].strip()
        # For document, allow broader types
        if mtype != "document" and clean_mime not in limits["mimes"]:
            return False, f"MIME type '{clean_mime}' is not supported for {mtype}. Allowed: {sorted(limits['mimes'])}"

    return True, None


def verify_meta_signature(
    raw_payload: bytes,
    signature_header: Optional[str],
    app_secret: str
) -> bool:
    """
    Verify Meta webhook X-Hub-Signature-256 header.
    Format: sha256=<hex_digest>
    """
    if not raw_payload or not signature_header or not app_secret:
        return False

    clean_header = signature_header.strip()
    if not clean_header.startswith("sha256="):
        return False

    expected_signature = clean_header[len("sha256="):].strip()
    if not expected_signature:
        return False

    try:
        computed_signature = hmac.new(
            app_secret.encode("utf-8"),
            raw_payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, computed_signature)
    except Exception:
        return False


def classify_whatsapp_error(
    code: Optional[int],
    subcode: Optional[int] = None,
    http_status: Optional[int] = None,
    error_message: Optional[str] = None
) -> Tuple[bool, Optional[int]]:
    """
    Classify Meta Graph API error codes into (is_retryable, retry_after_seconds).
    """
    # 1. Explicit retryable codes
    if code in RETRYABLE_ERROR_CODES:
        _, retry_after = RETRYABLE_ERROR_CODES[code]
        return True, retry_after

    # 2. Explicit permanent codes
    if code in PERMANENT_ERROR_CODES:
        return False, None

    # 3. HTTP status fallback
    if http_status == 429:
        return True, 10
    if http_status in (500, 502, 503, 504):
        return True, 5
    if http_status and 400 <= http_status < 500:
        return False, None

    # 4. Message heuristics
    if error_message:
        low = error_message.lower()
        if "rate limit" in low or "throttled" in low or "too many requests" in low:
            return True, 10
        if "temporarily unavailable" in low or "service unavailable" in low or "timeout" in low:
            return True, 5

    return False, None


def redact_sensitive(text: str, secrets: List[Optional[str]]) -> str:
    """Redact sensitive credentials (tokens, app secrets) from logs or error messages."""
    if not text:
        return text

    redacted = str(text)
    for s in secrets:
        if s and isinstance(s, str) and len(s) > 4:
            masked = f"{s[:3]}...{s[-3:]}"
            redacted = redacted.replace(s, masked)
    return redacted


def normalize_whatsapp_response(
    success: bool,
    provider: str = "meta",
    channel: str = "whatsapp",
    provider_message_id: Optional[str] = None,
    status: str = "ACCEPTED",
    recipient: Optional[str] = None,
    timestamp: Optional[str] = None,
    error_code: Optional[Any] = None,
    error_message: Optional[str] = None,
    is_retryable: bool = False,
    raw_response: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Return unified normalized dictionary representation of WhatsApp provider response."""
    return {
        "success": bool(success),
        "provider": provider,
        "channel": channel,
        "provider_message_id": provider_message_id,
        "status": status,
        "recipient": recipient,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "error_code": str(error_code) if error_code is not None else None,
        "error_message": error_message,
        "is_retryable": is_retryable,
        "raw_response": raw_response
    }
