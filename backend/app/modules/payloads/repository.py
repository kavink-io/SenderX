"""
SenderX Ingested Payloads & Audit Trail Repository
MongoDB persistence layer for immutable original payloads, versioned edits, and audit logs.
"""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from flask import current_app

from app.modules.payloads.encryption import PayloadEncryption


class PayloadRepository:
    """
    Persistence layer for ingested JSON payloads and audit logs.
    Guarantees immutable preservation of original payloads and multi-tenant isolation.
    """

    PAYLOADS_COLLECTION = "ingested_payloads"
    AUDIT_COLLECTION = "payload_audit_logs"

    @classmethod
    def _payloads_col(cls):
        return current_app.mongo_db[cls.PAYLOADS_COLLECTION]

    @classmethod
    def _audit_col(cls):
        return current_app.mongo_db[cls.AUDIT_COLLECTION]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _decrypt_payload_doc(cls, doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Decrypt original_payload, current_payload, and version payloads transparently."""
        if not doc:
            return None
        doc = dict(doc)
        if "original_payload" in doc:
            doc["original_payload"] = PayloadEncryption.decrypt_dict(doc["original_payload"])
        if "current_payload" in doc:
            doc["current_payload"] = PayloadEncryption.decrypt_dict(doc["current_payload"])
        if "versions" in doc and isinstance(doc["versions"], list):
            decrypted_versions = []
            for v in doc["versions"]:
                v_copy = dict(v)
                if "payload" in v_copy:
                    v_copy["payload"] = PayloadEncryption.decrypt_dict(v_copy["payload"])
                decrypted_versions.append(v_copy)
            doc["versions"] = decrypted_versions
        return doc

    # -----------------------------------------------------------------------
    # 1. PAYLOAD CREATION (IMMUTABLE ORIGINAL)
    # -----------------------------------------------------------------------

    @classmethod
    def create(cls, payload_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persist a new incoming JSON request.
        Preserves original_payload immutably and initializes version 1.
        Encrypts sensitive payload data at rest using authenticated encryption.
        """
        now = cls._now()
        doc = dict(payload_data)
        doc.setdefault("payload_id", str(uuid.uuid4()))
        doc.setdefault("received_at", now)
        doc.setdefault("updated_at", now)
        doc.setdefault("version", 1)

        # Store immutable original and initial current copy
        original = deepcopy(doc.get("original_payload") or {})
        current = deepcopy(doc.get("current_payload") or original)

        if "versions" not in doc:
            doc["versions"] = [
                {
                    "version": 1,
                    "payload": PayloadEncryption.encrypt_dict(deepcopy(original)),
                    "created_at": now,
                    "created_by": doc.get("created_by") or "SYSTEM",
                    "reason": "Original request ingestion",
                    "validation_status": doc.get("validation_status", "VALID"),
                    "validation_errors": doc.get("validation_errors", [])
                }
            ]
        else:
            encrypted_versions = []
            for v in doc["versions"]:
                v_copy = dict(v)
                if "payload" in v_copy and not (isinstance(v_copy["payload"], dict) and v_copy["payload"].get("_encrypted")):
                    v_copy["payload"] = PayloadEncryption.encrypt_dict(v_copy["payload"])
                encrypted_versions.append(v_copy)
            doc["versions"] = encrypted_versions

        if not (isinstance(original, dict) and original.get("_encrypted")):
            doc["original_payload"] = PayloadEncryption.encrypt_dict(original)
        if not (isinstance(current, dict) and current.get("_encrypted")):
            doc["current_payload"] = PayloadEncryption.encrypt_dict(current)

        cls._payloads_col().insert_one(doc)

        # Remove internal Mongo ObjectId before returning
        return cls.find_by_id(doc["payload_id"], organization_id=doc.get("organization_id"))

    # -----------------------------------------------------------------------
    # 2. RETRIEVAL (TENANT-SCOPED)
    # -----------------------------------------------------------------------

    @classmethod
    def find_by_id(cls, payload_id: str, organization_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve payload by ID strictly scoped to organization_id when provided, decrypting at rest."""
        query: Dict[str, Any] = {"payload_id": payload_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        doc = cls._payloads_col().find_one(query, {"_id": 0})
        return cls._decrypt_payload_doc(doc)

    @classmethod
    def find_all(
        cls,
        organization_id: str,
        limit: int = 50,
        page: int = 1,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        validation_status: Optional[str] = None,
        application_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Paginated list of received JSON requests scoped to an organization."""
        query: Dict[str, Any] = {"organization_id": organization_id}

        if status:
            query["status"] = status
        if channel:
            query["channel"] = channel.lower().strip()
        if validation_status:
            query["validation_status"] = validation_status
        if application_id:
            query["application_id"] = application_id

        if start_date or end_date:
            date_filter: Dict[str, Any] = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            query["received_at"] = date_filter

        try:
            limit = max(1, min(int(limit), 100))
        except (ValueError, TypeError):
            limit = 50

        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1

        skip = (page - 1) * limit
        col = cls._payloads_col()
        total = col.count_documents(query)

        cursor = col.find(query, {"_id": 0}).sort("received_at", -1).skip(skip).limit(limit)
        items = [cls._decrypt_payload_doc(item) for item in cursor]

        pages = (total + limit - 1) // limit if total > 0 else 1

        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": pages,
                "has_next": page < pages,
                "has_prev": page > 1
            }
        }

    # -----------------------------------------------------------------------
    # 3. VERSIONED EDITING (PRESERVES ORIGINAL)
    # -----------------------------------------------------------------------

    @classmethod
    def add_version(
        cls,
        payload_id: str,
        organization_id: str,
        new_payload: Dict[str, Any],
        edited_by: str,
        reason: str,
        validation_status: str,
        validation_errors: Optional[List[str]] = None,
        new_channel: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new version snapshot while keeping original_payload intact.
        Atomically increments version and appends to version history.
        Encrypts new payload at rest.
        """
        existing = cls.find_by_id(payload_id, organization_id=organization_id)
        if not existing:
            return None

        current_ver = int(existing.get("version", 1))
        next_ver = current_ver + 1
        now = cls._now()

        encrypted_payload = PayloadEncryption.encrypt_dict(deepcopy(new_payload))

        version_entry = {
            "version": next_ver,
            "payload": encrypted_payload,
            "created_at": now,
            "created_by": edited_by,
            "reason": reason or f"Version {next_ver} update",
            "validation_status": validation_status,
            "validation_errors": validation_errors or []
        }

        update_fields: Dict[str, Any] = {
            "current_payload": encrypted_payload,
            "version": next_ver,
            "status": "EDITED",
            "validation_status": validation_status,
            "validation_errors": validation_errors or [],
            "updated_at": now
        }

        if new_channel:
            update_fields["channel"] = new_channel

        res = cls._payloads_col().update_one(
            {
                "payload_id": payload_id,
                "organization_id": organization_id
            },
            {
                "$set": update_fields,
                "$push": {"versions": version_entry}
            }
        )

        if res.matched_count == 0:
            return None

        return cls.find_by_id(payload_id, organization_id=organization_id)

    # -----------------------------------------------------------------------
    # 4. STATUS & DISPATCH UPDATES (IDEMPOTENCY GUARDS)
    # -----------------------------------------------------------------------

    @classmethod
    def update_status(
        cls,
        payload_id: str,
        new_status: str,
        organization_id: Optional[str] = None,
        message_id: Optional[str] = None,
        dlq_id: Optional[str] = None,
        failure_code: Optional[str] = None,
        failure_reason: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update payload lifecycle status."""
        query: Dict[str, Any] = {"payload_id": payload_id}
        if organization_id:
            query["organization_id"] = organization_id

        update: Dict[str, Any] = {
            "status": new_status,
            "updated_at": cls._now()
        }

        if message_id:
            update["message_id"] = message_id
        if dlq_id:
            update["dlq_id"] = dlq_id
        if failure_code is not None:
            update["failure_code"] = failure_code
        if failure_reason is not None:
            update["failure_reason"] = failure_reason
        if extra_fields:
            update.update(extra_fields)

        res = cls._payloads_col().update_one(query, {"$set": update})
        return res.matched_count > 0

    @classmethod
    def transition_to_dispatching_atomically(
        cls,
        payload_id: str,
        organization_id: str
    ) -> bool:
        """
        Atomic transition to DISPATCHING preventing concurrent or duplicate retries.
        Only succeeds if status is in eligible retry states (IN_DLQ, EDITED, FAILED).
        """
        res = cls._payloads_col().update_one(
            {
                "payload_id": payload_id,
                "organization_id": organization_id,
                "status": {"$in": ["IN_DLQ", "EDITED", "FAILED"]}
            },
            {
                "$set": {
                    "status": "DISPATCHING",
                    "updated_at": cls._now(),
                    "last_retried_at": cls._now()
                }
            }
        )
        return res.modified_count > 0

    # -----------------------------------------------------------------------
    # 5. AUDIT TRAIL LOGGING
    # -----------------------------------------------------------------------

    @classmethod
    def log_audit(
        cls,
        payload_id: str,
        organization_id: str,
        event_type: str,
        details: Dict[str, Any],
        performed_by: str = "SYSTEM",
        version: Optional[int] = None
    ) -> Dict[str, Any]:
        """Record an immutable audit log entry for this payload."""
        import json
        try:
            safe_details = json.loads(json.dumps(details, default=str))
        except Exception:
            safe_details = {k: str(v) for k, v in details.items()} if isinstance(details, dict) else {}

        entry = {
            "audit_id": str(uuid.uuid4()),
            "payload_id": payload_id,
            "organization_id": organization_id,
            "event_type": event_type,
            "version": version,
            "details": safe_details,
            "performed_by": performed_by,
            "timestamp": cls._now()
        }
        cls._audit_col().insert_one(entry)
        entry.pop("_id", None)
        return entry

    @classmethod
    def get_audit_logs(
        cls,
        payload_id: str,
        organization_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve audit log entries for a payload in chronological order."""
        query: Dict[str, Any] = {"payload_id": payload_id}
        if organization_id:
            query["organization_id"] = organization_id

        cursor = cls._audit_col().find(query, {"_id": 0}).sort("timestamp", 1).limit(limit)
        return list(cursor)
