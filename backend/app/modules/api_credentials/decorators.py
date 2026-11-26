"""
SenderX Ingestion Authentication Decorators
Validates external API keys (X-API-Key) or interactive organization JWT tokens.
Strictly binds verified organization_id and application_id.
"""

from functools import wraps
from typing import Any, Callable, List, Optional

from flask import current_app, g, jsonify, request
from app.modules.api_credentials.rate_limiter import DistributedRateLimiter
from app.modules.api_credentials.service import ApiCredentialService
from app.modules.auth.decorators import require_permissions


def extract_api_key_from_request() -> Optional[str]:
    """
    Extract external API key from request headers:
    1. 'X-API-Key: sx_live_...'
    2. 'Authorization: ApiKey sx_live_...'
    3. 'Authorization: Bearer sx_live_...' (or sx_test_...)
    """
    api_key = request.headers.get("X-API-Key")
    if api_key and api_key.strip():
        return api_key.strip()

    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        parts = auth_header.strip().split()
        if len(parts) == 2:
            scheme, token = parts[0].lower(), parts[1]
            if scheme == "apikey":
                return token.strip()
            if scheme == "bearer" and (token.startswith("sx_live_") or token.startswith("sx_test_")):
                return token.strip()

    return None


def require_api_key_or_token(required_permissions: Optional[List[str]] = None) -> Callable:
    """
    Dual-mode authentication decorator:
    - External applications authenticate using API credentials (X-API-Key).
      Binds organization_id and application_id strictly from database record.
      Rejects any spoofed application_id.
    - Dashboard users authenticate via JWT Bearer token with RBAC permissions check.
    """
    if required_permissions is None:
        required_permissions = ["organization:messages:create"]

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 1. Check for external API key first
            api_key = extract_api_key_from_request()
            if api_key:
                client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()

                cred, org = ApiCredentialService.verify_api_key(api_key)
                if not cred or not org:
                    allowed, retry_after = DistributedRateLimiter.record_auth_failure(client_ip)
                    if not allowed:
                        resp = jsonify({
                            "success": False,
                            "message": "Too many failed authentication attempts. Please try again later."
                        })
                        resp.headers["Retry-After"] = str(retry_after)
                        return resp, 429

                    return jsonify({
                        "success": False,
                        "message": "Invalid or revoked API key"
                    }), 401

                # Establish verified context
                g.current_organization = org
                g.current_application_id = cred["application_id"]
                g.auth_type = "API_KEY"
                g.current_credential = cred

                # API-key scopes are intentionally narrower than dashboard RBAC.
                # Map organization permissions to the equivalent public API scope.
                scope_aliases = {
                    "organization:messages:create": "messages:create",
                    "organization:messages:read": "messages:read",
                    "organization:messages:manage": "messages:manage",
                }
                scope_compatibility = {"payloads:write": "payloads:ingest", "messages:write": "messages:create"}
                granted_scopes = {
                    scope_compatibility.get(scope, scope)
                    for scope in (cred.get("scopes") or [])
                }
                missing_scopes = [
                    ("payloads:ingest" if permission == "organization:messages:create" and "/payloads" in request.path
                     else scope_aliases.get(permission, permission))
                    for permission in required_permissions
                    if ("payloads:ingest" if permission == "organization:messages:create" and "/payloads" in request.path
                        else scope_aliases.get(permission, permission)) not in granted_scopes
                ]
                if missing_scopes:
                    return jsonify({
                        "success": False,
                        "message": "API credential does not have the required scope",
                        "missing_scopes": sorted(set(missing_scopes)),
                    }), 403

                # Rate limiting (CRED-06)
                for dim, ident in [
                    ("credential", cred["credential_id"]),
                    ("application", cred["application_id"]),
                    ("organization", org["organization_id"])
                ]:
                    custom_limit = current_app.config.get(f"RATE_LIMIT_{dim.upper()}_RPM")
                    is_allowed, retry_after = DistributedRateLimiter.check_rate_limit(
                        dimension=dim,
                        identifier=ident,
                        limit=custom_limit
                    )
                    if not is_allowed:
                        resp = jsonify({
                            "success": False,
                            "message": f"Rate limit exceeded for {dim}. Please throttle requests.",
                            "retry_after": retry_after
                        })
                        resp.headers["Retry-After"] = str(retry_after)
                        return resp, 429

                # Environment isolation check (CRED-05)
                import os
                app_env = current_app.config.get("APP_ENV", os.getenv("APP_ENV", "development")).lower()
                cred_env = (cred.get("environment") or "live").lower()

                if app_env == "production" and cred_env == "test":
                    return jsonify({
                        "success": False,
                        "message": "Test credentials cannot be used in a production environment"
                    }), 403

                if app_env == "test" and cred_env == "live":
                    return jsonify({
                        "success": False,
                        "message": "Live credentials cannot be used in a test environment"
                    }), 403

                # Verify client did not spoof a mismatched application_id
                client_app_id = request.headers.get("X-Application-ID")
                if not client_app_id and request.is_json:
                    json_body = request.get_json(silent=True) or {}
                    if isinstance(json_body, dict):
                        client_app_id = json_body.get("application_id")

                if client_app_id and str(client_app_id).strip() != str(cred["application_id"]).strip():
                    return jsonify({
                        "success": False,
                        "message": (
                            f"Application ID mismatch: API credential is bound to application "
                            f"'{cred['application_id']}', cannot submit for '{client_app_id}'"
                        )
                    }), 403

                return func(*args, **kwargs)

            # Preserve the project's full RBAC behavior for dashboard callers,
            # including application-scoped role assignments and token versioning.
            return require_permissions(*required_permissions)(func)(*args, **kwargs)

        return wrapper
    return decorator
