
import re
from flask import current_app
from datetime import datetime, timezone


class MessageRepository:

    COLLECTION = "messages"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    # --------------------------------------------------
    # CREATE MESSAGE
    # --------------------------------------------------

    @classmethod
    def save(cls, message):

        response_document = message.copy()
        db_document = message.copy()

        db_document.setdefault("retry_count", 0)
        db_document.setdefault("manual_retry_count", 0)
        db_document.setdefault("application_id", None)

        cls._collection().insert_one(db_document)

        return response_document

    # --------------------------------------------------
    # FIND MESSAGE BY ID
    # --------------------------------------------------

    @classmethod
    def find_by_id(cls, message_id, organization_id=None, application_ids=None):

        query = {
            "message_id": message_id
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        if application_ids is not None:
            if isinstance(application_ids, (list, set, tuple)):
                query["application_id"] = {"$in": list(application_ids)}
            elif isinstance(application_ids, str):
                query["application_id"] = application_ids

        return cls._collection().find_one(
            query,
            {"_id": 0}
        )

    # --------------------------------------------------
    # FIND ALL MESSAGES
    # --------------------------------------------------

    @classmethod
    def find_all(
        cls,
        organization_id=None,
        limit=50,
        page=1,
        status=None,
        channel=None,
        provider=None,
        recipient=None,
        application_id=None,
        search=None,
        start_date=None,
        end_date=None
    ):
        query = {}

        if organization_id is not None:
            query["organization_id"] = organization_id

        if status:
            query["status"] = status
        if channel:
            query["channel"] = channel
        if provider:
            query["provider"] = provider
        if recipient:
            query["recipient"] = recipient

        if application_id is not None:
            if isinstance(application_id, (list, set, tuple)):
                query["application_id"] = {"$in": list(application_id)}
            elif isinstance(application_id, str) and application_id.strip():
                query["application_id"] = application_id.strip()

        if search:
            search_clean = str(search).strip()
            if search_clean:
                escaped = re.escape(search_clean)
                query["$or"] = [
                    {"recipient": {"$regex": escaped, "$options": "i"}},
                    {"message_id": {"$regex": escaped, "$options": "i"}},
                    {"provider_message_id": {"$regex": escaped, "$options": "i"}},
                    {"data.subject": {"$regex": escaped, "$options": "i"}}
                ]

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = str(start_date).strip()
            if end_date:
                date_filter["$lte"] = str(end_date).strip()
            if date_filter:
                query["created_at"] = date_filter

        try:
            limit = max(1, min(int(limit), 100))
        except (ValueError, TypeError):
            limit = 50

        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1

        total = cls._collection().count_documents(query)

        items = list(
            cls._collection().find(
                query,
                {"_id": 0}
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

    # --------------------------------------------------
    # UPDATE MESSAGE STATUS
    # --------------------------------------------------

    @classmethod
    def update_status(
        cls,
        message_id,
        new_status,
        old_status,
        organization_id=None
    ):

        now = cls._now()

        query = {
            "message_id": message_id,
            "status": old_status
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "status": new_status,
                    "updated_at": now
                },
                "$push": {
                    "status_history": {
                        "from": old_status,
                        "to": new_status,
                        "timestamp": now
                    }
                }
            }
        )

        return result.modified_count > 0

    # --------------------------------------------------
    # UPDATE RETRY INFORMATION
    # --------------------------------------------------

    
    @classmethod
    def update_retry_info(
        cls,
        message_id,
        retry_count,
        old_status,
        new_status,
        error=None,
        organization_id=None
    ):
        now = cls._now()

        query = {
            "message_id": message_id,
            "status": old_status
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        update_fields = {
            "retry_count": retry_count,
            "status": new_status,
            "updated_at": now
        }

        if error:
            update_fields["last_error"] = str(error)

        result = cls._collection().update_one(
            query,
            {
                "$set": update_fields,
                "$push": {
                    "status_history": {
                        "from": old_status,
                        "to": new_status,
                        "timestamp": now,
                        "reason": str(error) if error else None
                    }
                }
            }
        )

        return result.modified_count > 0

    # --------------------------------------------------
    # MARK MESSAGE FAILED
    # --------------------------------------------------

    @classmethod
    def mark_failed(
        cls,
        message_id,
        retry_count,
        error,
        organization_id=None
    ):
        return cls.update_retry_info(
            message_id=message_id,
            retry_count=retry_count,
            old_status="PROCESSING",
            new_status="FAILED",
            error=str(error),
            organization_id=organization_id
        )
    # --------------------------------------------------
    # MARK MESSAGE SENT
    # --------------------------------------------------

    @classmethod
    def mark_sent(
        cls,
        message_id,
        provider,
        provider_message_id,
        organization_id=None
    ):
        now = cls._now()

        query = {
            "message_id": message_id,
            "status": "PROCESSING"
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "status": "SENT",
                    "provider": provider,
                    "provider_message_id": provider_message_id,
                    "updated_at": now
                },
                "$push": {
                    "status_history": {
                        "from": "PROCESSING",
                        "to": "SENT",
                        "timestamp": now
                    }
                }
            }
        )

        return result.modified_count > 0

    # --------------------------------------------------
    # FIND BY PROVIDER MESSAGE ID
    # --------------------------------------------------

    @classmethod
    def find_by_provider_message_id(cls, provider_message_id, organization_id=None):
        if not provider_message_id:
            return None
        query = {"provider_message_id": provider_message_id}
        if organization_id is not None:
            query["organization_id"] = organization_id
        return cls._collection().find_one(query, {"_id": 0})

    # --------------------------------------------------
    # UPDATE DELIVERY STATUS (CALLBACK / WEBHOOK)
    # --------------------------------------------------

    @classmethod
    def update_delivery_status(
        cls,
        provider_message_id,
        new_status,
        raw_status=None,
        error_code=None,
        error_message=None,
        organization_id=None
    ):
        if not provider_message_id:
            return False

        query = {"provider_message_id": provider_message_id}
        if organization_id is not None:
            query["organization_id"] = organization_id

        collection = cls._collection()
        status_rank = {"ACCEPTED": 0, "QUEUED": 0, "PROCESSING": 0, "SENT": 1, "DELIVERED": 2, "READ": 3}

        # Compare-and-set prevents concurrent callbacks from overwriting a newer
        # state. Re-read on a race so a later state can still advance correctly.
        for _ in range(5):
            doc = collection.find_one(query)
            if not doc:
                return False

            old_status = doc.get("status")
            if old_status == new_status and (not raw_status or doc.get("provider_status") == raw_status):
                return True

            if old_status in ("DELIVERED", "READ"):
                old_rank = status_rank.get(old_status, 0)
                new_rank = status_rank.get(new_status, 0)
                if new_rank <= old_rank:
                    return False

            now = cls._now()
            update_fields = {"status": new_status, "updated_at": now}
            if raw_status:
                update_fields["provider_status"] = raw_status
            if error_code is not None:
                update_fields["delivery_error_code"] = str(error_code)
            if error_message is not None:
                update_fields["delivery_error_message"] = str(error_message)

            history_entry = {
                "from": old_status,
                "to": new_status,
                "timestamp": now,
                "source": "provider_callback"
            }
            if raw_status:
                history_entry["raw_status"] = raw_status
            if error_message:
                history_entry["reason"] = str(error_message)

            compare_query = dict(query)
            if "status" in doc:
                compare_query["status"] = old_status
            else:
                compare_query["status"] = {"$exists": False}
            res = collection.update_one(
                compare_query,
                {"$set": update_fields, "$push": {"status_history": history_entry}}
            )
            if res.modified_count > 0:
                return True

        return False

    # --------------------------------------------------
    # MANUAL RETRY
    # --------------------------------------------------

    @classmethod
    def requeue_dead_message(
        cls,
        message_id,
        previous_retry_count,
        organization_id=None
    ):
        now = cls._now()

        query = {
            "message_id": message_id,
            "status": "DEAD"
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "status": "QUEUED",
                    "retry_count": 0,
                    "updated_at": now
                },
                "$unset": {
                    "last_error": "",
                    "provider_message_id": ""
                },
                "$inc": {
                    "manual_retry_count": 1
                },
                "$push": {
                    "status_history": {
                        "from": "DEAD",
                        "to": "QUEUED",
                        "timestamp": now,
                        "reason": (
                            "Manual retry requested. "
                            f"Previous retry count: {previous_retry_count}"
                        )
                    }
                }
            }
        )

        return result.modified_count > 0
    # --------------------------------------------------
    # ROLLBACK MANUAL RETRY
    # --------------------------------------------------

    @classmethod
    def rollback_manual_retry(
        cls,
        message_id,
        previous_retry_count,
        previous_manual_retry_count,
        organization_id=None
    ):
        now = cls._now()

        query = {
            "message_id": message_id,
            "status": "QUEUED"
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "status": "DEAD",
                    "retry_count": previous_retry_count,
                    "manual_retry_count": previous_manual_retry_count,
                    "updated_at": now
                },
                "$unset": {
                    "last_error": "",
                    "provider_message_id": ""
                },
                "$push": {
                    "status_history": {
                        "from": "QUEUED",
                        "to": "DEAD",
                        "timestamp": now,
                        "reason": "Manual retry dispatch failed"
                    }
                }
            }
        )

        return result.modified_count > 0

    # --------------------------------------------------
    # REQUEUE FAILED MESSAGE (MANUAL RETRY)
    # --------------------------------------------------

    @classmethod
    def requeue_failed_message(
        cls,
        message_id,
        organization_id=None
    ):
        now = cls._now()

        query = {
            "message_id": message_id,
            "status": "FAILED"
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "status": "QUEUED",
                    "retry_count": 0,
                    "updated_at": now
                },
                "$unset": {
                    "last_error": "",
                    "provider_message_id": ""
                },
                "$inc": {
                    "manual_retry_count": 1
                },
                "$push": {
                    "status_history": {
                        "from": "FAILED",
                        "to": "QUEUED",
                        "timestamp": now,
                        "reason": "Manual retry requested from dashboard"
                    }
                }
            }
        )

        return result.modified_count > 0
