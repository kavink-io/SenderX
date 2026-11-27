from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.modules.users.service import UserService
from app.modules.users.repository import UserRepository
from app.modules.users.preferences_service import UserPreferencesService
from app.modules.auth.decorators import require_permissions
from app.modules.auth.otp_service import OTPService, OTPServiceError

users_bp = Blueprint("users", __name__)


def _resolve_authenticated_preference_owner():
    """Verify active account + token_version from DB for preference endpoints."""
    from app.modules.auth.routes import resolve_account

    identity = get_jwt_identity()
    claims = get_jwt()
    account, error = resolve_account(identity, claims)
    if error or not account:
        return None, None, (error or "Unauthorized")

    account_type = account.get("account_type")
    if account_type == "PLATFORM_ADMIN":
        return account.get("admin_id") or identity, None, None
    return account.get("user_id") or identity, account.get("organization_id"), None


# ======================================================
# USER ENDPOINTS
# ======================================================

@users_bp.route("/", methods=["POST"])
@require_permissions("organization:users:manage")
def create_user():
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None
    actor_email = g.current_user.get("email") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.create_user(
        data,
        organization_id=organization_id,
        actor_id=actor_id,
        actor_email=actor_email
    )
    status_code = 201 if result.get("success") else result.get("status_code", 400)
    return jsonify(result), status_code


@users_bp.route("/", methods=["GET"])
@require_permissions("organization:users:manage")
def list_users():
    organization_id = g.current_organization["organization_id"]
    limit = request.args.get("limit", 50)
    page = request.args.get("page", 1)
    search = request.args.get("search")
    status = request.args.get("status")
    role_id = request.args.get("role_id")
    application_id = request.args.get("application_id")
    employee_code = request.args.get("employee_code")

    result = UserService.get_users(
        organization_id=organization_id,
        limit=limit,
        page=page,
        search=search,
        status=status,
        role_id=role_id,
        application_id=application_id,
        employee_code=employee_code
    )

    return jsonify({
        "success": True,
        "count": len(result["items"]),
        "total_count": result["pagination"]["total"],
        "pagination": result["pagination"],
        "data": result["items"]
    }), 200


@users_bp.route("/me/dashboard-context", methods=["GET"])
@jwt_required()
def get_my_dashboard_context():
    """Return authoritative dynamic dashboard context for the authenticated user."""
    identity = get_jwt_identity()
    claims = get_jwt()
    if claims.get("account_type") != "ORGANIZATION_USER":
        return jsonify({"success": False, "message": "Organization user access required"}), 403

    user = UserRepository.find_by_id(identity)
    if not user or not user.get("is_active", False):
        return jsonify({"success": False, "message": "User not found or inactive"}), 401

    if claims.get("token_version", 1) != user.get("token_version", 1):
        return jsonify({"success": False, "message": "Session expired or password changed. Please log in again."}), 401

    organization_id = user.get("organization_id")
    result = UserService.get_dashboard_context(identity, organization_id=organization_id)
    return jsonify(result), result.get("status_code", 200 if result.get("success") else 400)


@users_bp.route("/me/profile", methods=["PATCH", "PUT"])
@jwt_required()
def update_my_profile():
    identity = get_jwt_identity()
    claims = get_jwt()
    if claims.get("account_type") != "ORGANIZATION_USER":
        return jsonify({"success": False, "message": "Organization user access required"}), 403

    user = UserRepository.find_by_id(identity)
    if not user or not user.get("is_active", False):
        return jsonify({"success": False, "message": "User not found or inactive"}), 401

    if claims.get("token_version", 1) != user.get("token_version", 1):
        return jsonify({"success": False, "message": "Session expired or password changed. Please log in again."}), 401

    data = request.get_json(silent=True) or {}
    result = UserService.update_own_profile(identity, data)
    status_code = 200 if result.get("success") else result.get("status_code", 400)
    return jsonify(result), status_code


@users_bp.route("/me", methods=["PATCH", "PUT"])
@jwt_required()
def update_my_profile_alias():
    return update_my_profile()


@users_bp.route("/me/preferences", methods=["GET"])
@jwt_required()
def get_my_preferences():
    user_id, organization_id, auth_error = _resolve_authenticated_preference_owner()
    if auth_error:
        return jsonify({"success": False, "message": auth_error}), 401

    result = UserPreferencesService.get_preferences(user_id, organization_id=organization_id)
    return jsonify(result), 200


@users_bp.route("/me/preferences", methods=["PUT", "PATCH"])
@jwt_required()
def update_my_preferences():
    user_id, organization_id, auth_error = _resolve_authenticated_preference_owner()
    if auth_error:
        return jsonify({"success": False, "message": auth_error}), 401

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"success": False, "message": "Invalid or missing JSON payload"}), 400

    result = UserPreferencesService.save_preferences(
        user_id=user_id,
        organization_id=organization_id,
        payload=data,
        replace=(request.method == "PUT"),
    )
    status_code = 200 if result.get("success") else result.get("status_code", 400)
    return jsonify(result), status_code


@users_bp.route("/<string:user_id>", methods=["GET"])
@require_permissions("organization:users:manage")
def get_user(user_id):
    organization_id = g.current_organization["organization_id"]
    result = UserService.get_user_by_id(user_id, organization_id=organization_id)
    return jsonify(result), 200 if result.get("success") else 404


@users_bp.route("/<string:user_id>", methods=["PATCH", "PUT"])
@require_permissions("organization:users:manage")
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.update_user(user_id, organization_id=organization_id, data=data, actor_id=actor_id)
    if not result.get("success"):
        status_code = result.get("status_code", 404 if result.get("message") == "User not found" else 400)
        return jsonify(result), status_code
    return jsonify(result), 200


@users_bp.route("/<string:user_id>/roles", methods=["POST"])
@require_permissions("organization:users:manage")
def assign_user_roles(user_id):
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.assign_user_roles(
        user_id=user_id,
        organization_id=organization_id,
        data=data,
        actor_id=actor_id
    )
    if not result.get("success"):
        status_code = result.get("status_code", 404 if result.get("message") == "User not found" else 400)
        return jsonify(result), status_code
    return jsonify(result), 200


@users_bp.route("/<string:user_id>/activate", methods=["POST"])
@require_permissions("organization:users:manage")
def activate_user(user_id):
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.activate_user(user_id, organization_id=organization_id, actor_id=actor_id)
    if not result.get("success"):
        status_code = result.get("status_code", 404 if result.get("message") == "User not found" else 400)
        return jsonify(result), status_code
    return jsonify(result), 200


@users_bp.route("/<string:user_id>/activation/resend", methods=["POST"])
@require_permissions("organization:users:manage")
def resend_activation_otp(user_id):
    actor = g.current_user
    organization_id = g.current_organization["organization_id"]
    target_user = UserRepository.find_by_id(
        user_id,
        organization_id=organization_id,
        include_deleted=True
    )
    if not target_user:
        return jsonify({"success": False, "message": "Employee not found"}), 404

    is_org_admin = any(
        role.get("name") == "ORG_ADMIN"
        for role in getattr(g, "current_roles", [])
    )
    try:
        from app.core.client_ip import resolve_client_ip
        result = OTPService.request_code(
            target_user.get("email"),
            OTPService.ACTIVATION,
            client_ip=resolve_client_ip(request),
            target_user_id=user_id,
            organization_id=organization_id,
            actor={
                "actor_id": actor.get("user_id"),
                "document": actor,
                "actor_role_label": "Organization Admin" if is_org_admin else "Employee"
            }
        )
        return jsonify(result), 202
    except OTPServiceError as error:
        response = jsonify({"success": False, "message": error.message})
        if error.retry_after:
            response.headers["Retry-After"] = str(error.retry_after)
        return response, error.status_code


@users_bp.route("/<string:user_id>", methods=["DELETE"])
@require_permissions("organization:users:manage")
def delete_user(user_id):
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None
    actor_email = g.current_user.get("email") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.delete_user(user_id, organization_id=organization_id, actor_id=actor_id, actor_email=actor_email)
    status_code = result.get("status_code", 200 if result.get("success") else 400)
    return jsonify(result), status_code


@users_bp.route("/<string:user_id>/deactivate", methods=["POST"])
@require_permissions("organization:users:manage")
def deactivate_user(user_id):
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None
    actor_email = g.current_user.get("email") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.deactivate_user(user_id, organization_id=organization_id, actor_id=actor_id, actor_email=actor_email)
    if not result.get("success"):
        status_code = result.get("status_code", 404 if result.get("message") == "User not found" else 400)
        return jsonify(result), status_code
    return jsonify(result), 200


# ======================================================
# ROLE ENDPOINTS
# ======================================================

@users_bp.route("/roles", methods=["POST"])
@require_permissions("organization:roles:manage")
def create_role():
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.create_role(data, organization_id=organization_id, actor_id=actor_id)
    status_code = 201 if result.get("success") else result.get("status_code", 400)
    return jsonify(result), status_code


@users_bp.route("/roles", methods=["GET"])
@require_permissions("organization:roles:manage")
def list_roles():
    organization_id = g.current_organization["organization_id"]
    result = UserService.get_roles(organization_id=organization_id)
    return jsonify(result), 200


@users_bp.route("/roles/<string:role_id>", methods=["GET"])
@require_permissions("organization:roles:manage")
def get_role(role_id):
    organization_id = g.current_organization["organization_id"]
    result = UserService.get_role_by_id(role_id, organization_id=organization_id)
    return jsonify(result), 200 if result.get("success") else 404


@users_bp.route("/roles/<string:role_id>", methods=["PATCH"])
@require_permissions("organization:roles:manage")
def update_role(role_id):
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.update_role(role_id, organization_id=organization_id, data=data, actor_id=actor_id)
    if not result.get("success"):
        status_code = result.get("status_code", 404 if result.get("message") == "Role not found" else 400)
        return jsonify(result), status_code
    return jsonify(result), 200


@users_bp.route("/roles/<string:role_id>", methods=["DELETE"])
@require_permissions("organization:roles:manage")
def delete_role(role_id):
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.delete_role(role_id, organization_id=organization_id, actor_id=actor_id)
    if not result.get("success"):
        status_code = result.get("status_code", 404 if result.get("message") == "Role not found" else 400)
        return jsonify(result), status_code
    return jsonify(result), 200


@users_bp.route("/permissions", methods=["GET"])
@require_permissions("organization:roles:manage")
def list_available_permissions():
    result = UserService.list_permissions()
    return jsonify(result), 200


@users_bp.route("/audit-logs", methods=["GET"])
@require_permissions("organization:users:manage")
def list_audit_logs():
    organization_id = g.current_organization["organization_id"]
    target_id = request.args.get("target_id")
    event_type = request.args.get("event_type")
    search = request.args.get("search")
    action = request.args.get("action")
    actor = request.args.get("actor")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    result_filter = request.args.get("result")
    limit = request.args.get("limit", 50)
    page = request.args.get("page", 1)

    result = UserService.get_audit_logs(
        organization_id=organization_id,
        target_id=target_id,
        event_type=event_type,
        search=search,
        action=action,
        actor=actor,
        start_date=start_date,
        end_date=end_date,
        result=result_filter,
        limit=limit,
        page=page
    )
    return jsonify({
        "success": True,
        "count": len(result["items"]),
        "total_count": result["pagination"]["total"],
        "pagination": result["pagination"],
        "data": result["items"],
        "items": result["items"]
    }), 200
