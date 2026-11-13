"""
SenderX Analytics Pipelines Test Suite
"""

import uuid
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
