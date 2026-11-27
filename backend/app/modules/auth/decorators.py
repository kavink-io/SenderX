
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

            if claims.get("token_version", 1) != admin.get("token_version", 1):
                return jsonify({
                    "success": False,
                    "message": "Session expired or password changed. Please log in again."
                }), 401

            current_role = admin.get("role")

            if current_role not in allowed_roles:
                return jsonify({
                    "success": False,
                    "message": "You do not have permission to perform this action"
                }), 403

            g.current_admin = admin
            g.auth_type = "PLATFORM_ADMIN"
            g.current_credential = None
            g.current_application_id = None
            g.user_application_ids = None

            return func(*args, **kwargs)

        return wrapper

    return decorator


def _expand_organization_permissions(raw_permissions):
    """Expand organization permissions with compatibility aliases."""
    effective = set(raw_permissions)
    if "organization:users:manage" in raw_permissions:
        effective.add("organization:users:delete")
    if "organization:users:delete" in raw_permissions:
        effective.add("organization:users:manage")
    if "organization:dead_letters:read" in raw_permissions:
        effective.add("organization:dlq:read")
    if "organization:dlq:read" in raw_permissions:
        effective.add("organization:dead_letters:read")
    if "organization:dead_letters:manage" in raw_permissions:
        effective.add("organization:dlq:retry")
    if "organization:dlq:retry" in raw_permissions:
        effective.add("organization:dead_letters:manage")
    if "organization:configuration:manage" in raw_permissions:
        effective.add("organization:providers:manage")
        effective.add("organization:providers:read")
    if "organization:providers:manage" in raw_permissions:
        effective.add("organization:providers:read")
    if "organization:templates:manage" in raw_permissions:
        effective.update([
            "organization:templates:create",
            "organization:templates:read",
            "templates.read",
            "templates.create",
            "templates.update",
            "templates.publish",
            "templates.delete"
        ])
    if "organization:templates:read" in raw_permissions:
        effective.add("templates.read")
    if "templates.read" in raw_permissions:
        effective.add("organization:templates:read")
    if any(p in raw_permissions for p in ["templates.create", "templates.update", "templates.publish", "templates.delete"]):
        effective.add("organization:templates:manage")
    return effective


def _extract_target_application_id(kwargs):
    """Extract and validate target application_id across header, query, body, and route kwargs."""
    candidates = []
    header_app = request.headers.get("X-Application-ID")
    query_app = request.args.get("application_id")
    body_app = None
    if request.is_json:
        body = request.get_json(silent=True) or {}
        if isinstance(body, dict) and "application_id" in body:
            body_app = body.get("application_id")
    kwarg_app = kwargs.get("application_id")

    for val in (header_app, query_app, body_app, kwarg_app):
        if val is None:
            continue
        if not isinstance(val, str):
            return None, ("application_id must be a string", 400)
        cleaned = val.strip()
        if cleaned:
            candidates.append(cleaned)

    distinct = list(dict.fromkeys(candidates))
    if len(distinct) > 1:
        return None, ("Conflicting application_id values supplied in request", 403)
    return (distinct[0] if distinct else None), None


def resolve_authorized_application_scope():
    """
    Return the authoritative application ID scope for the current request:
    - None when caller has verified organization-wide scope for this endpoint.
    - A non-empty list[str] of authorized application IDs when caller is application-scoped or API-key bound.
    """
    if getattr(g, "auth_type", None) == "API_KEY":
        app_id = getattr(g, "current_application_id", None)
        return [str(app_id).strip()] if app_id else []

    user_scopes = getattr(g, "user_application_ids", None)
    if user_scopes is not None:
        return [str(aid).strip() for aid in user_scopes if aid]

    return None


def require_organization_wide_scope():
    """Reject callers restricted to specific applications on organization-wide configuration routes."""
    if resolve_authorized_application_scope() is not None:
        return jsonify({
            "success": False,
            "message": "Organization-wide permission scope is required for this resource"
        }), 403
    return None


def require_permissions(*required_permissions):
    """
    Organization-user permission authorization.

    All requested permissions must be assigned to the user's
    organization-scoped roles and match any targeted or assigned application scope.
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

            if not user or not user.get("is_active", False) or user.get("status") == "DELETED" or user.get("is_deleted") is True:
                return jsonify({
                    "success": False,
                    "message": "Organization user not found or inactive"
                }), 401

            if claims.get("token_version", 1) != user.get("token_version", 1):
                return jsonify({
                    "success": False,
                    "message": "Session expired or password changed. Please log in again."
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

            # 1. Extract and validate Target Application Context
            target_app_id, extract_err = _extract_target_application_id(kwargs)
            if extract_err:
                err_msg, err_code = extract_err
                return jsonify({"success": False, "message": err_msg}), err_code

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
                role_assignments = [{"role_id": r, "application_id": None} for r in user.get("role_ids", [])]

            org_wide_raw_permissions = set()
            app_raw_permissions = {}
            user_roles = []
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

                if not role or role.get("scope") != "ORGANIZATION":
                    continue

                permissions = role.get("permissions", [])
                if not isinstance(permissions, list):
                    continue

                clean_perms = [p for p in permissions if isinstance(p, str)]
                if "*" in clean_perms or "organization:*" in clean_perms:
                    return jsonify({
                        "success": False,
                        "message": "Invalid wildcard permission configuration"
                    }), 403

                user_roles.append(role)

                assigned_app = assignment.get("application_id") or role.get("application_id")
                if assigned_app and str(assigned_app).strip().lower() not in ("all", "none", "", "null"):
                    assigned_app_clean = str(assigned_app).strip()
                    app_raw_permissions.setdefault(assigned_app_clean, set()).update(clean_perms)
                else:
                    has_org_wide_scope = True
                    org_wide_raw_permissions.update(clean_perms)

            req_set = set(required_permissions)
            org_wide_effective = _expand_organization_permissions(org_wide_raw_permissions)
            has_required_org_wide = bool(has_org_wide_scope and req_set.issubset(org_wide_effective))

            if target_app_id:
                combined_raw = org_wide_raw_permissions | app_raw_permissions.get(target_app_id, set())
                effective_permissions = _expand_organization_permissions(combined_raw)
                missing_permissions = req_set - effective_permissions
                if missing_permissions:
                    return jsonify({
                        "success": False,
                        "message": f"You do not have permission to perform this action for application '{target_app_id}'",
                        "missing_permissions": sorted(missing_permissions)
                    }), 403
                authorized_app_ids = None if has_required_org_wide else [target_app_id]
            else:
                if has_required_org_wide:
                    authorized_app_ids = None
                else:
                    eligible_apps = sorted(
                        aid for aid, perms in app_raw_permissions.items()
                        if req_set.issubset(_expand_organization_permissions(org_wide_raw_permissions | perms))
                    )
                    if not eligible_apps:
                        all_combined = set(org_wide_raw_permissions)
                        for perms in app_raw_permissions.values():
                            all_combined.update(perms)
                        effective_all = _expand_organization_permissions(all_combined)
                        missing_permissions = req_set - effective_all
                        if not missing_permissions:
                            missing_permissions = req_set
                        return jsonify({
                            "success": False,
                            "message": "You do not have permission to perform this action",
                            "missing_permissions": sorted(missing_permissions)
                        }), 403
                    authorized_app_ids = eligible_apps
                    if len(eligible_apps) == 1:
                        target_app_id = eligible_apps[0]

            # Store verified account context for the route handler.
            g.auth_type = "ORGANIZATION_USER"
            g.current_credential = None
            g.current_user = user
            g.current_organization = organization
            g.current_roles = user_roles
            g.current_application_id = target_app_id
            g.user_application_ids = authorized_app_ids

            return func(*args, **kwargs)

        return wrapper

    return decorator
