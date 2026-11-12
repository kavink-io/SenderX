
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    create_access_token
)

from app.modules.auth.service import AuthService
from app.modules.auth.repository import AuthRepository


auth_bp = Blueprint("auth", __name__)


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
def get_current_admin():

    admin_id = get_jwt_identity()

    admin = AuthRepository.find_by_id(admin_id)

    if not admin or not admin.get("is_active", False):
        return jsonify({
            "success": False,
            "message": "Admin account not found or inactive"
        }), 401

    return jsonify({
        "success": True,
        "data": {
            "admin_id": admin["admin_id"],
            "email": admin["email"],
            "role": admin.get("role", "VIEWER")
        }
    }), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():

    admin_id = get_jwt_identity()

    admin = AuthRepository.find_by_id(admin_id)

    if not admin or not admin.get("is_active", False):
        return jsonify({
            "success": False,
            "message": "Admin account not found or inactive"
        }), 401

    claims = get_jwt()

    new_access_token = create_access_token(
        identity=admin_id,
        additional_claims={
            "role": admin.get("role", "VIEWER"),
            "email": admin["email"]
        }
    )

    return jsonify({
        "success": True,
        "access_token": new_access_token,
        "token_type": "Bearer"
    }), 200
