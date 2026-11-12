
from datetime import datetime, timezone
from flask import current_app


class RoleRepository:

    COLLECTION = "roles"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, role_data, session=None):
        role_data = dict(role_data)
        role_data.setdefault("created_at", cls._now())

        cls._collection().insert_one(
            role_data,
            session=session
        )

        return role_data

    @classmethod
    def find_by_id(cls, role_id, organization_id=None):
        query = {"role_id": role_id}

        if organization_id:
            query["organization_id"] = organization_id

        return cls._collection().find_one(query)

    @classmethod
    def find_by_organization(cls, organization_id):
        return list(
            cls._collection().find(
                {"organization_id": organization_id},
                {"_id": 0}
            )
        )
