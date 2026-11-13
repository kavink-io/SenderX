"""
SenderX Email Template Management Routes
API endpoints for organization-scoped email template CRUD, previews,
versioning, publishing, archiving, and duplication.
"""

from flask import Blueprint, request, jsonify, g
from app.modules.auth.decorators import require_permissions
from app.modules.templates.service import TemplateService

templates_bp = Blueprint("templates", __name__)


# ---------------------------------------------------------------------------
# 1. CREATE TEMPLATE
# ---------------------------------------------------------------------------
@templates_bp.route("/", methods=["POST"])
@require_permissions("organization:templates:manage")
def create_template():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.create_template(
        data=payload,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 201 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 2. LIST TEMPLATES
# ---------------------------------------------------------------------------
@templates_bp.route("/", methods=["GET"])
@require_permissions("organization:templates:read")
def list_templates():
    organization_id = g.current_organization["organization_id"]

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = min(100, max(1, int(request.args.get("limit", 50))))
    except (ValueError, TypeError):
        page = 1
        limit = 50

    status = request.args.get("status")
    category = request.args.get("category")
    search = request.args.get("search")

    result = TemplateService.list_templates(
        organization_id=organization_id,
        page=page,
        limit=limit,
        status=status,
        category=category,
        search=search
    )

    return jsonify(result), 200


# ---------------------------------------------------------------------------
# 3. GET TEMPLATE BY ID
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>", methods=["GET"])
@require_permissions("organization:templates:read")
def get_template(template_id):
    organization_id = g.current_organization["organization_id"]

    result = TemplateService.get_template(
        template_id=template_id,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 4. UPDATE TEMPLATE
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>", methods=["PUT"])
@require_permissions("organization:templates:manage")
def update_template(template_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "message": "Valid JSON body is required"
        }), 400

    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.update_template(
        template_id=template_id,
        data=payload,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 5. DELETE TEMPLATE
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>", methods=["DELETE"])
@require_permissions("organization:templates:manage")
def delete_template(template_id):
    organization_id = g.current_organization["organization_id"]

    result = TemplateService.delete_template(
        template_id=template_id,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 6. LIVE PREVIEW (By ID)
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/preview", methods=["POST"])
@require_permissions("organization:templates:read")
def preview_template(template_id):
    payload = request.get_json(silent=True) or {}
    sample_data = payload.get("sample_data", payload) if isinstance(payload, dict) else {}

    organization_id = g.current_organization["organization_id"]

    result = TemplateService.preview_template(
        template_id=template_id,
        sample_data=sample_data,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 7. PUBLISH TEMPLATE
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/publish", methods=["POST"])
@require_permissions("organization:templates:manage")
def publish_template(template_id):
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.publish_template(
        template_id=template_id,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 8. ARCHIVE TEMPLATE
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/archive", methods=["POST"])
@require_permissions("organization:templates:manage")
def archive_template(template_id):
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.archive_template(
        template_id=template_id,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 9. DUPLICATE TEMPLATE
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/duplicate", methods=["POST"])
@require_permissions("organization:templates:manage")
def duplicate_template(template_id):
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id") or g.current_user.get("email")

    result = TemplateService.duplicate_template(
        template_id=template_id,
        organization_id=organization_id,
        user_id=user_id
    )

    status_code = result.get("status_code", 201 if result["success"] else 400)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 10. LIST TEMPLATE VERSIONS
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/versions", methods=["GET"])
@require_permissions("organization:templates:read")
def get_template_versions(template_id):
    organization_id = g.current_organization["organization_id"]

    result = TemplateService.get_versions(
        template_id=template_id,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# 11. GET SPECIFIC TEMPLATE VERSION
# ---------------------------------------------------------------------------
@templates_bp.route("/<string:template_id>/versions/<int:version>", methods=["GET"])
@require_permissions("organization:templates:read")
def get_template_version(template_id, version):
    organization_id = g.current_organization["organization_id"]

    result = TemplateService.get_version(
        template_id=template_id,
        version=version,
        organization_id=organization_id
    )

    status_code = result.get("status_code", 200 if result["success"] else 404)
    return jsonify(result), status_code
