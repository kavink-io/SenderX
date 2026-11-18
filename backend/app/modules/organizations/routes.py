
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.modules.organizations.service import OrganizationService
from app.modules.organizations.repository import OrganizationRepository
from app.modules.users.repository import UserRepository
from app.modules.auth.decorators import require_roles, require_permissions


organizations_bp = Blueprint(
    "organizations",
    __name__
)


@organizations_bp.route("/", methods=["POST"])
@require_roles("SUPER_ADMIN")
def create_organization():

    data = request.get_json(silent=True) or {}

    result = OrganizationService.create_organization(
        data=data,
        created_by=g.current_admin["admin_id"]
    )

    return jsonify(result), (
        201 if result.get("success") else 400
    )


@organizations_bp.route("/", methods=["GET"])
@require_roles("SUPER_ADMIN")
def list_organizations():

    limit = request.args.get("limit", 50)
    page = request.args.get("page", 1)
    search = request.args.get("search", "").strip() or None
    status = request.args.get("status", "").strip().upper() or None

    result = OrganizationService.list_organizations(
        limit=limit,
        page=page,
        search=search,
        status=status
    )

    return jsonify({
        "success": True,
        "count": len(result["items"]),
        "total_count": result["pagination"]["total"],
        "pagination": result["pagination"],
        "data": result["items"]
    }), 200


@organizations_bp.route("/<string:organization_id>", methods=["GET"])
@require_roles("SUPER_ADMIN")
def get_organization(organization_id):

    result = OrganizationService.get_organization(organization_id)
    return jsonify(result), 200 if result.get("success") else 404


@organizations_bp.route("/<string:organization_id>/status", methods=["PATCH"])
@require_roles("SUPER_ADMIN")
def update_organization_status(organization_id):

    data = request.get_json(silent=True) or {}
    status = data.get("status")

    if not status:
        return jsonify({"success": False, "message": "status is required"}), 400

    result = OrganizationService.update_organization_status(organization_id, status)
    return jsonify(result), 200 if result.get("success") else 400


@organizations_bp.route("/current", methods=["GET"])
@require_permissions("organization:users:manage")
def get_current_organization():

    org = g.current_organization
    return jsonify({
        "success": True,
        "data": {
            "organization_id": org["organization_id"],
            "name": org["name"],
            "slug": org["slug"],
            "employee_id_prefix": org.get("employee_id_prefix"),
            "status": org.get("status", "ACTIVE"),
            "created_at": org.get("created_at")
        }
    }), 200


@organizations_bp.route("/employee-prefix", methods=["GET"])
@organizations_bp.route("/identity", methods=["GET"])
@jwt_required()
def get_organization_employee_prefix():
    """Retrieve organization employee ID sequence configuration."""
    claims = get_jwt()
    if claims.get("account_type") != "ORGANIZATION_USER":
        return jsonify({"success": False, "message": "Organization user access required"}), 403

    identity = get_jwt_identity()
    user = UserRepository.find_by_id(identity)
    if not user or not user.get("is_active", False):
        return jsonify({"success": False, "message": "User not found or inactive"}), 401

    org_id = user["organization_id"]
    res = OrganizationService.get_employee_id_config(org_id)
    return jsonify(res), res.get("status_code", 200 if res.get("success") else 400)


@organizations_bp.route("/employee-prefix", methods=["PATCH"])
@organizations_bp.route("/identity", methods=["PATCH"])
@require_permissions("organization:users:manage")
def configure_organization_employee_prefix():
    """Configure or update organization employee ID prefix."""
    data = request.get_json(silent=True) or {}
    org_id = g.current_organization["organization_id"]
    actor_id = g.current_user.get("user_id") if hasattr(g, "current_user") and g.current_user else None
    actor_email = g.current_user.get("email") if hasattr(g, "current_user") and g.current_user else None

    res = OrganizationService.configure_employee_prefix(
        organization_id=org_id,
        data=data,
        actor_id=actor_id,
        actor_email=actor_email
    )
    return jsonify(res), res.get("status_code", 200 if res.get("success") else 400)
    return jsonify(res), res.get("status_code", 200 if res.get("success") else 400)

