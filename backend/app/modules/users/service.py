import re
import uuid
import bcrypt
from pymongo.errors import DuplicateKeyError
from flask import current_app
from app.config.settings import Config

from app.modules.users.repository import UserRepository
from app.modules.users.audit_repository import SecurityAuditRepository
from app.modules.auth.repository import AuthRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.service import OrganizationService
from app.modules.applications.repository import ApplicationRepository


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
            "organization:users:manage",
            "organization:users:delete"
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
    def validate_employee_code(code):
        if not isinstance(code, str):
            return None, "Employee ID must be a string"
        clean = code.strip().upper()
        if len(clean) < 3 or len(clean) > 40:
            return None, "Employee ID must be between 3 and 40 characters"
        if not re.fullmatch(r"^[A-Z0-9]+(-[A-Z0-9]+)*$", clean):
            return None, "Employee ID must contain only uppercase letters, numbers, and hyphens (e.g. ABC-EMP-001)"
        return clean, None

    @staticmethod
    def validate_role_name(name):
        if not isinstance(name, str):
            return None, "Role name must be a string"
        clean = re.sub(r"\s+", " ", name.strip())
        if len(clean) < 2 or len(clean) > 60:
            return None, "Role name must be between 2 and 60 characters"
        if not re.fullmatch(r"^[A-Za-z0-9\s\-&]+$", clean):
            return None, "Role name can only contain letters, digits, spaces, hyphens, and ampersands (&)"
        return clean, None

    @staticmethod
    def validate_department(department):
        if department is None or department == "":
            return None, None
        if not isinstance(department, str):
            return None, "Department must be a string"
        clean = department.strip()
        if not clean:
            return None, None
        if len(clean) < 2 or len(clean) > 60:
            return None, "Department must be between 2 and 60 characters"
        return clean, None

    @staticmethod
    def validate_phone(phone):
        if phone is None or phone == "":
            return None, None
        if not isinstance(phone, str):
            return None, "Phone number must be a string"
        clean = re.sub(r"\s+", " ", phone.strip())
        if not clean:
            return None, None
        if not re.fullmatch(r"^\+?[0-9\s\-\(\)\.]{7,25}$", clean):
            return None, "Invalid phone number format. Please provide a valid number (e.g. +1 555-123-4567)"
        digit_count = sum(c.isdigit() for c in clean)
        if digit_count < 7 or digit_count > 15:
            return None, "Phone number must contain between 7 and 15 digits"
        return clean, None

    # ======================================================
    # EMPLOYEE MANAGEMENT
    # ======================================================

    @classmethod
    def create_user(cls, data, organization_id, actor_id=None, actor_email=None):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body"}
        if "password" in data:
            return {
                "success": False,
                "status_code": 400,
                "message": "Employees set their password through account activation"
            }

        name = data.get("name")
        email = data.get("email")
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

        if UserRepository.find_by_email(email):
            return {"success": False, "message": "A user with this email already exists", "status_code": 409}

        if AuthRepository.find_by_email(email):
            return {"success": False, "message": "This email is registered to a platform administrator", "status_code": 409}

        # Validate required employee business ID (employee_code) - manual entry only
        requested_code = data.get("employee_code")
        if requested_code is None or str(requested_code).strip() == "":
            return {
                "success": False,
                "message": "Employee ID is required",
                "status_code": 400
            }

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

        # Validate optional department
        dept_clean, dept_err = cls.validate_department(data.get("department"))
        if dept_err:
            return {"success": False, "message": dept_err, "status_code": 400}

        # Validate optional phone
        phone_clean, phone_err = cls.validate_phone(data.get("phone"))
        if phone_err:
            return {"success": False, "message": phone_err, "status_code": 400}

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

        user_id = str(uuid.uuid4())
        user_doc = {
            "user_id": user_id,
            "organization_id": organization_id,
            "employee_code": assigned_employee_code,
            "employee_code_lower": assigned_employee_code.lower() if assigned_employee_code else None,
            "name": name,
            "email": email,
            "department": dept_clean,
            "phone": phone_clean,
            "role_ids": derived_role_ids,
            "role_assignments": validated_assignments,
            "application_ids": derived_app_ids,
            "status": "PENDING_ACTIVATION",
            "is_active": False
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
                    "department": dept_clean,
                    "phone": phone_clean,
                    "role_ids": derived_role_ids,
                    "application_ids": derived_app_ids,
                    "status": "PENDING_ACTIVATION"
                }
            )

            response_data = {
                "user_id": created["user_id"],
                "organization_id": created["organization_id"],
                "employee_code": created.get("employee_code"),
                "name": created["name"],
                "email": created["email"],
                "department": created.get("department"),
                "phone": created.get("phone"),
                "role_ids": created["role_ids"],
                "role_assignments": created.get("role_assignments", []),
                "application_ids": created.get("application_ids", []),
                "is_active": created["is_active"],
                "status": created["status"],
                "created_at": created.get("created_at")
            }

            return {
                "success": True,
                "message": "Employee created. They must activate their account before signing in.",
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
    def get_user_by_id(cls, user_id, organization_id):
        user = UserRepository.find_by_id(user_id, organization_id=organization_id)
        if not user or user.get("status") == "DELETED" or user.get("is_deleted") is True:
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
                "department": user.get("department"),
                "phone": user.get("phone"),
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
                "status": "ACTIVE" if user.get("is_active", True) else "INACTIVE",
                "is_active": user.get("is_active", True),
                "created_at": user.get("created_at"),
                "last_login_at": user.get("last_login_at"),
                "last_login": user.get("last_login_at"),
                "organization_id": organization_id,
                "organization_name": organization.get("name", "Organization Workspace"),
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
        if not user or user.get("status") == "DELETED" or user.get("is_deleted") is True:
            return {"success": False, "message": "User not found"}

        update_fields = {}

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

        if "name" in data:
            name = str(data["name"]).strip()
            if not name or len(name) > 100:
                return {"success": False, "message": "Name must be between 1 and 100 characters"}
            update_fields["name"] = name

        if "department" in data:
            dept_val = data.get("department")
            dept_clean, dept_err = cls.validate_department(dept_val)
            if dept_err:
                return {"success": False, "status_code": 400, "message": dept_err}
            update_fields["department"] = dept_clean

        if "phone" in data:
            phone_val = data.get("phone")
            phone_clean, phone_err = cls.validate_phone(phone_val)
            if phone_err:
                return {"success": False, "status_code": 400, "message": phone_err}
            update_fields["phone"] = phone_clean

        if "is_active" in data:
            if not isinstance(data["is_active"], bool):
                return {"success": False, "message": "is_active must be a boolean"}
            if data["is_active"] is False:
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
            update_fields["is_active"] = data["is_active"]

        if "password" in data:
            new_pwd = str(data["password"])
            if not cls._validate_password(new_pwd):
                return {"success": False, "message": "Password must be at least 12 characters and at most 72 bytes"}
            from app.config.settings import Config
            bcrypt_rounds = current_app.config.get("BCRYPT_ROUNDS", getattr(Config, "BCRYPT_ROUNDS", 12)) if current_app else getattr(Config, "BCRYPT_ROUNDS", 12)
            update_fields["password_hash"] = bcrypt.hashpw(
                new_pwd.encode("utf-8"),
                bcrypt.gensalt(rounds=bcrypt_rounds)
            ).decode("utf-8")

        if "role_ids" in data or "role_assignments" in data:
            if actor_id and str(actor_id) == str(user_id):
                return {
                    "success": False,
                    "status_code": 403,
                    "message": "You cannot modify your own roles, permissions, or access scopes"
                }

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

        if actor_id and str(actor_id) == str(user_id):
            return {
                "success": False,
                "status_code": 403,
                "message": "You cannot modify your own roles, permissions, or access scopes"
            }

        role_assignments = data.get("role_assignments")
        role_ids = data.get("role_ids")

        if role_assignments is None and role_ids is None and "department" not in data and "phone" not in data and "name" not in data:
            return {"success": False, "message": "Either 'role_assignments' or 'role_ids' is required"}

        update_payload = {}
        if role_assignments is not None:
            update_payload["role_assignments"] = role_assignments
        if role_ids is not None:
            update_payload["role_ids"] = role_ids
        if "department" in data:
            update_payload["department"] = data["department"]
        if "phone" in data:
            update_payload["phone"] = data["phone"]
        if "name" in data:
            update_payload["name"] = data["name"]

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

        if user.get("status") == "PENDING_ACTIVATION":
            return {
                "success": False,
                "status_code": 409,
                "message": "Pending employees must activate their account with an email code"
            }

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

    @classmethod
    def delete_user(cls, user_id, organization_id, actor_id=None, actor_email=None):
        """
        Soft-delete an organization employee.
        Invariants:
        1. Cannot delete another organization's employee (404).
        2. Cannot delete already deleted employee (404).
        3. Cannot delete yourself (403).
        4. Cannot delete the last active ORG_ADMIN (409).
        5. Cannot delete an ORG_ADMIN unless another active ORG_ADMIN remains (409).
        6. Employee ID and email are released for future reuse via partial index filter on deleted_at: None.
        7. Invalidate all active tokens immediately by bumping token_version.
        """
        from datetime import datetime, timezone

        user = UserRepository.find_by_id(user_id, organization_id=organization_id)
        if not user or user.get("status") == "DELETED" or user.get("is_deleted") is True:
            return {"success": False, "status_code": 404, "message": "User not found"}

        # Protection 1: Cannot delete yourself (409)
        if actor_id and str(actor_id) == str(user_id):
            return {
                "success": False,
                "status_code": 409,
                "message": "You cannot delete your own account. Administrators cannot deactivate their own account."
            }

        # Protection 2: Last active administrator invariant (409)
        if cls._is_user_admin(user, organization_id):
            remaining_admins = cls._count_active_admins(organization_id, exclude_user_id=user_id)
            if remaining_admins < 1:
                return {
                    "success": False,
                    "status_code": 409,
                    "message": "Cannot delete the last active administrator in the organization"
                }

        now_iso = datetime.now(timezone.utc).isoformat()
        new_token_version = user.get("token_version", 1) + 1

        update_fields = {
            "status": "DELETED",
            "is_active": False,
            "is_deleted": True,
            "deleted_at": now_iso,
            "deleted_by": actor_id,
            "token_version": new_token_version,
            "updated_at": now_iso
        }

        res = UserRepository._collection().update_one(
            {"user_id": user_id, "organization_id": organization_id},
            {"$set": update_fields}
        )
        if res.matched_count == 0:
            return {"success": False, "status_code": 404, "message": "User not found"}

        # Write-time audit log snapshot
        emp_code = user.get("employee_code")
        emp_code_hint = f" ({emp_code})" if emp_code else ""
        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="EMPLOYEE_DELETED",
            actor_id=actor_id,
            actor_email=actor_email,
            target_id=user_id,
            target_type="USER",
            target_name=user.get("name") or user.get("email"),
            details={
                "name": user.get("name"),
                "email": user.get("email"),
                "employee_code": emp_code
            },
            summary=f"Deleted employee {user.get('name', 'Employee')}{emp_code_hint}"
        )

        return {
            "success": True,
            "status_code": 200,
            "message": "Employee deleted successfully"
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
            return {"success": False, "status_code": 400, "message": "Role name is required"}

        name_clean, name_err = cls.validate_role_name(name)
        if name_err:
            return {"success": False, "status_code": 400, "message": name_err}
        name = name_clean

        if not isinstance(permissions, list) or not permissions:
            return {"success": False, "status_code": 400, "message": "Permissions must be a non-empty list"}

        # Validate permissions - prevent wildcards and privilege escalation
        for perm in permissions:
            if not isinstance(perm, str):
                return {"success": False, "status_code": 400, "message": "Invalid permission format"}
            if perm in ("*", "organization:*", "platform:*"):
                return {"success": False, "status_code": 400, "message": "Wildcard permissions are not allowed"}
            if perm not in cls.ALLOWED_ORGANIZATION_PERMISSIONS:
                return {
                    "success": False,
                    "status_code": 400,
                    "message": f"Permission '{perm}' is not an allowed organization permission"
                }

        # Validate application_id if supplied
        app_clean = None
        if application_id is not None and str(application_id).strip().lower() not in ("", "all", "none", "null"):
            app_clean = str(application_id).strip()
            app = ApplicationRepository.find_by_id(app_clean, organization_id=organization_id)
            if not app:
                return {"success": False, "status_code": 400, "message": f"Connected application '{app_clean}' not found in your organization"}
            if app.get("status") not in ("ACTIVE", None):
                return {"success": False, "status_code": 400, "message": f"Connected application '{app_clean}' is inactive or deactivated"}

        # Check duplicate role name in organization (case-insensitive)
        existing_role = RoleRepository.find_by_name(name, organization_id=organization_id)
        if existing_role:
            return {"success": False, "status_code": 409, "message": f"A role named '{name}' already exists in this organization"}

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
            name_raw = data["name"]
            if not isinstance(name_raw, str) or not name_raw.strip():
                return {"success": False, "status_code": 400, "message": "Role name is required"}
            current_name = role.get("name", "")
            if name_raw.strip() != current_name.strip():
                name_clean, name_err = cls.validate_role_name(name_raw)
                if name_err:
                    return {"success": False, "status_code": 400, "message": name_err}
                if name_clean.lower() != current_name.lower():
                    dup = RoleRepository.find_by_name(name_clean, organization_id=organization_id)
                    if dup and dup["role_id"] != role_id:
                        return {"success": False, "status_code": 409, "message": f"A role named '{name_clean}' already exists in this organization"}
                update_fields["name"] = name_clean

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
    def get_audit_logs(
        cls,
        organization_id,
        target_id=None,
        event_type=None,
        search=None,
        action=None,
        actor=None,
        start_date=None,
        end_date=None,
        result=None,
        limit=50,
        page=1
    ):
        return SecurityAuditRepository.find_by_organization(
            organization_id=organization_id,
            target_id=target_id,
            event_type=event_type,
            search=search,
            action=action,
            actor=actor,
            start_date=start_date,
            end_date=end_date,
            result=result,
            limit=limit,
            page=page
        )

    @classmethod
    def update_own_profile(cls, user_id, data):
        """Allow ORG_ADMIN / employees to update their own name, email, and password."""
        from datetime import datetime, timezone
        if not isinstance(data, dict):
            return {"success": False, "status_code": 400, "message": "Invalid request body"}

        user = UserRepository.find_by_id(user_id)
        if not user or not user.get("is_active", False):
            return {"success": False, "status_code": 404, "message": "User not found or inactive"}

        organization_id = user.get("organization_id")

        # 1. Reject direct organization name or slug changes
        forbidden_org_fields = ["organization_name", "org_name", "slug", "organization_slug", "organization_id"]
        if any(field in data for field in forbidden_org_fields):
            return {
                "success": False,
                "status_code": 403,
                "message": "Direct organization name or slug changes are not permitted. Please submit an organization change request."
            }

        # 2. Reject self-role / permission / scope changes
        forbidden_priv_fields = ["role_ids", "role_assignments", "roles", "permissions", "application_ids"]
        if any(field in data for field in forbidden_priv_fields):
            return {
                "success": False,
                "status_code": 403,
                "message": "You cannot modify your own roles, permissions, or access scopes"
            }

        # 3. Reject self-deactivation
        if data.get("is_active") is False:
            return {
                "success": False,
                "status_code": 409,
                "message": "Administrators cannot deactivate their own account"
            }

        # 4. Reject employee_code changes if already assigned
        if "employee_code" in data:
            requested_code = str(data["employee_code"]).strip().upper() if data["employee_code"] is not None else None
            existing_code = user.get("employee_code")
            if existing_code and requested_code != existing_code:
                return {
                    "success": False,
                    "status_code": 400,
                    "message": "Employee ID is immutable and cannot be changed"
                }

        update_fields = {}
        audit_details = {}

        # Update name
        if "name" in data:
            name = str(data["name"]).strip()
            if not name or len(name) > 100:
                return {"success": False, "status_code": 400, "message": "Name must be between 1 and 100 characters"}
            update_fields["name"] = name
            audit_details["name"] = name

        # Update email
        if "email" in data:
            new_email = str(data["email"]).strip().lower()
            if new_email != user.get("email"):
                if not cls._validate_email(new_email):
                    return {"success": False, "status_code": 400, "message": "Invalid email address format"}

                current_password = data.get("current_password")
                if not current_password or not isinstance(current_password, str):
                    return {"success": False, "status_code": 400, "message": "Current password is required to change email"}

                from app.modules.auth.service import AuthService
                if not AuthService._verify_password(current_password, user.get("password_hash")):
                    return {"success": False, "status_code": 400, "message": "Incorrect current password"}

                # Check uniqueness
                existing_user = UserRepository.find_by_email(new_email)
                if existing_user and existing_user.get("user_id") != user_id:
                    return {"success": False, "status_code": 409, "message": "A user with this email already exists"}

                if AuthRepository.find_by_email(new_email):
                    return {"success": False, "status_code": 409, "message": "This email is registered to a platform administrator"}

                update_fields["email"] = new_email
                audit_details["old_email"] = user.get("email")
                audit_details["new_email"] = new_email

        # Update password
        new_tokens = None
        if "password" in data or "new_password" in data:
            new_password = str(data.get("new_password") or data.get("password"))
            current_password = data.get("current_password")

            if not current_password or not isinstance(current_password, str):
                return {"success": False, "status_code": 400, "message": "Current password is required to change password"}

            from app.modules.auth.service import AuthService
            if not AuthService._verify_password(current_password, user.get("password_hash")):
                return {"success": False, "status_code": 400, "message": "Incorrect current password"}

            if not cls._validate_password(new_password):
                return {"success": False, "status_code": 400, "message": "New password must be at least 12 characters and at most 72 bytes"}

            bcrypt_rounds = int(current_app.config.get("BCRYPT_ROUNDS", getattr(Config, "BCRYPT_ROUNDS", 12))) if current_app else getattr(Config, "BCRYPT_ROUNDS", 12)
            new_password_hash = bcrypt.hashpw(
                new_password.encode("utf-8"),
                bcrypt.gensalt(rounds=bcrypt_rounds)
            ).decode("utf-8")

            # Increment token_version to invalidate all existing tokens
            new_token_version = user.get("token_version", 1) + 1
            update_fields["password_hash"] = new_password_hash
            update_fields["token_version"] = new_token_version
            update_fields["password_changed_at"] = datetime.now(timezone.utc).isoformat()
            audit_details["password_changed"] = True
            audit_details["token_version"] = new_token_version

            # Generate fresh replacement tokens with the new token_version
            claims = {
                "account_type": "ORGANIZATION_USER",
                "organization_id": organization_id,
                "role_ids": user.get("role_ids", []),
                "email": update_fields.get("email", user.get("email")),
                "token_version": new_token_version
            }
            new_tokens = AuthService._generate_tokens(user_id, claims)

        if not update_fields:
            return {"success": False, "status_code": 400, "message": "No valid fields provided for update"}

        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        UserRepository._collection().update_one(
            {"user_id": user_id},
            {"$set": update_fields}
        )

        # Log security audit event
        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="PROFILE_UPDATED",
            actor_id=user_id,
            actor_email=user.get("email"),
            target_id=user_id,
            target_type="USER",
            details=audit_details
        )

        updated_user = UserRepository.find_by_id(user_id)
        response_data = {
            "user_id": updated_user["user_id"],
            "organization_id": updated_user["organization_id"],
            "name": updated_user["name"],
            "email": updated_user["email"],
            "employee_code": updated_user.get("employee_code"),
            "is_active": updated_user.get("is_active", True),
            "created_at": updated_user.get("created_at"),
            "updated_at": updated_user.get("updated_at")
        }
        if new_tokens:
            response_data["access_token"] = new_tokens["access_token"]
            response_data["refresh_token"] = new_tokens["refresh_token"]
            response_data["token_type"] = new_tokens["token_type"]

        return {
            "success": True,
            "message": "Profile updated successfully",
            "data": response_data
        }
