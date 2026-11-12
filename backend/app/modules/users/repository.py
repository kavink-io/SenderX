
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
    def find_by_email(cls, email):
        return cls._collection().find_one({
            "email": email.lower().strip()
        })

    @classmethod
    def find_by_id(cls, user_id):
        return cls._collection().find_one({
            "user_id": user_id
        })

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
