
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
            "status": org.get("status", "ACTIVE"),
            "created_at": org.get("created_at")
        }
    }), 200


@organizations_bp.route("/current", methods=["PATCH", "PUT"])
@jwt_required()
def update_current_organization():
    return jsonify({
        "success": False,
        "message": "Direct organization name or slug changes are not permitted. Please submit an organization change request."
    }), 403


@organizations_bp.route("/<string:organization_id>", methods=["PATCH", "PUT"])
@jwt_required()
def update_organization_direct(organization_id):
    claims = get_jwt()
    if claims.get("account_type") != "PLATFORM_ADMIN":
        return jsonify({
            "success": False,
            "message": "Direct organization name or slug changes are not permitted. Please submit an organization change request."
        }), 403
    return jsonify({"success": False, "message": "Direct modification not supported"}), 400


# ======================================================
# CHANGE REQUESTS (Phase 5 Task 5.3)
# ======================================================

@organizations_bp.route("/change-requests", methods=["POST"])
@require_permissions("organization:users:manage")
def submit_change_request():
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id")
    user_email = g.current_user.get("email")

    result = OrganizationService.submit_change_request(
        organization_id=organization_id,
        user_id=user_id,
        user_email=user_email,
        data=data
    )
    status_code = 201 if result.get("success") else result.get("status_code", 400)
    return jsonify(result), status_code


@organizations_bp.route("/change-requests", methods=["GET"])
@require_permissions("organization:users:manage")
def list_org_change_requests():
    organization_id = g.current_organization["organization_id"]
    limit = request.args.get("limit", 50)
    page = request.args.get("page", 1)

    result = OrganizationService.list_org_change_requests(
        organization_id=organization_id,
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


@organizations_bp.route("/change-requests/<string:request_id>/cancel", methods=["POST"])
@require_permissions("organization:users:manage")
def cancel_change_request(request_id):
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user.get("user_id")
    user_email = g.current_user.get("email")

    result = OrganizationService.cancel_change_request(
        request_id=request_id,
        organization_id=organization_id,
        user_id=user_id,
        user_email=user_email
    )
    status_code = 200 if result.get("success") else result.get("status_code", 400)
    return jsonify(result), status_code


@organizations_bp.route("/change-requests/all", methods=["GET"])
@require_roles("SUPER_ADMIN")
def list_all_change_requests():
    limit = request.args.get("limit", 50)
    page = request.args.get("page", 1)
    status = request.args.get("status")
    search = request.args.get("search")

    result = OrganizationService.platform_list_change_requests(
        limit=limit,
        page=page,
        status=status,
        search=search
    )
    return jsonify({
        "success": True,
        "count": len(result["items"]),
        "total_count": result["pagination"]["total"],
        "pagination": result["pagination"],
        "data": result["items"],
        "items": result["items"]
    }), 200


@organizations_bp.route("/change-requests/<string:request_id>/approve", methods=["POST"])
@require_roles("SUPER_ADMIN")
def approve_change_request(request_id):
    admin_id = g.current_admin["admin_id"]
    admin_email = g.current_admin.get("email")

    result = OrganizationService.approve_change_request(
        request_id=request_id,
        admin_id=admin_id,
        admin_email=admin_email
    )
    status_code = 200 if result.get("success") else result.get("status_code", 400)
    return jsonify(result), status_code


@organizations_bp.route("/change-requests/<string:request_id>/reject", methods=["POST"])
@require_roles("SUPER_ADMIN")
def reject_change_request(request_id):
    admin_id = g.current_admin["admin_id"]
    admin_email = g.current_admin.get("email")
    data = request.get_json(silent=True) or {}
    rejection_reason = data.get("rejection_reason")

    result = OrganizationService.reject_change_request(
        request_id=request_id,
        admin_id=admin_id,
        admin_email=admin_email,
        rejection_reason=rejection_reason
    )
    status_code = 200 if result.get("success") else result.get("status_code", 400)
    return jsonify(result), status_code


# ======================================================
# SUPER_ADMIN ORGANIZATION DELETION (Phase 5 Task 5.3)
# ======================================================

@organizations_bp.route("/<string:organization_id>/deletion-summary", methods=["GET"])
@require_roles("SUPER_ADMIN")
def get_org_deletion_summary(organization_id):
    result = OrganizationService.get_deletion_summary(organization_id)
    status_code = 200 if result.get("success") else result.get("status_code", 404)
    return jsonify(result), status_code


@organizations_bp.route("/<string:organization_id>/delete", methods=["POST", "DELETE"])
@organizations_bp.route("/<string:organization_id>", methods=["DELETE"])
@require_roles("SUPER_ADMIN")
def delete_organization(organization_id):
    data = request.get_json(silent=True) or {}
    confirm_slug = data.get("confirm_slug") or request.args.get("confirm_slug")
    admin_id = g.current_admin["admin_id"]
    admin_email = g.current_admin.get("email")

    result = OrganizationService.delete_organization(
        organization_id=organization_id,
        confirm_slug=confirm_slug,
        admin_id=admin_id,
        admin_email=admin_email
    )
    status_code = 200 if result.get("success") else result.get("status_code", 400)
    return jsonify(result), status_code


# Platform blueprint for platform-scoped change request routes
platform_bp = Blueprint("platform", __name__)


@platform_bp.route("/change-requests", methods=["GET"])
@require_roles("SUPER_ADMIN")
def platform_list_change_requests_route():
    return list_all_change_requests()


@platform_bp.route("/change-requests/<string:request_id>/approve", methods=["POST"])
@require_roles("SUPER_ADMIN")
def platform_approve_change_request_route(request_id):
    return approve_change_request(request_id)


@platform_bp.route("/change-requests/<string:request_id>/reject", methods=["POST"])
@require_roles("SUPER_ADMIN")
def platform_reject_change_request_route(request_id):
    return reject_change_request(request_id)


@platform_bp.route("/audit-logs", methods=["GET"])
@require_roles("SUPER_ADMIN")
def platform_list_audit_logs():
    organization_id = request.args.get("organization_id")
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

    from app.modules.users.audit_repository import SecurityAuditRepository
    res = SecurityAuditRepository.find_by_organization(
        organization_id=organization_id if organization_id and organization_id != "all" else None,
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
        "count": len(res["items"]),
        "total_count": res["pagination"]["total"],
        "pagination": res["pagination"],
        "data": res["items"],
        "items": res["items"]
    }), 200


