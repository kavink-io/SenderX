"""
SenderX Connected Applications Routes
REST endpoints for organization administrators to manage external connected applications.
"""

from flask import Blueprint, jsonify, request, g

from app.modules.applications.service import ApplicationService
from app.modules.auth.decorators import require_permissions, resolve_authorized_application_scope


applications_bp = Blueprint("applications", __name__)


@applications_bp.route("/", methods=["POST"])
@require_permissions("organization:configuration:manage")
def register_application():
    """Register a new external application bound to the current organization."""
    if resolve_authorized_application_scope() is not None:
        return jsonify({
            "success": False,
            "message": "Organization-wide configuration permission is required to register new applications",
        }), 403
    data = request.get_json(silent=True) or {}
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]

    name = data.get("name")
    description = data.get("description")
    environment = data.get("environment", "all")

    res = ApplicationService.register_application(
        organization_id=organization_id,
        name=name,
        description=description,
        environment=environment,
        created_by=user_id
    )

    return jsonify(res), res.get("status_code", 200)


@applications_bp.route("/", methods=["GET"])
@require_permissions("organization:configuration:manage")
def list_applications():
    """List registered connected applications for the organization."""
    organization_id = g.current_organization["organization_id"]
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))

    res = ApplicationService.list_applications(
        organization_id=organization_id,
        status=status,
        limit=limit,
        page=page
    )
    user_app_scopes = resolve_authorized_application_scope()
    if user_app_scopes is not None and isinstance(res.get("data"), list):
        allowed = set(user_app_scopes)
        filtered = [a for a in res["data"] if a.get("application_id") in allowed]
        res["data"] = filtered
        if isinstance(res.get("pagination"), dict):
            res["pagination"]["total"] = len(filtered)
    return jsonify(res), 200


def _check_application_scope(application_id: str):
    """Fail closed when an application-scoped caller targets an unauthorized application."""
    user_app_scopes = resolve_authorized_application_scope()
    if user_app_scopes is not None and application_id not in set(user_app_scopes):
        return jsonify({
            "success": False,
            "message": f"You do not have permission to access or modify application '{application_id}'",
        }), 403
    return None


@applications_bp.route("/<string:application_id>", methods=["GET"])
@require_permissions("organization:configuration:manage")
def get_application(application_id):
    """Get metadata for a specific connected application."""
    scope_err = _check_application_scope(application_id)
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]

    app = ApplicationService.get_application(
        application_id=application_id,
        organization_id=organization_id
    )
    if not app:
        return jsonify({"success": False, "message": "Application not found"}), 404

    return jsonify({"success": True, "data": app}), 200


@applications_bp.route("/<string:application_id>", methods=["PATCH"])
@require_permissions("organization:configuration:manage")
def update_application(application_id):
    """Update metadata for a connected application."""
    scope_err = _check_application_scope(application_id)
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]
    data = request.get_json(silent=True) or {}

    res = ApplicationService.update_application(
        application_id=application_id,
        organization_id=organization_id,
        data=data,
        user_id=user_id
    )
    return jsonify(res), res.get("status_code", 200)


@applications_bp.route("/<string:application_id>/deactivate", methods=["POST"])
@require_permissions("organization:configuration:manage")
def deactivate_application(application_id):
    """Deactivate application and cascade revocation to all active credentials."""
    scope_err = _check_application_scope(application_id)
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]

    res = ApplicationService.deactivate_application(
        application_id=application_id,
        organization_id=organization_id,
        user_id=user_id
    )
    return jsonify(res), res.get("status_code", 200)


@applications_bp.route("/<string:application_id>/activate", methods=["POST"])
@require_permissions("organization:configuration:manage")
def activate_application(application_id):
    """Reactivate a previously deactivated application."""
    scope_err = _check_application_scope(application_id)
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]

    res = ApplicationService.activate_application(
        application_id=application_id,
        organization_id=organization_id,
        user_id=user_id
    )
    return jsonify(res), res.get("status_code", 200)


@applications_bp.route("/<string:application_id>/stats", methods=["GET"])
@require_permissions("organization:configuration:manage")
def get_application_stats(application_id):
    """Get usage statistics and resource counts for an application."""
    scope_err = _check_application_scope(application_id)
    if scope_err:
        return scope_err
    organization_id = g.current_organization["organization_id"]

    res = ApplicationService.get_application_stats(
        application_id=application_id,
        organization_id=organization_id
    )
    return jsonify(res), res.get("status_code", 200)


@applications_bp.route("/<string:application_id>", methods=["DELETE"])
@require_permissions("organization:configuration:manage")
def delete_application(application_id):
    """Safely remove an application from active management without deleting history."""
    scope_err = _check_application_scope(application_id)
    if scope_err:
        return scope_err
    res = ApplicationService.delete_application(
        application_id=application_id,
        organization_id=g.current_organization["organization_id"],
        user_id=g.current_user["user_id"],
    )
    return jsonify(res), res.get("status_code", 200)
