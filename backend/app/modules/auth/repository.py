
from datetime import datetime, timezone
from flask import current_app


class AuthRepository:

    COLLECTION = "admins"

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
    def find_by_id(cls, admin_id):
        return cls._collection().find_one({
            "admin_id": admin_id
        })

    @classmethod
    def create_admin(cls, admin_data):
        admin_data = dict(admin_data)

        admin_data.setdefault("created_at", cls._now())
        admin_data.setdefault("is_active", True)

        cls._collection().insert_one(admin_data)

        return cls.find_by_id(admin_data["admin_id"])

    @classmethod
    def update_last_login(cls, admin_id):
        return cls._collection().update_one(
            {"admin_id": admin_id},
            {
                "$set": {
                    "last_login_at": cls._now()
                }
            }
        ).modified_count > 0
