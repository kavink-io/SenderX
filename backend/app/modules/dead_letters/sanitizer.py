"""
SenderX Dead Letter Queue & Error Sanitization Module
Provides deterministic secret redaction for error messages, stack traces, and DLQ entries.
Prevents leaking API keys, JWTs, passwords, password hashes, OTPs, provider secrets, and encryption keys.
"""

import re
from typing import Any, Dict, List, Union


# 1. Bearer / JWT Tokens (ey...)
JWT_PATTERN = re.compile(
    r"(?:Bearer\s+)?ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]*)?",
    re.IGNORECASE
)

# 2. Provider API Keys (SendGrid, Twilio, generic sk_live, etc.)
SENDGRID_KEY_PATTERN = re.compile(r"SG\.[A-Za-z0-9_\-\.]{20,}")
GENERIC_KEY_PATTERN = re.compile(r"\b(?:sk_live_|key-|whsec_)[A-Za-z0-9_\-]{16,}\b")

# 3. Bcrypt Password Hashes ($2a$, $2b$, $2y$)
BCRYPT_HASH_PATTERN = re.compile(r"\$2[abxy]\$\d{2}\$[A-Za-z0-9./]{53}")

# 4. Fernet / Base64 32-byte Encryption Keys
FERNET_KEY_PATTERN = re.compile(r"\b[A-Za-z0-9_\-]{43}=\b")

# 5. Basic Auth in URLs (https://user:pass@host)
URL_AUTH_PATTERN = re.compile(r"https?://([^:\s]+):([^@\s]+)@")

# 6. Sensitive Key-Value pairs in JSON / text error outputs
SENSITIVE_KV_PATTERN = re.compile(
    r"""(?i)(["']?(?:password|admin_password|password_hash|client_secret|secret|secret_key|api_key|token|access_token|refresh_token|auth_token|otp|otp_code|otp_secret|encryption_key|credential_encryption_key|private_key)["']?\s*[:=]\s*["']?)(?:[^"'\s,\r\n}\]]{1,300})"""
)

# 7. Isolated 6-digit OTP codes in auth error contexts
OTP_CONTEXT_PATTERN = re.compile(
    r"""(?i)\b(?:otp|code|pin|verification[_\s]*code)\b[:=\s]+["']?(\d{6})["']?"""
)


def sanitize_dlq_error(error: Any) -> str:
    """
    Sanitize an exception, error string, or dictionary error representation
    by redacting known secrets, keys, and tokens.
    """
    if error is None:
        return ""

    text = str(error)

    # 1. Redact JWTs
    text = JWT_PATTERN.sub("[REDACTED_JWT]", text)

    # 2. Redact SendGrid & API keys
    text = SENDGRID_KEY_PATTERN.sub("SG.[REDACTED_API_KEY]", text)
    text = GENERIC_KEY_PATTERN.sub("[REDACTED_API_KEY]", text)

    # 3. Redact Bcrypt hashes
    text = BCRYPT_HASH_PATTERN.sub("[REDACTED_BCRYPT_HASH]", text)

    # 4. Redact Fernet / Base64 encryption keys
    text = FERNET_KEY_PATTERN.sub("[REDACTED_ENCRYPTION_KEY]", text)

    # 5. Redact URL embedded basic credentials
    text = URL_AUTH_PATTERN.sub(r"https://[REDACTED_AUTH]@", text)

    # 6. Redact sensitive key-value pairs
    text = SENSITIVE_KV_PATTERN.sub(r"\1[REDACTED]", text)

    # 7. Redact contextual 6-digit OTPs
    text = OTP_CONTEXT_PATTERN.sub(r"code: [REDACTED_OTP]", text)

    return text


def sanitize_dlq_dict(data: Union[Dict, List, Any]) -> Any:
    """
    Recursively sanitize dictionaries/lists stored in DLQ diagnostic records
    to prevent persistence of sensitive secrets in plaintext.
    """
    sensitive_keys = {
        "password", "admin_password", "password_hash", "secret", "secret_key",
        "api_key", "token", "access_token", "refresh_token", "otp", "otp_code",
        "otp_secret", "encryption_key", "private_key", "authorization"
    }

    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if k.lower() in sensitive_keys:
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                sanitized[k] = sanitize_dlq_dict(v)
            elif isinstance(v, str):
                sanitized[k] = sanitize_dlq_error(v)
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(data, list):
        return [sanitize_dlq_dict(item) for item in data]
    elif isinstance(data, str):
        return sanitize_dlq_error(data)
    return data
