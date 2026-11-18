
from flask import Blueprint, request, jsonify, current_app, g

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    create_access_token
)

from app.modules.auth.decorators import require_permissions
from app.modules.auth.service import AuthService
from app.modules.auth.repository import AuthRepository
from app.modules.users.repository import UserRepository
from app.modules.organizations.repository import OrganizationRepository


auth_bp = Blueprint("auth", __name__)


def resolve_account(identity, claims):
    """
    Resolve the account from the database.
    Never trust JWT claims alone for account status or organization access.
    """

    account_type = claims.get("account_type")

    if account_type == "PLATFORM_ADMIN":
        admin = AuthRepository.find_by_id(identity)

        if not admin or not admin.get("is_active", False):
            return None, "Platform administrator not found or inactive"

        return {
            "account_type": "PLATFORM_ADMIN",
            "id": admin["admin_id"],
            "email": admin["email"],
            "role": admin.get("role", "VIEWER")
        }, None

    if account_type == "ORGANIZATION_USER":
        user = UserRepository.find_by_id(identity)

        if not user or not user.get("is_active", False):
            return None, "Organization user not found or inactive"

        organization_id = user.get("organization_id")

        organization = OrganizationRepository.find_by_id(
            organization_id
        )

        if not organization or organization.get("status") != "ACTIVE":
            return None, "Organization is inactive or unavailable"

        from app.modules.users.service import UserService
        ctx = UserService.get_dashboard_context(identity, organization_id)
        if ctx.get("success") and ctx.get("data"):
            account_data = dict(ctx["data"])
            account_data["id"] = user["user_id"]
            account_data["role_ids"] = user.get("role_ids", [])
            return account_data, None

        return {
            "account_type": "ORGANIZATION_USER",
            "id": user["user_id"],
            "email": user["email"],
            "organization_id": organization_id,
            "role_ids": user.get("role_ids", [])
        }, None

    # Backward compatibility for older platform-admin tokens.
    admin = AuthRepository.find_by_id(identity)

    if admin and admin.get("is_active", False):
        return {
            "account_type": "PLATFORM_ADMIN",
            "id": admin["admin_id"],
            "email": admin["email"],
            "role": admin.get("role", "VIEWER")
        }, None

    return None, "Account not found or inactive"


@auth_bp.route("/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    email = email.strip().lower()

    if not email or len(email) > 254:
        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 400

    if not password or len(password.encode("utf-8")) > 72:
        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 400

    result = AuthService.login(email, password)

    return jsonify(result), (
        200 if result.get("success") else 401
    )


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_account():

    identity = get_jwt_identity()
    claims = get_jwt()

    account, error = resolve_account(identity, claims)

    if error:
        return jsonify({
            "success": False,
            "message": error
        }), 401

    return jsonify({
        "success": True,
        "data": account
    }), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():

    identity = get_jwt_identity()
    claims = get_jwt()

    account, error = resolve_account(identity, claims)

    if error:
        return jsonify({
            "success": False,
            "message": error
        }), 401

    if account["account_type"] == "PLATFORM_ADMIN":

        additional_claims = {
            "account_type": "PLATFORM_ADMIN",
            "role": account["role"],
            "email": account["email"]
        }

    else:

        additional_claims = {
            "account_type": "ORGANIZATION_USER",
            "organization_id": account["organization_id"],
            "role_ids": account["role_ids"],
            "email": account["email"]
        }

    new_access_token = create_access_token(
        identity=identity,
        additional_claims=additional_claims
    )

    return jsonify({
        "success": True,
        "access_token": new_access_token,
        "token_type": "Bearer"
    }), 200


@auth_bp.route("/organization-check", methods=["GET"])
@require_permissions("organization:messages:read")
def organization_check():

    return jsonify({
        "success": True,
        "message": "Organization permission verified",
        "data": {
            "user_id": g.current_user["user_id"],
            "organization_id": g.current_organization["organization_id"],
            "permissions": [
                "organization:messages:read"
            ]
        }
    }), 200
