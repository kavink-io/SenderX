"""
SenderX API Credential Management Endpoints
Routes for organization administrators to generate, list, inspect, revoke, and rotate API keys.
"""

from flask import Blueprint, jsonify, request, g

from app.modules.api_credentials.service import ApiCredentialService
from app.modules.auth.decorators import require_permissions


api_credentials_bp = Blueprint("api_credentials", __name__)


@api_credentials_bp.route("/", methods=["POST"])
@require_permissions("organization:configuration:manage")
def create_credential():
    """Generate a new external application API key. Returns raw key ONCE."""
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    application_id = data.get("application_id")
    environment = data.get("environment", "live")
    scopes = data.get("scopes")

    if not name or not application_id:
        return jsonify({
            "success": False,
            "message": "Both 'name' and 'application_id' are required"
        }), 400

    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]

    try:
        res = ApiCredentialService.create_credential(
            organization_id=organization_id,
            application_id=str(application_id).strip(),
            name=str(name).strip(),
            created_by=user_id,
            environment=environment,
            scopes=scopes
        )
        res["api_key"] = res.get("raw_key")
        res["data"] = {**res.get("credential", {}), "api_key": res.get("raw_key")}
        return jsonify(res), 201
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400


@api_credentials_bp.route("/", methods=["GET"])
@require_permissions("organization:configuration:manage")
def list_credentials():
    """List API credentials for the authenticated organization."""
    organization_id = g.current_organization["organization_id"]
    app_id = request.args.get("application_id")

    items = ApiCredentialService.list_credentials(
        organization_id=organization_id,
        application_id=app_id
    )

    return jsonify({
        "success": True,
        "count": len(items),
        "data": items
    }), 200


@api_credentials_bp.route("/<string:credential_id>", methods=["GET"])
@require_permissions("organization:configuration:manage")
def get_credential(credential_id):
    """Retrieve metadata for a specific API credential."""
    organization_id = g.current_organization["organization_id"]

    cred = ApiCredentialService.get_credential(
        credential_id=credential_id,
        organization_id=organization_id
    )
    if not cred:
        return jsonify({"success": False, "message": "API credential not found"}), 404

    return jsonify({"success": True, "data": cred}), 200


@api_credentials_bp.route("/<string:credential_id>", methods=["DELETE"])
@require_permissions("organization:configuration:manage")
def revoke_credential(credential_id):
    """Revoke an active API credential immediately."""
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]

    success = ApiCredentialService.revoke_credential(
        credential_id=credential_id,
        organization_id=organization_id,
        user_id=user_id
    )
    if not success:
        return jsonify({"success": False, "message": "Credential not found or already revoked"}), 404

    return jsonify({"success": True, "message": "API credential revoked successfully"}), 200


@api_credentials_bp.route("/<string:credential_id>/rotate", methods=["POST"])
@require_permissions("organization:configuration:manage")
def rotate_credential(credential_id):
    """Rotate an existing API key, returning the new raw key once."""
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]
    data = request.get_json(silent=True) or {}
    env = data.get("environment", "live")

    res = ApiCredentialService.rotate_credential(
        credential_id=credential_id,
        organization_id=organization_id,
        user_id=user_id,
        environment=env
    )
    if res.get("success"):
        res["api_key"] = res.get("raw_key")
        res["data"] = {**res.get("credential", {}), "api_key": res.get("raw_key")}
    status_code = 200 if res.get("success") else 400
    return jsonify(res), status_code
