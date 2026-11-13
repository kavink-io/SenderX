from flask import current_app
from datetime import datetime, timezone, timedelta


class AnalyticsService:

    @classmethod
    def get_platform_analytics(cls):
        return cls._aggregate_analytics(organization_id=None)

    @classmethod
    def get_organization_analytics(cls, organization_id):
        if not organization_id:
            raise ValueError("organization_id is required for organization analytics")
        return cls._aggregate_analytics(organization_id=organization_id)

    @classmethod
    def _aggregate_analytics(cls, organization_id=None):
        messages_col = current_app.mongo_db["messages"]
        dlq_col = current_app.mongo_db["dead_letters"]

        match_filter = {}
        if organization_id is not None:
            match_filter["organization_id"] = organization_id

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
        failed_count = status_counts.get("FAILED", 0)
        dead_count = status_counts.get("DEAD", 0)
        queued_count = status_counts.get("QUEUED", 0)
        processing_count = status_counts.get("PROCESSING", 0)

        delivery_rate = round((sent_count / total_messages * 100), 2) if total_messages > 0 else 0.0
        failure_rate = round(((failed_count + dead_count) / total_messages * 100), 2) if total_messages > 0 else 0.0

        # 2. Channel distribution
        channel_pipeline = [
            {"$match": match_filter},
            {"$group": {
                "_id": "$channel",
                "count": {"$sum": 1},
                "sent": {"$sum": {"$cond": [{"$eq": ["$status", "SENT"]}, 1, 0]}},
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

        # 5. Recent daily message volume (last 14 days)
        fourteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        trend_filter = dict(match_filter)
        trend_filter["created_at"] = {"$gte": fourteen_days_ago}

        trend_pipeline = [
            {"$match": trend_filter},
            {"$group": {
                "_id": {"$substr": ["$created_at", 0, 10]},
                "total": {"$sum": 1},
                "sent": {"$sum": {"$cond": [{"$eq": ["$status", "SENT"]}, 1, 0]}},
                "failed": {"$sum": {"$cond": [{"$in": ["$status", ["FAILED", "DEAD"]]}, 1, 0]}}
            }},
            {"$sort": {"_id": 1}}
        ]
        daily_trends = list(messages_col.aggregate(trend_pipeline))

        return {
            "success": True,
            "organization_id": organization_id,
            "overview": {
                "total_messages": total_messages,
                "sent": sent_count,
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
                    "failed": item["failed"]
                }
                for item in channels
            ],
            "providers": [
                {
                    "provider": item["_id"],
                    "count": item["count"],
                    "sent": item["sent"],
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
                    "failed": item["failed"]
                }
                for item in daily_trends
            ]
        }
