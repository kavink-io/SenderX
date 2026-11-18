import re
import secrets
import string
import uuid
import bcrypt
from pymongo.errors import DuplicateKeyError
from flask import current_app

from app.modules.users.repository import UserRepository
from app.modules.users.audit_repository import SecurityAuditRepository
from app.modules.auth.repository import AuthRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.service import OrganizationService
from app.modules.applications.repository import ApplicationRepository
from app.modules.organizations.sequence_repository import SequenceRepository


class UserService:

    ALLOWED_ORGANIZATION_PERMISSIONS = set(OrganizationService.ORG_ADMIN_PERMISSIONS)

    PERMISSION_CATEGORIES = {
        "MESSAGING": [
            "organization:messages:read",
            "organization:messages:create",
            "organization:messages:manage"
        ],
        "TEMPLATES": [
            "organization:templates:read",
            "organization:templates:create",
            "organization:templates:manage"
        ],
        "PAYLOADS": [
            "organization:payloads:read",
            "organization:payloads:edit",
            "organization:payloads:validate"
        ],
        "DEAD_LETTERS": [
            "organization:dead_letters:read",
            "organization:dead_letters:manage",
            "organization:dlq:read",
            "organization:dlq:retry"
        ],
        "MEDIA": [
            "organization:media:read",
            "organization:media:upload",
            "organization:media:delete",
            "organization:media:manage"
        ],
        "ANALYTICS": [
            "organization:analytics:read"
        ],
        "USERS": [
            "organization:users:manage"
        ],
        "ROLES": [
            "organization:roles:manage"
        ],
        "CONFIGURATION": [
            "organization:configuration:manage",
            "organization:providers:read",
            "organization:providers:manage"
        ]
    }

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

    @staticmethod
    def _generate_temporary_password():
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_"
        return "".join(secrets.choice(alphabet) for _ in range(16))

    @staticmethod
    def validate_employee_code(code):
        if not isinstance(code, str):
            return None, "Employee ID must be a string"
        clean = code.strip().upper()
        if len(clean) < 3 or len(clean) > 40:
            return None, "Employee ID must be between 3 and 40 characters"
        if not re.fullmatch(r"^[A-Z0-9]+(-[A-Z0-9]+)*$", clean):
            return None, "Employee ID must contain only uppercase letters, numbers, and hyphens (e.g. ABC-EMP-001)"
        return clean, None

    # ======================================================
    # EMPLOYEE MANAGEMENT
    # ======================================================

    @classmethod
    def create_user(cls, data, organization_id, actor_id=None, actor_email=None):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        role_ids = data.get("role_ids")
        role_assignments = data.get("role_assignments")

        if not isinstance(name, str) or not isinstance(email, str):
            return {"success": False, "message": "Name and email are required strings"}

        name = name.strip()
        email = email.strip().lower()

        if not name or len(name) > 100:
            return {"success": False, "message": "Name must be between 1 and 100 characters"}

        if not cls._validate_email(email):
            return {"success": False, "message": "Invalid email address format"}

        generated_password = None
        if password is None or password == "":
            generated_password = cls._generate_temporary_password()
            password = generated_password
        elif not cls._validate_password(password):
            return {"success": False, "message": "Password must be at least 12 characters and at most 72 bytes"}

        if UserRepository.find_by_email(email):
            return {"success": False, "message": "A user with this email already exists"}

        if AuthRepository.find_by_email(email):
            return {"success": False, "message": "This email is registered to a platform administrator"}

        # Validate or allocate employee business ID (employee_code)
        requested_code = data.get("employee_code")
        assigned_employee_code = None

        org = OrganizationRepository.find_by_id(organization_id)
        default_prefix = (org.get("employee_id_prefix") or "EMP") if org else "EMP"

        if requested_code is not None and str(requested_code).strip() != "":
            code_clean, err = cls.validate_employee_code(requested_code)
            if err:
                return {"success": False, "message": err, "status_code": 400}
            existing = UserRepository.find_by_employee_code(code_clean, organization_id=organization_id)
            if existing:
                return {
                    "success": False,
                    "message": f"Employee ID '{code_clean}' already exists in this organization",
                    "status_code": 409
                }
            assigned_employee_code = code_clean
        else:
            # Atomic allocation using SequenceRepository
            seq = SequenceRepository.allocate_next_sequence(
                organization_id=organization_id,
                sequence_type="employee",
                default_prefix=default_prefix
            )
            assigned_employee_code = seq["code"]

        # Normalize and validate role assignments
        validated_assignments, validation_err = cls._normalize_and_validate_role_assignments(
            role_ids=role_ids,
            role_assignments=role_assignments,
            organization_id=organization_id
        )
        if validation_err:
            return {"success": False, "message": validation_err}

        derived_role_ids = sorted(list(set(a["role_id"] for a in validated_assignments)))
        derived_app_ids = sorted(list(set(
            a["application_id"] for a in validated_assignments if a.get("application_id")
        )))

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

        user_id = str(uuid.uuid4())
        user_doc = {
            "user_id": user_id,
            "organization_id": organization_id,
            "employee_code": assigned_employee_code,
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "role_ids": derived_role_ids,
            "role_assignments": validated_assignments,
            "application_ids": derived_app_ids,
            "is_active": True
        }

        try:
            created = UserRepository.create(user_doc)

            # Record security audit log
            SecurityAuditRepository.log_event(
                organization_id=organization_id,
                event_type="EMPLOYEE_CREATED",
                actor_id=actor_id,
                actor_email=actor_email,
                target_id=user_id,
                target_type="USER",
                details={
                    "name": name,
                    "email": email,
                    "employee_code": assigned_employee_code,
                    "role_ids": derived_role_ids,
                    "application_ids": derived_app_ids
                }
            )

            response_data = {
                "user_id": created["user_id"],
                "organization_id": created["organization_id"],
                "employee_code": created.get("employee_code"),
                "name": created["name"],
                "email": created["email"],
                "role_ids": created["role_ids"],
                "role_assignments": created.get("role_assignments", []),
                "application_ids": created.get("application_ids", []),
                "is_active": created["is_active"],
                "created_at": created.get("created_at")
            }
            if generated_password:
                response_data["temporary_password"] = generated_password

            return {
                "success": True,
                "message": "Organization employee created successfully",
                "data": response_data
            }
        except DuplicateKeyError as e:
            if "employee_code" in str(e):
                return {
                    "success": False,
                    "message": f"Employee ID '{assigned_employee_code}' already exists in this organization",
                    "status_code": 409
                }
            return {"success": False, "message": "User with this email already exists", "status_code": 409}

    @classmethod
    def get_users(cls, organization_id, limit=50, page=1, search=None, status=None, role_id=None, application_id=None, employee_code=None):
        result = UserRepository.find_all_by_organization(
            organization_id=organization_id,
            limit=limit,
            page=page,
            search=search,
            status=status,
            role_id=role_id,
            application_id=application_id,
            employee_code=employee_code
        )

        # Pre-fetch organization roles and apps to enrich employee records
        roles_list = RoleRepository.find_by_organization(organization_id)
        roles_map = {r["role_id"]: r for r in roles_list}

        apps_cursor = ApplicationRepository._collection().find(
            {"organization_id": organization_id},
            {"_id": 0, "application_id": 1, "name": 1, "status": 1, "environment": 1}
        )
        apps_map = {a["application_id"]: a for a in apps_cursor}

        enriched_items = []
        for user in result["items"]:
            enriched = dict(user)

            assignments = user.get("role_assignments")
            if not isinstance(assignments, list) or not assignments:
                assignments = [{"role_id": r, "application_id": None} for r in user.get("role_ids", [])]

            enriched_assignments = []
            assigned_apps_set = set()

            for assign in assignments:
                r_id = assign.get("role_id")
                r_doc = roles_map.get(r_id, {})
                app_id = assign.get("application_id") or r_doc.get("application_id")
                app_doc = apps_map.get(app_id, {}) if app_id else {}

                enriched_assign = {
                    "role_id": r_id,
                    "role_name": r_doc.get("name", "Unknown Role"),
                    "is_system_role": r_doc.get("is_system_role", False),
                    "application_id": app_id,
                    "application_name": app_doc.get("name") if app_id else "All Applications (Org-wide)"
                }
                enriched_assignments.append(enriched_assign)
                if app_id and app_id in apps_map:
                    assigned_apps_set.add((app_id, apps_map[app_id].get("name", app_id)))

            enriched["role_assignments"] = enriched_assignments
            enriched["roles"] = enriched_assignments
            enriched["assigned_applications"] = [
                {"application_id": aid, "name": aname} for aid, aname in sorted(list(assigned_apps_set))
            ]
            enriched_items.append(enriched)

        return {
            "items": enriched_items,
            "pagination": result["pagination"]
        }

    @classmethod
    def get_next_employee_code(cls, organization_id):
        """Preview the next auto-allocated employee business ID for the organization."""
        org = OrganizationRepository.find_by_id(organization_id)
        if not org:
            return {"success": False, "message": "Organization not found", "status_code": 404}
        default_prefix = org.get("employee_id_prefix") or "EMP"
        seq_info = SequenceRepository.preview_next_sequence(
            organization_id=organization_id,
            sequence_type="employee",
            default_prefix=default_prefix
        )
        return {
            "success": True,
            "data": {
                "organization_id": organization_id,
                "prefix": seq_info["prefix"],
                "next_value": seq_info["next_value"],
                "next_code": seq_info["code"]
            }
        }

    @classmethod
    def get_user_by_id(cls, user_id, organization_id):
        user = UserRepository.find_by_id(user_id, organization_id=organization_id)
        if not user:
            return {"success": False, "message": "User not found"}

        roles_list = RoleRepository.find_by_organization(organization_id)
        roles_map = {r["role_id"]: r for r in roles_list}

        apps_cursor = ApplicationRepository._collection().find(
            {"organization_id": organization_id},
            {"_id": 0, "application_id": 1, "name": 1, "status": 1, "environment": 1}
        )
        apps_map = {a["application_id"]: a for a in apps_cursor}

        assignments = user.get("role_assignments")
        if not isinstance(assignments, list) or not assignments:
            assignments = [{"role_id": r, "application_id": None} for r in user.get("role_ids", [])]

        enriched_assignments = []
        effective_permissions_by_app = {}
        assigned_apps_set = set()

        for assign in assignments:
            r_id = assign.get("role_id")
            r_doc = roles_map.get(r_id, {})
            app_id = assign.get("application_id") or r_doc.get("application_id")
            app_doc = apps_map.get(app_id, {}) if app_id else {}

            scope_key = app_id if app_id else "org_wide"
            if scope_key not in effective_permissions_by_app:
                effective_permissions_by_app[scope_key] = {
                    "application_id": app_id,
                    "application_name": app_doc.get("name") if app_id else "All Applications (Org-wide)",
                    "permissions": set()
                }
            effective_permissions_by_app[scope_key]["permissions"].update(r_doc.get("permissions", []))

            enriched_assignments.append({
                "role_id": r_id,
                "role_name": r_doc.get("name", "Unknown Role"),
                "is_system_role": r_doc.get("is_system_role", False),
                "permissions": r_doc.get("permissions", []),
                "application_id": app_id,
                "application_name": app_doc.get("name") if app_id else "All Applications (Org-wide)"
            })
            if app_id and app_id in apps_map:
                assigned_apps_set.add((app_id, apps_map[app_id].get("name", app_id)))

        permissions_matrix = [
            {
                "scope": k,
                "application_id": v["application_id"],
                "application_name": v["application_name"],
                "permissions": sorted(list(v["permissions"]))
            }
            for k, v in effective_permissions_by_app.items()
        ]

        return {
            "success": True,
            "data": {
                "user_id": user["user_id"],
                "organization_id": user["organization_id"],
                "employee_code": user.get("employee_code"),
                "name": user["name"],
                "email": user["email"],
                "role_ids": user.get("role_ids", []),
                "role_assignments": enriched_assignments,
                "roles": enriched_assignments,
                "assigned_applications": [
                    {"application_id": aid, "name": aname} for aid, aname in sorted(list(assigned_apps_set))
                ],
                "permissions_matrix": permissions_matrix,
                "is_active": user.get("is_active", True),
                "created_at": user.get("created_at"),
                "updated_at": user.get("updated_at"),
                "last_login_at": user.get("last_login_at")
            }
        }

    @classmethod
    def _is_user_admin(cls, user, organization_id):
        """Check if user possesses administrator role or permissions in the organization."""
        if not user or not user.get("is_active", False):
            return False
        role_ids = set(user.get("role_ids", []) or [])
        for a in user.get("role_assignments", []) or []:
            if isinstance(a, dict) and a.get("role_id"):
                role_ids.add(a["role_id"])

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
    def get_dashboard_context(cls, user_id, organization_id):
        """
        Calculates and returns the authoritative dynamic dashboard context for an organization user.
        Resolves current roles, role assignments, effective permissions, authorized application scopes,
        and allowed navigation menu items from the database in real time.
        """
        user = UserRepository.find_by_id(user_id, organization_id=organization_id)
        if not user or not user.get("is_active", False):
            return {"success": False, "message": "User not found or inactive", "status_code": 401}

        organization = OrganizationRepository.find_by_id(organization_id)
        if not organization or organization.get("status") != "ACTIVE":
            return {"success": False, "message": "Organization is inactive or unavailable", "status_code": 403}

        # Check if user is Organization Admin
        is_admin = cls._is_user_admin(user, organization_id)

        # Retrieve all organization roles & connected applications
        roles_list = RoleRepository.find_by_organization(organization_id)
        roles_map = {r["role_id"]: r for r in roles_list}

        apps_cursor = ApplicationRepository._collection().find(
            {"organization_id": organization_id},
            {"_id": 0, "application_id": 1, "name": 1, "status": 1, "environment": 1, "description": 1}
        )
        apps_map = {a["application_id"]: a for a in apps_cursor}

        role_assignments = user.get("role_assignments")
        if not isinstance(role_assignments, list) or not role_assignments:
            role_assignments = [{"role_id": r, "application_id": None} for r in user.get("role_ids", [])]

        effective_permissions = set()
        permissions_by_app = {}
        assigned_apps_dict = {}
        enriched_assignments = []
        user_roles_list = []
        seen_role_ids = set()

        for assign in role_assignments:
            if not isinstance(assign, dict):
                continue
            r_id = assign.get("role_id")
            if not r_id:
                continue
            r_doc = roles_map.get(r_id)
            if not r_doc or r_doc.get("scope") != "ORGANIZATION":
                continue

            app_id = assign.get("application_id") or r_doc.get("application_id")
            clean_app_id = str(app_id).strip() if app_id and str(app_id).strip().lower() not in ("all", "none", "", "null") else None
            app_doc = apps_map.get(clean_app_id, {}) if clean_app_id else {}

            r_perms = r_doc.get("permissions", [])
            if isinstance(r_perms, list):
                effective_permissions.update(p for p in r_perms if isinstance(p, str))

                scope_key = clean_app_id if clean_app_id else "org_wide"
                if scope_key not in permissions_by_app:
                    permissions_by_app[scope_key] = set()
                permissions_by_app[scope_key].update(p for p in r_perms if isinstance(p, str))

            if r_id not in seen_role_ids:
                seen_role_ids.add(r_id)
                user_roles_list.append({
                    "role_id": r_id,
                    "name": r_doc.get("name", "Unknown Role"),
                    "is_system_role": r_doc.get("is_system_role", False),
                    "is_application_scoped": r_doc.get("is_application_scoped", False),
                    "application_id": r_doc.get("application_id")
                })

            enriched_assignments.append({
                "role_id": r_id,
                "role_name": r_doc.get("name", "Unknown Role"),
                "is_system_role": r_doc.get("is_system_role", False),
                "permissions": r_perms,
                "application_id": clean_app_id,
                "application_name": app_doc.get("name") if clean_app_id else "All Applications (Org-wide)"
            })

            if clean_app_id and clean_app_id in apps_map:
                assigned_apps_dict[clean_app_id] = apps_map[clean_app_id]

        # If ORG_ADMIN, grant full org admin permissions & full application visibility
        if is_admin:
            effective_permissions.update(cls.ALLOWED_ORGANIZATION_PERMISSIONS)
            assigned_applications = list(apps_map.values())
        else:
            assigned_applications = list(assigned_apps_dict.values())

        # Define dynamic navigation catalog
        nav_catalog = [
            {
                "id": "menu-overview",
                "name": "Overview",
                "tab_id": "tab-org-overview",
                "required_permission": None,
                "icon": "grid",
                "allowed_actions": ["view_dashboard"]
            },
            {
                "id": "menu-applications",
                "name": "Connected Applications",
                "tab_id": "tab-org-applications",
                "required_permission": "organization:configuration:manage",
                "icon": "smartphone",
                "allowed_actions": ["register_app", "activate_app", "deactivate_app"]
            },
            {
                "id": "menu-credentials",
                "name": "API Credentials",
                "tab_id": "tab-org-credentials",
                "required_permission": "organization:configuration:manage",
                "icon": "key",
                "allowed_actions": ["create_key", "rotate_key", "revoke_key"]
            },
            {
                "id": "menu-messages",
                "name": "Messages",
                "tab_id": "tab-org-messages",
                "required_permission": "organization:messages:read",
                "icon": "mail",
                "allowed_actions": ["view_messages", "send_message", "queue_message"]
            },
            {
                "id": "menu-templates",
                "name": "Email Templates",
                "tab_id": "tab-org-templates",
                "required_permission": "organization:templates:read",
                "icon": "file-text",
                "allowed_actions": ["view_templates", "create_template", "publish_template"]
            },
            {
                "id": "menu-json-requests",
                "name": "JSON Requests",
                "tab_id": "tab-org-json-requests",
                "required_permission": "organization:payloads:read",
                "icon": "code",
                "allowed_actions": ["view_payload", "edit_payload", "validate_payload", "retry_payload"]
            },
            {
                "id": "menu-dlq",
                "name": "Dead Letter Queue",
                "tab_id": "tab-org-dlq",
                "required_permission": "organization:dead_letters:read",
                "icon": "alert-triangle",
                "allowed_actions": ["view_dlq", "retry_dlq", "delete_dlq"]
            },
            {
                "id": "menu-analytics",
                "name": "Analytics",
                "tab_id": "tab-org-analytics",
                "required_permission": "organization:analytics:read",
                "icon": "bar-chart",
                "allowed_actions": ["view_analytics"]
            },
            {
                "id": "menu-users",
                "name": "Employees & Roles",
                "tab_id": "tab-org-users",
                "required_permission": "organization:users:manage",
                "icon": "users",
                "allowed_actions": ["add_employee", "assign_roles", "manage_roles", "deactivate_employee"]
            },
            {
                "id": "menu-settings",
                "name": "Settings",
                "tab_id": "tab-org-settings",
                "required_permission": "organization:providers:read",
                "icon": "settings",
                "allowed_actions": ["view_settings", "configure_providers"]
            }
        ]

        allowed_navigation = []
        allowed_tabs = []

        for item in nav_catalog:
            req_perm = item["required_permission"]
            if req_perm is None:
                allowed_navigation.append(item)
                allowed_tabs.append(item["tab_id"])
            elif is_admin or req_perm in effective_permissions:
                allowed_navigation.append(item)
                allowed_tabs.append(item["tab_id"])

        # Define dynamic widgets catalog for overview
        widgets_catalog = [
            {"id": "widget-apps", "name": "Connected Apps", "required_permission": "organization:configuration:manage"},
            {"id": "widget-requests", "name": "Total API Requests", "required_permission": "organization:payloads:read"},
            {"id": "widget-messages", "name": "Messages Processed", "required_permission": "organization:messages:read"},
            {"id": "widget-delivered", "name": "Delivered Rate", "required_permission": "organization:messages:read"},
            {"id": "widget-failed", "name": "Failed Dispatches", "required_permission": "organization:messages:read"},
            {"id": "widget-dlq", "name": "Pending DLQ Entries", "required_permission": "organization:dead_letters:read"},
            {"id": "widget-chart", "name": "Activity Chart", "required_permission": "organization:analytics:read"},
            {"id": "widget-channels", "name": "Channel Distribution", "required_permission": "organization:analytics:read"},
            {"id": "widget-recent-requests", "name": "Recent API Requests", "required_permission": "organization:payloads:read"},
            {"id": "widget-recent-failures", "name": "Recent Delivery Failures", "required_permission": "organization:dead_letters:read"},
            {"id": "widget-apps-table", "name": "Applications Overview", "required_permission": "organization:configuration:manage"}
        ]

        allowed_widgets = [
            w["id"] for w in widgets_catalog
            if is_admin or w["required_permission"] in effective_permissions
        ]

        return {
            "success": True,
            "data": {
                "user_id": user["user_id"],
                "employee_code": user.get("employee_code"),
                "name": user.get("name", user["email"]),
                "email": user["email"],
                "account_type": "ORGANIZATION_USER",
                "organization_id": organization_id,
                "organization_name": organization.get("name", "Organization Workspace"),
                "employee_id_prefix": organization.get("employee_id_prefix"),
                "organization_status": organization.get("status", "ACTIVE"),
                "is_org_admin": is_admin,
                "roles": user_roles_list,
                "role_assignments": enriched_assignments,
                "assigned_applications": assigned_applications,
                "effective_permissions": sorted(list(effective_permissions)),
                "permissions_by_application": {
                    k: sorted(list(v)) for k, v in permissions_by_app.items()
                },
                "navigation": allowed_navigation,
                "allowed_tabs": allowed_tabs,
                "allowed_widgets": allowed_widgets
            }
        }

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
    def _normalize_and_validate_role_assignments(cls, role_ids, role_assignments, organization_id):
        """Helper to validate and normalize role assignments."""
        assignments_to_validate = []

        if role_assignments is not None:
            if not isinstance(role_assignments, list):
                return None, "role_assignments must be a list of objects"
            for item in role_assignments:
                if not isinstance(item, dict):
                    return None, "Each role assignment must be a JSON object"
                rid = item.get("role_id")
                if not rid or not isinstance(rid, str):
                    return None, "Each role assignment must contain a valid 'role_id'"
                appid = item.get("application_id")
                if appid is not None and not isinstance(appid, str):
                    return None, "'application_id' must be a string or null"
                assignments_to_validate.append({
                    "role_id": rid.strip(),
                    "application_id": appid.strip() if appid else None
                })
        elif role_ids is not None:
            if not isinstance(role_ids, list):
                return None, "role_ids must be a list"
            for rid in role_ids:
                if not isinstance(rid, str):
                    return None, "role_ids must contain valid strings"
                assignments_to_validate.append({
                    "role_id": rid.strip(),
                    "application_id": None
                })
        else:
            return [], None

        validated = []
        for assign in assignments_to_validate:
            rid = assign["role_id"]
            role = RoleRepository.find_by_id(rid, organization_id=organization_id)
            if not role or role.get("scope") != "ORGANIZATION":
                return None, f"Role '{rid}' is invalid or does not belong to your organization"

            # Check if role itself has default application_id
            app_id = assign.get("application_id") or role.get("application_id")
            if app_id:
                app_id = app_id.strip()
                app = ApplicationRepository.find_by_id(app_id, organization_id=organization_id)
                if not app:
                    return None, f"Connected application '{app_id}' does not belong to your organization"
                if app.get("status") not in ("ACTIVE", None):
                    return None, f"Connected application '{app_id}' is inactive or deactivated"

            validated.append({
                "role_id": rid,
                "application_id": app_id
            })

        return validated, None

    @classmethod
    def update_user(cls, user_id, organization_id, data, actor_id=None, actor_email=None):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}

        user = UserRepository.find_by_id(user_id, organization_id=organization_id)
        if not user:
            return {"success": False, "message": "User not found"}

        # Protection: Employee ID immutability
        if "employee_code" in data:
            requested_code = str(data["employee_code"]).strip().upper() if data["employee_code"] is not None else None
            existing_code = user.get("employee_code")
            if existing_code and requested_code != existing_code:
                return {
                    "success": False,
                    "status_code": 400,
                    "message": "Employee ID is immutable and cannot be changed"
                }
            if not existing_code and requested_code:
                code_clean, err = cls.validate_employee_code(requested_code)
                if err:
                    return {"success": False, "status_code": 400, "message": err}
                conflict = UserRepository.find_by_employee_code(code_clean, organization_id=organization_id)
                if conflict and conflict.get("user_id") != user_id:
                    return {
                        "success": False,
                        "status_code": 409,
                        "message": f"Employee ID '{code_clean}' already exists in this organization"
                    }
                update_fields["employee_code"] = code_clean

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

        if "password" in data:
            new_pwd = str(data["password"])
            if not cls._validate_password(new_pwd):
                return {"success": False, "message": "Password must be at least 12 characters and at most 72 bytes"}
            update_fields["password_hash"] = bcrypt.hashpw(
                new_pwd.encode("utf-8"),
                bcrypt.gensalt(12)
            ).decode("utf-8")

        if "role_ids" in data or "role_assignments" in data:
            validated_assignments, err = cls._normalize_and_validate_role_assignments(
                role_ids=data.get("role_ids"),
                role_assignments=data.get("role_assignments"),
                organization_id=organization_id
            )
            if err:
                return {"success": False, "message": err}

            new_role_ids = sorted(list(set(a["role_id"] for a in validated_assignments)))
            new_app_ids = sorted(list(set(a["application_id"] for a in validated_assignments if a.get("application_id"))))

            # Invariant: Stripping admin rights from last active admin
            if cls._is_user_admin(user, organization_id):
                has_admin_now = False
                for r_id in new_role_ids:
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

            update_fields["role_ids"] = new_role_ids
            update_fields["role_assignments"] = validated_assignments
            update_fields["application_ids"] = new_app_ids

        if not update_fields:
            return {"success": False, "message": "No valid update fields provided"}

        updated = UserRepository.update_user(user_id, organization_id, update_fields)
        if not updated:
            return {"success": False, "message": "User update failed"}

        # Record audit log
        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="EMPLOYEE_UPDATED",
            actor_id=actor_id,
            actor_email=actor_email,
            target_id=user_id,
            target_type="USER",
            details={k: v for k, v in update_fields.items() if k != "password_hash"}
        )

        return cls.get_user_by_id(user_id, organization_id)

    @classmethod
    def assign_user_roles(cls, user_id, organization_id, data, actor_id=None, actor_email=None):
        """Dedicated method for updating employee role assignments with application scopes."""
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}

        role_assignments = data.get("role_assignments")
        role_ids = data.get("role_ids")

        if role_assignments is None and role_ids is None:
            return {"success": False, "message": "Either 'role_assignments' or 'role_ids' is required"}

        update_payload = {}
        if role_assignments is not None:
            update_payload["role_assignments"] = role_assignments
        if role_ids is not None:
            update_payload["role_ids"] = role_ids

        res = cls.update_user(user_id, organization_id, update_payload, actor_id=actor_id, actor_email=actor_email)
        if res.get("success"):
            SecurityAuditRepository.log_event(
                organization_id=organization_id,
                event_type="ROLES_ASSIGNED",
                actor_id=actor_id,
                actor_email=actor_email,
                target_id=user_id,
                target_type="USER",
                details={
                    "role_ids": res["data"].get("role_ids", []),
                    "role_assignments": res["data"].get("role_assignments", [])
                }
            )
        return res

    @classmethod
    def deactivate_user(cls, user_id, organization_id, actor_id=None, actor_email=None):
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
        if updated:
            SecurityAuditRepository.log_event(
                organization_id=organization_id,
                event_type="EMPLOYEE_DEACTIVATED",
                actor_id=actor_id,
                actor_email=actor_email,
                target_id=user_id,
                target_type="USER",
                details={"name": user.get("name"), "email": user.get("email")}
            )

        return {
            "success": updated,
            "status_code": 200 if updated else 400,
            "message": "User deactivated successfully" if updated else "Failed to deactivate user"
        }

    @classmethod
    def activate_user(cls, user_id, organization_id, actor_id=None, actor_email=None):
        user = UserRepository.find_by_id(user_id, organization_id=organization_id)
        if not user:
            return {"success": False, "status_code": 404, "message": "User not found"}

        if user.get("is_active", True):
            return {"success": True, "status_code": 200, "message": "User is already active"}

        updated = UserRepository.update_user(user_id, organization_id, {"is_active": True})
        if updated:
            SecurityAuditRepository.log_event(
                organization_id=organization_id,
                event_type="EMPLOYEE_ACTIVATED",
                actor_id=actor_id,
                actor_email=actor_email,
                target_id=user_id,
                target_type="USER",
                details={"name": user.get("name"), "email": user.get("email")}
            )

        return {
            "success": updated,
            "status_code": 200 if updated else 400,
            "message": "User activated successfully" if updated else "Failed to activate user"
        }

    # ======================================================
    # ROLE MANAGEMENT
    # ======================================================

    @classmethod
    def create_role(cls, data, organization_id, actor_id=None, actor_email=None):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}

        name = data.get("name")
        description = data.get("description", "")
        permissions = data.get("permissions", [])
        application_id = data.get("application_id")

        if not isinstance(name, str) or not name.strip():
            return {"success": False, "message": "Role name is required"}

        name = name.strip()
        if len(name) > 60:
            return {"success": False, "message": "Role name must be between 1 and 60 characters"}

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

        # Validate application_id if supplied
        app_clean = None
        if application_id is not None and str(application_id).strip().lower() not in ("", "all", "none", "null"):
            app_clean = str(application_id).strip()
            app = ApplicationRepository.find_by_id(app_clean, organization_id=organization_id)
            if not app:
                return {"success": False, "message": f"Connected application '{app_clean}' not found in your organization"}
            if app.get("status") not in ("ACTIVE", None):
                return {"success": False, "message": f"Connected application '{app_clean}' is inactive or deactivated"}

        # Check duplicate role name in organization
        existing_role = RoleRepository.find_by_name(name, organization_id=organization_id)
        if existing_role:
            return {"success": False, "message": f"A role named '{name}' already exists in this organization"}

        role_id = str(uuid.uuid4())
        role_doc = {
            "role_id": role_id,
            "organization_id": organization_id,
            "name": name,
            "description": str(description).strip() if description else "",
            "scope": "ORGANIZATION",
            "permissions": sorted(list(set(permissions))),
            "application_id": app_clean,
            "is_system_role": False
        }

        try:
            created = RoleRepository.create(role_doc)

            SecurityAuditRepository.log_event(
                organization_id=organization_id,
                event_type="ROLE_CREATED",
                actor_id=actor_id,
                actor_email=actor_email,
                target_id=role_id,
                target_type="ROLE",
                details={
                    "name": name,
                    "permissions": created["permissions"],
                    "application_id": app_clean
                }
            )

            return {
                "success": True,
                "message": "Custom role created successfully",
                "data": {
                    "role_id": created["role_id"],
                    "organization_id": created["organization_id"],
                    "name": created["name"],
                    "description": created.get("description", ""),
                    "permissions": created["permissions"],
                    "application_id": created.get("application_id"),
                    "is_system_role": created.get("is_system_role", False),
                    "created_at": created.get("created_at")
                }
            }
        except DuplicateKeyError:
            return {"success": False, "message": f"A role named '{name}' already exists in this organization"}

    @classmethod
    def get_roles(cls, organization_id):
        roles = RoleRepository.find_by_organization(organization_id)

        # Pre-fetch applications to enrich names
        apps_cursor = ApplicationRepository._collection().find(
            {"organization_id": organization_id},
            {"_id": 0, "application_id": 1, "name": 1}
        )
        apps_map = {a["application_id"]: a["name"] for a in apps_cursor}

        enriched_roles = []
        for role in roles:
            r = dict(role)
            r_id = r["role_id"]
            app_id = r.get("application_id")
            r["application_name"] = apps_map.get(app_id) if app_id else "All Applications (Org-wide)"
            r["assigned_employees_count"] = UserRepository.count_active_by_role(r_id, organization_id=organization_id)
            enriched_roles.append(r)

        return {
            "success": True,
            "count": len(enriched_roles),
            "data": enriched_roles
        }

    @classmethod
    def get_role_by_id(cls, role_id, organization_id):
        role = RoleRepository.find_by_id(role_id, organization_id=organization_id)
        if not role:
            return {"success": False, "message": "Role not found"}

        app_id = role.get("application_id")
        app_name = "All Applications (Org-wide)"
        if app_id:
            app_doc = ApplicationRepository.find_by_id(app_id, organization_id=organization_id)
            if app_doc:
                app_name = app_doc.get("name", app_id)

        assigned_employees = UserRepository.find_active_by_role(role_id, organization_id=organization_id)

        return {
            "success": True,
            "data": {
                "role_id": role["role_id"],
                "organization_id": role["organization_id"],
                "name": role["name"],
                "description": role.get("description", ""),
                "permissions": role.get("permissions", []),
                "application_id": app_id,
                "application_name": app_name,
                "is_system_role": role.get("is_system_role", False),
                "assigned_employees": assigned_employees,
                "assigned_employees_count": len(assigned_employees),
                "created_at": role.get("created_at")
            }
        }

    @classmethod
    def update_role(cls, role_id, organization_id, data, actor_id=None, actor_email=None):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}

        role = RoleRepository.find_by_id(role_id, organization_id=organization_id)
        if not role:
            return {"success": False, "status_code": 404, "message": "Role not found"}

        if role.get("is_system_role"):
            return {"success": False, "status_code": 400, "message": "System roles cannot be modified"}

        update_fields = {}

        if "name" in data:
            name = str(data["name"]).strip()
            if not name or len(name) > 60:
                return {"success": False, "status_code": 400, "message": "Role name must be between 1 and 60 characters"}
            if name != role.get("name"):
                dup = RoleRepository.find_by_name(name, organization_id=organization_id)
                if dup and dup["role_id"] != role_id:
                    return {"success": False, "status_code": 400, "message": f"A role named '{name}' already exists in this organization"}
            update_fields["name"] = name

        if "description" in data:
            desc = data["description"]
            update_fields["description"] = str(desc).strip() if desc else ""

        if "application_id" in data:
            raw_app = data["application_id"]
            if raw_app and str(raw_app).strip().lower() not in ("", "all", "none", "null"):
                app_clean = str(raw_app).strip()
                app = ApplicationRepository.find_by_id(app_clean, organization_id=organization_id)
                if not app:
                    return {"success": False, "status_code": 400, "message": f"Connected application '{app_clean}' not found in your organization"}
                if app.get("status") not in ("ACTIVE", None):
                    return {"success": False, "status_code": 400, "message": f"Connected application '{app_clean}' is inactive or deactivated"}
                update_fields["application_id"] = app_clean
            else:
                update_fields["application_id"] = None

        if "permissions" in data:
            permissions = data["permissions"]
            if not isinstance(permissions, list) or not permissions:
                return {"success": False, "status_code": 400, "message": "Permissions must be a non-empty list"}

            for perm in permissions:
                if not isinstance(perm, str) or perm in ("*", "organization:*", "platform:*"):
                    return {"success": False, "status_code": 400, "message": "Invalid or wildcard permission"}
                if perm not in cls.ALLOWED_ORGANIZATION_PERMISSIONS:
                    return {"success": False, "status_code": 400, "message": f"Permission '{perm}' is not allowed"}

            update_fields["permissions"] = sorted(list(set(permissions)))

        if not update_fields:
            return {"success": False, "status_code": 400, "message": "No valid fields to update"}

        RoleRepository._collection().update_one(
            {"role_id": role_id, "organization_id": organization_id},
            {"$set": update_fields}
        )

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="ROLE_UPDATED",
            actor_id=actor_id,
            actor_email=actor_email,
            target_id=role_id,
            target_type="ROLE",
            details=update_fields
        )

        return cls.get_role_by_id(role_id, organization_id)

    @classmethod
    def delete_role(cls, role_id, organization_id, actor_id=None, actor_email=None):
        role = RoleRepository.find_by_id(role_id, organization_id=organization_id)
        if not role:
            return {"success": False, "status_code": 404, "message": "Role not found"}

        # Safety Check 1: Cannot delete system roles
        if role.get("is_system_role"):
            return {
                "success": False,
                "status_code": 403,
                "message": f"System role '{role.get('name')}' cannot be deleted"
            }

        # Safety Check 2: Cannot delete role if assigned to any active employee
        assigned_count = UserRepository.count_active_by_role(role_id, organization_id=organization_id)
        if assigned_count > 0:
            return {
                "success": False,
                "status_code": 409,
                "message": f"Cannot delete role '{role.get('name')}': {assigned_count} active employee(s) are currently assigned to it. Please reassign their roles first."
            }

        deleted = RoleRepository.delete(role_id, organization_id=organization_id)
        if not deleted:
            return {"success": False, "status_code": 500, "message": "Failed to delete role"}

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="ROLE_DELETED",
            actor_id=actor_id,
            actor_email=actor_email,
            target_id=role_id,
            target_type="ROLE",
            details={"name": role.get("name")}
        )

        return {
            "success": True,
            "status_code": 200,
            "message": f"Role '{role.get('name')}' deleted successfully"
        }

    # ======================================================
    # PERMISSIONS & AUDIT LOGS
    # ======================================================

    @classmethod
    def list_permissions(cls):
        return {
            "success": True,
            "count": len(cls.ALLOWED_ORGANIZATION_PERMISSIONS),
            "data": sorted(list(cls.ALLOWED_ORGANIZATION_PERMISSIONS)),
            "categories": cls.PERMISSION_CATEGORIES
        }

    @classmethod
    def get_audit_logs(cls, organization_id, target_id=None, event_type=None, limit=50, page=1):
        return SecurityAuditRepository.find_by_organization(
            organization_id=organization_id,
            target_id=target_id,
            event_type=event_type,
            limit=limit,
            page=page
        )
