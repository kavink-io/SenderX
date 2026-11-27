"""
SenderX Analytics Pipelines Test Suite
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest

from app import create_app
from app.modules.analytics.service import AnalyticsService
from app.modules.messages.repository import MessageRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


def test_zero_record_organization_analytics(app):
    with app.app_context():
        ghost_org_id = f"ghost-org-{uuid.uuid4().hex[:6]}"
        res = AnalyticsService.get_organization_analytics(ghost_org_id)

        assert res["success"] is True
        assert res["organization_id"] == ghost_org_id
        assert res["overview"]["total_messages"] == 0
        assert res["overview"]["sent"] == 0
        assert res["overview"]["delivery_rate_percent"] == 0.0
        assert res["channels"] == []
        assert res["providers"] == []
        assert res["today"]["total_messages"] == 0


def test_organization_scoped_analytics_isolation(app):
    with app.app_context():
        org_a = f"org-analytics-a-{uuid.uuid4().hex[:6]}"
        org_b = f"org-analytics-b-{uuid.uuid4().hex[:6]}"

        msg_a_id = f"msg-a-{uuid.uuid4()}"
        msg_b_id = f"msg-b-{uuid.uuid4()}"

        try:
            # Org A message: SENT
            MessageRepository.save({
                "message_id": msg_a_id,
                "organization_id": org_a,
                "channel": "email",
                "provider": "mock",
                "recipient": "a@example.com",
                "status": "SENT",
                "retry_count": 0,
                "created_at": MessageRepository._now()
            })

            # Org B message: FAILED
            MessageRepository.save({
                "message_id": msg_b_id,
                "organization_id": org_b,
                "channel": "sms",
                "provider": "mock",
                "recipient": "b@example.com",
                "status": "FAILED",
                "retry_count": 3,
                "created_at": MessageRepository._now()
            })

            # Check Org A analytics
            analytics_a = AnalyticsService.get_organization_analytics(org_a)
            assert analytics_a["overview"]["total_messages"] == 1
            assert analytics_a["overview"]["sent"] == 1
            assert analytics_a["overview"]["failed"] == 0
            assert analytics_a["overview"]["delivery_rate_percent"] == 100.0
            assert analytics_a["channels"][0]["channel"] == "email"

            # Check Org B analytics
            analytics_b = AnalyticsService.get_organization_analytics(org_b)
            assert analytics_b["overview"]["total_messages"] == 1
            assert analytics_b["overview"]["sent"] == 0
            assert analytics_b["overview"]["failed"] == 1
            assert analytics_b["overview"]["failure_rate_percent"] == 100.0
            assert analytics_b["channels"][0]["channel"] == "sms"

            # Platform analytics aggregates across both
            platform_analytics = AnalyticsService.get_platform_analytics()
            assert platform_analytics["overview"]["total_messages"] >= 2

        finally:
            MessageRepository._collection().delete_one({"message_id": msg_a_id})
            MessageRepository._collection().delete_one({"message_id": msg_b_id})


def test_organization_analytics_date_and_application_scopes(app):
    with app.app_context():
        organization_id = f"org-analytics-range-{uuid.uuid4().hex[:6]}"
        other_organization_id = f"org-analytics-other-{uuid.uuid4().hex[:6]}"
        application_id = f"app-analytics-{uuid.uuid4().hex[:6]}"
        other_application_id = f"app-analytics-other-{uuid.uuid4().hex[:6]}"
        sent_id = f"msg-analytics-sent-{uuid.uuid4()}"
        failed_id = f"msg-analytics-failed-{uuid.uuid4()}"
        other_app_id = f"msg-analytics-other-app-{uuid.uuid4()}"
        other_org_id = f"msg-analytics-other-org-{uuid.uuid4()}"
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        start = (now.date() - timedelta(days=2)).isoformat()
        created_at = (now - timedelta(seconds=10)).isoformat()

        try:
            MessageRepository.save({
                "message_id": sent_id,
                "organization_id": organization_id,
                "application_id": application_id,
                "channel": "email",
                "status": "SENT",
                "created_at": created_at,
                "status_history": [{
                    "from": "PROCESSING",
                    "to": "SENT",
                    "timestamp": now.isoformat()
                }]
            })
            MessageRepository.save({
                "message_id": failed_id,
                "organization_id": organization_id,
                "application_id": application_id,
                "channel": "sms",
                "status": "FAILED",
                "created_at": (now - timedelta(days=1)).isoformat(),
                "delivery_error_code": "RETRY_EXHAUSTED"
            })
            MessageRepository.save({
                "message_id": other_app_id,
                "organization_id": organization_id,
                "application_id": other_application_id,
                "channel": "telegram",
                "status": "FAILED",
                "created_at": created_at
            })
            MessageRepository.save({
                "message_id": other_org_id,
                "organization_id": other_organization_id,
                "application_id": application_id,
                "channel": "sms",
                "status": "FAILED",
                "created_at": created_at
            })

            analytics = AnalyticsService.get_organization_analytics(
                organization_id,
                start_date=today,
                end_date=today,
                application_id=application_id,
                include_details=True
            )
            assert analytics["overview"]["total_messages"] == 1
            assert analytics["overview"]["delivered"] == 1
            assert analytics["today"]["total_messages"] == 1
            assert analytics["daily_trends"][0]["total"] == 1
            assert analytics["overview"]["delivery_time_sample_size"] == 1
            assert analytics["overview"]["average_delivery_time_ms"] >= 0

            wider_range = AnalyticsService.get_organization_analytics(
                organization_id,
                start_date=start,
                end_date=today,
                application_id=application_id,
                include_details=True
            )
            assert wider_range["overview"]["total_messages"] == 2
            assert wider_range["failure_reasons"] == [
                {"reason": "RETRY_EXHAUSTED", "count": 1}
            ]

            with pytest.raises(ValueError, match="start_date"):
                AnalyticsService.get_organization_analytics(
                    organization_id,
                    start_date=today,
                    end_date=start
                )
        finally:
            MessageRepository._collection().delete_many({
                "message_id": {"$in": [sent_id, failed_id, other_app_id, other_org_id]}
            })
