"""
SenderX SMS Utilities
Common helpers for:
- International E.164 phone number validation and normalization
- GSM-7 and UCS-2 encoding and multi-segment calculation
- Twilio error classification and retry determinations
- Response normalization and sensitive credential redaction
"""

from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Optional, Tuple

# Strict E.164 regex: starts with +, followed by 1-9, then 6-14 digits (total 7-15 digits)
E164_REGEX = re.compile(r"^\+[1-9]\d{6,14}$")

# Maximum concatenated SMS character length supported by Twilio
MAX_SMS_CHARACTERS = 1600

# Standard GSM 03.38 Basic Character Set
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)

# Standard GSM 03.38 Extended Character Set (each counts as 2 characters in GSM-7)
GSM7_EXTENDED = set("|^{}\\[~]|€")


def validate_e164(phone: Any) -> str:
    """
    Validate and normalize a phone number to international E.164 format (+14155552671).
    Raises ValueError if invalid.
    """
    if not phone or not isinstance(phone, (str, int)):
        raise ValueError("Phone number must be a non-empty string or integer")

    cleaned = str(phone).strip()
    # Strip common formatting characters: spaces, hyphens, parentheses, dots
    cleaned = re.sub(r"[\s\-\(\)\.]", "", cleaned)

    # If missing leading '+', check if it has valid international format
    if not cleaned.startswith("+"):
        # If it looks like digits only, prefix with '+'
        if cleaned.isdigit() and len(cleaned) >= 7 and cleaned[0] != "0":
            cleaned = f"+{cleaned}"
        else:
            raise ValueError(
                f"Invalid phone number '{phone}'. International E.164 numbers must start with '+' and country code."
            )

    if not E164_REGEX.match(cleaned):
        raise ValueError(
            f"Invalid phone number '{phone}'. Must be formatted in international E.164 format (e.g. +14155552671), "
            "containing 7 to 15 digits starting with country code."
        )

    return cleaned


def parse_sms_recipients(value: Any) -> List[str]:
    """
    Parse a recipient field into a list of normalized E.164 phone numbers.
    Supports a single phone string, comma/semicolon-separated string, or list of strings.
    """
    if not value:
        return []

    if isinstance(value, str):
        parts = re.split(r"[,;]", value)
        raw_list = [p.strip() for p in parts if p.strip()]
    elif isinstance(value, (list, tuple, set)):
        raw_list = [str(p).strip() for p in value if p and str(p).strip()]
    else:
        raw_list = [str(value).strip()]

    return [validate_e164(p) for p in raw_list]


def is_gsm7(text: str) -> bool:
    """Check if all characters in text belong to the standard GSM 7-bit alphabet."""
    if not text:
        return True
    return all(c in GSM7_BASIC or c in GSM7_EXTENDED for c in text)


def calculate_sms_segments(text: str) -> Dict[str, Any]:
    """
    Calculate encoding (GSM-7 vs UCS-2 Unicode) and segmentation counts for an SMS message.
    - GSM-7: 160 characters for single segment, 153 chars per segment if concatenated.
    - UCS-2: 70 characters for single segment, 67 chars per segment if concatenated.
    """
    if not text:
        return {
            "encoding": "GSM-7",
            "char_count": 0,
            "segments": 1,
            "max_single": 160,
            "max_concat": 153
        }

    raw_len = len(text)
    if raw_len > MAX_SMS_CHARACTERS:
        raise ValueError(
            f"SMS content length ({raw_len} characters) exceeds maximum supported limit of {MAX_SMS_CHARACTERS} characters"
        )

    if is_gsm7(text):
        # In GSM-7, characters in extended set take 2 character units
        effective_len = sum(2 if c in GSM7_EXTENDED else 1 for c in text)
        if effective_len <= 160:
            segments = 1
        else:
            segments = math.ceil(effective_len / 153)

        return {
            "encoding": "GSM-7",
            "char_count": raw_len,
            "effective_units": effective_len,
            "segments": segments,
            "max_single": 160,
            "max_concat": 153
        }
    else:
        # UCS-2 Unicode encoding
        effective_len = raw_len
        if effective_len <= 70:
            segments = 1
        else:
            segments = math.ceil(effective_len / 67)

        return {
            "encoding": "UCS-2",
            "char_count": raw_len,
            "effective_units": effective_len,
            "segments": segments,
            "max_single": 70,
            "max_concat": 67
        }


def classify_twilio_error(
    error_code: Optional[int],
    http_status: Optional[int],
    error_message: str = ""
) -> Tuple[bool, Optional[int]]:
    """
    Determine whether a Twilio API or delivery error is retryable,
    and return (is_retryable: bool, retry_after: Optional[int]).
    """
    code = int(error_code) if error_code is not None else None
    status = int(http_status) if http_status is not None else None
    msg = (error_message or "").lower()

    # 1. Rate Limiting (Twilio 20429 or HTTP 429) -> Always retryable
    if code == 20429 or status == 429:
        retry_after = 5
        # Attempt to parse Retry-After header or message
        match = re.search(r"retry[-_ ]after[:\s]+(\d+)", msg)
        if match:
            try:
                retry_after = int(match.group(1))
            except Exception:
                pass
        return True, retry_after

    # 2. Twilio temporary provider / carrier queue issues
    # 30001: Queue overflow (carrier congestion)
    # 30003: Unreachable destination handset (temporary radio outage)
    # 30008: Unknown error (temporary carrier blip)
    if code in (30001, 30008):
        return True, 10

    # 3. HTTP Server Errors (500, 502, 503, 504) -> Provider outage / gateway timeout
    if status and status in (500, 502, 503, 504):
        return True, 5

    # 4. Permanent Twilio Errors (DO NOT RETRY)
    # 20003: Authentication Error (Invalid Account SID / Auth Token)
    # 20404: Account SID not found
    # 21211: Invalid 'To' Phone Number
    # 21614: 'To' number is not a mobile number
    # 21610: Attempt to send to unsubscribed recipient
    # 21612: 'To' number cannot be reached
    # 21408: Permission to send to country/region not enabled
    # 20005: Account balance depleted / suspended
    # 21606: From number is not a valid SMS-capable Twilio number
    # 21608: Trial account restriction
    # 30002: Account suspended
    # 30004: Message blocked by carrier
    # 30005: Unknown destination handset (unallocated number)
    # 30006: Landline or unreachable carrier
    # 30007: Carrier violation (filtered as spam)
    permanent_codes = {
        20003, 20404, 21404, 20005,
        21211, 21614, 21610, 21612, 21408,
        21606, 21608,
        30002, 30004, 30005, 30006, 30007
    }
    if code in permanent_codes:
        return False, None

    # 4xx client errors (bad request, unauthorized, forbidden, not found) are non-retryable
    if status and 400 <= status < 500:
        return False, None

    # Connection / timeout keywords in error message
    if any(k in msg for k in ("timeout", "connection refused", "network unreachable", "dns")):
        return True, 5

    # Default to False for unclassified errors
    return False, None


def redact_sensitive(text: str, secrets: List[Optional[str]]) -> str:
    """Redact sensitive auth tokens, Account SIDs, and passwords from logs/errors."""
    if not text:
        return ""
    result = str(text)
    for s in secrets:
        if s and len(s) > 4:
            result = result.replace(s, "[REDACTED]")
    return result


def normalize_sms_response(
    success: bool,
    provider: str = "twilio",
    channel: str = "sms",
    provider_message_id: Optional[str] = None,
    status: str = "ACCEPTED",
    timestamp: Optional[str] = None,
    error_code: Optional[Any] = None,
    error_message: Optional[str] = None,
    segments: int = 1,
    is_retryable: bool = False,
    retry_after: Optional[int] = None
) -> Dict[str, Any]:
    """Produce a normalized response dictionary matching SenderX standard schema."""
    return {
        "success": bool(success),
        "provider": str(provider),
        "channel": str(channel),
        "provider_message_id": provider_message_id,
        "status": status,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "error_code": str(error_code) if error_code is not None else None,
        "error_message": error_message,
        "segments": int(segments),
        "is_retryable": bool(is_retryable),
        "retry_after": retry_after
    }
