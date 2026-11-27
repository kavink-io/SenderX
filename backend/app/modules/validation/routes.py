"""
SenderX Secured JSON Validation & Analyzer Endpoint.

Enforces:
- Organization RBAC / API credential authentication (`organization:payloads:validate`)
- Tenant & application boundary checks
- Pre-parse request byte limits & strict malformed JSON handling (no NaN/Infinity/RecursionError)
- Fail-closed threat, resource limit, and schema validation responses
- Sanitized error messages without leaking raw payload data, secrets, or internal traces
"""

import json
import logging

from flask import Blueprint, current_app, g, jsonify, request

from app.modules.api_credentials.decorators import require_api_key_or_token
from app.modules.api_credentials.rate_limiter import DistributedRateLimiter, RateLimiterError
from app.validators.dynamic_json_validator import DynamicJSONValidator

logger = logging.getLogger(__name__)

validation_bp = Blueprint("validation", __name__)


def _reject_non_finite_json(token: str) -> None:
    raise ValueError(f"Non-standard JSON constant '{token}' is not permitted")


@validation_bp.route("/analyze", methods=["POST"])
@require_api_key_or_token(required_permissions=["organization:payloads:validate"])
def analyze_json():
    auth_org_id = g.current_organization["organization_id"]

    # Enforce distributed rate limiting for JWT-authenticated validation callers
    # (API_KEY callers are already rate-limited across credential/application/organization dimensions)
    if getattr(g, "auth_type", None) != "API_KEY":
        current_user = getattr(g, "current_user", None) or {}
        user_id = current_user.get("user_id") or "anonymous"
        app_id = getattr(g, "current_application_id", None)
        rate_checks = [
            (
                "validation_analyze_user",
                DistributedRateLimiter.hash_identifier("val_user", f"{auth_org_id}:{user_id}"),
                int(current_app.config.get("RATE_LIMIT_VALIDATION_USER_RPM", 60)),
            ),
            (
                "validation_analyze_org",
                str(auth_org_id),
                int(current_app.config.get("RATE_LIMIT_VALIDATION_ORG_RPM", 300)),
            ),
        ]
        if app_id:
            rate_checks.append((
                "validation_analyze_app",
                f"{auth_org_id}:{str(app_id).strip()}",
                int(current_app.config.get("RATE_LIMIT_VALIDATION_APP_RPM", 150)),
            ))

        for dim, ident, limit in rate_checks:
            try:
                is_allowed, retry_after = DistributedRateLimiter.check_rate_limit(
                    dimension=dim,
                    identifier=ident,
                    limit=limit,
                    window_seconds=60,
                )
            except RateLimiterError:
                return jsonify({
                    "success": False,
                    "valid": False,
                    "status": DynamicJSONValidator.INTERNAL_ERROR_STATUS,
                    "message": "Rate limiting service temporarily unavailable. Please retry later.",
                    "errors": ["Rate limiting service temporarily unavailable"],
                    "threats": [],
                }), 503

            if not is_allowed:
                resp = jsonify({
                    "success": False,
                    "valid": False,
                    "status": DynamicJSONValidator.LIMIT_STATUS,
                    "message": "Rate limit exceeded for JSON validation. Please retry later.",
                    "errors": ["Rate limit exceeded for JSON validation"],
                    "retry_after": retry_after,
                    "threats": [],
                })
                resp.status_code = 429
                resp.headers["Retry-After"] = str(retry_after)
                return resp

    limits = DynamicJSONValidator.resolve_limits()
    max_body_bytes = limits["max_bytes"]

    # 1. Pre-parse body size guard (prevents parsing multi-MB DoS payloads into memory)
    content_length = request.content_length
    if content_length is not None and content_length > max_body_bytes:
        return jsonify({
            "success": False,
            "valid": False,
            "status": DynamicJSONValidator.LIMIT_STATUS,
            "message": f"Request body exceeds maximum allowed size of {max_body_bytes} bytes",
            "errors": [f"Request body exceeds maximum allowed size of {max_body_bytes} bytes"],
            "limit_errors": [f"Request body exceeds maximum allowed size of {max_body_bytes} bytes"],
            "threats": [],
        }), 413

    try:
        raw_bytes = request.get_data(cache=False)
    except Exception:
        return jsonify({
            "success": False,
            "valid": False,
            "status": DynamicJSONValidator.INVALID_STATUS,
            "message": "Could not read JSON request body",
            "errors": ["Could not read JSON request body"],
            "threats": [],
        }), 400

    if not raw_bytes or not raw_bytes.strip():
        return jsonify({
            "success": False,
            "valid": False,
            "status": DynamicJSONValidator.INVALID_STATUS,
            "message": "Valid JSON body is required",
            "errors": ["Valid JSON body is required"],
            "threats": [],
        }), 400

    if len(raw_bytes) > max_body_bytes:
        return jsonify({
            "success": False,
            "valid": False,
            "status": DynamicJSONValidator.LIMIT_STATUS,
            "message": f"Request body exceeds maximum allowed size of {max_body_bytes} bytes",
            "errors": [f"Request body exceeds maximum allowed size of {max_body_bytes} bytes"],
            "limit_errors": [f"Request body exceeds maximum allowed size of {max_body_bytes} bytes"],
            "threats": [],
        }), 413

    # 2. Strict JSON decoding (reject NaN/Infinity and catch C-level RecursionError)
    try:
        payload = json.loads(
            raw_bytes.decode("utf-8"),
            parse_constant=_reject_non_finite_json,
        )
    except RecursionError:
        return jsonify({
            "success": False,
            "valid": False,
            "status": DynamicJSONValidator.LIMIT_STATUS,
            "message": f"JSON nesting exceeds maximum depth of {limits['max_depth']}",
            "errors": [f"JSON nesting exceeds maximum depth of {limits['max_depth']}"],
            "limit_errors": [f"JSON nesting exceeds maximum depth of {limits['max_depth']}"],
            "threats": [],
        }), 422
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return jsonify({
            "success": False,
            "valid": False,
            "status": DynamicJSONValidator.INVALID_STATUS,
            "message": "Valid JSON body is required",
            "errors": ["Malformed JSON syntax"],
            "threats": [],
        }), 400

    # 3. Enforce organization & application isolation boundaries
    auth_org_id = g.current_organization["organization_id"]
    if isinstance(payload, dict):
        body_org_id = payload.get("organization_id")
        if body_org_id is not None and str(body_org_id).strip() != str(auth_org_id).strip():
            logger.warning("Cross-tenant organization_id rejected on /validation/analyze")
            return jsonify({
                "success": False,
                "valid": False,
                "status": "FORBIDDEN",
                "message": "Organization scope mismatch",
                "errors": ["Organization scope mismatch"],
                "threats": [],
            }), 403

        user_app_scopes = getattr(g, "user_application_ids", None)
        if getattr(g, "auth_type", None) != "API_KEY" and user_app_scopes:
            app_id = payload.get("application_id") or request.headers.get("X-Application-ID")
            if app_id and str(app_id).strip() not in user_app_scopes:
                return jsonify({
                    "success": False,
                    "valid": False,
                    "status": "FORBIDDEN",
                    "message": "Application scope access denied",
                    "errors": ["Application scope access denied"],
                    "threats": [],
                }), 403

    # 4. Run full iterative validation, resource checks & threat scanning
    try:
        result = DynamicJSONValidator.analyze(payload, limits=limits)
    except Exception:
        logger.exception("Unexpected internal error during JSON analysis")
        return jsonify({
            "success": False,
            "valid": False,
            "status": DynamicJSONValidator.INTERNAL_ERROR_STATUS,
            "message": "Internal validation failure",
            "errors": ["Internal validation failure"],
            "threats": [],
        }), 500

    if not result["valid"]:
        outcome = result.get("status", DynamicJSONValidator.INVALID_STATUS)
        if outcome == DynamicJSONValidator.LIMIT_STATUS:
            http_status = 413 if any("size" in e.lower() for e in result.get("limit_errors", [])) else 422
            msg = "JSON validation rejected: resource limit exceeded"
        elif outcome == DynamicJSONValidator.THREAT_STATUS:
            http_status = 422
            msg = "JSON validation failed: security threat detected"
        else:
            http_status = 400
            msg = "JSON validation failed"

        return jsonify({
            "success": False,
            "valid": False,
            "status": outcome,
            "message": msg,
            "errors": result["errors"],
            "threats": result.get("threats", []),
            "limit_errors": result.get("limit_errors", []),
            "contains_markup": result.get("contains_markup", False),
            "markup_fields": result.get("markup_fields", []),
            "channel": result.get("channel"),
        }), http_status

    return jsonify({
        "success": True,
        "valid": True,
        "status": DynamicJSONValidator.VALID_STATUS,
        "message": "JSON analyzed successfully",
        "data": result,
    }), 200
