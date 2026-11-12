
import re
import uuid
import bcrypt

from pymongo.errors import DuplicateKeyError
from flask import current_app

from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.auth.repository import AuthRepository


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
        "organization:analytics:read"
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

        user = {
            "user_id": user_id,
            "organization_id": organization_id,
            "name": admin_name,
            "email": admin_email,
            "password_hash": password_hash,
            "role_ids": [role_id],
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

            return {
                "success": True,
                "message": "Organization created successfully",
                "data": {
                    "organization_id": organization_id,
                    "organization_name": name,
                    "slug": slug,
                    "admin": {
                        "user_id": user_id,
                        "name": admin_name,
                        "email": admin_email,
                        "role": "ORG_ADMIN"
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