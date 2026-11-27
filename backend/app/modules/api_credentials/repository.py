"""
SenderX API Credentials Repository
Persistence layer for hashed and encrypted external application API credentials.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from flask import current_app


class ApiCredentialRepository:
    """Repository managing external API credentials in collection 'api_credentials'."""

    COLLECTION = "api_credentials"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist a new API credential without plaintext key material."""
        now = cls._now()
        doc = dict(data)
        doc.setdefault("credential_id", str(uuid.uuid4()))
        doc.setdefault("status", "ACTIVE")
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        doc.setdefault("last_used_at", None)
        doc.setdefault("scopes", ["payloads:ingest", "messages:create"])

        cls._collection().insert_one(doc)
        return cls.find_by_id(doc["credential_id"], organization_id=doc.get("organization_id"))

    @classmethod
    def find_by_hash(cls, key_hash: str) -> Optional[Dict[str, Any]]:
        """Look up credential by SHA-256 key hash."""
        return cls._collection().find_one({"key_hash": key_hash}, {"_id": 0})

    @classmethod
    def find_by_id(cls, credential_id: str, organization_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find credential by ID strictly scoped to organization when provided."""
        query: Dict[str, Any] = {"credential_id": credential_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        return cls._collection().find_one(query, {"_id": 0})

    @classmethod
    def find_all(
        cls,
        organization_id: str,
        application_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all credentials for an organization (excluding internal _id and hash)."""
        query: Dict[str, Any] = {"organization_id": organization_id}
        if application_id:
            query["application_id"] = application_id
        if status:
            query["status"] = status

        cursor = cls._collection().find(
            query,
            {
                "_id": 0,
                "key_hash": 0,
                "key_encrypted": 0,
                "api_key": 0,
                "raw_key": 0,
                "secret_key": 0,
            }
        ).sort("created_at", -1)
        return list(cursor)

    @classmethod
    def update(
        cls,
        credential_id: str,
        organization_id: str,
        update_fields: Dict[str, Any]
    ) -> bool:
        """Update credential metadata or encrypted key material within its organization."""
        if not update_fields:
            return False

        fields = dict(update_fields)
        fields["updated_at"] = cls._now()
        result = cls._collection().update_one(
            {"credential_id": credential_id, "organization_id": organization_id},
            {"$set": fields}
        )
        return result.matched_count > 0

    @classmethod
    def delete(cls, credential_id: str, organization_id: str) -> bool:
        """Permanently remove a credential scoped to its organization."""
        result = cls._collection().delete_one({
            "credential_id": credential_id,
            "organization_id": organization_id,
        })
        return result.deleted_count > 0

    @classmethod
    def update_last_used(cls, credential_id: str, organization_id: str, application_id: str) -> bool:
        """Atomically record credential usage timestamp."""
        res = cls._collection().update_one(
            {
                "credential_id": credential_id,
                "organization_id": organization_id,
                "application_id": application_id,
            },
            {"$set": {"last_used_at": cls._now()}}
        )
        return res.modified_count > 0

    @classmethod
    def revoke(cls, credential_id: str, organization_id: str, revoked_by: Optional[str] = None) -> bool:
        """Revoke an active API credential."""
        now = cls._now()
        res = cls._collection().update_one(
            {
                "credential_id": credential_id,
                "organization_id": organization_id,
                "status": "ACTIVE"
            },
            {
                "$set": {
                    "status": "REVOKED",
                    "revoked_at": now,
                    "revoked_by": revoked_by,
                    "updated_at": now
                }
            }
        )
        return res.modified_count > 0
