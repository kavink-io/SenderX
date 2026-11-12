
from datetime import datetime, timezone, timedelta
import re
import uuid

from flask import current_app


class DeadLetterRepository:

    COLLECTION = "dead_letters"

    @classmethod
    def _collection(cls):
        return current_app.mongo_db[cls.COLLECTION]

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_date(value, is_end_date=False):
        """
        Convert an ISO date or datetime into a UTC datetime.

        Date-only start_date:
            2026-11-01 -> 2026-11-01 00:00 UTC

        Date-only end_date:
            2026-11-10 -> 2026-11-11 00:00 UTC
            This makes the entire end date inclusive.

        Datetime values are treated as exclusive for end_date.
        """

        if value is None:
            return None

        if isinstance(value, datetime):
            parsed = value
        else:
            value = str(value).strip()

            if not value:
                return None

            date_only = len(value) == 10

            try:
                parsed = datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise ValueError(
                    "Invalid date format. Use YYYY-MM-DD "
                    "or an ISO 8601 datetime."
                ) from exc

            if is_end_date and date_only:
                parsed += timedelta(days=1)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    # --------------------------------------------------
    # SAVE DEAD LETTER
    # --------------------------------------------------

    
    @classmethod
    def save_from_message(cls, message, error):
        """
        Save an exhausted message in the DLQ.

        Supports automatic and manual failure cycles.

        Uses a deterministic failure_cycle_id to prevent
        duplicate failure-cycle entries.
        """

        now = cls._now()
        message_id = message["message_id"]

        retry_count = message.get("retry_count", 0)
        manual_retry_count = message.get("manual_retry_count", 0)

        # Deterministic identifier for this processing cycle
        failure_cycle_id = (
            f"{message_id}:{retry_count}:{manual_retry_count}"
        )

        snapshot_fields = [
                "message_id",
                "organization_id",
                "channel",
                "provider",
                "recipient",
                "data",
                "status",
                "retry_count",
                "last_error",
                "status_history",
                "created_at",
                "updated_at",
                "provider_message_id",
                "manual_retry_count"
            ]

        snapshot = {
            field: message[field]
            for field in snapshot_fields
            if field in message
        }

        organization_id = message.get("organization_id")

        if organization_id:
            snapshot["organization_id"] = organization_id

        snapshot["last_error"] = str(error)
        snapshot["dead_letter_status"] = "PENDING_REVIEW"
        snapshot["dead_lettered_at"] = now
        snapshot["manual_retry_count"] = manual_retry_count

        failure_cycle = {
            "failure_cycle_id": failure_cycle_id,
            "cycle_type": (
                "MANUAL"
                if manual_retry_count > 0
                else "AUTOMATIC"
            ),
            "retry_count": retry_count,
            "manual_retry_cycle": manual_retry_count,
            "error": str(error),
            "dead_lettered_at": now
        }

        collection = cls._collection()

        # Ensure the DLQ document exists.
        # This also preserves its original creation timestamp.
        collection.update_one(
            {"message_id": message_id},
            {
                "$setOnInsert": {
                    "message_id": message_id,
                    "created_in_dlq_at": now
                }
            },
            upsert=True
        )

        # Only append the failure cycle if its identifier
        # has not already been recorded.
        result = collection.update_one(
            {
                "message_id": message_id,
                "failure_cycles.failure_cycle_id": {
                    "$ne": failure_cycle_id
                }
            },
            {
                "$set": snapshot,

                "$push": {
                    "failure_cycles": failure_cycle
                },

                "$unset": {
                    "manual_retry_requested_at": "",
                    "manual_retry_queued_at": "",
                    "manual_retry_task_id": ""
                }
            }
        )

        if result.modified_count == 0:
            current_app.logger.info(
                "Duplicate failure cycle ignored: %s",
                failure_cycle_id
            )

        return cls.find_by_message_id(message_id)

    # --------------------------------------------------
    # FIND DEAD LETTER
    # --------------------------------------------------

    @classmethod
    def find_by_message_id(cls, message_id, organization_id=None):

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
    # FIND ALL DEAD LETTERS
    # --------------------------------------------------
    
    @classmethod
    def find_all(
    cls,
    limit=50,
    page=1,
    status=None,
    message_id=None,
    recipient=None,
    provider=None,
    include_metadata=False,
    organization_id=None
):
        """
        Retrieve dead letters with optional filtering
        and pagination.
        """

        query = {}
        if organization_id is not None:
            query["organization_id"] = organization_id

        if status:
            query["dead_letter_status"] = status.strip().upper()

        if message_id:
            query["message_id"] = message_id.strip()

        if recipient:
            query["recipient"] = {
                "$regex": re.escape(recipient.strip()),
                "$options": "i"
            }

        if provider:
            query["provider"] = {
                "$regex": f"^{re.escape(provider.strip())}$",
                "$options": "i"
            }

        page = max(int(page), 1)
        limit = max(min(int(limit), 100), 1)

        skip = (page - 1) * limit

        collection = cls._collection()

        total = collection.count_documents(query)

        records = list(
            collection.find(query, {"_id": 0})
            .sort("dead_lettered_at", -1)
            .skip(skip)
            .limit(limit)
        )

        if not include_metadata:
            return records

        total_pages = (total + limit - 1) // limit

        return {
            "items": records,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            }
        }

    # --------------------------------------------------
    # DLQ STATISTICS
    # --------------------------------------------------

    @classmethod
    def get_statistics(cls, organization_id=None):
        """
        Generate DLQ monitoring statistics.
        """

        pipeline = [
            {
                "$match": {
                    "organization_id": organization_id
                }
                if organization_id is not None else {}
            },
            {
                "$facet": {

                    "summary": [
                        {
                            "$group": {
                                "_id": None,
                                "total": {"$sum": 1},

                                "pending_review": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$eq": [
                                                    "$dead_letter_status",
                                                    "PENDING_REVIEW"
                                                ]
                                            },
                                            1,
                                            0
                                        ]
                                    }
                                },

                                "retry_requested": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$eq": [
                                                    "$dead_letter_status",
                                                    "RETRY_REQUESTED"
                                                ]
                                            },
                                            1,
                                            0
                                        ]
                                    }
                                },

                                "retry_queued": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$eq": [
                                                    "$dead_letter_status",
                                                    "RETRY_QUEUED"
                                                ]
                                            },
                                            1,
                                            0
                                        ]
                                    }
                                },

                                "total_manual_retries": {
                                    "$sum": {
                                        "$ifNull": [
                                            "$manual_retry_count",
                                            0
                                        ]
                                    }
                                },

                                "total_failure_cycles": {
                                    "$sum": {
                                        "$size": {
                                            "$cond": [
                                                {"$isArray": "$failure_cycles"},
                                                "$failure_cycles",
                                                []
                                            ]
                                        }
                                    }
                                }
                            }
                        }
                    ],

                    "provider_breakdown": [
                        {
                            "$group": {
                                "_id": {
                                    "$ifNull": ["$provider", "unknown"]
                                },
                                "count": {"$sum": 1}
                            }
                        }
                    ]
                }
            }
        ]

        result = list(cls._collection().aggregate(pipeline))

        if not result:
            return {
                "total": 0,
                "pending_review": 0,
                "retry_requested": 0,
                "retry_queued": 0,
                "total_manual_retries": 0,
                "total_failure_cycles": 0,
                "provider_breakdown": {}
            }

        summary = result[0]["summary"]

        statistics = summary[0] if summary else {
            "total": 0,
            "pending_review": 0,
            "retry_requested": 0,
            "retry_queued": 0,
            "total_manual_retries": 0,
            "total_failure_cycles": 0
        }

        statistics.pop("_id", None)

        statistics["provider_breakdown"] = {
            item["_id"]: item["count"]
            for item in result[0]["provider_breakdown"]
        }

        return statistics

    # --------------------------------------------------
    # PROVIDER ANALYTICS
    # --------------------------------------------------

    @classmethod
    def get_provider_analytics(cls, organization_id=None):
        """
        Generate provider-wise DLQ failure analytics.
        """

        collection = cls._collection()

        match_criteria = {"organization_id": organization_id} if organization_id is not None else {}
        query = {}

        if organization_id is not None:
            query["organization_id"] = organization_id

        total = collection.count_documents(query)

        provider_pipeline = [
            {
                "$group": {
                    "_id": {
                        "$ifNull": ["$provider", "unknown"]
                    },
                    "failure_count": {"$sum": 1},

                    "manual_retry_count": {
                        "$sum": {
                            "$ifNull": ["$manual_retry_count", 0]
                        }
                    },

                    "failure_cycles": {
                        "$sum": {
                            "$size": {
                                "$cond": [
                                    {"$isArray": "$failure_cycles"},
                                    "$failure_cycles",
                                    []
                                ]
                            }
                        }
                    }
                }
            },
            {"$sort": {"failure_count": -1}}
        ]

        provider_results = list(
            collection.aggregate(
                ([{"$match": query}] if query else []) + provider_pipeline
            )
        )

        providers = []

        for item in provider_results:
            failure_count = item["failure_count"]

            percentage = (
                round((failure_count / total) * 100, 2)
                if total > 0 else 0
            )

            providers.append({
                "provider": item["_id"],
                "failure_count": failure_count,
                "failure_percentage": percentage,
                "manual_retry_count": item["manual_retry_count"],
                "failure_cycles": item["failure_cycles"]
            })

        channel_pipeline = [
            {
                "$group": {
                    "_id": {
                        "$ifNull": ["$channel", "unknown"]
                    },
                    "failure_count": {"$sum": 1}
                }
            },
            {"$sort": {"failure_count": -1}}
        ]

        channel_results = list(
            collection.aggregate(channel_pipeline)
        )

        channels = {
            item["_id"]: item["failure_count"]
            for item in channel_results
        }

        error_pipeline = [
            {
                "$group": {
                    "_id": {
                        "$ifNull": ["$last_error", "Unknown error"]
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]

        error_results = list(
            collection.aggregate(error_pipeline)
        )

        common_errors = [
            {
                "error": item["_id"],
                "count": item["count"]
            }
            for item in error_results
        ]

        return {
            "total_dlq_records": total,
            "providers": providers,
            "channels": channels,
            "common_errors": common_errors
        }

    # --------------------------------------------------
    # FAILURE TRENDS WITH DASHBOARD FILTERS
    # --------------------------------------------------

    @classmethod
    def get_daily_failure_trends(
        cls,
        start_date=None,
        end_date=None,
        provider=None,
        organization_id=None
    ):
        """
        Generate:

        1. Daily failure trends
        2. Weekly failure trends
        3. Monthly failure trends
        4. Provider-wise daily failures
        5. Historical retry-exhaustion trends

        Supports:
            start_date
            end_date
            provider

        Date-only end_date is inclusive.
        """

        start_date = cls._parse_date(start_date)
        end_date = cls._parse_date(
            end_date,
            is_end_date=True
        )

        if start_date and end_date and start_date >= end_date:
            raise ValueError(
                "start_date must be earlier than end_date."
            )

        if provider is not None:
            provider = str(provider).strip()

            if not provider:
                provider = None

        # Standard failure-date filters
        date_conditions = {}

        if start_date:
            date_conditions["$gte"] = start_date

        if end_date:
            date_conditions["$lt"] = end_date

        standard_date_match = {}

        if date_conditions:
            standard_date_match["parsed_dead_lettered_at"] = (
                date_conditions
            )

        # Historical failure-cycle date filters
        cycle_date_match = {}

        if start_date:
            cycle_date_match["$gte"] = start_date

        if end_date:
            cycle_date_match["$lt"] = end_date

        cycle_match = {}

        if cycle_date_match:
            cycle_match["parsed_cycle_at"] = cycle_date_match

        # Apply provider filter to all analytics datasets
        provider_match = {}

        if provider:
            provider_match["provider"] = {
                "$regex": f"^{re.escape(provider)}$",
                "$options": "i"
            }

        pipeline = [

            # Convert stored ISO timestamps into dates

            {
                "$match": (
                    {"organization_id": organization_id}
                    if organization_id is not None
                    else {}
                )
            },

            {
                "$addFields": {
                    "parsed_dead_lettered_at": {
                        "$dateFromString": {
                            "dateString": "$dead_lettered_at",
                            "onError": None,
                            "onNull": None
                        }
                    }
                }
            },

            # Provider filtering
            {
                "$match": provider_match
            },

            # Five analytics pipelines
            {
                "$facet": {

                    # 1. Daily failure trends
                    "daily": [
                        {
                            "$match": {
                                "parsed_dead_lettered_at": {
                                    "$ne": None
                                }
                            }
                        },
                        {
                            "$match": standard_date_match
                        },
                        {
                            "$group": {
                                "_id": {
                                    "$dateToString": {
                                        "format": "%Y-%m-%d",
                                        "date": "$parsed_dead_lettered_at",
                                        "timezone": "UTC"
                                    }
                                },

                                "failure_count": {
                                    "$sum": 1
                                },

                                "failure_cycles": {
                                    "$sum": {
                                        "$size": {
                                            "$cond": [
                                                {"$isArray": "$failure_cycles"},
                                                "$failure_cycles",
                                                []
                                            ]
                                        }
                                    }
                                },

                                "manual_retry_count": {
                                    "$sum": {
                                        "$ifNull": [
                                            "$manual_retry_count",
                                            0
                                        ]
                                    }
                                }
                            }
                        },
                        {"$sort": {"_id": 1}}
                    ],

                    # 2. Weekly failure trends
                    "weekly": [
                        {
                            "$match": {
                                "parsed_dead_lettered_at": {
                                    "$ne": None
                                }
                            }
                        },
                        {
                            "$match": standard_date_match
                        },
                        {
                            "$group": {
                                "_id": {
                                    "year": {
                                        "$isoWeekYear": "$parsed_dead_lettered_at"
                                    },
                                    "week": {
                                        "$isoWeek": "$parsed_dead_lettered_at"
                                    }
                                },
                                "failure_count": {
                                    "$sum": 1
                                }
                            }
                        },
                        {
                            "$sort": {
                                "_id.year": 1,
                                "_id.week": 1
                            }
                        }
                    ],

                    # 3. Monthly failure trends
                    "monthly": [
                        {
                            "$match": {
                                "parsed_dead_lettered_at": {
                                    "$ne": None
                                }
                            }
                        },
                        {
                            "$match": standard_date_match
                        },
                        {
                            "$group": {
                                "_id": {
                                    "$dateToString": {
                                        "format": "%Y-%m",
                                        "date": "$parsed_dead_lettered_at",
                                        "timezone": "UTC"
                                    }
                                },
                                "failure_count": {
                                    "$sum": 1
                                }
                            }
                        },
                        {"$sort": {"_id": 1}}
                    ],

                    # 4. Provider-wise daily failures
                    "provider_daily": [
                        {
                            "$match": {
                                "parsed_dead_lettered_at": {
                                    "$ne": None
                                }
                            }
                        },
                        {
                            "$match": standard_date_match
                        },
                        {
                            "$group": {
                                "_id": {
                                    "date": {
                                        "$dateToString": {
                                            "format": "%Y-%m-%d",
                                            "date": "$parsed_dead_lettered_at",
                                            "timezone": "UTC"
                                        }
                                    },
                                    "provider": {
                                        "$ifNull": [
                                            "$provider",
                                            "unknown"
                                        ]
                                    }
                                },
                                "failure_count": {
                                    "$sum": 1
                                }
                            }
                        },
                        {
                            "$sort": {
                                "_id.date": 1,
                                "_id.provider": 1
                            }
                        }
                    ],

                    # 5. Historical retry-exhaustion trends
                    "retry_exhaustion_daily": [
                        {
                            "$unwind": "$failure_cycles"
                        },
                        {
                            "$addFields": {
                                "parsed_cycle_at": {
                                    "$dateFromString": {
                                        "dateString": "$failure_cycles.dead_lettered_at",
                                        "onError": None,
                                        "onNull": None
                                    }
                                }
                            }
                        },
                        {
                            "$match": {
                                "parsed_cycle_at": {
                                    "$ne": None
                                }
                            }
                        },
                        {
                            "$match": cycle_match
                        },
                        {
                            "$group": {
                                "_id": {
                                    "$dateToString": {
                                        "format": "%Y-%m-%d",
                                        "date": "$parsed_cycle_at",
                                        "timezone": "UTC"
                                    }
                                },
                                "exhaustion_count": {
                                    "$sum": 1
                                }
                            }
                        },
                        {"$sort": {"_id": 1}}
                    ]
                }
            }
        ]

        result = list(
            cls._collection().aggregate(pipeline)
        )

        if not result:
            analytics = {
                "daily": [],
                "weekly": [],
                "monthly": [],
                "provider_daily": [],
                "retry_exhaustion_daily": []
            }
        else:
            analytics = result[0]

        return {

            "daily": [
                {
                    "date": item["_id"],
                    "failure_count": item["failure_count"],
                    "failure_cycles": item["failure_cycles"],
                    "manual_retry_count": item["manual_retry_count"]
                }
                for item in analytics["daily"]
            ],

            "weekly": [
                {
                    "year": item["_id"]["year"],
                    "week": item["_id"]["week"],
                    "failure_count": item["failure_count"]
                }
                for item in analytics["weekly"]
            ],

            "monthly": [
                {
                    "month": item["_id"],
                    "failure_count": item["failure_count"]
                }
                for item in analytics["monthly"]
            ],

            "provider_daily": [
                {
                    "date": item["_id"]["date"],
                    "provider": item["_id"]["provider"],
                    "failure_count": item["failure_count"]
                }
                for item in analytics["provider_daily"]
            ],

            "retry_exhaustion_daily": [
                {
                    "date": item["_id"],
                    "exhaustion_count": item["exhaustion_count"]
                }
                for item in analytics["retry_exhaustion_daily"]
            ]
        }

    # --------------------------------------------------
    # MANUAL RETRY REQUEST
    # --------------------------------------------------


    @classmethod
    def mark_retry_requested(cls, message_id, organization_id=None):

        current = cls.find_by_message_id(
            message_id,
            organization_id=organization_id
        )

        if not current:
            return None

        current_count = current.get("manual_retry_count", 0)
        next_count = current_count + 1

        now = cls._now()
        task_id = str(uuid.uuid4())

        query = {
            "message_id": message_id,
            "dead_letter_status": "PENDING_REVIEW",
            "manual_retry_count": current_count
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "dead_letter_status": "RETRY_REQUESTED",
                    "manual_retry_requested_at": now,
                    "manual_retry_dispatch_state": "DISPATCHING",
                    "manual_retry_task_id": task_id,
                    "manual_retry_dispatch_started_at": now
                },
                "$inc": {
                    "manual_retry_count": 1
                },
                "$push": {
                    "manual_retry_history": {
                        "attempt": next_count,
                        "requested_at": now,
                        "status": "DISPATCHING",
                        "task_id": task_id,
                        "dispatch_started_at": now
                    }
                }
            }
        )

        if result.modified_count == 0:
            return None

        return {
            "task_id": task_id,
            "attempt": next_count
        }

    # --------------------------------------------------
    # RESTORE PENDING REVIEW
    # --------------------------------------------------

    @classmethod
    def restore_pending_review(cls, message_id, organization_id=None):

        now = cls._now()

        query = {
            "message_id": message_id,
            "dead_letter_status": "RETRY_REQUESTED",
            "manual_retry_dispatch_state": "DISPATCHING"
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "dead_letter_status": "PENDING_REVIEW",
                    "manual_retry_history.$[entry].status": "CANCELLED",
                    "manual_retry_history.$[entry].cancelled_at": now
                },
                "$unset": {
                    "manual_retry_requested_at": "",
                    "manual_retry_dispatch_state": "",
                    "manual_retry_task_id": "",
                    "manual_retry_dispatch_started_at": ""
                },
                "$inc": {
                    "manual_retry_count": -1
                }
            },
            array_filters=[
                {
                    "entry.status": "DISPATCHING"
                }
            ]
        )

        return result.modified_count > 0

    # --------------------------------------------------
    # MARK RETRY QUEUED
    # --------------------------------------------------

    @classmethod
    def mark_retry_queued(
        cls,
        message_id,
        task_id,
        organization_id=None
    ):

        now = cls._now()

        query = {
            "message_id": message_id,
            "dead_letter_status": "RETRY_REQUESTED",
            "manual_retry_dispatch_state": "DISPATCHING",
            "manual_retry_task_id": task_id
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "dead_letter_status": "RETRY_QUEUED",
                    "manual_retry_dispatch_state": "QUEUED",
                    "manual_retry_queued_at": now,
                    "manual_retry_history.$[entry].status": "QUEUED",
                    "manual_retry_history.$[entry].queued_at": now
                },
                "$push": {
                    "status_history": {
                        "from": "RETRY_REQUESTED",
                        "to": "RETRY_QUEUED",
                        "timestamp": now
                    }
                }
            },
            array_filters=[
                {
                    "entry.task_id": task_id,
                    "entry.status": "DISPATCHING"
                }
            ]
        )

        return result.modified_count > 0

    # --------------------------------------------------
    # MARK RETRY DISPATCH FAILED
    # --------------------------------------------------

    @classmethod
    def mark_retry_dispatch_failed(
        cls,
        message_id,
        error,
        task_id,
        organization_id=None
    ):

        now = cls._now()

        query = {
            "message_id": message_id,
            "dead_letter_status": "RETRY_REQUESTED",
            "manual_retry_dispatch_state": "DISPATCHING",
            "manual_retry_task_id": task_id
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().update_one(
            query,
            {
                "$set": {
                    "dead_letter_status": "PENDING_REVIEW",
                    "manual_retry_dispatch_failed_at": now,
                    "manual_retry_history.$[entry].status": "DISPATCH_FAILED",
                    "manual_retry_history.$[entry].error": str(error),
                    "manual_retry_history.$[entry].failed_at": now
                },
                "$unset": {
                    "manual_retry_requested_at": "",
                    "manual_retry_dispatch_state": "",
                    "manual_retry_task_id": "",
                    "manual_retry_dispatch_started_at": ""
                },
                "$inc": {
                    "manual_retry_count": -1
                }
            },
            array_filters=[
                {
                    "entry.task_id": task_id,
                    "entry.status": "DISPATCHING"
                }
            ]
        )

        return result.modified_count > 0

    # --------------------------------------------------
    # DELETE DEAD LETTER
    # --------------------------------------------------

    @classmethod
    def delete_by_message_id(cls, message_id, organization_id=None):

        query = {
            "message_id": message_id,
            "dead_letter_status": "PENDING_REVIEW"
        }

        if organization_id is not None:
            query["organization_id"] = organization_id

        result = cls._collection().delete_one(query)

        return result.deleted_count > 0

    @classmethod
    def find_stale_dispatches(cls, minutes=5, limit=100):

        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=minutes
        )

        cutoff = cutoff.isoformat()

        records = cls._collection().find(
            {
                "dead_letter_status": "RETRY_REQUESTED",
                "manual_retry_dispatch_state": "DISPATCHING",
                "manual_retry_dispatch_started_at": {
                    "$lt": cutoff
                }
            },
            {
                "_id": 0,
                "message_id": 1,
                "manual_retry_task_id": 1,
                "manual_retry_count": 1,
                "manual_retry_dispatch_started_at": 1,
                "manual_retry_history": 1
            }
        ).sort(
            "manual_retry_dispatch_started_at", 1
        ).limit(limit)

        return list(records)


    @classmethod
    def mark_dispatch_recovery_required(cls, message_id, task_id):

        now = cls._now()

        result = cls._collection().update_one(
            {
                "message_id": message_id,
                "dead_letter_status": "RETRY_REQUESTED",
                "manual_retry_dispatch_state": "DISPATCHING",
                "manual_retry_task_id": task_id
            },
            {
                "$set": {
                    "manual_retry_dispatch_state": "RECOVERY_REQUIRED",
                    "manual_retry_recovery_required_at": now
                },
                "$push": {
                    "manual_retry_history.$[entry].recovery_events": {
                        "status": "RECOVERY_REQUIRED",
                        "timestamp": now
                    }
                }
            },
            array_filters=[
                {
                    "entry.task_id": task_id,
                    "entry.status": "DISPATCHING"
                }
            ]
        )

        return result.modified_count > 0

    @classmethod
    def resolve_recovery(
        cls,
        message_id,
        task_id,
        resolved_by,
        notes=None
    ):

        now = cls._now()

        result = cls._collection().update_one(
            {
                "message_id": message_id,
                "dead_letter_status": "RETRY_REQUESTED",
                "manual_retry_dispatch_state": "RECOVERY_REQUIRED",
                "manual_retry_task_id": task_id
            },
            {
                "$set": {
                    "dead_letter_status": "RESOLVED",
                    "manual_retry_dispatch_state": "RESOLVED",
                    "manual_retry_resolved_at": now,
                    "manual_retry_resolution": {
                        "type": "MESSAGE_COMPLETED",
                        "resolved_by": resolved_by,
                        "notes": notes,
                        "resolved_at": now
                    }
                },
                "$push": {
                    "recovery_history": {
                        "action": "RESOLVED",
                        "task_id": task_id,
                        "resolved_by": resolved_by,
                        "notes": notes,
                        "timestamp": now
                    }
                }
            }
        )

        return result.modified_count > 0
