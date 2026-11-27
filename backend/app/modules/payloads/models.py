"""
SenderX Ingested Payload & Routing Models
Definitions for payload lifecycle, failure codes, validation, and sanitization.
"""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple


CANONICAL_ROUTING_CHANNELS: Set[str] = {
    "email",
    "sms",
    "whatsapp",
    "teams"
}

SUPPORTED_ROUTING_CHANNELS: Set[str] = {
    "email",
    "sms",
    "whatsapp",
    "teams",
    "microsoft_teams",
    "msteams"
}

# Aliases to normalize channel identifiers to canonical channel names
CHANNEL_ALIASES: Dict[str, str] = {
    "teams": "teams",
    "microsoft_teams": "teams",
    "msteams": "teams",
    "email": "email",
    "sms": "sms",
    "whatsapp": "whatsapp"
}

# Machine-readable failure codes
class PayloadFailureCode:
    MISSING_CHANNEL = "MISSING_CHANNEL"
    UNSUPPORTED_CHANNEL = "UNSUPPORTED_CHANNEL"
    INVALID_JSON_STRUCTURE = "INVALID_JSON_STRUCTURE"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    JSON_NESTING_TOO_DEEP = "JSON_NESTING_TOO_DEEP"
    MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"
    INVALID_RECIPIENT = "INVALID_RECIPIENT"
    INVALID_MESSAGE_DATA = "INVALID_MESSAGE_DATA"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    ROUTING_FAILED = "ROUTING_FAILED"


# Payload lifecycle statuses
class PayloadStatus:
    INGESTED = "INGESTED"
    ROUTED = "ROUTED"
    IN_DLQ = "IN_DLQ"
    EDITED = "EDITED"
    DISPATCHING = "DISPATCHING"
    DISPATCHED = "DISPATCHED"
    FAILED = "FAILED"


# Sensitive keys for redaction
SENSITIVE_KEY_PATTERNS = [
    re.compile(r"api[-_]?key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"auth(orization)?", re.IGNORECASE),
    re.compile(r"private[-_]?key", re.IGNORECASE),
    re.compile(r"access[-_]?token", re.IGNORECASE),
    re.compile(r"refresh[-_]?token", re.IGNORECASE),
    re.compile(r"client[-_]?secret", re.IGNORECASE),
    re.compile(r"webhook[-_]?secret", re.IGNORECASE),
    re.compile(r"credit[-_]?card", re.IGNORECASE),
    re.compile(r"cvv", re.IGNORECASE),
    re.compile(r"pin", re.IGNORECASE),
    re.compile(r"passphrase", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
]


def redact_sensitive_payload(obj: Any) -> Any:
    """
    Recursively sanitize sensitive tokens, keys, and credentials
    from payload dictionaries or lists before logging or API rendering.
    """
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if any(pattern.search(str(k)) for pattern in SENSITIVE_KEY_PATTERNS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = redact_sensitive_payload(v)
        return sanitized
    elif isinstance(obj, list):
        return [redact_sensitive_payload(item) for item in obj]
    return obj


def calculate_json_depth(value: Any, current_depth: int = 1) -> int:
    """Iteratively calculate the maximum nesting depth of a JSON-serializable structure."""
    from app.validators.dynamic_json_validator import DynamicJSONValidator
    return DynamicJSONValidator.get_depth(value, current_depth)


def validate_json_structure_and_limits(
    payload: Any,
    max_bytes: int = 10 * 1024 * 1024,
    max_depth: int = 20
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verify root is a dictionary, valid JSON encoding, size <= max_bytes, and iterative
    complexity limits (depth, node count, array length, object keys, string length, types).
    Returns (is_valid, failure_code, error_message).
    """
    from app.validators.dynamic_json_validator import DynamicJSONValidator

    if not isinstance(payload, dict):
        return False, PayloadFailureCode.INVALID_JSON_STRUCTURE, "JSON root must be an object"

    limits = DynamicJSONValidator.resolve_limits(
        overrides={"max_bytes": max_bytes, "max_depth": max_depth},
        for_ingestion=True,
    )
    inspect_res = DynamicJSONValidator.inspect_limits_and_threats(payload, limits=limits)
    if inspect_res["type_errors"]:
        return False, PayloadFailureCode.INVALID_JSON_STRUCTURE, inspect_res["type_errors"][0]

    for err in inspect_res["limit_errors"]:
        if "depth" in err.lower():
            return False, PayloadFailureCode.JSON_NESTING_TOO_DEEP, err
        return False, PayloadFailureCode.PAYLOAD_TOO_LARGE, err

    try:
        serialized = json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return False, PayloadFailureCode.INVALID_JSON_STRUCTURE, "Invalid JSON data"

    byte_len = len(serialized.encode("utf-8"))
    if byte_len > limits["max_bytes"]:
        return (
            False,
            PayloadFailureCode.PAYLOAD_TOO_LARGE,
            f"JSON payload size ({byte_len} bytes) exceeds maximum limit of {limits['max_bytes']} bytes"
        )

    return True, None, None


def validate_channel_and_routing_fields(payload: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Analyze payload for channel, recipient, and message data.
    Strict routing rules:
    - Never automatically guess or select a channel.
    - Missing channel -> MISSING_CHANNEL
    - Unsupported channel -> UNSUPPORTED_CHANNEL
    - Missing recipient or data -> MISSING_REQUIRED_FIELDS / INVALID_MESSAGE_DATA
    Returns (is_valid, normalized_channel, failure_code, error_message).
    """
    raw_channel = payload.get("channel")
    if raw_channel is None:
        return (
            False,
            None,
            PayloadFailureCode.MISSING_CHANNEL,
            "Channel is missing from incoming JSON payload. SenderX never guesses channels."
        )

    if not isinstance(raw_channel, str) or not raw_channel.strip():
        return (
            False,
            None,
            PayloadFailureCode.MISSING_CHANNEL,
            "Channel field must be a non-empty string"
        )

    clean_channel = raw_channel.strip().lower()
    if clean_channel not in SUPPORTED_ROUTING_CHANNELS:
        return (
            False,
            clean_channel,
            PayloadFailureCode.UNSUPPORTED_CHANNEL,
            f"Unsupported channel '{raw_channel}'. Supported channels: {sorted(list(SUPPORTED_ROUTING_CHANNELS))}"
        )

    normalized_channel = CHANNEL_ALIASES.get(clean_channel, clean_channel)

    recipient = payload.get("recipient")
    if recipient is None or (isinstance(recipient, str) and not recipient.strip()):
        return (
            False,
            normalized_channel,
            PayloadFailureCode.MISSING_REQUIRED_FIELDS,
            "Recipient is required for message routing"
        )

    if not isinstance(recipient, (str, list)):
        return (
            False,
            normalized_channel,
            PayloadFailureCode.INVALID_RECIPIENT,
            "Recipient must be a string or list of recipient identifiers"
        )

    if clean_channel in ("sms", "whatsapp"):
        recip_str = recipient if isinstance(recipient, str) else (recipient[0] if recipient else "")
        if not any(c.isdigit() for c in str(recip_str)):
            return (
                False,
                normalized_channel,
                PayloadFailureCode.INVALID_RECIPIENT,
                f"Invalid recipient '{recipient}' for channel '{clean_channel}': recipient must be a valid phone number"
            )

    data = payload.get("data")
    if data is None:
        return (
            False,
            normalized_channel,
            PayloadFailureCode.MISSING_REQUIRED_FIELDS,
            "Message 'data' payload object is required"
        )

    if not isinstance(data, dict) or not data:
        return (
            False,
            normalized_channel,
            PayloadFailureCode.INVALID_MESSAGE_DATA,
            "Message 'data' must be a non-empty JSON object"
        )

    return True, normalized_channel, None, None
