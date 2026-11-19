import re
from datetime import datetime, timezone
from flask import current_app


class OrganizationChangeRequestRepository:

    COLLECTION = "organization_change_requests"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(cls, request_data):
        doc = dict(request_data)
        doc.setdefault("created_at", cls._now())
        doc.setdefault("updated_at", cls._now())
        doc.setdefault("status", "PENDING")
        cls._collection().insert_one(doc)
        doc.pop("_id", None)
        return doc

    @classmethod
    def find_by_id(cls, request_id):
        return cls._collection().find_one({"request_id": request_id}, {"_id": 0})

    @classmethod
    def find_pending_by_organization(cls, organization_id):
        return cls._collection().find_one({
            "organization_id": organization_id,
            "status": "PENDING"
        }, {"_id": 0})

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
            cls._collection()
            .find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
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
    def find_all(cls, limit=50, page=1, status=None, search=None):
        try:
            limit = max(1, min(int(limit), 100))
        except (ValueError, TypeError):
            limit = 50
        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1

        query = {}
        if status:
            status_clean = str(status).strip().upper()
            if status_clean != "ALL":
                query["status"] = status_clean

        if search:
            search_clean = str(search).strip()
            if search_clean:
                escaped = re.escape(search_clean)
                search_regex = {"$regex": escaped, "$options": "i"}
                query["$or"] = [
                    {"current_name": search_regex},
                    {"requested_name": search_regex},
                    {"current_slug": search_regex},
                    {"requested_slug": search_regex},
                    {"requester_email": search_regex},
                    {"reason": search_regex}
                ]

        total = cls._collection().count_documents(query)
        items = list(
            cls._collection()
            .find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
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
    def update(cls, request_id, update_fields):
        update_fields = dict(update_fields)
        update_fields["updated_at"] = cls._now()
        res = cls._collection().update_one(
            {"request_id": request_id},
            {"$set": update_fields}
        )
        return res.matched_count > 0
