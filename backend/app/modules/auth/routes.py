
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
from app.modules.auth.otp_service import OTPService, OTPServiceError
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

        if claims.get("token_version", 1) != admin.get("token_version", 1):
            return None, "Session expired or password changed. Please log in again."

        return {
            "account_type": "PLATFORM_ADMIN",
            "id": admin["admin_id"],
            "admin_id": admin["admin_id"],
            "name": admin.get("name") or "Platform Administrator",
            "email": admin["email"],
            "role": admin.get("role", "SUPER_ADMIN"),
            "status": "ACTIVE" if admin.get("is_active", True) else "INACTIVE",
            "is_active": admin.get("is_active", True),
            "created_at": admin.get("created_at"),
            "last_login_at": admin.get("last_login_at"),
            "last_login": admin.get("last_login_at")
        }, None

    if account_type == "ORGANIZATION_USER":
        user = UserRepository.find_by_id(identity)

        if not user or not user.get("is_active", False):
            return None, "Organization user not found or inactive"

        if claims.get("token_version", 1) != user.get("token_version", 1):
            return None, "Session expired or password changed. Please log in again."

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
            account_data["name"] = user.get("name", user["email"])
            account_data["email"] = user["email"]
            account_data["employee_code"] = user.get("employee_code")
            account_data["status"] = "ACTIVE" if user.get("is_active", True) else "INACTIVE"
            account_data["is_active"] = user.get("is_active", True)
            account_data["created_at"] = user.get("created_at")
            account_data["last_login_at"] = user.get("last_login_at")
            account_data["last_login"] = user.get("last_login_at")
            account_data["role_ids"] = user.get("role_ids", [])
            account_data["role"] = "ORG_ADMIN" if account_data.get("is_org_admin") else (
                account_data.get("roles", [{}])[0].get("name") if account_data.get("roles") else "EMPLOYEE"
            )
            return account_data, None

        return {
            "account_type": "ORGANIZATION_USER",
            "id": user["user_id"],
            "name": user.get("name", user["email"]),
            "email": user["email"],
            "employee_code": user.get("employee_code"),
            "organization_id": organization_id,
            "status": "ACTIVE" if user.get("is_active", True) else "INACTIVE",
            "is_active": user.get("is_active", True),
            "created_at": user.get("created_at"),
            "last_login_at": user.get("last_login_at"),
            "last_login": user.get("last_login_at"),
            "role_ids": user.get("role_ids", []),
            "role": "EMPLOYEE"
        }, None

    # Backward compatibility for older platform-admin tokens.
    admin = AuthRepository.find_by_id(identity)

    if admin and admin.get("is_active", False):
        return {
            "account_type": "PLATFORM_ADMIN",
            "id": admin["admin_id"],
            "admin_id": admin["admin_id"],
            "name": admin.get("name") or "Platform Administrator",
            "email": admin["email"],
            "role": admin.get("role", "SUPER_ADMIN"),
            "status": "ACTIVE" if admin.get("is_active", True) else "INACTIVE",
            "is_active": admin.get("is_active", True),
            "created_at": admin.get("created_at"),
            "last_login_at": admin.get("last_login_at"),
            "last_login": admin.get("last_login_at")
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


def _otp_error_response(error):
    payload = {
        "success": False,
        "message": error.message
    }
    if error.retry_after:
        payload["retry_after"] = error.retry_after
    response = jsonify(payload)
    if error.retry_after:
        response.headers["Retry-After"] = str(error.retry_after)
    return response, error.status_code


@auth_bp.route("/activation/request-otp", methods=["POST"])
def request_activation_otp():
    data = request.get_json(silent=True) or {}
    try:
        result = OTPService.request_code(
            data.get("email"),
            OTPService.ACTIVATION,
            client_ip=request.remote_addr
        )
        return jsonify(result), 200
    except OTPServiceError as error:
        return _otp_error_response(error)


@auth_bp.route("/password/forgot", methods=["POST"])
def request_password_reset_otp():
    data = request.get_json(silent=True) or {}
    try:
        result = OTPService.request_code(
            data.get("email"),
            OTPService.PASSWORD_RESET,
            client_ip=request.remote_addr
        )
        return jsonify(result), 200
    except OTPServiceError as error:
        return _otp_error_response(error)


@auth_bp.route("/otp/verify", methods=["POST"])
def verify_otp():
    data = request.get_json(silent=True) or {}
    try:
        result = OTPService.verify_code(
            data.get("email"),
            data.get("purpose"),
            data.get("code"),
            client_ip=request.remote_addr
        )
        return jsonify(result), 200
    except OTPServiceError as error:
        return _otp_error_response(error)


@auth_bp.route("/otp/set-password", methods=["POST"])
def set_password_with_otp():
    data = request.get_json(silent=True) or {}
    try:
        result = OTPService.set_password(
            data.get("purpose"),
            data.get("reset_token"),
            data.get("password")
        )
        return jsonify(result), 200
    except OTPServiceError as error:
        return _otp_error_response(error)


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

        admin = AuthRepository.find_by_id(identity)
        additional_claims = {
            "account_type": "PLATFORM_ADMIN",
            "role": account["role"],
            "email": account["email"],
            "token_version": admin.get("token_version", 1)
        }

    else:

        user = UserRepository.find_by_id(identity)
        additional_claims = {
            "account_type": "ORGANIZATION_USER",
            "organization_id": account["organization_id"],
            "role_ids": account["role_ids"],
            "email": account["email"],
            "token_version": user.get("token_version", 1)
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
