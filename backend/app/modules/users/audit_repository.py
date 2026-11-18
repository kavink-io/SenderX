"""
SenderX Security & Role Audit Repository
Records immutable audit logs for employee management, role lifecycle, and permission assignments.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from flask import current_app


class SecurityAuditRepository:
    """Persistence repository for security and role audit events."""

    COLLECTION = "security_audit_logs"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def log_event(
        cls,
        organization_id: str,
        event_type: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        target_id: Optional[str] = None,
        target_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an immutable security audit entry."""
        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        entry = {
            "audit_id": audit_id,
            "organization_id": organization_id,
            "event_type": event_type,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "target_id": target_id,
            "target_type": target_type,
            "details": details or {},
            "ip_address": ip_address,
            "timestamp": cls._now()
        }
        cls._collection().insert_one(entry)
        entry.pop("_id", None)
        return entry

    @classmethod
    def find_by_organization(
        cls,
        organization_id: str,
        target_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> Dict[str, Any]:
        """Query security audit logs for an organization with pagination."""
        try:
            limit = max(1, min(int(limit), 100))
        except (ValueError, TypeError):
            limit = 50

        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1

        query: Dict[str, Any] = {"organization_id": organization_id}
        if target_id:
            query["target_id"] = target_id
        if event_type:
            query["event_type"] = event_type

        total = cls._collection().count_documents(query)
        items = list(
            cls._collection()
            .find(query, {"_id": 0})
            .sort("timestamp", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        return {
            "items": items,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit if total > 0 else 0
            }
        }
