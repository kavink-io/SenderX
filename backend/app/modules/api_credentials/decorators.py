"""
SenderX Ingestion Authentication Decorators
Validates external API keys (X-API-Key) or interactive organization JWT tokens.
Strictly binds verified organization_id and application_id.
"""

from functools import wraps
from typing import Any, Callable, List, Optional

from flask import current_app, g, jsonify, request
from app.core.client_ip import resolve_client_ip
from app.modules.api_credentials.rate_limiter import DistributedRateLimiter, RateLimiterError
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
                client_ip = resolve_client_ip(request)

                try:
                    pre_allowed, pre_retry = DistributedRateLimiter.peek_auth_failure(client_ip)
                except RateLimiterError:
                    return jsonify({
                        "success": False,
                        "message": "Rate limiting service temporarily unavailable. Please retry later."
                    }), 503

                if not pre_allowed:
                    resp = jsonify({
                        "success": False,
                        "message": "Too many failed authentication attempts. Please try again later.",
                        "retry_after": pre_retry,
                    })
                    resp.headers["Retry-After"] = str(pre_retry)
                    return resp, 429

                cred, org = ApiCredentialService.verify_api_key(api_key)
                if not cred or not org:
                    try:
                        allowed, retry_after = DistributedRateLimiter.record_auth_failure(client_ip)
                    except RateLimiterError:
                        return jsonify({
                            "success": False,
                            "message": "Rate limiting service temporarily unavailable. Please retry later."
                        }), 503

                    if not allowed:
                        resp = jsonify({
                            "success": False,
                            "message": "Too many failed authentication attempts. Please try again later.",
                            "retry_after": retry_after,
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
                g.user_application_ids = [cred["application_id"]]
                g.auth_type = "API_KEY"
                g.current_credential = cred

                # API-key scopes are intentionally narrower than dashboard RBAC.
                # Map organization permissions to the equivalent public API scope.
                scope_aliases = {
                    "organization:messages:create": ["messages:create"],
                    "organization:messages:read": ["messages:read"],
                    "organization:messages:manage": ["messages:manage"],
                    "organization:payloads:read": ["messages:read", "payloads:read"],
                    "organization:payloads:edit": ["payloads:edit"],
                    "organization:payloads:validate": ["payloads:ingest", "messages:create"],
                    "organization:analytics:read": ["messages:read", "analytics:read"],
                    "organization:dead_letters:read": ["messages:read", "dead_letters:read"],
                    "organization:dlq:read": ["messages:read", "dlq:read"],
                    "organization:dead_letters:manage": ["messages:manage"],
                    "organization:dlq:retry": ["messages:manage"],
                }
                scope_compatibility = {"payloads:write": "payloads:ingest", "messages:write": "messages:create"}
                granted_scopes = {
                    scope_compatibility.get(scope, scope)
                    for scope in (cred.get("scopes") or [])
                }
                missing_scopes = []
                for permission in required_permissions:
                    if permission == "organization:messages:create" and "/payloads" in request.path:
                        candidates = ["payloads:ingest"]
                    else:
                        mapped = scope_aliases.get(permission, [permission])
                        candidates = mapped if isinstance(mapped, list) else [mapped]
                    if not any(c in granted_scopes for c in candidates):
                        missing_scopes.append(candidates[0])
                if missing_scopes:
                    return jsonify({
                        "success": False,
                        "message": "API credential does not have the required scope",
                        "missing_scopes": sorted(set(missing_scopes)),
                    }), 403

                # Rate limiting (CRED-06)
                for dim, ident in [
                    ("credential", DistributedRateLimiter.hash_identifier("cred", cred["credential_id"])),
                    ("application", cred["application_id"]),
                    ("organization", org["organization_id"])
                ]:
                    custom_limit = current_app.config.get(f"RATE_LIMIT_{dim.upper()}_RPM")
                    try:
                        is_allowed, retry_after = DistributedRateLimiter.check_rate_limit(
                            dimension=dim,
                            identifier=ident,
                            limit=custom_limit
                        )
                    except RateLimiterError:
                        return jsonify({
                            "success": False,
                            "message": "Rate limiting service temporarily unavailable. Please retry later."
                        }), 503

                    if not is_allowed:
                        resp = jsonify({
                            "success": False,
                            "message": "Rate limit exceeded. Please throttle requests.",
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

                # Verify client did not spoof a mismatched application_id in ANY request carrier
                supplied_apps = [
                    request.headers.get("X-Application-ID"),
                    request.args.get("application_id"),
                    kwargs.get("application_id"),
                ]
                if request.is_json:
                    json_body = request.get_json(silent=True) or {}
                    if isinstance(json_body, dict) and "application_id" in json_body:
                        supplied_apps.append(json_body.get("application_id"))

                for candidate_app in supplied_apps:
                    if candidate_app is None:
                        continue
                    if not isinstance(candidate_app, str):
                        return jsonify({
                            "success": False,
                            "message": "application_id must be a string",
                        }), 400
                    clean_app = candidate_app.strip()
                    if clean_app and clean_app != str(cred["application_id"]).strip():
                        return jsonify({
                            "success": False,
                            "message": (
                                f"Application ID mismatch: API credential is bound to application "
                                f"'{cred['application_id']}', cannot submit for '{clean_app}'"
                            )
                        }), 403

                return func(*args, **kwargs)

            # Preserve the project's full RBAC behavior for dashboard callers,
            # including application-scoped role assignments and token versioning.
            g.auth_type = None
            g.current_credential = None
            return require_permissions(*required_permissions)(func)(*args, **kwargs)

        return wrapper
    return decorator
