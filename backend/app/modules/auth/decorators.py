
from functools import wraps

from flask import jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.modules.auth.repository import AuthRepository


def require_roles(*allowed_roles):

    def decorator(func):

        @wraps(func)
        @jwt_required()
        def wrapper(*args, **kwargs):

            admin_id = get_jwt_identity()

            admin = AuthRepository.find_by_id(admin_id)

            if not admin or not admin.get("is_active", False):
                return jsonify({
                    "success": False,
                    "message": "Admin account not found or inactive"
                }), 401

            current_role = admin.get("role")

            if current_role not in allowed_roles:
                return jsonify({
                    "success": False,
                    "message": "You do not have permission to perform this action"
                }), 403

            # Store the authenticated admin for use in route handlers.
            g.current_admin = admin

            return func(*args, **kwargs)

        return wrapper

    return decorator
