
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

        cls._collection().insert_one(db_document)

        return response_document

    # --------------------------------------------------
    # FIND MESSAGE BY ID
    # --------------------------------------------------

    @classmethod
    def find_by_id(cls, message_id, organization_id=None):

        query = {
            "message_id": message_id
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        return cls._collection().find_one(
            query,
            {"_id": 0}
        )

    # --------------------------------------------------
    # FIND ALL MESSAGES
    # --------------------------------------------------

    @classmethod
    def find_all(cls, limit=50, organization_id=None):

        query = {}

        if organization_id is not None:
            query["organization_id"] = organization_id

        limit = max(1, min(int(limit), 100))

        return list(
            cls._collection().find(
                query,
                {"_id": 0}
            ).sort(
                "created_at", -1
            ).limit(limit)
        )

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