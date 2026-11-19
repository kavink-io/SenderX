
import bcrypt

from flask_jwt_extended import (
    create_access_token,
    create_refresh_token
)

from app.modules.auth.repository import AuthRepository


class AuthService:

    @staticmethod
    def _verify_password(password, stored_hash):
        if not stored_hash:
            return False

        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                stored_hash.encode("utf-8")
            )
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _generate_tokens(identity, claims):
        access_token = create_access_token(
            identity=identity,
            additional_claims=claims
        )

        refresh_token = create_refresh_token(
            identity=identity,
            additional_claims=claims
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer"
        }

    @staticmethod
    def login(email, password):

        if not isinstance(email, str) or not isinstance(password, str):
            return {
                "success": False,
                "message": "Email and password are required"
            }

        email = email.strip().lower()

        if not email or not password:
            return {
                "success": False,
                "message": "Email and password are required"
            }

        # 1. Check platform administrator
        admin = AuthRepository.find_by_email(email)

        if admin:
            if not admin.get("is_active", False):
                return {
                    "success": False,
                    "message": "Account is inactive"
                }

            if not AuthService._verify_password(
                password,
                admin.get("password_hash")
            ):
                return {
                    "success": False,
                    "message": "Invalid password"
                }

            admin_id = admin["admin_id"]
            role = admin.get("role", "VIEWER")

            claims = {
                "account_type": "PLATFORM_ADMIN",
                "role": role,
                "email": email,
                "token_version": admin.get("token_version", 1)
            }

            tokens = AuthService._generate_tokens(
                admin_id,
                claims
            )

            AuthRepository.update_last_login(admin_id)

            return {
                "success": True,
                "message": "Login successful",
                "data": {
                    "account": {
                        "id": admin_id,
                        "admin_id": admin_id,
                        "name": admin.get("name") or "Platform Administrator",
                        "email": email,
                        "account_type": "PLATFORM_ADMIN",
                        "role": role,
                        "status": "ACTIVE" if admin.get("is_active", True) else "INACTIVE",
                        "is_active": admin.get("is_active", True),
                        "created_at": admin.get("created_at"),
                        "last_login_at": admin.get("last_login_at"),
                        "last_login": admin.get("last_login_at")
                    },
                    **tokens
                }
            }

        # 2. Check organization user
        user = AuthRepository.find_user_by_email(email)

        if not user:
            return {
                "success": False,
                "message": "Invalid email"
            }

        if user.get("status") == "DELETED" or user.get("is_deleted") is True:
            return {
                "success": False,
                "message": "Account has been deactivated or deleted"
            }

        if user.get("status") == "PENDING_ACTIVATION":
            return {
                "success": False,
                "message": "Activate your account with the code sent to your email before signing in"
            }

        organization_id = user["organization_id"]

        # Check organization status first
        from app.modules.organizations.repository import OrganizationRepository
        organization = OrganizationRepository.find_by_id(organization_id)
        if not organization or organization.get("status") != "ACTIVE":
            return {
                "success": False,
                "message": "Organization is inactive or unavailable"
            }

        if not user.get("is_active", False):
            return {
                "success": False,
                "message": "Account is inactive"
            }

        if not AuthService._verify_password(
            password,
            user.get("password_hash")
        ):
            return {
                "success": False,
                "message": "Invalid password"
            }

        user_id = user["user_id"]

        claims = {
            "account_type": "ORGANIZATION_USER",
            "organization_id": organization_id,
            "role_ids": user.get("role_ids", []),
            "email": email,
            "token_version": user.get("token_version", 1)
        }

        tokens = AuthService._generate_tokens(
            user_id,
            claims
        )

        AuthRepository.update_user_last_login(user_id)

        account_data = {
            "id": user_id,
            "name": user.get("name", email),
            "email": email,
            "account_type": "ORGANIZATION_USER",
            "organization_id": organization_id,
            "employee_code": user.get("employee_code"),
            "status": "ACTIVE" if user.get("is_active", True) else "INACTIVE",
            "is_active": user.get("is_active", True),
            "created_at": user.get("created_at"),
            "last_login_at": user.get("last_login_at"),
            "last_login": user.get("last_login_at"),
            "role_ids": user.get("role_ids", [])
        }

        try:
            from app.modules.users.service import UserService
            ctx = UserService.get_dashboard_context(user_id, organization_id)
            if ctx.get("success") and ctx.get("data"):
                account_data.update(ctx["data"])
                account_data["id"] = user_id
                account_data["role_ids"] = user.get("role_ids", [])
        except Exception:
            pass

        return {
            "success": True,
            "message": "Login successful",
            "data": {
                "account": account_data,
                **tokens
            }
        }
