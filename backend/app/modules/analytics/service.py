from flask import current_app
from datetime import date, datetime, time, timezone, timedelta


class AnalyticsService:
    SUCCESS_STATUSES = ("SENT", "DELIVERED", "READ")

    @classmethod
    def get_platform_analytics(cls):
        return cls._aggregate_analytics(organization_id=None)

    @classmethod
    def get_organization_analytics(
        cls,
        organization_id,
        start_date=None,
        end_date=None,
        application_id=None,
        application_ids=None,
        include_details=False
    ):
        if not organization_id:
            raise ValueError("organization_id is required for organization analytics")
        return cls._aggregate_analytics(
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            application_id=application_id,
            application_ids=application_ids,
            include_details=include_details
        )

    @classmethod
    def _aggregate_analytics(
        cls,
        organization_id=None,
        start_date=None,
        end_date=None,
        application_id=None,
        application_ids=None,
        include_details=False
    ):
        messages_col = current_app.mongo_db["messages"]
        dlq_col = current_app.mongo_db["dead_letters"]

        scope_filter = {}
        if organization_id is not None:
            scope_filter["organization_id"] = organization_id
        if application_ids is not None:
            if application_id:
                scope_filter["application_id"] = (
                    application_id if application_id in application_ids else {"$in": []}
                )
            else:
                scope_filter["application_id"] = {"$in": list(application_ids)}
        elif application_id:
            scope_filter["application_id"] = application_id

        date_filter = cls._created_at_filter(start_date, end_date)
        match_filter = {**scope_filter, **date_filter}

        # 1. Message overview & status breakdown
        status_pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_retries": {"$sum": {"$ifNull": ["$retry_count", 0]}},
                "total_manual_retries": {"$sum": {"$ifNull": ["$manual_retry_count", 0]}}
            }}
        ]

        status_results = list(messages_col.aggregate(status_pipeline))

        total_messages = sum(item["count"] for item in status_results)
        total_retries = sum(item.get("total_retries", 0) for item in status_results)
        total_manual_retries = sum(item.get("total_manual_retries", 0) for item in status_results)

        status_counts = {item["_id"]: item["count"] for item in status_results if item["_id"]}

        sent_count = status_counts.get("SENT", 0)
        delivered_count = sum(status_counts.get(status, 0) for status in cls.SUCCESS_STATUSES)
        failed_count = status_counts.get("FAILED", 0)
        dead_count = status_counts.get("DEAD", 0)
        queued_count = status_counts.get("QUEUED", 0)
        processing_count = status_counts.get("PROCESSING", 0)

        delivery_rate = round((delivered_count / total_messages * 100), 2) if total_messages > 0 else 0.0
        failure_rate = round(((failed_count + dead_count) / total_messages * 100), 2) if total_messages > 0 else 0.0

        # Current-day activity is independent of the selected report range.
        today = datetime.now(timezone.utc).date()
        today_filter = {
            **scope_filter,
            **cls._created_at_filter(today.isoformat(), today.isoformat())
        }
        today_results = list(messages_col.aggregate([
            {"$match": today_filter},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]))
        today_counts = {item["_id"]: item["count"] for item in today_results if item["_id"]}

        # 2. Channel distribution
        channel_pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": "$channel",
                "count": {"$sum": 1},
                "sent": {"$sum": {"$cond": [{"$eq": ["$status", "SENT"]}, 1, 0]}},
                "delivered": {"$sum": {"$cond": [{"$in": ["$status", list(cls.SUCCESS_STATUSES)]}, 1, 0]}},
                "failed": {"$sum": {"$cond": [{"$in": ["$status", ["FAILED", "DEAD"]]}, 1, 0]}}
            }},
            {"$sort": {"count": -1}}
        ]
        channels = list(messages_col.aggregate(channel_pipeline))

        # 3. Provider breakdown & performance
        provider_pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": {"$ifNull": ["$provider", "unassigned"]},
                "count": {"$sum": 1},
                "sent": {"$sum": {"$cond": [{"$eq": ["$status", "SENT"]}, 1, 0]}},
                "delivered": {"$sum": {"$cond": [{"$in": ["$status", list(cls.SUCCESS_STATUSES)]}, 1, 0]}},
                "failed": {"$sum": {"$cond": [{"$in": ["$status", ["FAILED", "DEAD"]]}, 1, 0]}}
            }},
            {"$sort": {"count": -1}}
        ]
        providers = list(messages_col.aggregate(provider_pipeline))

        # 4. DLQ summary
        dlq_pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": "$dead_letter_status",
                "count": {"$sum": 1}
            }}
        ]
        dlq_status_results = list(dlq_col.aggregate(dlq_pipeline))
        dlq_counts = {item["_id"]: item["count"] for item in dlq_status_results if item["_id"]}
        total_dlq = sum(dlq_counts.values())

        # 5. Daily message volume for the selected range, or the latest 14 days.
        trend_filter = dict(match_filter)
        if not start_date and not end_date:
            fourteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
            trend_filter["created_at"] = {"$gte": fourteen_days_ago}

        trend_pipeline = [
            {"$match": trend_filter},
            {"$group": {
                "_id": {"$substr": ["$created_at", 0, 10]},
                "total": {"$sum": 1},
                "sent": {"$sum": {"$cond": [{"$eq": ["$status", "SENT"]}, 1, 0]}},
                "delivered": {"$sum": {"$cond": [{"$in": ["$status", list(cls.SUCCESS_STATUSES)]}, 1, 0]}},
                "failed": {"$sum": {"$cond": [{"$in": ["$status", ["FAILED", "DEAD"]]}, 1, 0]}}
            }},
            {"$sort": {"_id": 1}}
        ]
        daily_trends = list(messages_col.aggregate(trend_pipeline))

        response = {
            "success": True,
            "organization_id": organization_id,
            "overview": {
                "total_messages": total_messages,
                "sent": sent_count,
                "delivered": delivered_count,
                "failed": failed_count,
                "dead": dead_count,
                "queued": queued_count,
                "processing": processing_count,
                "delivery_rate_percent": delivery_rate,
                "failure_rate_percent": failure_rate,
                "total_retries": total_retries,
                "total_manual_retries": total_manual_retries
            },
            "status_breakdown": status_counts,
            "channels": [
                {
                    "channel": item["_id"],
                    "count": item["count"],
                    "sent": item["sent"],
                    "delivered": item["delivered"],
                    "failed": item["failed"]
                }
                for item in channels
            ],
            "providers": [
                {
                    "provider": item["_id"],
                    "count": item["count"],
                    "sent": item["sent"],
                    "delivered": item["delivered"],
                    "failed": item["failed"],
                    "success_rate_percent": round(item["sent"] / item["count"] * 100, 2) if item["count"] > 0 else 0.0
                }
                for item in providers
            ],
            "dead_letter_queue": {
                "total_records": total_dlq,
                "pending_review": dlq_counts.get("PENDING_REVIEW", 0),
                "retry_requested": dlq_counts.get("RETRY_REQUESTED", 0),
                "retry_queued": dlq_counts.get("RETRY_QUEUED", 0),
                "resolved": dlq_counts.get("RESOLVED", 0)
            },
            "daily_trends": [
                {
                    "date": item["_id"],
                    "total": item["total"],
                    "sent": item["sent"],
                    "delivered": item["delivered"],
                    "failed": item["failed"]
                }
                for item in daily_trends
            ]
        }
        response["today"] = {
            "total_messages": sum(today_counts.values()),
            "sent": today_counts.get("SENT", 0),
            "delivered": sum(today_counts.get(status, 0) for status in cls.SUCCESS_STATUSES),
            "failed": today_counts.get("FAILED", 0),
            "dead": today_counts.get("DEAD", 0),
            "queued": today_counts.get("QUEUED", 0),
            "processing": today_counts.get("PROCESSING", 0)
        }

        if include_details:
            detail_filter = dict(match_filter)
            if not start_date and not end_date:
                detail_filter = dict(trend_filter)
            response["hourly_trends"] = cls._get_hourly_trends(messages_col, detail_filter)
            response["failure_reasons"] = cls._get_failure_reasons(messages_col, match_filter)
            latency_trends = cls._get_delivery_latency_trends(messages_col, match_filter)
            latency_count = sum(item["sample_size"] for item in latency_trends)
            latency_total = sum(item["average_ms"] * item["sample_size"] for item in latency_trends)
            response["overview"]["average_delivery_time_ms"] = (
                round(latency_total / latency_count, 2) if latency_count else None
            )
            response["overview"]["delivery_time_sample_size"] = latency_count
            response["delivery_latency_trends"] = latency_trends

        return response

    @staticmethod
    def _created_at_filter(start_date=None, end_date=None):
        bounds = {}
        parsed_start = date.fromisoformat(start_date) if start_date else None
        parsed_end = date.fromisoformat(end_date) if end_date else None
        if parsed_start and parsed_end and parsed_start > parsed_end:
            raise ValueError("start_date must be on or before end_date")
        if parsed_start:
            bounds["$gte"] = datetime.combine(parsed_start, time.min, tzinfo=timezone.utc).isoformat()
        if parsed_end:
            end_exclusive = parsed_end + timedelta(days=1)
            bounds["$lt"] = datetime.combine(end_exclusive, time.min, tzinfo=timezone.utc).isoformat()
        return {"created_at": bounds} if bounds else {}

    @classmethod
    def _get_hourly_trends(cls, messages_col, match_filter):
        pipeline = [
            {"$match": match_filter},
            {"$project": {
                "created_at_date": {
                    "$convert": {"input": "$created_at", "to": "date", "onError": None, "onNull": None}
                }
            }},
            {"$match": {"created_at_date": {"$ne": None}}},
            {"$group": {"_id": {"$hour": "$created_at_date"}, "total": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]
        return [{"hour": item["_id"], "total": item["total"]} for item in messages_col.aggregate(pipeline)]

    @staticmethod
    def _get_failure_reasons(messages_col, match_filter):
        pipeline = [
            {"$match": {**match_filter, "status": {"$in": ["FAILED", "DEAD"]}}},
            {"$group": {
                "_id": {"$ifNull": ["$delivery_error_code", {"$ifNull": ["$error_code", "UNSPECIFIED"]}]},
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        return [
            {
                "reason": "Not recorded" if item["_id"] == "UNSPECIFIED" else str(item["_id"]),
                "count": item["count"]
            }
            for item in messages_col.aggregate(pipeline)
        ]

    @classmethod
    def _get_delivery_latency_trends(cls, messages_col, match_filter):
        success_statuses = list(cls.SUCCESS_STATUSES)
        pipeline = [
            {"$match": match_filter},
            {"$project": {
                "created_at_date": {
                    "$convert": {"input": "$created_at", "to": "date", "onError": None, "onNull": None}
                },
                "success_transitions": {
                    "$filter": {
                        "input": {"$ifNull": ["$status_history", []]},
                        "as": "transition",
                        "cond": {"$and": [
                            {"$in": [{"$ifNull": ["$$transition.to", ""]}, success_statuses]},
                            {"$ne": [{"$ifNull": ["$$transition.timestamp", None]}, None]}
                        ]}
                    }
                }
            }},
            {"$addFields": {
                "delivery_at": {
                    "$convert": {
                        "input": {"$arrayElemAt": ["$success_transitions.timestamp", 0]},
                        "to": "date",
                        "onError": None,
                        "onNull": None
                    }
                }
            }},
            {"$addFields": {
                "latency_ms": {
                    "$cond": [
                        {"$and": [
                            {"$ne": ["$created_at_date", None]},
                            {"$ne": ["$delivery_at", None]}
                        ]},
                        {"$subtract": ["$delivery_at", "$created_at_date"]},
                        None
                    ]
                }
            }},
            {"$match": {"latency_ms": {"$gte": 0}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at_date", "timezone": "UTC"}},
                "average_ms": {"$avg": "$latency_ms"},
                "sample_size": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        return [
            {
                "date": item["_id"],
                "average_ms": round(item["average_ms"], 2),
                "sample_size": item["sample_size"]
            }
            for item in messages_col.aggregate(pipeline)
        ]
