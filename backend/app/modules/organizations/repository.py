
import re
from datetime import datetime, timezone
from flask import current_app


class OrganizationRepository:

    COLLECTION = "organizations"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, organization, session=None):
        organization = dict(organization)
        organization.setdefault("created_at", cls._now())

        cls._collection().insert_one(
            organization,
            session=session
        )

        return organization

    @classmethod
    def find_by_id(cls, organization_id):
        return cls._collection().find_one({
            "organization_id": organization_id
        })

    @classmethod
    def find_by_slug(cls, slug):
        return cls._collection().find_one({
            "slug": slug
        })

    @classmethod
    def update(cls, organization_id, update_fields, session=None):
        update_fields = dict(update_fields)
        update_fields["updated_at"] = cls._now()
        cls._collection().update_one(
            {"organization_id": organization_id},
            {"$set": update_fields},
            session=session
        )
        return cls.find_by_id(organization_id)

    @classmethod
    def find_all(cls, limit=50, page=1, search=None, status=None):
        try:
            limit = max(1, min(int(limit), 100))
        except (ValueError, TypeError):
            limit = 50

        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1

        collection = cls._collection()

        query = {}
        if status:
            status_clean = str(status).strip().upper()
            if status_clean in ("ACTIVE", "INACTIVE", "DELETED", "SUSPENDED"):
                query["status"] = status_clean
            elif status_clean == "ALL":
                pass
        else:
            query["status"] = {"$ne": "DELETED"}

        if search:
            search_clean = str(search).strip()
            if search_clean:
                escaped_search = re.escape(search_clean)
                query["$or"] = [
                    {"name": {"$regex": escaped_search, "$options": "i"}},
                    {"slug": {"$regex": escaped_search, "$options": "i"}}
                ]

        total = collection.count_documents(query)

        items = list(
            collection.find(
                query,
                {"_id": 0}
            )
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        total_pages = max(1, (total + limit - 1) // limit) if total > 0 else 1

        return {
            "items": items,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            }
        }

    @classmethod
    def ensure_indexes(cls):
        db = current_app.mongo_db

        db["organizations"].create_index(
            [("organization_id", 1)],
            unique=True
        )

        db["organizations"].create_index(
            [("slug", 1)],
            unique=True
        )

        db["users"].create_index(
            [("organization_id", 1), ("email", 1)],
            unique=True
        )

        db["roles"].create_index(
            [("role_id", 1)],
            unique=True
        )

        db["roles"].create_index(
            [("organization_id", 1), ("name", 1)],
            unique=True
        )

    @classmethod
    def ensure_indexes(cls):
        db = current_app.mongo_db

        db["organizations"].create_index(
            "organization_id",
            unique=True
        )

        db["organizations"].create_index(
            "slug",
            unique=True
        )

        db["users"].create_index(
            "user_id",
            unique=True
        )

        # Email-only login requires globally unique organization-user emails.
        db["users"].create_index(
            "email",
            unique=True
        )

        db["roles"].create_index(
            "role_id",
            unique=True
        )

        db["roles"].create_index(
            [("organization_id", 1), ("name", 1)],
            unique=True
        )

        db["admins"].create_index(
            "email",
            unique=True
        )
