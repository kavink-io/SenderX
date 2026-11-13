"""
SenderX Connected Applications Service
Business logic for connected application lifecycle, validation, metrics, and cascade deactivation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from flask import current_app

from app.modules.applications.models import (
    ApplicationEnvironment,
    ApplicationStatus,
    validate_application_input,
)
from app.modules.applications.repository import ApplicationRepository
from app.modules.organizations.repository import OrganizationRepository


class ApplicationService:
    """Service managing external connected application lifecycle and cascades."""

    @classmethod
    def register_application(
        cls,
        organization_id: str,
        name: str,
        description: Optional[str] = None,
        environment: str = ApplicationEnvironment.ALL,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a new external application bound to an organization."""
        if not organization_id:
            return {"success": False, "status_code": 400, "message": "organization_id is required"}

        org = OrganizationRepository.find_by_id(organization_id)
        if not org or org.get("status") != "ACTIVE":
            return {"success": False, "status_code": 403, "message": "Organization is inactive or not found"}

        is_valid, err, sanitized = validate_application_input({
            "name": name,
            "description": description,
            "environment": environment
        })
        if not is_valid:
            return {"success": False, "status_code": 400, "message": err}

        # Check name uniqueness per organization
        existing = ApplicationRepository.find_by_name(organization_id, sanitized["name"])
        if existing:
            return {
                "success": False,
                "status_code": 409,
                "message": f"An application named '{sanitized['name']}' already exists in this organization"
            }

        app_doc = {
            "organization_id": organization_id,
            "name": sanitized["name"],
            "description": sanitized.get("description", ""),
            "environment": sanitized["environment"],
            "status": ApplicationStatus.ACTIVE,
            "created_by": created_by
        }

        created = ApplicationRepository.create(app_doc)
        return {
            "success": True,
            "status_code": 201,
            "message": "Connected application registered successfully",
            "data": created
        }

    @classmethod
    def get_application(cls, application_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
        """Fetch application strictly scoped to organization."""
        return ApplicationRepository.find_by_id(application_id, organization_id=organization_id)

    @classmethod
    def list_applications(
        cls,
        organization_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """List applications for an organization with pagination."""
        items, total = ApplicationRepository.find_all(
            organization_id=organization_id,
            status=status,
            limit=limit,
            page=page
        )
        return {
            "success": True,
            "data": items,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit
            }
        }

    @classmethod
    def update_application(
        cls,
        application_id: str,
        organization_id: str,
        data: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update application metadata (name, description, environment)."""
        app = ApplicationRepository.find_by_id(application_id, organization_id=organization_id)
        if not app:
            return {"success": False, "status_code": 404, "message": "Application not found"}

        if app.get("status") == ApplicationStatus.DEACTIVATED:
            return {"success": False, "status_code": 400, "message": "Cannot update a deactivated application"}

        is_valid, err, sanitized = validate_application_input(data, is_update=True)
        if not is_valid:
            return {"success": False, "status_code": 400, "message": err}

        if not sanitized:
            return {"success": False, "status_code": 400, "message": "No valid fields provided to update"}

        # If name is being changed, check uniqueness
        new_name = sanitized.get("name")
        if new_name and new_name != app.get("name"):
            existing = ApplicationRepository.find_by_name(organization_id, new_name)
            if existing and existing.get("application_id") != application_id:
                return {
                    "success": False,
                    "status_code": 409,
                    "message": f"An application named '{new_name}' already exists in this organization"
                }

        updated = ApplicationRepository.update(application_id, organization_id, sanitized)
        if not updated:
            return {"success": False, "status_code": 400, "message": "Failed to update application"}

        refreshed = ApplicationRepository.find_by_id(application_id, organization_id=organization_id)
        return {
            "success": True,
            "status_code": 200,
            "message": "Application updated successfully",
            "data": refreshed
        }

    @classmethod
    def deactivate_application(
        cls,
        application_id: str,
        organization_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deactivate an application and cascade deactivation/revocation to all its active API credentials.
        """
        app = ApplicationRepository.find_by_id(application_id, organization_id=organization_id)
        if not app:
            return {"success": False, "status_code": 404, "message": "Application not found"}

        if app.get("status") == ApplicationStatus.DEACTIVATED:
            return {"success": True, "status_code": 200, "message": "Application is already deactivated"}

        # Set status to DEACTIVATED
        ApplicationRepository.set_status(
            application_id=application_id,
            organization_id=organization_id,
            status=ApplicationStatus.DEACTIVATED,
            user_id=user_id
        )

        # Cascade revocation to all active API credentials for this application
        now = datetime.now(timezone.utc).isoformat()
        db = current_app.mongo_db
        cred_res = db["api_credentials"].update_many(
            {
                "organization_id": organization_id,
                "application_id": application_id,
                "status": "ACTIVE"
            },
            {
                "$set": {
                    "status": "REVOKED",
                    "revoked_at": now,
                    "revoked_by": user_id,
                    "revocation_reason": "Application deactivated",
                    "updated_at": now
                }
            }
        )

        return {
            "success": True,
            "status_code": 200,
            "message": f"Application deactivated successfully. {cred_res.modified_count} API credential(s) revoked.",
            "revoked_credentials_count": cred_res.modified_count
        }

    @classmethod
    def activate_application(
        cls,
        application_id: str,
        organization_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reactivate a previously deactivated or inactive application."""
        app = ApplicationRepository.find_by_id(application_id, organization_id=organization_id)
        if not app:
            return {"success": False, "status_code": 404, "message": "Application not found"}

        if app.get("status") == ApplicationStatus.ACTIVE:
            return {"success": True, "status_code": 200, "message": "Application is already active"}

        ApplicationRepository.set_status(
            application_id=application_id,
            organization_id=organization_id,
            status=ApplicationStatus.ACTIVE,
            user_id=user_id
        )

        return {
            "success": True,
            "status_code": 200,
            "message": "Application activated successfully. Note that previously revoked credentials remain revoked."
        }

    @classmethod
    def get_application_stats(cls, application_id: str, organization_id: str) -> Dict[str, Any]:
        """Aggregate usage metrics and counts for an application."""
        app = ApplicationRepository.find_by_id(application_id, organization_id=organization_id)
        if not app:
            return {"success": False, "status_code": 404, "message": "Application not found"}

        db = current_app.mongo_db
        total_creds = db["api_credentials"].count_documents({
            "organization_id": organization_id,
            "application_id": application_id
        })
        active_creds = db["api_credentials"].count_documents({
            "organization_id": organization_id,
            "application_id": application_id,
            "status": "ACTIVE"
        })
        payload_count = db["ingested_payloads"].count_documents({
            "organization_id": organization_id,
            "application_id": application_id
        })
        dlq_count = db["dead_letters"].count_documents({
            "organization_id": organization_id,
            "application_id": application_id
        })

        return {
            "success": True,
            "status_code": 200,
            "data": {
                "application_id": application_id,
                "name": app.get("name"),
                "status": app.get("status"),
                "environment": app.get("environment"),
                "total_credentials": total_creds,
                "active_credentials": active_creds,
                "ingested_payloads_count": payload_count,
                "dead_letters_count": dlq_count,
                "last_activity_at": app.get("last_activity_at"),
                "created_at": app.get("created_at")
            }
        }
