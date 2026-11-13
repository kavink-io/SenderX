"""
SenderX Microsoft Teams & Graph API Utilities
Includes:
- Delegated permission scopes configuration
- Cryptographic state generation & validation for OAuth 2.0 authorization code flow
- Error classification for Microsoft Graph API (permanent vs retryable with Retry-After)
- Sensitive credential masking (client_secret, access_token, refresh_token)
- Standardized response normalization
"""

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import jwt
from jwt import PyJWKClient, ExpiredSignatureError, InvalidAudienceError, InvalidIssuerError, InvalidTokenError

# Official delegated scopes required for normal Microsoft Teams messaging:
# - ChatMessage.Send: Send messages in 1:1 and group chats
# - ChannelMessage.Send: Send messages in team channels
# - openid, profile: Retrieve connected user identity (UPN/email)
# - offline_access: Retrieve refresh_token for persistent background token refresh
TEAMS_DELEGATED_SCOPES = [
    "https://graph.microsoft.com/ChatMessage.Send",
    "https://graph.microsoft.com/ChannelMessage.Send",
    "openid",
    "profile",
    "offline_access"
]

# Configured redirect URI allowlist to prevent open redirect and token leakage
DEFAULT_ALLOWED_REDIRECT_URIS = [
    "https://api.senderx.io/api/v1/provider-config/teams/oauth/callback",
    "https://senderx.io/api/v1/provider-config/teams/oauth/callback",
    "http://localhost:5000/api/v1/provider-config/teams/oauth/callback",
    "http://127.0.0.1:5000/api/v1/provider-config/teams/oauth/callback",
    "http://localhost:3000/callback",
    "http://127.0.0.1:3000/callback"
]


def generate_pkce_pair() -> Tuple[str, str]:
    """
    Generate RFC 7636 PKCE code_verifier and code_challenge (S256).
    code_verifier is high-entropy 43-128 unreserved URL-safe characters.
    code_challenge = base64url(sha256(code_verifier)).
    """
    code_verifier = base64.urlsafe_b64encode(os.urandom(64)).decode("utf-8").rstrip("=")
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


def verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    """Verify that sha256(code_verifier) matches code_challenge using constant-time comparison."""
    if not code_verifier or not code_challenge:
        return False
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    computed_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return hmac.compare_digest(computed_challenge, code_challenge)


def is_redirect_uri_allowed(redirect_uri: str, allowed_uris: Optional[List[str]] = None) -> bool:
    """
    Validate that redirect_uri is within the configured allowlist.
    Prevents open redirect and authorization code interception attacks.
    """
    if not redirect_uri or not isinstance(redirect_uri, str):
        return False

    clean_uri = redirect_uri.strip().rstrip("/")
    target_allowlist = allowed_uris if allowed_uris is not None else DEFAULT_ALLOWED_REDIRECT_URIS
    clean_allowlist = [u.strip().rstrip("/") for u in target_allowlist if u]

    return clean_uri in clean_allowlist


# OpenID Connect Discovery & JWKS endpoints
MICROSOFT_COMMON_JWKS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
_jwks_clients: Dict[str, PyJWKClient] = {}
_jwks_lock = threading.Lock()


def get_microsoft_jwks_client(jwks_url: Optional[str] = None, tenant_id: Optional[str] = None) -> PyJWKClient:
    """
    Retrieve or initialize cached PyJWKClient with automatic key rotation support.
    """
    url = jwks_url
    if not url:
        if tenant_id and tenant_id not in ("common", "organizations", "consumers"):
            url = f"https://login.microsoftonline.com/{tenant_id.strip()}/discovery/v2.0/keys"
        else:
            url = MICROSOFT_COMMON_JWKS_URL

    with _jwks_lock:
        if url not in _jwks_clients:
            _jwks_clients[url] = PyJWKClient(
                uri=url,
                cache_keys=True,
                cache_jwk_set=True,
                lifespan=86400
            )
        return _jwks_clients[url]


def verify_microsoft_id_token(
    id_token: str,
    client_id: str,
    expected_nonce: Optional[str] = None,
    expected_tenant_id: Optional[str] = None,
    jwks_client: Optional[Any] = None,
    jwks_url: Optional[str] = None,
    signing_key: Optional[Any] = None,
    leeway: int = 60
) -> Dict[str, Any]:
    """
    Cryptographically verify Microsoft Entra ID OpenID Connect ID token:
    1. Verify header algorithm is RS256 and key ID (kid) is present.
    2. Retrieve signing key from Microsoft JWKS (handles key rotation).
    3. Verify cryptographic RSA signature.
    4. Verify audience ('aud') matches configured client_id.
    5. Verify expiration ('exp') and issued-at ('iat') claims with leeway.
    6. Verify issuer ('iss') matches Microsoft Entra ID v2.0 or v1.0 endpoint.
    7. Verify nonce matches the original OAuth transaction nonce.
    8. Verify tenant ID ('tid') matches expected tenant ID if specified.
    """
    if not id_token or not isinstance(id_token, str) or not id_token.strip():
        raise ValueError("ID token is required and cannot be empty")
    if not client_id or not isinstance(client_id, str) or not client_id.strip():
        raise ValueError("client_id is required to verify ID token audience")

    token_str = id_token.strip()

    # 1. Unverified header check
    try:
        header = jwt.get_unverified_header(token_str)
    except Exception as exc:
        raise ValueError(f"Invalid ID token format: {str(exc)}")

    alg = header.get("alg")
    if alg != "RS256":
        raise ValueError(f"Invalid ID token algorithm '{alg}'. Only RS256 is permitted.")

    kid = header.get("kid")
    if not kid and not signing_key:
        raise ValueError("ID token header is missing required 'kid' (Key ID)")

    # 2. Key resolution
    resolved_key = signing_key
    if not resolved_key:
        client = jwks_client or get_microsoft_jwks_client(jwks_url=jwks_url, tenant_id=expected_tenant_id)
        try:
            resolved_key = client.get_signing_key_from_jwt(token_str).key
        except Exception as exc:
            raise ValueError(f"Failed to obtain Microsoft signing key for kid '{kid}': {str(exc)}")

    # 3 & 4 & 5. Signature, Audience, Expiry & IAT verification
    try:
        claims = jwt.decode(
            token_str,
            resolved_key,
            algorithms=["RS256"],
            audience=client_id.strip(),
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "iat", "iss", "aud", "sub"]
            },
            leeway=leeway
        )
    except ExpiredSignatureError:
        raise ValueError("ID token has expired")
    except InvalidAudienceError:
        raise ValueError(f"ID token audience does not match configured client_id '{client_id}'")
    except InvalidTokenError as exc:
        raise ValueError(f"ID token cryptographic verification failed: {str(exc)}")

    # 6. Issuer verification
    iss = claims.get("iss", "")
    tid = claims.get("tid")
    valid_v2_prefix = "https://login.microsoftonline.com/"
    valid_v1_prefix = "https://sts.windows.net/"
    if not (iss.startswith(valid_v2_prefix) or iss.startswith(valid_v1_prefix)):
        raise ValueError(f"Invalid ID token issuer '{iss}'. Must be a trusted Microsoft Entra authority.")

    if expected_tenant_id and expected_tenant_id not in ("common", "organizations", "consumers"):
        expected_iss_v2 = f"https://login.microsoftonline.com/{expected_tenant_id}/v2.0"
        expected_iss_v1 = f"https://sts.windows.net/{expected_tenant_id}/"
        if iss not in (expected_iss_v2, expected_iss_v1):
            raise ValueError(f"ID token issuer '{iss}' does not match expected tenant authority '{expected_iss_v2}'")

    # 7. Nonce verification
    if expected_nonce:
        token_nonce = claims.get("nonce")
        if not token_nonce or not hmac.compare_digest(token_nonce, expected_nonce):
            raise ValueError("ID token nonce does not match original OAuth transaction")

    # 8. Tenant ID verification
    if expected_tenant_id and expected_tenant_id not in ("common", "organizations", "consumers"):
        if not tid or tid.lower() != expected_tenant_id.lower():
            raise ValueError(f"Tenant mismatch: authorized account belongs to tenant '{tid}', but expected '{expected_tenant_id}'")

    return claims


def generate_oauth_state(organization_id: str, secret_key: Optional[str] = None) -> str:
    """
    Generate a tamper-proof, signed state parameter binding the organization ID
    with a random nonce and expiration timestamp.
    """
    if not organization_id:
        raise ValueError("organization_id is required to generate OAuth state")

    secret = (secret_key or os.getenv("SECRET_KEY", "senderx_default_teams_state_secret")).encode("utf-8")
    payload = {
        "org_id": organization_id,
        "nonce": os.urandom(12).hex(),
        "ts": int(time.time())
    }
    raw_json = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_json).decode("utf-8").rstrip("=")

    sig = hmac.new(secret, b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"


def validate_oauth_state(
    state_str: str,
    secret_key: Optional[str] = None,
    max_age_seconds: int = 900
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate the HMAC signature and expiration (default 15 minutes) of an OAuth state string.
    Returns (is_valid, organization_id, error_message).
    """
    if not state_str or "." not in state_str:
        return False, None, "Malformed or empty OAuth state string"

    parts = state_str.split(".", 1)
    if len(parts) != 2:
        return False, None, "Invalid OAuth state format"

    b64_payload, signature = parts
    secret = (secret_key or os.getenv("SECRET_KEY", "senderx_default_teams_state_secret")).encode("utf-8")

    expected_sig = hmac.new(secret, b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        return False, None, "Invalid state signature (tampered or forged)"

    # Pad base64 string
    padded = b64_payload + "=" * ((4 - len(b64_payload) % 4) % 4)
    try:
        raw_json = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        payload = json.loads(raw_json)
    except Exception as exc:
        return False, None, f"Could not decode state payload: {str(exc)}"

    ts = payload.get("ts", 0)
    if time.time() - ts > max_age_seconds:
        return False, None, "OAuth state has expired. Please initiate connection again."

    org_id = payload.get("org_id")
    if not org_id:
        return False, None, "State payload missing organization_id"

    return True, org_id, None


def classify_teams_error(
    status_code: int,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> Tuple[bool, Optional[int]]:
    """
    Classify Microsoft Graph API errors into (is_retryable, retry_after_seconds).
    Respects HTTP 429, Retry-After headers, transient 5xx, and identifies permanent 4xx.
    """
    # 1. Throttling (HTTP 429)
    if status_code == 429 or (error_code and "throttl" in error_code.lower()):
        retry_after = 10
        if headers:
            for k, v in headers.items():
                if k.lower() == "retry-after":
                    try:
                        val = int(v.strip())
                        if val > 0:
                            retry_after = val
                    except (ValueError, TypeError):
                        pass
                    break
        return True, retry_after

    # 2. Server-side transient failures (500, 502, 503, 504)
    if status_code in (500, 502, 503, 504):
        return True, 5

    # 3. Permanent Client Errors
    # 401: Invalid or expired credentials (requires reconnection if refresh fails)
    # 403: Forbidden - Application lacks required delegated permissions (ChatMessage.Send / ChannelMessage.Send)
    # 404: ResourceNotFound - Chat, Team, or Channel not found
    # 400: BadRequest - Malformed card or payload
    if status_code in (400, 401, 403, 404, 405, 409, 422):
        return False, None

    # 4. Message heuristics
    if error_message:
        low = error_message.lower()
        if "timeout" in low or "temporarily unavailable" in low or "service unavailable" in low:
            return True, 5
        if "throttled" in low or "rate limit" in low:
            return True, 10

    return False, None


def redact_sensitive(text: str, secrets: List[Optional[str]]) -> str:
    """Mask client secret, tokens, and sensitive strings in exceptions and logs."""
    if not text:
        return text

    redacted = str(text)
    for s in secrets:
        if s and isinstance(s, str) and len(s) > 4:
            masked = f"{s[:3]}...{s[-3:]}"
            redacted = redacted.replace(s, masked)
    return redacted


def normalize_teams_response(
    success: bool,
    provider: str = "teams",
    channel: str = "microsoft_teams",
    provider_message_id: Optional[str] = None,
    status: str = "ACCEPTED",
    recipient: Optional[str] = None,
    target_type: Optional[str] = None,
    chat_id: Optional[str] = None,
    team_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    timestamp: Optional[str] = None,
    error_code: Optional[Any] = None,
    error_message: Optional[str] = None,
    is_retryable: bool = False,
    raw_response: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Return unified normalized dictionary representation of Teams provider response."""
    return {
        "success": bool(success),
        "provider": provider,
        "channel": channel,
        "provider_message_id": provider_message_id,
        "status": status,
        "recipient": recipient,
        "target_type": target_type,
        "chat_id": chat_id,
        "team_id": team_id,
        "channel_id": channel_id,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "error_code": str(error_code) if error_code is not None else None,
        "error_message": error_message,
        "is_retryable": is_retryable,
        "raw_response": raw_response
    }
