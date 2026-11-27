"""
Trusted Client IP Extraction for Reverse Proxy Environments.

Reuses SenderX's Phase 2 trusted-proxy configuration (`TRUST_PROXY_HEADERS` and
`TRUSTED_PROXY_IPS`) so arbitrary clients cannot spoof `X-Forwarded-For` or
`X-Real-IP` to bypass rate limits or frame another client's rate-limit bucket.
"""

import ipaddress
from typing import List, Optional

from flask import current_app, has_app_context


def _parse_valid_ip(raw_value: Optional[str]) -> Optional[str]:
    if not raw_value or not isinstance(raw_value, str):
        return None
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    # Strip optional IPv4 :port or bracketed [IPv6]:port safely
    if cleaned.startswith("[") and "]" in cleaned:
        cleaned = cleaned[1:cleaned.index("]")]
    elif cleaned.count(":") == 1 and "." in cleaned:
        cleaned = cleaned.split(":", 1)[0]
    try:
        return str(ipaddress.ip_address(cleaned))
    except ValueError:
        return None


def _is_trusted_proxy_ip(ip_str: Optional[str], trusted_proxy_entries: List[str]) -> bool:
    parsed_ip_str = _parse_valid_ip(ip_str)
    if not parsed_ip_str:
        return False
    remote_ip = ipaddress.ip_address(parsed_ip_str)

    for entry in trusted_proxy_entries or []:
        clean_entry = str(entry).strip()
        if not clean_entry:
            continue
        try:
            if "/" in clean_entry:
                if remote_ip in ipaddress.ip_network(clean_entry, strict=False):
                    return True
            else:
                if remote_ip == ipaddress.ip_address(clean_entry):
                    return True
        except ValueError:
            continue
    return False


def resolve_client_ip(flask_request) -> str:
    """
    Resolve the trustworthy client IP address from the Flask request.

    - Ignores X-Forwarded-For and X-Real-IP unless TRUST_PROXY_HEADERS=True AND
      request.remote_addr matches an entry in TRUSTED_PROXY_IPS.
    - When behind trusted proxies, inspects X-Forwarded-For from right to left,
      stripping trusted proxy hops so client-injected leftmost entries cannot
      spoof identity.
    - Validates every candidate with ipaddress.ip_address.
    """
    cfg = current_app.config if has_app_context() else {}
    trust_proxy = bool(cfg.get("TRUST_PROXY_HEADERS", False))
    trusted_ips = list(cfg.get("TRUSTED_PROXY_IPS") or [])

    direct_ip = _parse_valid_ip(getattr(flask_request, "remote_addr", None))
    if not trust_proxy or not direct_ip or not _is_trusted_proxy_ip(direct_ip, trusted_ips):
        return direct_ip or "unknown"

    headers = getattr(flask_request, "headers", {}) or {}
    xff = headers.get("X-Forwarded-For")
    if isinstance(xff, str) and xff.strip():
        parts = [part.strip() for part in xff.split(",") if part.strip()]
        # Walk right-to-left skipping trusted proxy hops
        for candidate in reversed(parts):
            parsed = _parse_valid_ip(candidate)
            if not parsed:
                break
            if not _is_trusted_proxy_ip(parsed, trusted_ips):
                return parsed
        # If every hop was a trusted proxy, fall through safely to rightmost valid or X-Real-IP

    real_ip = _parse_valid_ip(headers.get("X-Real-IP"))
    if real_ip and not _is_trusted_proxy_ip(real_ip, trusted_ips):
        return real_ip

    return direct_ip
