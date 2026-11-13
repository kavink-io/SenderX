"""
SenderX API Credential Models & Utilities
Cryptographically secure API key generation, SHA-256 hashing, and prefix extraction.
"""

from datetime import datetime, timezone
import hashlib
import re
import secrets
from typing import Any, Dict, List, Optional, Tuple


API_KEY_PREFIX = "sx_live_"


def generate_api_key(environment: str = "live") -> Tuple[str, str, str]:
    """
    Generate a cryptographically secure external API key.
    Returns:
        raw_key: full unhashed key shown ONCE to the user (e.g. sx_live_abcdef123...)
        key_prefix: short preview for dashboard identification (e.g. sx_live_abcd...)
        key_hash: SHA-256 hex digest stored in database
    """
    prefix = "sx_test_" if environment.lower() == "test" else "sx_live_"
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{prefix}{random_part}"
    
    # Prefix preview: first 12 characters (e.g. 'sx_live_ab12')
    key_prefix = raw_key[:12] + "..."
    
    # Secure hash (SHA-256)
    key_hash = hash_api_key(raw_key)
    
    return raw_key, key_prefix, key_hash


def hash_api_key(raw_key: str) -> str:
    """Compute SHA-256 hash of raw API key for storage and constant-time comparison."""
    if not raw_key or not isinstance(raw_key, str):
        raise ValueError("Raw API key must be a non-empty string")
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()
