
from flask import Blueprint, request, jsonify, g

from app.modules.organizations.service import OrganizationService
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

    result = OrganizationService.list_organizations(limit=limit, page=page)

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
            "status": org.get("status", "ACTIVE"),
            "created_at": org.get("created_at")
        }
    }), 200

