
import re
import uuid
import bcrypt

from pymongo.errors import DuplicateKeyError
from flask import current_app

from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.auth.repository import AuthRepository
from app.modules.users.audit_repository import SecurityAuditRepository
from app.modules.organizations.sequence_repository import SequenceRepository


class OrganizationService:

    ORG_ADMIN_PERMISSIONS = [
        "organization:users:manage",
        "organization:roles:manage",
        "organization:messages:create",
        "organization:messages:read",
        "organization:messages:manage",
        "organization:dead_letters:read",
        "organization:dead_letters:manage",
        "organization:providers:read",
        "organization:providers:manage",
        "organization:configuration:manage",
        "organization:analytics:read",
        "organization:templates:read",
        "organization:templates:manage",
        "organization:templates:create",
        "organization:media:upload",
        "organization:media:read",
        "organization:media:delete",
        "organization:media:manage",
        "organization:payloads:read",
        "organization:payloads:edit",
        "organization:payloads:validate",
        "organization:dlq:read",
        "organization:dlq:retry"
    ]

    @staticmethod
    def create_organization(data, created_by):

        if not isinstance(data, dict):
            return {
                "success": False,
                "message": "Invalid request body"
            }

        name = data.get("name")
        slug = data.get("slug")
        admin_name = data.get("admin_name")
        admin_email = data.get("admin_email")
        admin_password = data.get("admin_password")

        # Validate input types
        if not all(isinstance(value, str) for value in [
            name, slug, admin_name, admin_email, admin_password
        ]):
            return {
                "success": False,
                "message": "All organization and admin fields are required"
            }

        name = name.strip()
        slug = slug.strip().lower()
        admin_name = admin_name.strip()
        admin_email = admin_email.strip().lower()

        if not all([name, slug, admin_name, admin_email, admin_password]):
            return {
                "success": False,
                "message": "All organization and admin fields are required"
            }

        if len(name) > 150:
            return {
                "success": False,
                "message": "Organization name is too long"
            }

        if len(admin_name) > 100:
            return {
                "success": False,
                "message": "Admin name is too long"
            }

        if len(slug) > 80 or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", slug
        ):
            return {
                "success": False,
                "message": "Invalid organization slug"
            }

        if not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            admin_email
        ):
            return {
                "success": False,
                "message": "Invalid admin email address"
            }

        if len(admin_password) < 12 or len(admin_password.encode("utf-8")) > 72:
            return {
                "success": False,
                "message": "Password must be at least 12 characters and at most 72 bytes"
            }

        # Check duplicate organization slug
        if OrganizationRepository.find_by_slug(slug):
            return {
                "success": False,
                "message": "Organization slug already exists"
            }

        # Email-only login requires unambiguous account lookup.
        # Check both account collections.
        if UserRepository.find_by_email(admin_email):
            return {
                "success": False,
                "message": "This email is already registered"
            }

        if AuthRepository.find_by_email(admin_email):
            return {
                "success": False,
                "message": "This email is already used by a platform administrator"
            }

        employee_prefix = data.get("employee_id_prefix")
        employee_prefix_clean = None
        if employee_prefix is not None and str(employee_prefix).strip() != "":
            employee_prefix_clean, err = OrganizationService.validate_employee_prefix(employee_prefix)
            if err:
                return {"success": False, "message": err, "status_code": 400}

        organization_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        role_id = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(
            admin_password.encode("utf-8"),
            bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

        organization = {
            "organization_id": organization_id,
            "name": name,
            "slug": slug,
            "employee_id_prefix": employee_prefix_clean,
            "status": "ACTIVE",
            "created_by": created_by
        }

        role = {
            "role_id": role_id,
            "organization_id": organization_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "permissions": OrganizationService.ORG_ADMIN_PERMISSIONS,
            "is_system_role": True
        }

        # Allocate initial employee code for creator/admin if prefix available
        admin_employee_code = None
        if employee_prefix_clean:
            admin_employee_code = f"{employee_prefix_clean}-001"

        user = {
            "user_id": user_id,
            "organization_id": organization_id,
            "name": admin_name,
            "email": admin_email,
            "password_hash": password_hash,
            "role_ids": [role_id],
            "role_assignments": [
                {"role_id": role_id, "application_id": None}
            ],
            "employee_code": admin_employee_code,
            "is_active": True
        }

        client = current_app.mongo_client

        try:
            with client.start_session() as session:
                with session.start_transaction():

                    OrganizationRepository.create(
                        organization,
                        session=session
                    )

                    RoleRepository.create(
                        role,
                        session=session
                    )

                    UserRepository.create(
                        user,
                        session=session
                    )

            if employee_prefix_clean:
                # If we used 001 for the admin, set next sequence to 2
                SequenceRepository.update_prefix(organization_id, "employee", employee_prefix_clean)
                if admin_employee_code:
                    SequenceRepository._collection().update_one(
                        {"organization_id": organization_id, "sequence_type": "employee"},
                        {"$set": {"next_value": 2}}
                    )

            return {
                "success": True,
                "message": "Organization created successfully",
                "data": {
                    "organization_id": organization_id,
                    "organization_name": name,
                    "slug": slug,
                    "employee_id_prefix": employee_prefix_clean,
                    "admin": {
                        "user_id": user_id,
                        "name": admin_name,
                        "email": admin_email,
                        "role": "ORG_ADMIN",
                        "employee_code": admin_employee_code
                    }
                }
            }

        except DuplicateKeyError:
            return {
                "success": False,
                "message": "Duplicate organization, user or role record"
            }

        except Exception as error:
            current_app.logger.exception(
                "Organization creation failed"
            )

            return {
                "success": False,
                "message": "Organization creation failed",
                "error_type": type(error).__name__
            }

    @staticmethod
    def list_organizations(limit=50, page=1, search=None, status=None):
        return OrganizationRepository.find_all(
            limit=limit,
            page=page,
            search=search,
            status=status
        )

    @staticmethod
    def get_organization(organization_id):
        org = OrganizationRepository.find_by_id(organization_id)
        if not org:
            return {"success": False, "message": "Organization not found"}

        # Retrieve admin contact
        admin_user = UserRepository._collection().find_one({
            "organization_id": organization_id,
            "role_assignments.role_name": "ORG_ADMIN"
        }, {"_id": 0, "password_hash": 0})

        if not admin_user:
            admin_user = UserRepository._collection().find_one({
                "organization_id": organization_id
            }, {"_id": 0, "password_hash": 0})

        user_count = UserRepository._collection().count_documents({"organization_id": organization_id})
        app_count = current_app.mongo_db["connected_applications"].count_documents({"organization_id": organization_id})

        return {
            "success": True,
            "data": {
                "organization_id": org["organization_id"],
                "name": org["name"],
                "slug": org["slug"],
                "status": org.get("status", "ACTIVE"),
                "employee_id_prefix": org.get("employee_id_prefix"),
                "created_at": org.get("created_at"),
                "created_by": org.get("created_by"),
                "user_count": user_count,
                "application_count": app_count,
                "admin": {
                    "name": admin_user.get("name") if admin_user else "-",
                    "email": admin_user.get("email") if admin_user else "-",
                    "role": "ORG_ADMIN"
                } if admin_user else None
            }
        }

    @staticmethod
    def update_organization_status(organization_id, status):
        status = str(status).upper().strip()
        if status not in ("ACTIVE", "INACTIVE"):
            return {"success": False, "message": "Status must be either ACTIVE or INACTIVE"}

        org = OrganizationRepository.find_by_id(organization_id)
        if not org:
            return {"success": False, "message": "Organization not found"}

        OrganizationRepository._collection().update_one(
            {"organization_id": organization_id},
            {"$set": {"status": status, "updated_at": OrganizationRepository._now()}}
        )

        return {
            "success": True,
            "message": f"Organization status updated to {status}",
            "data": {
                "organization_id": organization_id,
                "status": status
            }
        }

    @staticmethod
    def validate_employee_prefix(prefix):
        if not isinstance(prefix, str):
            return None, "Employee ID prefix must be a string"
        prefix_clean = prefix.strip().upper()
        if len(prefix_clean) < 2 or len(prefix_clean) > 20:
            return None, "Employee ID prefix must be between 2 and 20 characters"
        if not re.fullmatch(r"^[A-Z0-9]+(-[A-Z0-9]+)*$", prefix_clean):
            return None, "Employee ID prefix must contain only uppercase letters, numbers, and hyphens"
        return prefix_clean, None

    @staticmethod
    def get_employee_id_config(organization_id):
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
                "organization_id": org["organization_id"],
                "name": org["name"],
                "slug": org.get("slug"),
                "employee_id_prefix": org.get("employee_id_prefix") or default_prefix,
                "next_employee_sequence": seq_info["next_value"],
                "preview_next_code": seq_info["code"]
            }
        }

    @staticmethod
    def configure_employee_prefix(organization_id, data, actor_id=None, actor_email=None):
        if not isinstance(data, dict):
            return {"success": False, "message": "Invalid request body", "status_code": 400}

        org = OrganizationRepository.find_by_id(organization_id)
        if not org:
            return {"success": False, "message": "Organization not found", "status_code": 404}

        requested_prefix = data.get("employee_id_prefix") or data.get("prefix")
        if not requested_prefix or not isinstance(requested_prefix, str) or str(requested_prefix).strip() == "":
            return {"success": False, "message": "employee_id_prefix is required", "status_code": 400}

        prefix_clean, err = OrganizationService.validate_employee_prefix(requested_prefix)
        if err:
            return {"success": False, "message": err, "status_code": 400}

        update_fields = {"employee_id_prefix": prefix_clean}
        SequenceRepository.update_prefix(organization_id, "employee", prefix_clean)
        OrganizationRepository.update(organization_id, update_fields)

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="EMPLOYEE_PREFIX_CONFIGURED",
            actor_id=actor_id,
            actor_email=actor_email,
            target_id=organization_id,
            target_type="ORGANIZATION",
            details=update_fields
        )

        return OrganizationService.get_employee_id_config(organization_id)

    # Aliases for compatibility
    get_identity_config = get_employee_id_config
    configure_identity = configure_employee_prefix
