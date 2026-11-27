"""
SenderX API Credential Utilities
SHA-256 hashing for externally supplied API keys.
"""

import hashlib


def hash_api_key(raw_key: str) -> str:
    """Hash the exact supplied API key for storage and lookup."""
    if not raw_key or not isinstance(raw_key, str):
        raise ValueError("Raw API key must be a non-empty string")
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
