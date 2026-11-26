"""
SenderX Connected Applications Repository
Data persistence layer for connected external applications in collection 'connected_applications'.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from flask import current_app

from app.modules.applications.models import ApplicationStatus, generate_application_id


class ApplicationRepository:
    """Repository managing external connected applications."""

    COLLECTION = "connected_applications"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist a new connected application."""
        now = cls._now()
        doc = dict(data)
        if not doc.get("application_id"):
            doc["application_id"] = generate_application_id()

        doc.setdefault("status", ApplicationStatus.ACTIVE)
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        doc.setdefault("last_activity_at", None)
        doc.setdefault("deactivated_at", None)
        doc.setdefault("deactivated_by", None)

        cls._collection().insert_one(doc)
        return cls.find_by_id(doc["application_id"], organization_id=doc.get("organization_id"))

    @classmethod
    def find_by_id(cls, application_id: str, organization_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Look up an application by application_id, optionally scoped to organization."""
        query: Dict[str, Any] = {"application_id": application_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        return cls._collection().find_one(query, {"_id": 0})

    @classmethod
    def find_by_name(cls, organization_id: str, name: str) -> Optional[Dict[str, Any]]:
        """Find an application by exact name within an organization."""
        return cls._collection().find_one(
            {"organization_id": organization_id, "name": name},
            {"_id": 0}
        )

    @classmethod
    def find_all(
        cls,
        organization_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List applications for an organization with pagination."""
        query: Dict[str, Any] = {
            "organization_id": organization_id,
            "deleted_at": {"$exists": False},
        }
        if status:
            query["status"] = status

        total = cls._collection().count_documents(query)
        skip = max(0, (page - 1) * limit)

        cursor = cls._collection().find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit)

        return list(cursor), total

    @classmethod
    def update(cls, application_id: str, organization_id: str, update_fields: Dict[str, Any]) -> bool:
        """Update fields on an application document."""
        if not update_fields:
            return False

        fields = dict(update_fields)
        fields["updated_at"] = cls._now()

        res = cls._collection().update_one(
            {"application_id": application_id, "organization_id": organization_id},
            {"$set": fields}
        )
        return res.matched_count > 0

    @classmethod
    def set_status(
        cls,
        application_id: str,
        organization_id: str,
        status: str,
        user_id: Optional[str] = None
    ) -> bool:
        """Update application status with audit metadata."""
        now = cls._now()
        update_doc: Dict[str, Any] = {
            "status": status,
            "updated_at": now
        }

        if status == ApplicationStatus.DEACTIVATED:
            update_doc["deactivated_at"] = now
            update_doc["deactivated_by"] = user_id
        elif status == ApplicationStatus.ACTIVE:
            update_doc["deactivated_at"] = None
            update_doc["deactivated_by"] = None

        res = cls._collection().update_one(
            {"application_id": application_id, "organization_id": organization_id},
            {"$set": update_doc}
        )
        return res.matched_count > 0

    @classmethod
    def mark_deleted(cls, application_id: str, organization_id: str, user_id: Optional[str]) -> bool:
        """Soft-delete an application while retaining audit and message history."""
        now = cls._now()
        res = cls._collection().update_one(
            {
                "application_id": application_id,
                "organization_id": organization_id,
                "deleted_at": {"$exists": False},
            },
            {"$set": {"deleted_at": now, "deleted_by": user_id, "updated_at": now}},
        )
        return res.modified_count > 0

    @classmethod
    def record_activity(cls, application_id: str, organization_id: str) -> bool:
        """Update last_activity_at timestamp for an application."""
        now = cls._now()
        res = cls._collection().update_one(
            {"application_id": application_id, "organization_id": organization_id},
            {"$set": {"last_activity_at": now}}
        )
        return res.matched_count > 0
