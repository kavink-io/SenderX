
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
    def find_by_employee_code(cls, employee_code, organization_id=None):
        if not employee_code:
            return None
        query = {"employee_code": str(employee_code).strip().upper()}
        if organization_id is not None:
            query["organization_id"] = organization_id
        return cls._collection().find_one(query)

    @classmethod
    def find_all_by_organization(
        cls,
        organization_id,
        limit=50,
        page=1,
        search=None,
        status=None,
        role_id=None,
        application_id=None,
        employee_code=None
    ):
        try:
            limit = max(1, min(int(limit), 100))
        except (ValueError, TypeError):
            limit = 50

        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1

        query = {"organization_id": organization_id}

        # Status filter
        if status is not None:
            if isinstance(status, bool):
                query["is_active"] = status
            elif str(status).strip().upper() == "ACTIVE":
                query["is_active"] = True
            elif str(status).strip().upper() == "INACTIVE":
                query["is_active"] = False

        # Role filter
        if role_id:
            query["role_ids"] = str(role_id).strip()

        # Application scope filter
        if application_id:
            app_clean = str(application_id).strip()
            query["$or"] = [
                {"application_ids": app_clean},
                {"role_assignments.application_id": app_clean},
                {"role_assignments.application_id": None}  # Org-wide roles also cover this app
            ]

        # Explicit employee code filter
        if employee_code:
            query["employee_code"] = str(employee_code).strip().upper()

        # Search filter (name, email, or employee_code)
        if search:
            search_clean = str(search).strip()
            if search_clean:
                search_regex = {"$regex": search_clean, "$options": "i"}
                search_clause = [
                    {"name": search_regex},
                    {"email": search_regex},
                    {"employee_code": search_regex}
                ]
                if "$or" in query:
                    query = {"$and": [query, {"$or": search_clause}]}
                else:
                    query["$or"] = search_clause

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
    def count_active_by_role(cls, role_id, organization_id):
        """Count active employees who have this role assigned."""
        query = {
            "organization_id": organization_id,
            "is_active": True,
            "$or": [
                {"role_ids": role_id},
                {"role_assignments.role_id": role_id}
            ]
        }
        return cls._collection().count_documents(query)

    @classmethod
    def find_active_by_role(cls, role_id, organization_id, limit=50):
        """Find active employees who have this role assigned."""
        query = {
            "organization_id": organization_id,
            "is_active": True,
            "$or": [
                {"role_ids": role_id},
                {"role_assignments.role_id": role_id}
            ]
        }
        return list(
            cls._collection()
            .find(query, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "created_at": 1})
            .limit(limit)
        )

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
        return result.matched_count > 0

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
