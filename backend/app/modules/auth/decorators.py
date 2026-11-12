
from functools import wraps

from flask import jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.modules.auth.repository import AuthRepository
from app.modules.users.repository import UserRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository


def require_roles(*allowed_roles):
    """
    Platform administrator role authorization.
    Only platform administrators can pass this decorator.
    """

    def decorator(func):

        @wraps(func)
        @jwt_required()
        def wrapper(*args, **kwargs):

            identity = get_jwt_identity()
            claims = get_jwt()

            if claims.get("account_type") not in (
                "PLATFORM_ADMIN",
                None  # Backward compatibility with older admin tokens
            ):
                return jsonify({
                    "success": False,
                    "message": "Platform administrator access required"
                }), 403

            admin = AuthRepository.find_by_id(identity)

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

            g.current_admin = admin

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_permissions(*required_permissions):
    """
    Organization-user permission authorization.

    All requested permissions must be assigned to the user's
    organization-scoped roles.
    """

    def decorator(func):

        @wraps(func)
        @jwt_required()
        def wrapper(*args, **kwargs):

            identity = get_jwt_identity()
            claims = get_jwt()

            if claims.get("account_type") != "ORGANIZATION_USER":
                return jsonify({
                    "success": False,
                    "message": "Organization user access required"
                }), 403

            user = UserRepository.find_by_id(identity)

            if not user or not user.get("is_active", False):
                return jsonify({
                    "success": False,
                    "message": "Organization user not found or inactive"
                }), 401

            organization_id = user.get("organization_id")

            # Verify that the organization still exists and is active.
            organization = OrganizationRepository.find_by_id(
                organization_id
            )

            if not organization or organization.get("status") != "ACTIVE":
                return jsonify({
                    "success": False,
                    "message": "Organization is inactive or unavailable"
                }), 403

            # Resolve roles from the database, not from JWT claims.
            role_ids = user.get("role_ids", [])
            granted_permissions = set()
            user_roles = []

            for role_id in role_ids:

                role = RoleRepository.find_by_id(
                    role_id,
                    organization_id=organization_id
                )

                if not role:
                    continue

                # Only organization-scoped roles are accepted.
                if role.get("scope") != "ORGANIZATION":
                    continue

                permissions = role.get("permissions", [])

                if not isinstance(permissions, list):
                    continue

                granted_permissions.update(
                    permission
                    for permission in permissions
                    if isinstance(permission, str)
                )

                user_roles.append(role)

            # Wildcard permissions are intentionally not supported.
            if "*" in granted_permissions or "organization:*" in granted_permissions:
                return jsonify({
                    "success": False,
                    "message": "Invalid wildcard permission configuration"
                }), 403

            missing_permissions = (
                set(required_permissions) - granted_permissions
            )

            if missing_permissions:
                return jsonify({
                    "success": False,
                    "message": "You do not have permission to perform this action",
                    "missing_permissions": sorted(missing_permissions)
                }), 403

            # Store verified account context for the route handler.
            g.current_user = user
            g.current_organization = organization
            g.current_roles = user_roles

            return func(*args, **kwargs)

        return wrapper

    return decorator
