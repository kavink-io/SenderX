"""
SenderX Template Repository
MongoDB data access for email templates and historical template versions.
Enforces multi-tenant isolation.
"""

from typing import Any, Dict, List, Optional
from flask import current_app
import re


class TemplateRepository:

    COLLECTION = "templates"
    VERSIONS_COLLECTION = "template_versions"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @classmethod
    def _versions_collection(cls):
        return current_app.mongo_db[cls.VERSIONS_COLLECTION]

    @classmethod
    def create(cls, template: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new template document."""
        cls._collection().insert_one(template)
        return cls.find_by_id(template["template_id"], organization_id=template.get("organization_id"))

    @classmethod
    def find_by_id(cls, template_id: str, organization_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve a template by ID, enforcing organization scope when specified."""
        query = {"template_id": template_id}
        if organization_id is not None:
            query["organization_id"] = organization_id
        return cls._collection().find_one(query, {"_id": 0})

    @classmethod
    def find_by_name(cls, name: str, organization_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve a template by exact name within the organization."""
        query = {"name": name}
        if organization_id is not None:
            query["organization_id"] = organization_id
        return cls._collection().find_one(query, {"_id": 0})

    @classmethod
    def find_all(
        cls,
        organization_id: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """List templates with pagination and search filters."""
        query: Dict[str, Any] = {}
        if organization_id is not None:
            query["organization_id"] = organization_id

        if status:
            query["status"] = status.upper().strip()

        if category:
            query["category"] = category.lower().strip()

        if search:
            escaped_search = re.escape(search.strip())
            query["$or"] = [
                {"name": {"$regex": escaped_search, "$options": "i"}},
                {"subject": {"$regex": escaped_search, "$options": "i"}},
                {"description": {"$regex": escaped_search, "$options": "i"}}
            ]

        total = cls._collection().count_documents(query)
        skip = (page - 1) * limit

        cursor = cls._collection().find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit)

        items = list(cursor)

        return {
            "items": items,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit if limit > 0 else 0
            }
        }

    @classmethod
    def update(cls, template_id: str, update_fields: Dict[str, Any], organization_id: Optional[str] = None) -> bool:
        """Update template fields."""
        query = {"template_id": template_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        res = cls._collection().update_one(query, {"$set": update_fields})
        return res.modified_count > 0

    @classmethod
    def delete(cls, template_id: str, organization_id: Optional[str] = None) -> bool:
        """Permanently delete a template."""
        query = {"template_id": template_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        res = cls._collection().delete_one(query)
        if res.deleted_count > 0:
            # Also clean up historical version records for this template
            cls._versions_collection().delete_many(query)
            return True
        return False

    # --------------------------------------------------
    # VERSION HISTORY
    # --------------------------------------------------

    @classmethod
    def save_version(cls, version_snapshot: Dict[str, Any]) -> bool:
        """Persist a frozen historical snapshot of a template version."""
        cls._versions_collection().update_one(
            {
                "template_id": version_snapshot["template_id"],
                "version": version_snapshot["version"]
            },
            {"$set": version_snapshot},
            upsert=True
        )
        return True

    @classmethod
    def find_versions(cls, template_id: str, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List historical versions for a template."""
        query = {"template_id": template_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        cursor = cls._versions_collection().find(query, {"_id": 0}).sort("version", -1)
        return list(cursor)

    @classmethod
    def find_version(cls, template_id: str, version: int, organization_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve a specific historical version of a template."""
        query = {"template_id": template_id, "version": int(version)}
        if organization_id is not None:
            query["organization_id"] = organization_id

        return cls._versions_collection().find_one(query, {"_id": 0})
