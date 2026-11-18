
from functools import wraps

from flask import jsonify, g, request
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

            # 1. Extract Target Application Context (if present in request)
            header_app = request.headers.get("X-Application-ID")
            query_app = request.args.get("application_id")
            body_app = None
            if request.is_json:
                body = request.get_json(silent=True) or {}
                if isinstance(body, dict):
                    body_app = body.get("application_id")
            kwarg_app = kwargs.get("application_id")

            target_app_id = (header_app or query_app or body_app or kwarg_app or "").strip() or None

            # Validate target application ownership if explicitly specified
            if target_app_id:
                from app.modules.applications.repository import ApplicationRepository
                app_record = ApplicationRepository.find_by_id(target_app_id, organization_id=organization_id)
                if not app_record:
                    return jsonify({
                        "success": False,
                        "message": f"Connected application '{target_app_id}' not found in your organization"
                    }), 404

            # 2. Resolve roles and role_assignments from database
            role_assignments = user.get("role_assignments")
            if not isinstance(role_assignments, list) or not role_assignments:
                # Fallback to role_ids with None application_id (organization-wide)
                role_assignments = [{"role_id": r, "application_id": None} for r in user.get("role_ids", [])]

            granted_permissions = set()
            user_roles = []
            user_app_scopes = set()
            has_org_wide_scope = False

            for assignment in role_assignments:
                if not isinstance(assignment, dict):
                    continue
                role_id = assignment.get("role_id")
                if not role_id:
                    continue

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

                user_roles.append(role)

                # Determine effective application scope for this role assignment
                assigned_app = assignment.get("application_id") or role.get("application_id")
                if assigned_app and str(assigned_app).strip().lower() not in ("all", "none", "", "null"):
                    assigned_app_clean = str(assigned_app).strip()
                    user_app_scopes.add(assigned_app_clean)

                    # Application-scoped role:
                    # If target_app_id is specified, must match assigned_app_clean
                    if target_app_id:
                        if str(target_app_id).strip() == assigned_app_clean:
                            granted_permissions.update(
                                permission for permission in permissions if isinstance(permission, str)
                            )
                    else:
                        # Request is not targeting an application.
                        # Application-scoped roles do not grant organization-wide permissions.
                        pass
                else:
                    # Organization-wide role (e.g. ORG_ADMIN, application_id=None or 'all'):
                    # Applies unconditionally to all applications and org-wide operations.
                    has_org_wide_scope = True
                    granted_permissions.update(
                        permission for permission in permissions if isinstance(permission, str)
                    )

            # If target_app_id was not explicitly specified in header/query/body,
            # but user has role assignments scoped exclusively to a single application,
            # infer target_app_id to that assigned application scope for seamless API access.
            if not target_app_id and len(user_app_scopes) == 1 and not any(
                (assign.get("application_id") is None or str(assign.get("application_id")).strip().lower() in ("all", "none", "", "null"))
                for assign in role_assignments if isinstance(assign, dict)
            ):
                target_app_id = next(iter(user_app_scopes))
                for assignment in role_assignments:
                    if not isinstance(assignment, dict):
                        continue
                    r_id = assignment.get("role_id")
                    role = RoleRepository.find_by_id(r_id, organization_id=organization_id)
                    if not role:
                        continue
                    assigned_app = assignment.get("application_id") or role.get("application_id")
                    if assigned_app and str(assigned_app).strip() == target_app_id:
                        granted_permissions.update(
                            permission for permission in role.get("permissions", []) if isinstance(permission, str)
                        )

            # Wildcard permissions are intentionally not supported.
            if "*" in granted_permissions or "organization:*" in granted_permissions:
                return jsonify({
                    "success": False,
                    "message": "Invalid wildcard permission configuration"
                }), 403

            # Expand granted permissions with aliases for backward/forward compatibility
            effective_permissions = set(granted_permissions)
            if "organization:dead_letters:read" in granted_permissions:
                effective_permissions.add("organization:dlq:read")
            if "organization:dlq:read" in granted_permissions:
                effective_permissions.add("organization:dead_letters:read")
            if "organization:dead_letters:manage" in granted_permissions:
                effective_permissions.add("organization:dlq:retry")
            if "organization:dlq:retry" in granted_permissions:
                effective_permissions.add("organization:dead_letters:manage")

            missing_permissions = (
                set(required_permissions) - effective_permissions
            )

            if missing_permissions:
                msg = (
                    f"You do not have permission to perform this action for application '{target_app_id}'"
                    if target_app_id
                    else "You do not have permission to perform this action"
                )
                return jsonify({
                    "success": False,
                    "message": msg,
                    "missing_permissions": sorted(missing_permissions)
                }), 403

            # Store verified account context for the route handler.
            g.current_user = user
            g.current_organization = organization
            g.current_roles = user_roles
            g.current_application_id = target_app_id
            g.user_application_ids = None if has_org_wide_scope else (list(user_app_scopes) if user_app_scopes else None)

            return func(*args, **kwargs)

        return wrapper

    return decorator
