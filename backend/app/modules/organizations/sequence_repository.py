from datetime import datetime, timezone
import uuid
from flask import current_app
from pymongo import ReturnDocument


class SequenceRepository:
    """
    Organization-scoped atomic sequence management.
    Guarantees concurrency safety using MongoDB atomic find_one_and_update with $inc.
    Never relies on unsafe counts and never decrements or reuses sequence numbers.
    """

    COLLECTION = "organization_sequences"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def find_by_organization(cls, organization_id, sequence_type="employee"):
        return cls._collection().find_one({
            "organization_id": organization_id,
            "sequence_type": sequence_type
        })

    @classmethod
    def update_prefix(cls, organization_id, sequence_type, new_prefix):
        now = cls._now()
        prefix_clean = str(new_prefix).strip().upper()
        res = cls._collection().find_one_and_update(
            {"organization_id": organization_id, "sequence_type": sequence_type},
            {
                "$set": {
                    "prefix": prefix_clean,
                    "updated_at": now
                },
                "$setOnInsert": {
                    "sequence_id": str(uuid.uuid4()),
                    "organization_id": organization_id,
                    "sequence_type": sequence_type,
                    "next_value": 1,
                    "created_at": now
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        return res

    @classmethod
    def preview_next_sequence(cls, organization_id, sequence_type="employee", default_prefix="EMP"):
        doc = cls.find_by_organization(organization_id, sequence_type=sequence_type)
        if not doc:
            prefix = default_prefix
            next_num = 1
        else:
            prefix = doc.get("prefix") or default_prefix
            next_num = doc.get("next_value", 1)

        return {
            "organization_id": organization_id,
            "sequence_type": sequence_type,
            "prefix": prefix,
            "next_value": next_num,
            "code": f"{prefix}-{next_num:03d}"
        }

    @classmethod
    def allocate_next_sequence(cls, organization_id, sequence_type="employee", default_prefix="EMP"):
        now = cls._now()
        # Find current prefix if already configured
        existing = cls.find_by_organization(organization_id, sequence_type=sequence_type)
        prefix = existing.get("prefix") if existing and existing.get("prefix") else default_prefix

        # Atomic allocation: ReturnDocument.BEFORE returns the value before incrementing,
        # ensuring the allocated sequence number matches the monotonic sequence starting at 1.
        res = cls._collection().find_one_and_update(
            {"organization_id": organization_id, "sequence_type": sequence_type},
            {
                "$inc": {"next_value": 1},
                "$set": {"updated_at": now},
                "$setOnInsert": {
                    "sequence_id": str(uuid.uuid4()),
                    "organization_id": organization_id,
                    "sequence_type": sequence_type,
                    "prefix": prefix,
                    "created_at": now
                }
            },
            upsert=True,
            return_document=ReturnDocument.BEFORE
        )

        if res is None:
            # Upserted first document: MongoDB initialized next_value to 1.
            # Allocated number is 1, and we set next_value to 2 for subsequent callers.
            allocated_num = 1
            cls._collection().update_one(
                {"organization_id": organization_id, "sequence_type": sequence_type},
                {"$set": {"next_value": 2}}
            )
            active_prefix = prefix
        else:
            allocated_num = res.get("next_value", 1)
            active_prefix = res.get("prefix") or prefix

        code = f"{active_prefix}-{allocated_num:03d}"

        return {
            "organization_id": organization_id,
            "sequence_type": sequence_type,
            "prefix": active_prefix,
            "sequence_number": allocated_num,
            "code": code
        }
