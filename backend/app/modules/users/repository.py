
from datetime import datetime, timezone
from flask import current_app


class UserRepository:

    COLLECTION = "users"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def find_by_email(cls, email, organization_id=None):
        query = {"email": email.lower().strip()}
        if organization_id is not None:
            query["organization_id"] = organization_id
        return cls._collection().find_one(query)

    @classmethod
    def find_by_id(cls, user_id, organization_id=None):
        query = {"user_id": user_id}
        if organization_id is not None:
            query["organization_id"] = organization_id
        return cls._collection().find_one(query)

    @classmethod
    def find_all_by_organization(cls, organization_id, limit=50, page=1):
        try:
            limit = max(1, min(int(limit), 100))
        except (ValueError, TypeError):
            limit = 50

        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1

        query = {"organization_id": organization_id}
        total = cls._collection().count_documents(query)

        items = list(
            cls._collection().find(
                query,
                {"_id": 0, "password_hash": 0}
            ).sort(
                "created_at", -1
            ).skip((page - 1) * limit).limit(limit)
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

    @classmethod
    def update_user(cls, user_id, organization_id, update_fields):
        query = {
            "user_id": user_id,
            "organization_id": organization_id
        }
        update_fields = dict(update_fields)
        update_fields["updated_at"] = cls._now()

        result = cls._collection().update_one(
            query,
            {"$set": update_fields}
        )
        return result.modified_count > 0

    @classmethod
    def create(cls, user_data, session=None):
        user_data = dict(user_data)

        user_data.setdefault("created_at", cls._now())
        user_data.setdefault("is_active", True)

        cls._collection().insert_one(
            user_data,
            session=session
        )

        return user_data
