"""
SenderX Microsoft Graph API OAuth 2.0 Auth Client
Supports:
- Microsoft Entra ID Delegated OAuth 2.0 Authorization Code flow with offline_access
- Cryptographic state URL generation and code-for-token exchange
- Token expiration detection, proactive renewal, and refresh token rotation
- Automated token persistence callback
- Reconnection detection on consent revocation or expired refresh tokens
- Client Credentials flow compatibility
- Sensitive credential masking (client_secret, refresh_token)
"""

import logging
import os
import threading
import time
import urllib.parse
from typing import Any, Callable, Dict, List, Optional
import requests

from app.adapters.base_adapter import ProviderError
from app.adapters.teams.teams_utils import TEAMS_DELEGATED_SCOPES, redact_sensitive

logger = logging.getLogger(__name__)


def generate_authorization_url(
    tenant_id: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: Optional[List[str]] = None,
    code_challenge: Optional[str] = None,
    code_challenge_method: str = "S256",
    nonce: Optional[str] = None
) -> str:
    """
    Construct the Microsoft Entra ID OAuth 2.0 authorization URL
    for delegated consent (ChatMessage.Send, ChannelMessage.Send, offline_access)
    with PKCE (RFC 7636) code_challenge and OpenID Connect nonce support.
    """
    if not tenant_id or not client_id or not redirect_uri or not state:
        raise ValueError("tenant_id, client_id, redirect_uri, and state are required to generate auth URL")

    scope_str = " ".join(scopes or TEAMS_DELEGATED_SCOPES)
    base_url = f"https://login.microsoftonline.com/{tenant_id.strip()}/oauth2/v2.0/authorize"

    params = {
        "client_id": client_id.strip(),
        "response_type": "code",
        "redirect_uri": redirect_uri.strip(),
        "response_mode": "query",
        "scope": scope_str,
        "state": state.strip()
    }
    if code_challenge:
        params["code_challenge"] = code_challenge.strip()
        params["code_challenge_method"] = code_challenge_method
    if nonce:
        params["nonce"] = nonce.strip()

    return f"{base_url}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: Optional[str] = None,
    session: Optional[requests.Session] = None,
    timeout: int = 20
) -> Dict[str, Any]:
    """
    Exchange authorization code for delegated access_token and refresh_token,
    verifying PKCE code_verifier.
    POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
    """
    if not tenant_id or not client_id or not client_secret or not code or not redirect_uri:
        raise ValueError("Missing parameters for token exchange")

    token_url = f"https://login.microsoftonline.com/{tenant_id.strip()}/oauth2/v2.0/token"
    data = {
        "client_id": client_id.strip(),
        "scope": " ".join(TEAMS_DELEGATED_SCOPES),
        "code": code.strip(),
        "redirect_uri": redirect_uri.strip(),
        "grant_type": "authorization_code",
        "client_secret": client_secret.strip()
    }
    if code_verifier:
        data["code_verifier"] = code_verifier.strip()

    sess = session or requests.Session()
    try:
        resp = sess.post(token_url, data=data, timeout=timeout)
    except requests.RequestException as exc:
        redacted = redact_sensitive(str(exc), [client_secret, code, code_verifier])
        raise ProviderError(
            f"Network error during Microsoft token exchange: {redacted}",
            status_code=503,
            retryable=True,
            error_code="TOKEN_NETWORK_ERROR",
            retry_after=5
        )

    try:
        resp_data = resp.json()
    except ValueError:
        resp_data = {"raw_text": resp.text}

    if resp.status_code != 200:
        err_code = resp_data.get("error", "token_exchange_failed")
        err_desc = resp_data.get("error_description", resp.text)
        redacted_desc = redact_sensitive(err_desc, [client_secret, code, code_verifier])
        raise ProviderError(
            f"Microsoft token exchange failed ({err_code}): {redacted_desc}",
            status_code=resp.status_code,
            retryable=False,
            error_code=err_code
        )

    return resp_data


def refresh_access_token(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: Optional[List[str]] = None,
    session: Optional[requests.Session] = None,
    timeout: int = 20
) -> Dict[str, Any]:
    """
    Obtain a new access_token using a refresh_token.
    POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
    """
    if not tenant_id or not client_id or not client_secret or not refresh_token:
        raise ValueError("tenant_id, client_id, client_secret, and refresh_token are required to refresh token")

    token_url = f"https://login.microsoftonline.com/{tenant_id.strip()}/oauth2/v2.0/token"
    data = {
        "client_id": client_id.strip(),
        "scope": " ".join(scopes or TEAMS_DELEGATED_SCOPES),
        "refresh_token": refresh_token.strip(),
        "grant_type": "refresh_token",
        "client_secret": client_secret.strip()
    }

    sess = session or requests.Session()
    try:
        resp = sess.post(token_url, data=data, timeout=timeout)
    except requests.RequestException as exc:
        redacted = redact_sensitive(str(exc), [client_secret, refresh_token])
        raise ProviderError(
            f"Network error during Microsoft token refresh: {redacted}",
            status_code=503,
            retryable=True,
            error_code="TOKEN_NETWORK_ERROR",
            retry_after=5
        )

    try:
        resp_data = resp.json()
    except ValueError:
        resp_data = {"raw_text": resp.text}

    if resp.status_code != 200:
        err_code = resp_data.get("error", "token_refresh_failed")
        err_desc = resp_data.get("error_description", resp.text)
        redacted_desc = redact_sensitive(err_desc, [client_secret, refresh_token])

        # If refresh token expired or revoked, user must reconnect
        if err_code in ("invalid_grant", "unauthorized_client") or "AADSTS700084" in err_desc or "AADSTS65001" in err_desc:
            raise ProviderError(
                f"Microsoft Teams authorization expired or revoked. Please reconnect Microsoft 365 account: {redacted_desc}",
                status_code=401,
                retryable=False,
                error_code="TEAMS_AUTH_EXPIRED"
            )

        raise ProviderError(
            f"Microsoft token refresh failed ({err_code}): {redacted_desc}",
            status_code=resp.status_code,
            retryable=resp.status_code in (429, 500, 502, 503, 504),
            error_code=err_code
        )

    return resp_data


def get_user_profile(
    access_token: str,
    session: Optional[requests.Session] = None,
    timeout: int = 15
) -> Dict[str, Any]:
    """Retrieve connected user identity from Microsoft Graph GET /me."""
    if not access_token:
        raise ValueError("access_token is required to retrieve profile")

    url = "https://graph.microsoft.com/v1.0/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    sess = session or requests.Session()

    try:
        resp = sess.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


class MicrosoftGraphAuthClient:
    """
    Manages OAuth 2.0 token acquisition, caching, automatic refresh,
    and credential lifecycle for Microsoft Teams messaging.
    """

    OAUTH_LOGIN_BASE = "https://login.microsoftonline.com"
    GRAPH_DEFAULT_SCOPE = "https://graph.microsoft.com/.default"

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[float] = None,
        on_token_refresh: Optional[Callable[[Dict[str, Any]], None]] = None,
        organization_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        credential_loader: Optional[Callable[[], Optional[Dict[str, Any]]]] = None,
        allow_local_lock: Optional[bool] = None,
        session: Optional[requests.Session] = None,
        timeout: int = 20
    ):
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("Microsoft tenant_id (Directory ID) is required")
        if not client_id or not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("Microsoft client_id (Application ID) is required")
        if not client_secret or not isinstance(client_secret, str) or not client_secret.strip():
            raise ValueError("Microsoft client_secret is required")

        self.tenant_id = tenant_id.strip()
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.session = session or requests.Session()
        self.timeout = timeout
        self.on_token_refresh = on_token_refresh
        self.organization_id = organization_id.strip() if organization_id else None
        self.redis_client = redis_client
        self.credential_loader = credential_loader

        if allow_local_lock is not None:
            self.allow_local_lock = bool(allow_local_lock)
        else:
            local_flag = None
            try:
                from flask import current_app, has_app_context
                if has_app_context():
                    local_flag = current_app.config.get("TEAMS_ALLOW_LOCAL_LOCK")
                    if local_flag is None:
                        local_flag = current_app.config.get("TEAMS_SINGLE_PROCESS_MODE")
            except Exception:
                pass

            if local_flag is not None:
                self.allow_local_lock = bool(local_flag)
            else:
                env_val = os.getenv("TEAMS_SINGLE_PROCESS_MODE") or os.getenv("TEAMS_ALLOW_LOCAL_LOCK")
                if env_val is not None:
                    self.allow_local_lock = env_val.lower() in ("true", "1", "yes")
                else:
                    self.allow_local_lock = False

        if access_token:
            self._cached_token = access_token.strip()
            self._token_expires_at = float(token_expires_at) if token_expires_at else (time.time() + 3600)
        else:
            self._cached_token = None
            self._token_expires_at = 0.0
        self._refresh_token = refresh_token.strip() if refresh_token else None
        self._refresh_lock = threading.Lock()

    @property
    def token_endpoint(self) -> str:
        return f"{self.OAUTH_LOGIN_BASE}/{self.tenant_id}/oauth2/v2.0/token"

    def is_token_valid(self, margin_seconds: int = 60) -> bool:
        """Returns True if the cached access token exists and has not expired."""
        if not self._cached_token:
            return False
        return time.time() < (self._token_expires_at - margin_seconds)

    def update_credentials(self, credentials: Dict[str, Any]) -> None:
        """Update in-memory token state from freshly read credentials."""
        if not credentials or not isinstance(credentials, dict):
            return
        if credentials.get("access_token"):
            self._cached_token = str(credentials["access_token"]).strip()
        if credentials.get("refresh_token"):
            self._refresh_token = str(credentials["refresh_token"]).strip()
        if credentials.get("token_expires_at"):
            self._token_expires_at = float(credentials["token_expires_at"])
        if credentials.get("tenant_id"):
            self.tenant_id = str(credentials["tenant_id"]).strip()
        if credentials.get("client_id"):
            self.client_id = str(credentials["client_id"]).strip()
        if credentials.get("client_secret"):
            self.client_secret = str(credentials["client_secret"]).strip()

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Retrieve a valid access token.
        1. If cached access_token is still valid, return it.
        2. Coordinate distributed token refresh across workers using Redis lock.
        3. Re-read credentials from DB upon acquiring the lock to avoid redundant refresh.
        4. If still expired, perform refresh with Microsoft Entra ID.
        5. Atomically persist rotated tokens and update in-memory state.
        6. Release lock safely; handle crashes and timeouts gracefully.
        """
        if not force_refresh and self.is_token_valid():
            return self._cached_token  # type: ignore

        # Determine Redis client
        redis_inst = self.redis_client
        if redis_inst is None:
            try:
                from flask import current_app, has_app_context
                if has_app_context() and hasattr(current_app, "redis_client") and current_app.redis_client:
                    redis_inst = current_app.redis_client
            except Exception:
                redis_inst = None

        if redis_inst is None:
            if not self.allow_local_lock:
                raise ProviderError(
                    "Distributed locking via Redis is required for Microsoft Teams token refresh in production multi-worker mode, but Redis is not configured or unavailable.",
                    status_code=503,
                    retryable=True,
                    error_code="REDIS_LOCK_UNAVAILABLE",
                    retry_after=5
                )
            logger.info("Using local threading.Lock for token refresh in explicitly configured development/test mode")

        # Lock key scoped strictly to organization or client (never contains secrets/tokens)
        lock_scope = self.organization_id or self.client_id
        lock_name = f"lock:teams:token_refresh:{lock_scope}"

        distributed_lock = None
        lock_acquired = False

        if redis_inst is not None:
            try:
                distributed_lock = redis_inst.lock(
                    name=lock_name,
                    timeout=20.0,  # 20s lock TTL to ensure automatic release if worker crashes
                    sleep=0.1,
                    blocking=True,
                    blocking_timeout=10.0,  # Wait up to 10s for other worker to refresh
                    raise_on_release_error=False
                )
                lock_acquired = distributed_lock.acquire()
            except Exception as lock_exc:
                if not self.allow_local_lock:
                    raise ProviderError(
                        f"Failed to acquire Redis distributed lock for Teams token refresh: {str(lock_exc)}. Token refresh aborted to prevent race conditions.",
                        status_code=503,
                        retryable=True,
                        error_code="REDIS_LOCK_UNAVAILABLE",
                        retry_after=5
                    )
                logger.warning("Redis distributed lock warning: %s; using local concurrency lock in dev mode", lock_exc)
                distributed_lock = None
                lock_acquired = False

        try:
            with self._refresh_lock:
                if distributed_lock is not None and not lock_acquired:
                    # Timeout acquiring distributed lock - check if another worker refreshed in the meantime
                    if self.credential_loader:
                        fresh = self.credential_loader()
                        if fresh:
                            self.update_credentials(fresh)
                            if self.is_token_valid():
                                return self._cached_token  # type: ignore

                    raise ProviderError(
                        "Timed out waiting for distributed token refresh lock. Another process is refreshing.",
                        status_code=503,
                        retryable=True,
                        error_code="TOKEN_REFRESH_LOCK_TIMEOUT",
                        retry_after=3
                    )

                # Inside the lock: re-read credentials from DB to check if already refreshed
                if self.credential_loader:
                    fresh = self.credential_loader()
                    if fresh:
                        self.update_credentials(fresh)
                        if not force_refresh and self.is_token_valid():
                            logger.info("Access token was already refreshed by another worker; using freshly loaded token.")
                            return self._cached_token  # type: ignore

                # Double check inside the lock
                if not force_refresh and self.is_token_valid():
                    return self._cached_token  # type: ignore

                # 1. Delegated Flow using Refresh Token
                if self._refresh_token:
                    logger.info("Refreshing delegated Microsoft Teams access token using refresh_token...")
                    token_data = refresh_access_token(
                        tenant_id=self.tenant_id,
                        client_id=self.client_id,
                        client_secret=self.client_secret,
                        refresh_token=self._refresh_token,
                        session=self.session,
                        timeout=self.timeout
                    )

                    new_access_token = token_data.get("access_token")
                    new_refresh_token = token_data.get("refresh_token") or self._refresh_token
                    expires_in = int(token_data.get("expires_in", 3600))
                    new_expires_at = time.time() + expires_in

                    self._cached_token = new_access_token
                    self._refresh_token = new_refresh_token
                    self._token_expires_at = new_expires_at

                    # Atomically persist rotated tokens
                    if self.on_token_refresh:
                        try:
                            self.on_token_refresh({
                                "access_token": new_access_token,
                                "refresh_token": new_refresh_token,
                                "token_expires_at": new_expires_at,
                                "expires_in": expires_in
                            })
                        except Exception as exc:
                            logger.warning("on_token_refresh callback failed: %s", exc)

                    return new_access_token

                # 2. Client Credentials Fallback
                token_url = self.token_endpoint
                body = {
                    "client_id": self.client_id,
                    "scope": self.GRAPH_DEFAULT_SCOPE,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials"
                }

                try:
                    resp = self.session.post(token_url, data=body, timeout=self.timeout)
                except requests.RequestException as exc:
                    redacted = redact_sensitive(str(exc), [self.client_secret])
                    raise ProviderError(
                        f"Microsoft Entra ID token network error: {redacted}",
                        status_code=503,
                        retryable=True,
                        error_code="TOKEN_NETWORK_ERROR",
                        retry_after=5
                    )

                try:
                    resp_data = resp.json()
                except ValueError:
                    resp_data = {"raw_text": resp.text}

                if resp.status_code != 200:
                    err_code = resp_data.get("error", "token_acquisition_failed")
                    err_desc = resp_data.get("error_description", resp.text)
                    redacted_desc = redact_sensitive(err_desc, [self.client_secret])
                    is_retryable = resp.status_code in (429, 500, 502, 503, 504)
                    raise ProviderError(
                        f"Microsoft Entra ID authentication failed ({err_code}): {redacted_desc}",
                        status_code=resp.status_code,
                        retryable=is_retryable,
                        error_code=err_code,
                        retry_after=10 if is_retryable else None
                    )

                token = resp_data.get("access_token")
                expires_in = int(resp_data.get("expires_in", 3600))
                self._cached_token = token
                self._token_expires_at = time.time() + expires_in
                return token
        finally:
            if distributed_lock and lock_acquired:
                try:
                    distributed_lock.release()
                except Exception:
                    pass
