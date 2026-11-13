"""
SenderX Media Repository
MongoDB data access layer for media metadata documents.
Enforces multi-tenant isolation, pagination, search filtering, and lifecycle management.
"""

from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Optional
from flask import current_app


class MediaRepository:

    COLLECTION = "media"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @classmethod
    def create(cls, media_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new media metadata record."""
        cls._collection().insert_one(media_data)
        return cls.find_by_id(media_data["media_id"], organization_id=media_data.get("organization_id"))

    @classmethod
    def find_by_id(cls, media_id: str, organization_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve media by ID, strictly enforcing organization scoping when supplied."""
        query: Dict[str, Any] = {"media_id": media_id}
        if organization_id is not None:
            query["organization_id"] = organization_id
        return cls._collection().find_one(query, {"_id": 0})

    @classmethod
    def find_by_ids(cls, media_ids: List[str], organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve multiple media records by their IDs."""
        if not media_ids:
            return []
        query: Dict[str, Any] = {"media_id": {"$in": media_ids}}
        if organization_id is not None:
            query["organization_id"] = organization_id
        cursor = cls._collection().find(query, {"_id": 0})
        return list(cursor)

    @classmethod
    def find_all(
        cls,
        organization_id: str,
        page: int = 1,
        limit: int = 50,
        mime_type: Optional[str] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Paginated search for organization media."""
        query: Dict[str, Any] = {"organization_id": organization_id}

        if status:
            query["status"] = status
        else:
            # Default to active media
            query["status"] = {"$ne": "DELETED"}

        if mime_type:
            query["mime_type"] = mime_type

        if channel:
            query[f"channel_compatibility.{channel}"] = True

        if search:
            escaped = re.escape(search.strip())
            query["$or"] = [
                {"filename": {"$regex": escaped, "$options": "i"}},
                {"original_filename": {"$regex": escaped, "$options": "i"}},
                {"purpose": {"$regex": escaped, "$options": "i"}}
            ]

        total = cls._collection().count_documents(query)
        total_pages = max(1, math.ceil(total / limit)) if total > 0 else 1
        skip = (page - 1) * limit

        cursor = cls._collection().find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit)

        return {
            "data": list(cursor),
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": total_pages
            }
        }

    @classmethod
    def update(cls, media_id: str, update_data: Dict[str, Any], organization_id: Optional[str] = None) -> bool:
        """Update media metadata fields."""
        query: Dict[str, Any] = {"media_id": media_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(query, {"$set": update_data})
        return result.modified_count > 0 or result.matched_count > 0

    @classmethod
    def soft_delete(cls, media_id: str, organization_id: Optional[str] = None) -> bool:
        """Mark media as DELETED with timestamp."""
        query: Dict[str, Any] = {"media_id": media_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "status": "DELETED",
                    "deleted_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        return result.modified_count > 0

    @classmethod
    def hard_delete(cls, media_id: str, organization_id: Optional[str] = None) -> bool:
        """Permanently delete media record from database."""
        query: Dict[str, Any] = {"media_id": media_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().delete_one(query)
        return result.deleted_count > 0

    @classmethod
    def increment_usage(cls, media_id: str, organization_id: Optional[str] = None) -> bool:
        """Increment media reuse count."""
        query: Dict[str, Any] = {"media_id": media_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$inc": {"usage_count": 1},
                "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        return result.modified_count > 0

    @classmethod
    def find_expired(cls, cutoff_iso: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Find active media whose expires_at timestamp has passed."""
        query = {
            "status": "ACTIVE",
            "expires_at": {"$lte": cutoff_iso, "$ne": None}
        }
        cursor = cls._collection().find(query, {"_id": 0}).limit(limit)
        return list(cursor)

    @classmethod
    def find_all_storage_keys(cls, organization_id: Optional[str] = None) -> Set[str]:
        """Find all active storage keys in the database for orphan reconciliation."""
        query: Dict[str, Any] = {"status": {"$ne": "DELETED"}}
        if organization_id is not None:
            query["organization_id"] = organization_id
        cursor = cls._collection().find(query, {"_id": 0, "storage_key": 1})
        return {doc["storage_key"] for doc in cursor if doc.get("storage_key")}
