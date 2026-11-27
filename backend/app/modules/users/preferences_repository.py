from datetime import datetime, timezone
from flask import current_app


class UserPreferencesRepository:
    """Data access layer for user-scoped appearance and layout preferences."""

    COLLECTION = "user_preferences"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def find_by_user(cls, user_id, organization_id=None):
        query = {
            "user_id": user_id,
            "organization_id": organization_id,
        }
        return cls._collection().find_one(query, {"_id": 0})

    @classmethod
    def upsert_for_user(cls, user_id, organization_id, appearance, layout):
        now = cls._now()
        query = {
            "user_id": user_id,
            "organization_id": organization_id,
        }
        doc = {
            "user_id": user_id,
            "organization_id": organization_id,
            "appearance": dict(appearance),
            "layout": dict(layout),
            "updated_at": now,
        }
        cls._collection().update_one(
            query,
            {
                "$set": doc,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return cls.find_by_user(user_id, organization_id)
