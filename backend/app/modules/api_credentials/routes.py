"""
SenderX API Credential Management Endpoints
Routes for organization administrators to register and manage externally supplied API keys.
"""

from flask import Blueprint, jsonify, request, g

from app.modules.api_credentials.service import ApiCredentialService, DuplicateApiKeyError
from app.modules.auth.decorators import require_permissions


api_credentials_bp = Blueprint("api_credentials", __name__)


@api_credentials_bp.route("/", methods=["POST"])
@require_permissions("organization:configuration:manage")
def create_credential():
    """Register an API key supplied by a connected application."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Request body must be an object"}), 400

    name = data.get("name")
    application_id = data.get("application_id")
    api_key = data.get("api_key")
    if not name or not application_id or not api_key:
        return jsonify({
            "success": False,
            "message": "'name', 'application_id', and 'api_key' are required"
        }), 400

    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]

    try:
        result = ApiCredentialService.create_credential(
            organization_id=organization_id,
            application_id=application_id,
            name=name,
            api_key=api_key,
            created_by=user_id,
            environment=data.get("environment", "live"),
            status=data.get("status", "ACTIVE"),
            description=data.get("description"),
            notes=data.get("notes"),
            scopes=data.get("scopes")
        )
        return jsonify(result), 201
    except DuplicateApiKeyError as exc:
        return jsonify({"success": False, "message": str(exc)}), 409
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


@api_credentials_bp.route("/<string:credential_id>", methods=["PATCH"])
@require_permissions("organization:configuration:manage")
def update_credential(credential_id):
    """Update key metadata or supply a replacement key value."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Request body must be an object"}), 400

    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]
    try:
        result = ApiCredentialService.update_credential(
            credential_id=credential_id,
            organization_id=organization_id,
            user_id=user_id,
            data=data
        )
        status_code = result.pop("status_code", 200 if result.get("success") else 400)
        return jsonify(result), status_code
    except DuplicateApiKeyError as exc:
        return jsonify({"success": False, "message": str(exc)}), 409
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400


@api_credentials_bp.route("/<string:credential_id>", methods=["DELETE"])
@require_permissions("organization:configuration:manage")
def delete_credential(credential_id):
    """Delete one API key record without affecting its connected application."""
    organization_id = g.current_organization["organization_id"]
    user_id = g.current_user["user_id"]

    success = ApiCredentialService.delete_credential(
        credential_id=credential_id,
        organization_id=organization_id,
        user_id=user_id
    )
    if not success:
        return jsonify({"success": False, "message": "API credential not found"}), 404

    return jsonify({"success": True, "message": "API credential deleted successfully"}), 200
