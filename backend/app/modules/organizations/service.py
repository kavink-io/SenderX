
import re
import uuid
import bcrypt
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError
from flask import current_app
from app.config.settings import Config

from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.organizations.change_request_repository import OrganizationChangeRequestRepository
from app.modules.users.repository import UserRepository
from app.modules.auth.repository import AuthRepository
from app.modules.users.audit_repository import SecurityAuditRepository


class OrganizationService:

    ORG_ADMIN_PERMISSIONS = [
        "organization:users:manage",
        "organization:users:delete",
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
    def _validate_slug(slug):
        if not isinstance(slug, str):
            return False
        clean = slug.strip().lower()
        if len(clean) < 2 or len(clean) > 80:
            return False
        return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", clean))

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

        admin_employee_code = None
        if data.get("employee_code") or data.get("admin_employee_code"):
            raw_code = data.get("employee_code") or data.get("admin_employee_code")
            admin_employee_code = str(raw_code).strip().upper()

        organization_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        role_id = str(uuid.uuid4())

        bcrypt_rounds = int(current_app.config.get("BCRYPT_ROUNDS", getattr(Config, "BCRYPT_ROUNDS", 12))) if current_app else getattr(Config, "BCRYPT_ROUNDS", 12)
        password_hash = bcrypt.hashpw(
            admin_password.encode("utf-8"),
            bcrypt.gensalt(rounds=bcrypt_rounds)
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
            "role_assignments": [
                {"role_id": role_id, "application_id": None}
            ],
            "employee_code": admin_employee_code,
            "employee_code_lower": admin_employee_code.lower() if admin_employee_code else None,
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

    # ======================================================
    # CHANGE REQUESTS (Phase 5 Task 5.3)
    # ======================================================

    @classmethod
    def submit_change_request(cls, organization_id, user_id, user_email, data):
        if not isinstance(data, dict):
            return {"success": False, "status_code": 400, "message": "Invalid request body"}

        org = OrganizationRepository.find_by_id(organization_id)
        if not org or org.get("status") != "ACTIVE":
            return {"success": False, "status_code": 404, "message": "Organization not found or inactive"}

        # Enforce invariant: only 1 PENDING request per org at a time
        pending = OrganizationChangeRequestRepository.find_pending_by_organization(organization_id)
        if pending:
            return {
                "success": False,
                "status_code": 409,
                "message": "A change request is already pending review for this organization. Please wait for review or cancel it before submitting a new one."
            }

        requested_name = data.get("requested_name")
        requested_slug = data.get("requested_slug")
        reason = data.get("reason")

        if not reason or not isinstance(reason, str) or not reason.strip():
            return {"success": False, "status_code": 400, "message": "A reason for the requested change is required"}
        reason_clean = reason.strip()

        if not requested_name and not requested_slug:
            return {"success": False, "status_code": 400, "message": "At least one of requested_name or requested_slug must be provided"}

        name_clean = None
        if requested_name is not None and str(requested_name).strip():
            name_clean = str(requested_name).strip()
            if len(name_clean) < 2 or len(name_clean) > 100:
                return {"success": False, "status_code": 400, "message": "Organization name must be between 2 and 100 characters"}
            if name_clean == org.get("name") and not requested_slug:
                return {"success": False, "status_code": 400, "message": "Requested name is identical to current name"}

        slug_clean = None
        if requested_slug is not None and str(requested_slug).strip():
            slug_clean = str(requested_slug).strip().lower()
            if not cls._validate_slug(slug_clean):
                return {"success": False, "status_code": 400, "message": "Invalid slug format. Use only lowercase letters, numbers, and hyphens."}
            if slug_clean == org.get("slug") and not name_clean:
                return {"success": False, "status_code": 400, "message": "Requested slug is identical to current slug"}
            existing_org = OrganizationRepository.find_by_slug(slug_clean)
            if existing_org and existing_org.get("organization_id") != organization_id:
                return {"success": False, "status_code": 409, "message": f"Organization slug '{slug_clean}' is already in use"}

        request_id = str(uuid.uuid4())
        doc = {
            "request_id": request_id,
            "organization_id": organization_id,
            "current_name": org.get("name"),
            "current_slug": org.get("slug"),
            "requested_name": name_clean,
            "requested_slug": slug_clean,
            "reason": reason_clean,
            "status": "PENDING",
            "requested_by": user_id,
            "requester_email": user_email,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "reviewed_by": None,
            "reviewer_email": None,
            "reviewed_at": None,
            "rejection_reason": None
        }

        created = OrganizationChangeRequestRepository.create(doc)

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="ORGANIZATION_CHANGE_REQUEST_SUBMITTED",
            actor_id=user_id,
            actor_email=user_email,
            target_id=request_id,
            target_type="CHANGE_REQUEST",
            details={
                "requested_name": name_clean,
                "requested_slug": slug_clean,
                "reason": reason_clean
            }
        )

        return {
            "success": True,
            "message": "Organization change request submitted successfully",
            "data": created
        }

    @classmethod
    def cancel_change_request(cls, request_id, organization_id, user_id, user_email):
        req = OrganizationChangeRequestRepository.find_by_id(request_id)
        if not req or req.get("organization_id") != organization_id:
            return {"success": False, "status_code": 404, "message": "Change request not found"}

        if req.get("status") != "PENDING":
            return {"success": False, "status_code": 400, "message": f"Cannot cancel request with status '{req.get('status')}'"}

        OrganizationChangeRequestRepository.update(request_id, {"status": "CANCELLED"})

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="ORGANIZATION_CHANGE_REQUEST_CANCELLED",
            actor_id=user_id,
            actor_email=user_email,
            target_id=request_id,
            target_type="CHANGE_REQUEST",
            details={"previous_status": "PENDING", "new_status": "CANCELLED"}
        )

        return {"success": True, "message": "Change request cancelled successfully"}

    @classmethod
    def list_org_change_requests(cls, organization_id, limit=50, page=1):
        return OrganizationChangeRequestRepository.find_all_by_organization(
            organization_id=organization_id,
            limit=limit,
            page=page
        )

    @classmethod
    def platform_list_change_requests(cls, limit=50, page=1, status=None, search=None):
        return OrganizationChangeRequestRepository.find_all(
            limit=limit,
            page=page,
            status=status,
            search=search
        )

    @classmethod
    def approve_change_request(cls, request_id, admin_id, admin_email):
        req = OrganizationChangeRequestRepository.find_by_id(request_id)
        if not req:
            return {"success": False, "status_code": 404, "message": "Change request not found"}

        if req.get("status") != "PENDING":
            return {"success": False, "status_code": 400, "message": f"Cannot approve request with status '{req.get('status')}'"}

        org = OrganizationRepository.find_by_id(req["organization_id"])
        if not org:
            return {"success": False, "status_code": 404, "message": "Target organization not found"}

        # Re-validate slug at the exact moment of approval!
        if req.get("requested_slug"):
            req_slug = str(req["requested_slug"]).strip().lower()
            if not cls._validate_slug(req_slug):
                return {"success": False, "status_code": 400, "message": "Invalid slug format"}
            conflict = OrganizationRepository.find_by_slug(req_slug)
            if conflict and conflict.get("organization_id") != org.get("organization_id"):
                return {"success": False, "status_code": 409, "message": f"Organization slug '{req_slug}' is already in use by another organization"}

        org_updates = {}
        if req.get("requested_name"):
            org_updates["name"] = req["requested_name"].strip()
        if req.get("requested_slug"):
            org_updates["slug"] = req["requested_slug"].strip().lower()

        if org_updates:
            OrganizationRepository.update(org["organization_id"], org_updates)

        now = datetime.now(timezone.utc).isoformat()
        OrganizationChangeRequestRepository.update(request_id, {
            "status": "APPROVED",
            "reviewed_by": admin_id,
            "reviewer_email": admin_email,
            "reviewed_at": now
        })

        SecurityAuditRepository.log_event(
            organization_id=org["organization_id"],
            event_type="ORGANIZATION_CHANGE_REQUEST_APPROVED",
            actor_id=admin_id,
            actor_email=admin_email,
            target_id=request_id,
            target_type="CHANGE_REQUEST",
            details={
                "old_name": org.get("name"),
                "new_name": org_updates.get("name", org.get("name")),
                "old_slug": org.get("slug"),
                "new_slug": org_updates.get("slug", org.get("slug"))
            }
        )

        return {"success": True, "message": "Organization change request approved successfully"}

    @classmethod
    def reject_change_request(cls, request_id, admin_id, admin_email, rejection_reason):
        req = OrganizationChangeRequestRepository.find_by_id(request_id)
        if not req:
            return {"success": False, "status_code": 404, "message": "Change request not found"}

        if req.get("status") != "PENDING":
            return {"success": False, "status_code": 400, "message": f"Cannot reject request with status '{req.get('status')}'"}

        if not rejection_reason or not isinstance(rejection_reason, str) or not rejection_reason.strip():
            return {"success": False, "status_code": 400, "message": "Rejection reason is required"}

        now = datetime.now(timezone.utc).isoformat()
        OrganizationChangeRequestRepository.update(request_id, {
            "status": "REJECTED",
            "rejection_reason": rejection_reason.strip(),
            "reviewed_by": admin_id,
            "reviewer_email": admin_email,
            "reviewed_at": now
        })

        SecurityAuditRepository.log_event(
            organization_id=req["organization_id"],
            event_type="ORGANIZATION_CHANGE_REQUEST_REJECTED",
            actor_id=admin_id,
            actor_email=admin_email,
            target_id=request_id,
            target_type="CHANGE_REQUEST",
            details={
                "rejection_reason": rejection_reason.strip()
            }
        )

        return {"success": True, "message": "Organization change request rejected successfully"}

    # ======================================================
    # SUPER_ADMIN ORGANIZATION DELETION (Phase 5 Task 5.3)
    # ======================================================

    @classmethod
    def get_deletion_summary(cls, organization_id):
        org = OrganizationRepository.find_by_id(organization_id)
        if not org:
            return {"success": False, "status_code": 404, "message": "Organization not found"}

        db = current_app.mongo_db
        users_count = db["users"].count_documents({"organization_id": organization_id})
        apps_count = db["connected_applications"].count_documents({"organization_id": organization_id})
        messages_count = db["messages"].count_documents({"organization_id": organization_id})

        return {
            "success": True,
            "data": {
                "organization_id": org["organization_id"],
                "name": org["name"],
                "slug": org["slug"],
                "status": org.get("status", "ACTIVE"),
                "users_count": users_count,
                "applications_count": apps_count,
                "messages_count": messages_count
            }
        }

    @classmethod
    def delete_organization(cls, organization_id, confirm_slug, admin_id, admin_email):
        org = OrganizationRepository.find_by_id(organization_id)
        if not org:
            return {"success": False, "status_code": 404, "message": "Organization not found"}

        if not confirm_slug or str(confirm_slug).strip().lower() != org.get("slug", "").lower():
            return {
                "success": False,
                "status_code": 400,
                "message": f"Confirmation slug '{confirm_slug}' does not match organization slug '{org.get('slug')}'"
            }

        now = datetime.now(timezone.utc).isoformat()
        db = current_app.mongo_db

        # 1. Soft-delete the organization
        OrganizationRepository._collection().update_one(
            {"organization_id": organization_id},
            {"$set": {
                "status": "DELETED",
                "deleted_at": now,
                "deleted_by": admin_id,
                "updated_at": now
            }}
        )

        # 2. Cascade deactivate users
        db["users"].update_many(
            {"organization_id": organization_id},
            {"$set": {
                "is_active": False,
                "status": "INACTIVE",
                "deactivated_reason": "ORGANIZATION_DELETED",
                "updated_at": now
            }}
        )

        # 3. Cascade deactivate connected applications
        db["connected_applications"].update_many(
            {"organization_id": organization_id},
            {"$set": {
                "status": "INACTIVE",
                "deactivated_reason": "ORGANIZATION_DELETED",
                "updated_at": now
            }}
        )

        # 4. Revoke API credentials
        db["api_credentials"].update_many(
            {"organization_id": organization_id},
            {"$set": {
                "is_active": False,
                "status": "REVOKED",
                "revoked_reason": "ORGANIZATION_DELETED",
                "revoked_at": now,
                "updated_at": now
            }}
        )

        # 5. Cancel queued sends
        db["messages"].update_many(
            {"organization_id": organization_id, "status": "QUEUED"},
            {"$set": {
                "status": "CANCELLED",
                "cancellation_reason": "ORGANIZATION_DELETED",
                "updated_at": now
            }}
        )

        # 6. Audit log
        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="ORGANIZATION_DELETED",
            actor_id=admin_id,
            actor_email=admin_email,
            target_id=organization_id,
            target_type="ORGANIZATION",
            details={
                "slug": org.get("slug"),
                "name": org.get("name"),
                "mode": "SOFT_DELETE"
            }
        )

        return {
            "success": True,
            "message": f"Organization '{org.get('name')}' successfully deleted (soft-deleted)",
            "data": {
                "organization_id": organization_id,
                "slug": org.get("slug"),
                "status": "DELETED"
            }
        }


