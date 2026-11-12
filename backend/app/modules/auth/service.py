
import bcrypt
import uuid

from flask import current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token
)

from app.modules.auth.repository import AuthRepository


class AuthService:

    @staticmethod
    def login(email, password):

        admin = AuthRepository.find_by_email(email)

        if not admin:
            return {
                "success": False,
                "message": "Invalid email or password"
            }

        if not admin.get("is_active", False):
            return {
                "success": False,
                "message": "Account is inactive"
            }

        stored_hash = admin.get("password_hash")

        if not stored_hash:
            return {
                "success": False,
                "message": "Invalid email or password"
            }

        try:
            password_valid = bcrypt.checkpw(
                password.encode("utf-8"),
                stored_hash.encode("utf-8")
            )
        except (ValueError, TypeError):
            password_valid = False

        if not password_valid:
            return {
                "success": False,
                "message": "Invalid email or password"
            }

        admin_id = admin["admin_id"]
        role = admin.get("role", "VIEWER")

        additional_claims = {
            "role": role,
            "email": admin["email"]
        }

        access_token = create_access_token(
            identity=admin_id,
            additional_claims=additional_claims
        )

        refresh_token = create_refresh_token(
            identity=admin_id,
            additional_claims=additional_claims
        )

        AuthRepository.update_last_login(admin_id)

        return {
            "success": True,
            "message": "Login successful",
            "data": {
                "admin": {
                    "admin_id": admin_id,
                    "email": admin["email"],
                    "role": role
                },
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer"
            }
        }
