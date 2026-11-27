"""
SenderX Email Utilities
Common helpers for recipient parsing, attachment validation, template rendering,
and response normalization across production email providers (SendGrid, SES, SMTP).
"""

import base64
from datetime import datetime, timezone
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from jinja2.sandbox import SandboxedEnvironment

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_SINGLE_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_TOTAL_ATTACHMENT_BYTES = 25 * 1024 * 1024   # 25 MB
PROTECTED_EMAIL_HEADERS = {
    "from", "to", "cc", "bcc", "sender", "subject", "reply-to", "return-path"
}


def validate_no_crlf(value: Any, field_name: str = "header value") -> str:
    """Reject CR, LF, and NUL characters to prevent SMTP/email header injection."""
    if value is None:
        return ""
    text = str(value)
    if any(ch in text for ch in ("\r", "\n", "\x00")):
        raise ValueError(f"Illegal newline or control character in email {field_name}")
    return text


def validate_email_headers(headers: Any) -> Dict[str, str]:
    """Validate custom email headers against header injection and protected-header overrides."""
    if not headers:
        return {}
    if not isinstance(headers, dict):
        raise ValueError("Email headers must be a key-value object")
    cleaned: Dict[str, str] = {}
    for raw_key, raw_val in headers.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ValueError("Custom email header name must be a non-empty string")
        key = validate_no_crlf(raw_key.strip(), "header name")
        if ":" in key:
            raise ValueError("Custom email header name cannot contain ':'")
        if key.lower() in PROTECTED_EMAIL_HEADERS:
            raise ValueError(f"Email header '{key}' cannot be overridden via custom headers")
        val = validate_no_crlf(raw_val, f"header '{key}'")
        cleaned[key] = val
    return cleaned


def is_valid_email(email: str) -> bool:
    """Validate a single email address format."""
    if not isinstance(email, str):
        return False
    email = email.strip()
    return bool(EMAIL_REGEX.match(email))


def parse_recipients(value: Any) -> List[str]:
    """
    Parse a recipient field into a list of valid email addresses.
    Supports single email string, comma-separated string, or list of strings.
    """
    if not value:
        return []

    if isinstance(value, str):
        # Support comma or semicolon separated addresses
        parts = re.split(r"[,;]", value)
        cleaned = [p.strip() for p in parts if p.strip()]
    elif isinstance(value, (list, tuple, set)):
        cleaned = [str(p).strip() for p in value if p and str(p).strip()]
    else:
        cleaned = [str(value).strip()]

    # Validate each address
    for email in cleaned:
        if not is_valid_email(email):
            raise ValueError(f"Invalid email address: '{email}'")

    return cleaned


def validate_attachment(attachment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize an email attachment.
    Supported fields:
    - filename: string (required, no path traversal)
    - content: base64 string or bytes (required)
    - mime_type: string (optional, defaults to application/octet-stream)
    """
    if not isinstance(attachment, dict):
        raise ValueError("Attachment must be an object")

    filename = attachment.get("filename")
    if not filename or not isinstance(filename, str):
        raise ValueError("Attachment filename is required")

    filename = os.path.basename(filename.strip())
    if not filename or ".." in filename:
        raise ValueError(f"Invalid attachment filename: '{filename}'")

    mime_type = attachment.get("mime_type") or attachment.get("content_type") or "application/octet-stream"
    if "/" not in mime_type:
        mime_type = "application/octet-stream"

    content = attachment.get("content")
    if content is None:
        raise ValueError(f"Attachment content is required for file '{filename}'")

    if isinstance(content, bytes):
        raw_bytes = content
        base64_content = base64.b64encode(content).decode("ascii")
    elif isinstance(content, str):
        content_str = content.strip()
        try:
            raw_bytes = base64.b64decode(content_str, validate=True)
            base64_content = content_str
        except Exception:
            # If not valid base64, encode the string as raw bytes
            raw_bytes = content_str.encode("utf-8")
            base64_content = base64.b64encode(raw_bytes).decode("ascii")
    else:
        raise ValueError(f"Unsupported attachment content type for '{filename}'")

    # Size check
    size = len(raw_bytes)
    if size > MAX_SINGLE_ATTACHMENT_BYTES:
        raise ValueError(
            f"Attachment '{filename}' ({size} bytes) exceeds maximum single file limit of {MAX_SINGLE_ATTACHMENT_BYTES} bytes"
        )

    return {
        "filename": filename,
        "mime_type": mime_type,
        "raw_bytes": raw_bytes,
        "base64_content": base64_content,
        "size": size
    }


def validate_attachments(attachments: Any) -> List[Dict[str, Any]]:
    """Validate a list of attachments and enforce total size limit."""
    if not attachments:
        return []

    if not isinstance(attachments, list):
        raise ValueError("Attachments must be a list")

    normalized = []
    total_size = 0

    for att in attachments:
        item = validate_attachment(att)
        total_size += item["size"]
        if total_size > MAX_TOTAL_ATTACHMENT_BYTES:
            raise ValueError(
                f"Total attachment size ({total_size} bytes) exceeds maximum limit of {MAX_TOTAL_ATTACHMENT_BYTES} bytes"
            )
        normalized.append(item)

    return normalized


def render_template(template_text: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """
    Render a Jinja2 template string safely with the given variables.
    Falls back to template_text if variables are empty or rendering fails.
    """
    if not template_text or not variables:
        return template_text or ""

    try:
        env = SandboxedEnvironment(autoescape=True)
        tmpl = env.from_string(template_text)
        return tmpl.render(**variables)
    except Exception:
        # Fallback to simple string substitution if Jinja syntax error
        rendered = template_text
        for key, val in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(val))
            rendered = rendered.replace(f"{{{key}}}", str(val))
        return rendered


def redact_sensitive(text: str, secrets: List[Optional[str]]) -> str:
    """Redact sensitive keys, passwords, and tokens from error messages and logs."""
    if not text:
        return ""
    result = str(text)
    for secret in secrets:
        if secret and len(secret) > 4:
            result = result.replace(secret, "[REDACTED]")
    return result


def normalize_provider_response(
    success: bool,
    provider: str,
    channel: str = "email",
    provider_message_id: Optional[str] = None,
    status: str = "ACCEPTED",
    timestamp: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Produce a normalized response structure across all providers.
    Distinguishes between provider acceptance and final delivery.
    """
    return {
        "success": bool(success),
        "provider": str(provider),
        "channel": str(channel),
        "provider_message_id": provider_message_id,
        "status": status,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "error_code": error_code,
        "error_message": error_message
    }
