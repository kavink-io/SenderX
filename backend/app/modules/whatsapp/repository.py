"""
SenderX WhatsApp Multi-Tenant Database Repository
Encapsulates all MongoDB operations on the 'whatsapp_integrations' and 'platform_settings' collections.
Strictly scopes tenant queries to organization_id.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from flask import current_app
import pymongo


class WhatsAppIntegrationRepository:
    """Repository for organization-specific WhatsApp Cloud API integrations."""

    COLLECTION = "whatsapp_integrations"

    @classmethod
    def _col(cls, app=None):
        if app is not None and hasattr(app, "mongo_db"):
            return app.mongo_db[cls.COLLECTION]
        return current_app.mongo_db[cls.COLLECTION]

    @classmethod
    def create(cls, doc: Dict[str, Any], app=None) -> Dict[str, Any]:
        """Insert a new WhatsApp integration document."""
        col = cls._col(app)
        doc_to_save = dict(doc)
        if "_id" in doc_to_save:
            doc_to_save.pop("_id")
        if not doc_to_save.get("integration_id"):
            import uuid
            doc_to_save["integration_id"] = str(uuid.uuid4())
        col.insert_one(doc_to_save)
        return doc_to_save

    @classmethod
    def find_by_id(
        cls,
        integration_id: str,
        organization_id: Optional[str] = None,
        include_deleted: bool = False,
        app=None
    ) -> Optional[Dict[str, Any]]:
        """
        Find an integration by integration_id.
        If organization_id is provided, strictly enforces tenant boundary.
        """
        col = cls._col(app)
        query: Dict[str, Any] = {"integration_id": str(integration_id).strip()}

        if organization_id is not None:
            query["organization_id"] = str(organization_id).strip()

        if not include_deleted:
            query["deleted_at"] = None

        return col.find_one(query, {"_id": 0})

    @classmethod
    def find_by_phone_number_id(
        cls,
        phone_number_id: str,
        organization_id: Optional[str] = None,
        include_deleted: bool = False,
        app=None
    ) -> Optional[Dict[str, Any]]:
        """
        Find an integration by Meta Phone Number ID.
        """
        col = cls._col(app)
        query: Dict[str, Any] = {"phone_number_id": str(phone_number_id).strip()}

        if organization_id is not None:
            query["organization_id"] = str(organization_id).strip()

        if not include_deleted:
            query["deleted_at"] = None

        return col.find_one(query, {"_id": 0})

    @classmethod
    def find_all_by_organization(
        cls,
        organization_id: str,
        status: Optional[str] = None,
        include_deleted: bool = False,
        app=None
    ) -> List[Dict[str, Any]]:
        """
        List all integrations for an organization, optionally filtered by status.
        """
        col = cls._col(app)
        query: Dict[str, Any] = {"organization_id": str(organization_id).strip()}

        if not include_deleted:
            query["deleted_at"] = None

        if status is not None and str(status).upper() != "ALL":
            query["status"] = str(status).upper().strip()

        cursor = col.find(query, {"_id": 0}).sort("created_at", pymongo.DESCENDING)
        return list(cursor)

    @classmethod
    def find_active_by_organization(
        cls,
        organization_id: str,
        app=None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all currently connected/active integrations for an organization.
        """
        col = cls._col(app)
        query = {
            "organization_id": str(organization_id).strip(),
            "status": "CONNECTED",
            "deleted_at": None
        }
        cursor = col.find(query, {"_id": 0}).sort("created_at", pymongo.ASCENDING)
        return list(cursor)

    @classmethod
    def count_active_by_organization(
        cls,
        organization_id: str,
        app=None
    ) -> int:
        """Count active WhatsApp integrations for an organization."""
        col = cls._col(app)
        return col.count_documents({
            "organization_id": str(organization_id).strip(),
            "status": "CONNECTED",
            "deleted_at": None
        })

    @classmethod
    def update(
        cls,
        integration_id: str,
        organization_id: str,
        update_fields: Dict[str, Any],
        app=None
    ) -> bool:
        """
        Update fields on an existing integration strictly scoped to organization_id.
        """
        col = cls._col(app)
        query = {
            "integration_id": str(integration_id).strip(),
            "organization_id": str(organization_id).strip(),
            "deleted_at": None
        }
        update_doc = dict(update_fields)
        update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        res = col.update_one(query, {"$set": update_doc})
        return res.modified_count > 0 or res.matched_count > 0

    @classmethod
    def soft_delete(
        cls,
        integration_id: str,
        organization_id: str,
        deleted_by: Optional[str] = None,
        app=None
    ) -> bool:
        """
        Soft-delete an integration: marks status=DISCONNECTED and sets deleted_at timestamp.
        """
        col = cls._col(app)
        query = {
            "integration_id": str(integration_id).strip(),
            "organization_id": str(organization_id).strip(),
            "deleted_at": None
        }
        now_iso = datetime.now(timezone.utc).isoformat()
        update_doc = {
            "status": "DISCONNECTED",
            "deleted_at": now_iso,
            "updated_at": now_iso,
            "deleted_by": deleted_by
        }
        res = col.update_one(query, {"$set": update_doc})
        return res.modified_count > 0

    @classmethod
    def reconnect(
        cls,
        integration_id: str,
        organization_id: str,
        update_fields: Dict[str, Any],
        app=None
    ) -> bool:
        """
        Reconnect / reactivate a soft-deleted integration.
        Clears deleted_at and sets status=CONNECTED.
        """
        col = cls._col(app)
        query = {
            "integration_id": str(integration_id).strip(),
            "organization_id": str(organization_id).strip()
        }
        update_doc = dict(update_fields)
        update_doc["deleted_at"] = None
        update_doc["status"] = "CONNECTED"
        update_doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        res = col.update_one(query, {"$set": update_doc})
        return res.modified_count > 0 or res.matched_count > 0

    @classmethod
    def hard_delete(
        cls,
        integration_id: str,
        organization_id: Optional[str] = None,
        app=None
    ) -> bool:
        """Permanently delete an integration (for test isolation only)."""
        col = cls._col(app)
        query: Dict[str, Any] = {"integration_id": str(integration_id).strip()}
        if organization_id is not None:
            query["organization_id"] = str(organization_id).strip()
        res = col.delete_one(query)
        return res.deleted_count > 0


class PlatformSettingsRepository:
    """Repository for centralized encrypted platform settings (Meta App credentials, Webhooks)."""

    COLLECTION = "platform_settings"

    @classmethod
    def _col(cls, app=None):
        if app is not None and hasattr(app, "mongo_db"):
            return app.mongo_db[cls.COLLECTION]
        return current_app.mongo_db[cls.COLLECTION]

    @classmethod
    def get_setting(cls, key: str = "meta_whatsapp", app=None) -> Optional[Dict[str, Any]]:
        """Retrieve a platform setting document by key."""
        col = cls._col(app)
        return col.find_one({"setting_key": key}, {"_id": 0})

    @classmethod
    def save_setting(cls, key: str, data: Dict[str, Any], app=None) -> Dict[str, Any]:
        """Upsert a platform setting document."""
        col = cls._col(app)
        doc = dict(data)
        doc["setting_key"] = key
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        col.update_one(
            {"setting_key": key},
            {"$set": doc},
            upsert=True
        )
        return doc
