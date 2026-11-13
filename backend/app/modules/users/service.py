import re
import uuid
import bcrypt
from pymongo.errors import DuplicateKeyError
from flask import current_app

from app.modules.users.repository import UserRepository
from app.modules.auth.repository import AuthRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.organizations.service import OrganizationService


class UserService:

    ALLOWED_ORGANIZATION_PERMISSIONS = set(OrganizationService.ORG_ADMIN_PERMISSIONS)

    @staticmethod
    def _validate_email(email):
        if not isinstance(email, str):
            return False
        return bool(re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            email.strip().lower()
        ))

    @staticmethod
    def _validate_password(password):
        if not isinstance(password, str):
            return False
        return 12 <= len(password) and len(password.encode("utf-8")) <= 72

    @classmethod
    def create_user(cls, data, organization_id):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        role_ids = data.get("role_ids", [])

        if not all(isinstance(v, str) for v in [name, email, password]):
            return {"success": False, "message": "Name, email, and password are required strings"}

        name = name.strip()
        email = email.strip().lower()

        if not name or len(name) > 100:
            return {"success": False, "message": "Name must be between 1 and 100 characters"}

        if not cls._validate_email(email):
            return {"success": False, "message": "Invalid email address format"}

        if not cls._validate_password(password):
            return {"success": False, "message": "Password must be at least 12 characters and at most 72 bytes"}

        if UserRepository.find_by_email(email):
            return {"success": False, "message": "A user with this email already exists"}

        if AuthRepository.find_by_email(email):
            return {"success": False, "message": "This email is registered to a platform administrator"}

        # Validate role assignments
        if not isinstance(role_ids, list):
            return {"success": False, "message": "role_ids must be a list"}

        for role_id in role_ids:
            role = RoleRepository.find_by_id(role_id, organization_id=organization_id)
            if not role or role.get("scope") != "ORGANIZATION":
                return {
                    "success": False,
                    "message": f"Role '{role_id}' is invalid or does not belong to your organization"
                }

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

        user_id = str(uuid.uuid4())
        user_doc = {
            "user_id": user_id,
            "organization_id": organization_id,
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "role_ids": role_ids,
            "is_active": True
        }

        try:
            created = UserRepository.create(user_doc)
            return {
                "success": True,
                "message": "Organization user created successfully",
                "data": {
                    "user_id": created["user_id"],
                    "organization_id": created["organization_id"],
                    "name": created["name"],
                    "email": created["email"],
                    "role_ids": created["role_ids"],
                    "is_active": created["is_active"],
                    "created_at": created.get("created_at")
                }
            }
        except DuplicateKeyError:
            return {"success": False, "message": "User with this email already exists"}

    @classmethod
    def get_users(cls, organization_id, limit=50, page=1):
        return UserRepository.find_all_by_organization(
            organization_id=organization_id,
            limit=limit,
            page=page
        )

    @classmethod
    def get_user_by_id(cls, user_id, organization_id):
        user = UserRepository.find_by_id(user_id, organization_id=organization_id)
        if not user:
            return {"success": False, "message": "User not found"}

        return {
            "success": True,
            "data": {
                "user_id": user["user_id"],
                "organization_id": user["organization_id"],
                "name": user["name"],
                "email": user["email"],
                "role_ids": user.get("role_ids", []),
                "is_active": user.get("is_active", True),
                "created_at": user.get("created_at"),
                "last_login_at": user.get("last_login_at")
            }
        }

    @classmethod
    def _is_user_admin(cls, user, organization_id):
        """Check if user possesses administrator role or permissions in the organization."""
        if not user or not user.get("is_active", False):
            return False
        role_ids = user.get("role_ids", [])
        for r_id in role_ids:
            role = RoleRepository.find_by_id(r_id, organization_id=organization_id)
            if not role:
                continue
            if role.get("name") == "ORG_ADMIN":
                return True
            perms = role.get("permissions", [])
            if "organization:users:manage" in perms or "organization:roles:manage" in perms:
                return True
        return False

    @classmethod
    def _count_active_admins(cls, organization_id, exclude_user_id=None):
        """Count how many active administrators exist in the organization."""
        query = {"organization_id": organization_id, "is_active": True}
        if exclude_user_id:
            query["user_id"] = {"$ne": exclude_user_id}
        active_users = list(UserRepository._collection().find(query))
        count = 0
        for u in active_users:
            if cls._is_user_admin(u, organization_id):
                count += 1
        return count

    @classmethod
    def update_user(cls, user_id, organization_id, data, actor_id=None):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}

        user = UserRepository.find_by_id(user_id, organization_id=organization_id)
        if not user:
            return {"success": False, "message": "User not found"}

        # Protection: Deactivation safety checks
        if data.get("is_active") is False and user.get("is_active") is not False:
            if actor_id and str(actor_id) == str(user_id):
                return {
                    "success": False,
                    "status_code": 409,
                    "message": "Administrators cannot deactivate their own account"
                }
            if cls._is_user_admin(user, organization_id):
                remaining = cls._count_active_admins(organization_id, exclude_user_id=user_id)
                if remaining < 1:
                    return {
                        "success": False,
                        "status_code": 409,
                        "message": "Cannot deactivate the last active administrator in the organization"
                    }

        update_fields = {}

        if "name" in data:
            name = str(data["name"]).strip()
            if not name or len(name) > 100:
                return {"success": False, "message": "Name must be between 1 and 100 characters"}
            update_fields["name"] = name

        if "is_active" in data:
            if not isinstance(data["is_active"], bool):
                return {"success": False, "message": "is_active must be a boolean"}
            update_fields["is_active"] = data["is_active"]

        if "role_ids" in data:
            role_ids = data["role_ids"]
            if not isinstance(role_ids, list):
                return {"success": False, "message": "role_ids must be a list"}

            for role_id in role_ids:
                role = RoleRepository.find_by_id(role_id, organization_id=organization_id)
                if not role or role.get("scope") != "ORGANIZATION":
                    return {
                        "success": False,
                        "message": f"Role '{role_id}' is invalid or does not belong to your organization"
                    }

            # Check if stripping admin rights from last active admin
            if cls._is_user_admin(user, organization_id):
                # Check if new roles still have admin permissions
                has_admin_now = False
                for r_id in role_ids:
                    r = RoleRepository.find_by_id(r_id, organization_id=organization_id)
                    if r and (r.get("name") == "ORG_ADMIN" or "organization:users:manage" in r.get("permissions", [])):
                        has_admin_now = True
                        break
                if not has_admin_now:
                    remaining = cls._count_active_admins(organization_id, exclude_user_id=user_id)
                    if remaining < 1:
                        return {
                            "success": False,
                            "status_code": 409,
                            "message": "Cannot remove administrator role from the last active administrator in the organization"
                        }

            update_fields["role_ids"] = role_ids

        if not update_fields:
            return {"success": False, "message": "No valid update fields provided"}

        updated = UserRepository.update_user(user_id, organization_id, update_fields)
        if not updated:
            return {"success": False, "message": "User update failed"}

        return cls.get_user_by_id(user_id, organization_id)

    @classmethod
    def deactivate_user(cls, user_id, organization_id, actor_id=None):
        user = UserRepository.find_by_id(user_id, organization_id=organization_id)
        if not user:
            return {"success": False, "status_code": 404, "message": "User not found"}

        if not user.get("is_active", False):
            return {"success": True, "status_code": 200, "message": "User is already deactivated"}

        # Protection 1: Self-deactivation prevention
        if actor_id and str(actor_id) == str(user_id):
            return {
                "success": False,
                "status_code": 409,
                "message": "Administrators cannot deactivate their own account"
            }

        # Protection 2: Last active administrator invariant
        if cls._is_user_admin(user, organization_id):
            remaining_admins = cls._count_active_admins(organization_id, exclude_user_id=user_id)
            if remaining_admins < 1:
                return {
                    "success": False,
                    "status_code": 409,
                    "message": "Cannot deactivate the last active administrator in the organization"
                }

        updated = UserRepository.update_user(user_id, organization_id, {"is_active": False})
        return {
            "success": updated,
            "status_code": 200 if updated else 400,
            "message": "User deactivated successfully" if updated else "Failed to deactivate user"
        }

    # ==================================================
    # ROLE MANAGEMENT
    # ==================================================

    @classmethod
    def create_role(cls, data, organization_id):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}

        name = data.get("name")
        permissions = data.get("permissions", [])

        if not isinstance(name, str) or not name.strip():
            return {"success": False, "message": "Role name is required"}

        name = name.strip()
        if len(name) > 60:
            return {"success": False, "message": "Role name too long"}

        if not isinstance(permissions, list) or not permissions:
            return {"success": False, "message": "Permissions must be a non-empty list"}

        # Validate permissions - prevent wildcards and privilege escalation
        for perm in permissions:
            if not isinstance(perm, str):
                return {"success": False, "message": "Invalid permission format"}
            if perm in ("*", "organization:*", "platform:*"):
                return {"success": False, "message": "Wildcard permissions are not allowed"}
            if perm not in cls.ALLOWED_ORGANIZATION_PERMISSIONS:
                return {
                    "success": False,
                    "message": f"Permission '{perm}' is not an allowed organization permission"
                }

        role_id = str(uuid.uuid4())
        role_doc = {
            "role_id": role_id,
            "organization_id": organization_id,
            "name": name,
            "scope": "ORGANIZATION",
            "permissions": sorted(list(set(permissions))),
            "is_system_role": False
        }

        try:
            created = RoleRepository.create(role_doc)
            return {
                "success": True,
                "message": "Role created successfully",
                "data": {
                    "role_id": created["role_id"],
                    "organization_id": created["organization_id"],
                    "name": created["name"],
                    "permissions": created["permissions"],
                    "is_system_role": created.get("is_system_role", False)
                }
            }
        except DuplicateKeyError:
            return {"success": False, "message": f"A role named '{name}' already exists in this organization"}

    @classmethod
    def get_roles(cls, organization_id):
        roles = RoleRepository.find_by_organization(organization_id)
        return {
            "success": True,
            "count": len(roles),
            "data": roles
        }

    @classmethod
    def get_role_by_id(cls, role_id, organization_id):
        role = RoleRepository.find_by_id(role_id, organization_id=organization_id)
        if not role:
            return {"success": False, "message": "Role not found"}

        return {
            "success": True,
            "data": {
                "role_id": role["role_id"],
                "organization_id": role["organization_id"],
                "name": role["name"],
                "permissions": role.get("permissions", []),
                "is_system_role": role.get("is_system_role", False)
            }
        }

    @classmethod
    def update_role(cls, role_id, organization_id, data):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}

        role = RoleRepository.find_by_id(role_id, organization_id=organization_id)
        if not role:
            return {"success": False, "message": "Role not found"}

        if role.get("is_system_role"):
            return {"success": False, "message": "System roles cannot be modified"}

        update_fields = {}

        if "name" in data:
            name = str(data["name"]).strip()
            if not name or len(name) > 60:
                return {"success": False, "message": "Role name must be between 1 and 60 characters"}
            update_fields["name"] = name

        if "permissions" in data:
            permissions = data["permissions"]
            if not isinstance(permissions, list) or not permissions:
                return {"success": False, "message": "Permissions must be a non-empty list"}

            for perm in permissions:
                if not isinstance(perm, str) or perm in ("*", "organization:*", "platform:*"):
                    return {"success": False, "message": "Invalid or wildcard permission"}
                if perm not in cls.ALLOWED_ORGANIZATION_PERMISSIONS:
                    return {"success": False, "message": f"Permission '{perm}' is not allowed"}

            update_fields["permissions"] = sorted(list(set(permissions)))

        if not update_fields:
            return {"success": False, "message": "No valid fields to update"}

        RoleRepository._collection().update_one(
            {"role_id": role_id, "organization_id": organization_id},
            {"$set": update_fields}
        )

        return cls.get_role_by_id(role_id, organization_id)
