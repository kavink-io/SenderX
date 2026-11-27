"""
SenderX Ingested Payloads & Routing API Routes
Endpoints for JSON payload ingestion, viewing, versioned editing, validation, retry, and auditing.
"""

from flask import Blueprint, request, jsonify, g

from app.modules.auth.decorators import resolve_authorized_application_scope
from app.modules.api_credentials.decorators import require_api_key_or_token
from app.modules.payloads.service import PayloadService


payloads_bp = Blueprint("payloads", __name__)


# ---------------------------------------------------------------------------
# 1. INGESTION (EXTERNAL SITES & APPS)
# ---------------------------------------------------------------------------

@payloads_bp.route("/", methods=["POST"])
@payloads_bp.route("/ingest", methods=["POST"])
@require_api_key_or_token(required_permissions=["organization:messages:create"])
def ingest_payload():
    """
    Ingest external JSON request:
    - Authenticates via external API Key or organization JWT
    - Strictly derives organization_id and application_id from verified credentials
    - Validates size and depth
    - Preserves original JSON immutably
    - Analyzes channel & routes or moves to DLQ
    """
    raw_payload = request.get_json(silent=True)
    if raw_payload is None:
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    forbidden_fallback_keys = ("use_platform_provider", "allow_platform_fallback")
    raw_data = raw_payload.get("data") if isinstance(raw_payload, dict) and isinstance(raw_payload.get("data"), dict) else {}
    if (
        (isinstance(raw_payload, dict) and any(k in raw_payload for k in forbidden_fallback_keys))
        or any(k in raw_data for k in forbidden_fallback_keys)
        or any(k in request.args for k in forbidden_fallback_keys)
        or request.headers.get("X-Use-Platform-Provider") is not None
        or request.headers.get("X-Allow-Platform-Fallback") is not None
    ):
        return jsonify({
            "success": False,
            "message": "Platform-level provider fallback cannot be requested by clients"
        }), 403

    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()
    application_id = getattr(g, "current_application_id", None)
    if user_app_scopes is not None and not application_id:
        if len(user_app_scopes) == 1:
            application_id = user_app_scopes[0]
        else:
            return jsonify({
                "success": False,
                "message": "application_id is required within your authorized application scope",
            }), 400

    if getattr(g, "auth_type", None) != "API_KEY":
        from flask import current_app
        from app.modules.api_credentials.rate_limiter import DistributedRateLimiter, RateLimiterError

        try:
            ing_ok, ing_retry = DistributedRateLimiter.check_rate_limit(
                "ingest",
                str(organization_id),
                limit=int(current_app.config.get("RATE_LIMIT_ORGANIZATION_RPM", 1000)),
                window_seconds=60,
            )
            if not ing_ok:
                resp = jsonify({"success": False, "message": "Rate limit exceeded for payload ingestion.", "retry_after": ing_retry})
                resp.status_code = 429
                resp.headers["Retry-After"] = str(ing_retry)
                return resp
        except RateLimiterError:
            return jsonify({
                "success": False,
                "message": "Rate limiting service temporarily unavailable. Please retry later."
            }), 503
    
    if getattr(g, "auth_type", None) == "API_KEY":
        cred = getattr(g, "current_credential", {})
        user_id = f"api_key:{cred.get('credential_id')}"
    else:
        user_id = getattr(g, "current_user", {}).get("user_id") if hasattr(g, "current_user") else None

    result = PayloadService.ingest_payload(
        raw_json=raw_payload,
        organization_id=organization_id,
        application_id=application_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 200 if result.get("success") else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 2. QUERYING & VIEWING PAYLOADS
# ---------------------------------------------------------------------------

@payloads_bp.route("/", methods=["GET"])
@require_api_key_or_token(required_permissions=["organization:payloads:read"])
def list_payloads():
    """List organization received JSON requests with pagination and application-scoped filters."""
    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()
    requested_app = (request.args.get("application_id") or "").strip() or getattr(g, "current_application_id", None)

    result = PayloadService.list_payloads(
        organization_id=organization_id,
        limit=request.args.get("limit", 50),
        page=request.args.get("page", 1),
        status=request.args.get("status"),
        channel=request.args.get("channel"),
        validation_status=request.args.get("validation_status"),
        application_id=requested_app,
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
        user_application_ids=user_app_scopes,
    )

    return jsonify(result), result.get("status_code", 200)


@payloads_bp.route("/<string:payload_id>", methods=["GET"])
@require_api_key_or_token(required_permissions=["organization:payloads:read"])
def get_payload(payload_id):
    """View a specific request, its original immutable payload, and active version."""
    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()

    result = PayloadService.get_payload(
        payload_id=payload_id,
        organization_id=organization_id,
        user_application_ids=user_app_scopes,
    )

    return jsonify(result), result.get("status_code", 200)


@payloads_bp.route("/<string:payload_id>/versions", methods=["GET"])
@require_api_key_or_token(required_permissions=["organization:payloads:read"])
def get_payload_versions(payload_id):
    """View full payload version history."""
    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()

    result = PayloadService.get_version_history(
        payload_id=payload_id,
        organization_id=organization_id,
        user_application_ids=user_app_scopes,
    )

    return jsonify(result), result.get("status_code", 200)


# ---------------------------------------------------------------------------
# 3. VERSIONED EDITING
# ---------------------------------------------------------------------------

@payloads_bp.route("/<string:payload_id>", methods=["PUT"])
@payloads_bp.route("/<string:payload_id>/edit", methods=["POST"])
@require_api_key_or_token(required_permissions=["organization:payloads:edit"])
def edit_payload(payload_id):
    """
    Create a new payload version:
    - Preserves previous versions & original immutable JSON
    - Records editor, timestamp, and reason
    - Validates edited JSON
    - DOES NOT dispatch automatically
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    # Support envelope {"payload": {...}, "reason": "..."} or raw edited payload
    if "payload" in data and isinstance(data["payload"], dict):
        edited_json = data["payload"]
        reason = data.get("reason", "Payload edited via dashboard")
    else:
        edited_json = dict(data)
        reason = edited_json.pop("reason", "Payload edited via dashboard")

    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()
    if getattr(g, "auth_type", None) == "API_KEY":
        cred = getattr(g, "current_credential", {})
        user_id = f"api_key:{cred.get('credential_id')}"
    else:
        user_id = g.current_user["user_id"]

    result = PayloadService.edit_payload(
        payload_id=payload_id,
        organization_id=organization_id,
        edited_json=edited_json,
        user_id=user_id,
        reason=reason,
        user_application_ids=user_app_scopes,
    )

    return jsonify(result), result.get("status_code", 200)


# ---------------------------------------------------------------------------
# 4. PRE-DISPATCH VALIDATION
# ---------------------------------------------------------------------------

@payloads_bp.route("/<string:payload_id>/validate", methods=["POST"])
@require_api_key_or_token(required_permissions=["organization:payloads:validate"])
def validate_payload(payload_id):
    """Validate current or specific version without dispatching."""
    data = request.get_json(silent=True) or {}
    version_num = data.get("version")
    if version_num is not None:
        try:
            version_num = int(version_num)
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "version must be an integer"}), 400

    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()

    result = PayloadService.validate_payload(
        payload_id=payload_id,
        organization_id=organization_id,
        version_num=version_num,
        user_application_ids=user_app_scopes,
    )

    return jsonify(result), result.get("status_code", 200)


# ---------------------------------------------------------------------------
# 5. RETRY / REPROCESS (EXPLICIT ACTION)
# ---------------------------------------------------------------------------

@payloads_bp.route("/<string:payload_id>/retry", methods=["POST"])
@require_api_key_or_token(required_permissions=["organization:dlq:retry"])
def retry_payload(payload_id):
    """Explicitly retry/reprocess an eligible payload. Idempotent."""
    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()
    if getattr(g, "auth_type", None) == "API_KEY":
        cred = getattr(g, "current_credential", {})
        user_id = f"api_key:{cred.get('credential_id')}"
    else:
        user_id = g.current_user["user_id"]

    result = PayloadService.retry_payload(
        payload_id=payload_id,
        organization_id=organization_id,
        user_id=user_id,
        user_application_ids=user_app_scopes,
    )

    return jsonify(result), result.get("status_code", 200)


# ---------------------------------------------------------------------------
# 6. AUDIT TRAIL
# ---------------------------------------------------------------------------

@payloads_bp.route("/<string:payload_id>/audit", methods=["GET"])
@require_api_key_or_token(required_permissions=["organization:payloads:read"])
def get_payload_audit(payload_id):
    """Retrieve audit log entries for a payload."""
    organization_id = g.current_organization["organization_id"]
    user_app_scopes = resolve_authorized_application_scope()

    result = PayloadService.get_audit_trail(
        payload_id=payload_id,
        organization_id=organization_id,
        user_application_ids=user_app_scopes,
    )

    return jsonify(result), result.get("status_code", 200)
