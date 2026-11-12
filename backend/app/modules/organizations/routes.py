
from flask import Blueprint, request, jsonify, g

from app.modules.organizations.service import OrganizationService
from app.modules.auth.decorators import require_roles


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
