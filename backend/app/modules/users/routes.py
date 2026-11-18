from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.modules.users.service import UserService
from app.modules.users.repository import UserRepository
from app.modules.auth.decorators import require_permissions

users_bp = Blueprint("users", __name__)


# ======================================================
# USER ENDPOINTS
# ======================================================

@users_bp.route("/", methods=["POST"])
@require_permissions("organization:users:manage")
def create_user():
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.create_user(data, organization_id=organization_id, actor_id=actor_id)
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

    organization_id = user.get("organization_id")
    result = UserService.get_dashboard_context(identity, organization_id=organization_id)
    return jsonify(result), result.get("status_code", 200 if result.get("success") else 400)


@users_bp.route("/next-employee-code", methods=["GET"])
@require_permissions("organization:users:manage")
def get_next_employee_code():
    organization_id = g.current_organization["organization_id"]
    result = UserService.get_next_employee_code(organization_id)
    return jsonify(result), result.get("status_code", 200 if result.get("success") else 400)


@users_bp.route("/<string:user_id>", methods=["GET"])
@require_permissions("organization:users:manage")
def get_user(user_id):
    organization_id = g.current_organization["organization_id"]
    result = UserService.get_user_by_id(user_id, organization_id=organization_id)
    return jsonify(result), 200 if result.get("success") else 404


@users_bp.route("/<string:user_id>", methods=["PATCH"])
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


@users_bp.route("/<string:user_id>", methods=["DELETE"])
@require_permissions("organization:users:manage")
def deactivate_user(user_id):
    organization_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None

    result = UserService.deactivate_user(user_id, organization_id=organization_id, actor_id=actor_id)
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
    return jsonify(result), 201 if result.get("success") else 400


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
        status_code = 404 if result.get("message") == "Role not found" else 400
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
    limit = request.args.get("limit", 50)
    page = request.args.get("page", 1)

    result = UserService.get_audit_logs(
        organization_id=organization_id,
        target_id=target_id,
        event_type=event_type,
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
