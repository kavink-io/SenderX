"""
SenderX Ingestion Authentication Decorators
Validates external API keys (X-API-Key) or interactive organization JWT tokens.
Strictly binds verified organization_id and application_id.
"""

from functools import wraps
from typing import Any, Callable, List, Optional

from flask import current_app, g, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.modules.api_credentials.rate_limiter import DistributedRateLimiter
from app.modules.api_credentials.service import ApiCredentialService
from app.modules.auth.decorators import require_permissions
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository


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

            # 2. Fall back to JWT token authentication for dashboard operations
            try:
                verify_jwt_in_request(optional=False)
            except Exception:
                return jsonify({
                    "success": False,
                    "message": "Authentication required. Provide valid API key via X-API-Key header or valid JWT Bearer token."
                }), 401

            identity = get_jwt_identity()
            claims = get_jwt()

            if claims.get("account_type") != "ORGANIZATION_USER":
                return jsonify({
                    "success": False,
                    "message": "Organization user access required"
                }), 403

            user = UserRepository.find_by_id(identity)
            if not user or not user.get("is_active", False):
                return jsonify({
                    "success": False,
                    "message": "Organization user not found or inactive"
                }), 401

            organization_id = user.get("organization_id")
            organization = OrganizationRepository.find_by_id(organization_id)
            if not organization or organization.get("status") != "ACTIVE":
                return jsonify({
                    "success": False,
                    "message": "Organization is inactive or unavailable"
                }), 403

            # Verify permissions
            role_ids = user.get("role_ids", [])
            granted_permissions = set()
            for r_id in role_ids:
                role = RoleRepository.find_by_id(r_id, organization_id=organization_id)
                if role and role.get("scope") == "ORGANIZATION":
                    granted_permissions.update(role.get("permissions", []))

            # Expand aliases
            effective_permissions = set(granted_permissions)
            if "organization:dead_letters:read" in granted_permissions:
                effective_permissions.add("organization:dlq:read")
            if "organization:dead_letters:manage" in granted_permissions:
                effective_permissions.add("organization:dlq:retry")

            missing = set(required_permissions) - effective_permissions
            if missing:
                return jsonify({
                    "success": False,
                    "message": "You do not have permission to perform this action",
                    "missing_permissions": sorted(list(missing))
                }), 403

            g.current_user = user
            g.current_organization = organization
            g.auth_type = "JWT"
            # For JWT caller, application_id may optionally be supplied or None
            header_app_id = request.headers.get("X-Application-ID")
            body_app_id = None
            if request.is_json:
                body = request.get_json(silent=True) or {}
                if isinstance(body, dict):
                    body_app_id = body.get("application_id")
            g.current_application_id = header_app_id or body_app_id or None

            return func(*args, **kwargs)

        return wrapper
    return decorator
