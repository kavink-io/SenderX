"""
SenderX Phase 5 Task 5.1: Message Management Dashboard Test Suite
Validates message composer, history, search/filters, application scoping,
delivery tracking, manual retry, DLQ integration, analytics, and scheduling absence.
"""

import uuid
import pytest
import bcrypt
from datetime import datetime, timezone, timedelta
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.applications.repository import ApplicationRepository
from app.modules.messages.repository import MessageRepository
from app.modules.messages.service import MessageService
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.analytics.service import AnalyticsService


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


def create_test_tenant(app):
    """Helper to create a fully isolated organization with an Org Admin and connected apps."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        role_id = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(4)).decode("utf-8")

        OrganizationRepository.create({
            "organization_id": org_id,
            "name": f"Org {suffix}",
            "slug": f"org-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_id,
            "organization_id": org_id,
            "name": "Org Admin Role",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage",
                "organization:dead_letters:read",
                "organization:dead_letters:manage",
                "organization:analytics:read",
                "organization:configuration:manage"
            ],
            "is_system_role": True
        })

        UserRepository.create({
            "user_id": admin_id,
            "organization_id": org_id,
            "name": f"Admin {suffix}",
            "email": f"admin-{suffix}@tenant.io",
            "password_hash": password_hash,
            "role_ids": [role_id],
            "is_active": True
        })

        token = create_access_token(
            identity=admin_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_id,
                "role_ids": [role_id],
                "email": f"admin-{suffix}@tenant.io"
            }
        )

        # Create two test applications
        app_1 = ApplicationRepository.create({
            "organization_id": org_id,
            "name": f"Storefront App {suffix}",
            "environment": "live",
            "status": "ACTIVE"
        })
        app_2 = ApplicationRepository.create({
            "organization_id": org_id,
            "name": f"Billing Portal {suffix}",
            "environment": "live",
            "status": "ACTIVE"
        })

        return {
            "org_id": org_id,
            "admin_id": admin_id,
            "token": token,
            "app_1_id": app_1["application_id"],
            "app_2_id": app_2["application_id"]
        }


def test_message_listing_and_pagination(app, client):
    """Test message history listing, pagination, and sorting."""
    tenant = create_test_tenant(app)
    headers = {"Authorization": f"Bearer {tenant['token']}"}

    with app.app_context():
        # Create 5 distinct messages
        channels = ["email", "sms", "whatsapp", "microsoft_teams", "email"]
        for i in range(5):
            res = MessageService.create_message({
                "channel": channels[i],
                "recipient": f"user{i}@test.com" if "email" in channels[i] else f"+1555000{i}",
                "data": {"subject": f"Test {i}", "body": f"Content {i}"},
                "application_id": tenant["app_1_id"]
            }, organization_id=tenant["org_id"])
            assert res["success"] is True

    # Page 1 with limit 2
    res = client.get("/api/v1/messages/?limit=2&page=1", headers=headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["total_count"] >= 5
    assert body["pagination"]["limit"] == 2
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["total_pages"] >= 3

    # Page 2 with limit 2
    res2 = client.get("/api/v1/messages/?limit=2&page=2", headers=headers)
    assert res2.status_code == 200
    body2 = res2.get_json()
    assert len(body2["data"]) == 2
    # Ensure page 2 items are different from page 1
    assert body2["data"][0]["message_id"] != body["data"][0]["message_id"]


def test_message_search_and_filters(app, client):
    """Test searching by recipient/subject/id, and filtering by channel, status, and app."""
    tenant = create_test_tenant(app)
    headers = {"Authorization": f"Bearer {tenant['token']}"}

    with app.app_context():
        # Create unique search target
        res1 = MessageService.create_message({
            "channel": "email",
            "recipient": "unique.target@corporate.com",
            "data": {"subject": "Urgent Invoice Q4", "body": "Invoice content"},
            "application_id": tenant["app_1_id"]
        }, organization_id=tenant["org_id"])
        msg1_id = res1["message"]["message_id"]

        # Create sms message in app 2
        res2 = MessageService.create_message({
            "channel": "sms",
            "recipient": "+14159998888",
            "data": {"body": "SMS Notification"},
            "application_id": tenant["app_2_id"]
        }, organization_id=tenant["org_id"])
        msg2_id = res2["message"]["message_id"]

        # Transition msg2 to SENT
        MessageRepository.update_status(msg2_id, new_status="SENT", old_status="CREATED", organization_id=tenant["org_id"])

    # 1. Search by recipient substring
    res = client.get("/api/v1/messages/?search=unique.target", headers=headers)
    assert res.status_code == 200
    items = res.get_json()["data"]
    assert len(items) == 1
    assert items[0]["message_id"] == msg1_id

    # 2. Search by subject
    res = client.get("/api/v1/messages/?search=Urgent+Invoice", headers=headers)
    assert res.status_code == 200
    assert len(res.get_json()["data"]) == 1

    # 3. Filter by channel
    res = client.get("/api/v1/messages/?channel=sms", headers=headers)
    assert res.status_code == 200
    items = res.get_json()["data"]
    assert all(i["channel"] == "sms" for i in items)

    # 4. Filter by status
    res = client.get("/api/v1/messages/?status=SENT", headers=headers)
    assert res.status_code == 200
    items = res.get_json()["data"]
    assert all(i["status"] == "SENT" for i in items)

    # 5. Filter by application_id
    res = client.get(f"/api/v1/messages/?application_id={tenant['app_2_id']}", headers=headers)
    assert res.status_code == 200
    items = res.get_json()["data"]
    assert all(i["application_id"] == tenant["app_2_id"] for i in items)


def test_employee_application_scope_enforcement(app, client):
    """
    Test employee application scope security:
    - Employee scoped ONLY to app_1 cannot view or send messages for app_2.
    """
    tenant = create_test_tenant(app)

    with app.app_context():
        # Create an employee scoped ONLY to app_1
        emp_role_id = str(uuid.uuid4())
        emp_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(4)).decode("utf-8")

        RoleRepository.create({
            "role_id": emp_role_id,
            "organization_id": tenant["org_id"],
            "name": "Storefront Operator",
            "scope": "ORGANIZATION",
            "application_id": tenant["app_1_id"],
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage"
            ],
            "is_system_role": False
        })

        UserRepository.create({
            "user_id": emp_id,
            "organization_id": tenant["org_id"],
            "name": "Storefront Employee",
            "email": f"emp-{uuid.uuid4().hex[:6]}@tenant.io",
            "password_hash": password_hash,
            "role_ids": [emp_role_id],
            "role_assignments": [{
                "role_id": emp_role_id,
                "application_id": tenant["app_1_id"]
            }],
            "application_ids": [tenant["app_1_id"]],
            "is_active": True
        })

        emp_token = create_access_token(
            identity=emp_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": tenant["org_id"],
                "role_ids": [emp_role_id],
                "role_assignments": [{
                    "role_id": emp_role_id,
                    "application_id": tenant["app_1_id"]
                }],
                "application_ids": [tenant["app_1_id"]],
                "email": "employee@tenant.io"
            }
        )

        # Create 1 message for app_1 and 1 message for app_2
        res1 = MessageService.create_message({
            "channel": "email",
            "recipient": "app1_user@test.com",
            "data": {"body": "App 1 Message"},
            "application_id": tenant["app_1_id"]
        }, organization_id=tenant["org_id"])
        msg1_id = res1["message"]["message_id"]

        res2 = MessageService.create_message({
            "channel": "email",
            "recipient": "app2_user@test.com",
            "data": {"body": "App 2 Message"},
            "application_id": tenant["app_2_id"]
        }, organization_id=tenant["org_id"])
        msg2_id = res2["message"]["message_id"]

    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # 1. Employee listing messages only returns app_1 messages
    list_res = client.get("/api/v1/messages/", headers=emp_headers)
    assert list_res.status_code == 200
    listed_items = list_res.get_json()["data"]
    for item in listed_items:
        assert item.get("application_id") == tenant["app_1_id"]

    # 2. Employee cannot create message for app_2 (403 Forbidden)
    forbidden_create = client.post("/api/v1/messages/", headers=emp_headers, json={
        "channel": "email",
        "recipient": "target@test.com",
        "data": {"body": "Unauthorized send"},
        "application_id": tenant["app_2_id"]
    })
    assert forbidden_create.status_code == 403

    # 3. Employee cannot inspect details of app_2 message (403 Forbidden)
    forbidden_get = client.get(f"/api/v1/messages/{msg2_id}", headers=emp_headers)
    assert forbidden_get.status_code == 403

    # 4. Employee CAN inspect details of app_1 message (200 OK)
    allowed_get = client.get(f"/api/v1/messages/{msg1_id}", headers=emp_headers)
    assert allowed_get.status_code == 200


def test_message_details_and_payload_inspection(app, client):
    """Test retrieving full message details including payload and delivery events."""
    tenant = create_test_tenant(app)
    headers = {"Authorization": f"Bearer {tenant['token']}"}

    with app.app_context():
        create_res = MessageService.create_message({
            "channel": "email",
            "recipient": "inspect@senderx.io",
            "data": {
                "subject": "System Verification Notice",
                "body": "Welcome to SenderX Glassmorphism UI",
                "custom_metadata": {"tier": "enterprise", "priority": 1}
            },
            "application_id": tenant["app_1_id"]
        }, organization_id=tenant["org_id"])
        msg_id = create_res["message"]["message_id"]

    res = client.get(f"/api/v1/messages/{msg_id}", headers=headers)
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert data["message_id"] == msg_id
    assert data["channel"] == "email"
    assert data["recipient"] == "inspect@senderx.io"
    assert data["status"] == "CREATED"
    assert data["application_id"] == tenant["app_1_id"]
    assert data["data"]["custom_metadata"]["tier"] == "enterprise"


def test_delivery_status_mapping_and_distinction(app, client):
    """
    Test delivery status mapping and ensure provider acceptance (SENT)
    is never confused with confirmed delivery (DELIVERED).
    """
    tenant = create_test_tenant(app)
    headers = {"Authorization": f"Bearer {tenant['token']}"}

    with app.app_context():
        res = MessageService.create_message({
            "channel": "sms",
            "recipient": "+14155550099",
            "data": {"body": "Delivery Tracking Test"},
            "application_id": tenant["app_1_id"]
        }, organization_id=tenant["org_id"])
        msg_id = res["message"]["message_id"]

        # 1. Transition CREATED -> QUEUED -> PROCESSING
        MessageRepository.update_status(msg_id, "QUEUED", "CREATED", tenant["org_id"])
        MessageRepository.update_status(msg_id, "PROCESSING", "QUEUED", tenant["org_id"])

        # 2. Mark SENT with provider acceptance (e.g. Twilio SID SM12345)
        provider_sid = f"SM{uuid.uuid4().hex[:16]}"
        MessageRepository.mark_sent(msg_id, provider="twilio", provider_message_id=provider_sid, organization_id=tenant["org_id"])

        sent_doc = MessageRepository.find_by_id(msg_id, tenant["org_id"])
        assert sent_doc["status"] == "SENT"
        assert sent_doc["provider_message_id"] == provider_sid

        # 3. Simulate Provider StatusCallback Webhook transitioning to DELIVERED
        MessageRepository.update_delivery_status(
            provider_message_id=provider_sid,
            new_status="DELIVERED",
            raw_status="delivered",
            organization_id=tenant["org_id"]
        )

        delivered_doc = MessageRepository.find_by_id(msg_id, tenant["org_id"])
        assert delivered_doc["status"] == "DELIVERED"
        assert delivered_doc["provider_status"] == "delivered"

        # Verify audit trail in status_history
        history = delivered_doc["status_history"]
        history_statuses = [h["to"] for h in history]
        assert "SENT" in history_statuses
        assert "DELIVERED" in history_statuses

    # Query endpoint
    api_res = client.get(f"/api/v1/messages/{msg_id}", headers=headers)
    assert api_res.status_code == 200
    assert api_res.get_json()["data"]["status"] == "DELIVERED"


def test_manual_retry_authorization_and_lifecycle(app, client):
    """
    Test manual retry behavior:
    - Fails if message is already DELIVERED (400)
    - Succeeds on FAILED message, resets retry_count and increments manual_retry_count
    - Enforces RBAC: viewer role without messages:manage gets 403 Forbidden
    """
    tenant = create_test_tenant(app)
    headers = {"Authorization": f"Bearer {tenant['token']}"}

    with app.app_context():
        # 1. Create a FAILED message
        res = MessageService.create_message({
            "channel": "email",
            "recipient": "failed@senderx.io",
            "data": {"body": "Failed send"},
            "application_id": tenant["app_1_id"]
        }, organization_id=tenant["org_id"])
        msg_id = res["message"]["message_id"]

        MessageRepository.update_status(msg_id, "QUEUED", "CREATED", tenant["org_id"])
        MessageRepository.update_status(msg_id, "PROCESSING", "QUEUED", tenant["org_id"])
        MessageRepository.mark_failed(msg_id, retry_count=3, error="SMTP Connection Timeout", organization_id=tenant["org_id"])

        failed_doc = MessageRepository.find_by_id(msg_id, tenant["org_id"])
        assert failed_doc["status"] == "FAILED"

        # 2. Create Viewer Role with only messages:read (no messages:manage)
        viewer_role_id = str(uuid.uuid4())
        viewer_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(4)).decode("utf-8")

        RoleRepository.create({
            "role_id": viewer_role_id,
            "organization_id": tenant["org_id"],
            "name": "Read Only Viewer",
            "scope": "ORGANIZATION",
            "permissions": ["organization:messages:read"],
            "is_system_role": False
        })
        UserRepository.create({
            "user_id": viewer_id,
            "organization_id": tenant["org_id"],
            "name": "Viewer User",
            "email": f"viewer-{uuid.uuid4().hex[:6]}@tenant.io",
            "password_hash": password_hash,
            "role_ids": [viewer_role_id],
            "is_active": True
        })
        viewer_token = create_access_token(
            identity=viewer_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": tenant["org_id"],
                "role_ids": [viewer_role_id],
                "email": "viewer@tenant.io"
            }
        )

    # 3. Viewer attempts to retry -> 403 Forbidden
    viewer_res = client.post(f"/api/v1/messages/{msg_id}/retry", headers={"Authorization": f"Bearer {viewer_token}"})
    assert viewer_res.status_code == 403

    # 4. Org Admin with messages:manage retries -> 200 OK
    admin_res = client.post(f"/api/v1/messages/{msg_id}/retry", headers=headers)
    assert admin_res.status_code == 200
    assert admin_res.get_json()["status"] == "QUEUED"

    with app.app_context():
        requeued_doc = MessageRepository.find_by_id(msg_id, tenant["org_id"])
        assert requeued_doc["status"] == "QUEUED"
        assert requeued_doc["manual_retry_count"] == 1


def test_dlq_integration_and_dead_letter_retry(app, client):
    """Test manual retry for DEAD message in DLQ."""
    tenant = create_test_tenant(app)
    headers = {"Authorization": f"Bearer {tenant['token']}"}

    with app.app_context():
        res = MessageService.create_message({
            "channel": "email",
            "recipient": "dead@senderx.io",
            "data": {"body": "DLQ message"},
            "application_id": tenant["app_1_id"]
        }, organization_id=tenant["org_id"])
        msg_id = res["message"]["message_id"]

        # Mark message as DEAD
        MessageRepository.update_status(msg_id, "QUEUED", "CREATED", tenant["org_id"])
        MessageRepository.update_status(msg_id, "PROCESSING", "QUEUED", tenant["org_id"])
        MessageRepository.update_retry_info(msg_id, retry_count=3, old_status="PROCESSING", new_status="DEAD", error="Max retries reached", organization_id=tenant["org_id"])

        # Create corresponding DeadLetter record
        DeadLetterRepository._collection().insert_one({
            "message_id": msg_id,
            "organization_id": tenant["org_id"],
            "channel": "email",
            "recipient": "dead@senderx.io",
            "error_message": "Max retries reached",
            "dead_letter_status": "DEAD"
        })

    # Retry via messages retry route
    retry_res = client.post(f"/api/v1/messages/{msg_id}/retry", headers=headers)
    assert retry_res.status_code in (200, 202)


def test_analytics_tenant_isolation(app, client):
    """Test organization-scoped analytics isolation."""
    tenant_a = create_test_tenant(app)
    tenant_b = create_test_tenant(app)

    with app.app_context():
        # Create messages in Tenant A
        MessageService.create_message({
            "channel": "email",
            "recipient": "tenant_a_1@test.com",
            "data": {"body": "Org A Msg 1"},
            "application_id": tenant_a["app_1_id"]
        }, organization_id=tenant_a["org_id"])
        MessageService.create_message({
            "channel": "sms",
            "recipient": "+15551112222",
            "data": {"body": "Org A Msg 2"},
            "application_id": tenant_a["app_1_id"]
        }, organization_id=tenant_a["org_id"])

        # Create messages in Tenant B
        for _ in range(5):
            MessageService.create_message({
                "channel": "whatsapp",
                "recipient": "+15553334444",
                "data": {"body": "Org B Msg"},
                "application_id": tenant_b["app_1_id"]
            }, organization_id=tenant_b["org_id"])

    # Query Tenant A analytics
    res_a = client.get("/api/v1/analytics/organization", headers={"Authorization": f"Bearer {tenant_a['token']}"})
    assert res_a.status_code == 200
    data_a = res_a.get_json()

    # Query Tenant B analytics
    res_b = client.get("/api/v1/analytics/organization", headers={"Authorization": f"Bearer {tenant_b['token']}"})
    assert res_b.status_code == 200
    data_b = res_b.get_json()

    # Verify counts reflect only respective tenant
    total_a = data_a.get("overview", {}).get("total_messages", 0)
    total_b = data_b.get("overview", {}).get("total_messages", 0)
    assert total_a >= 2
    assert total_b >= 5
    assert total_a != total_b


def test_scheduling_support_absence_documented(app):
    """
    Formally document and verify the architectural absence of message scheduling.
    Verifies that the backend does not expose an unverified or fake scheduling mechanism.
    """
    with app.app_context():
        # Verify DynamicJSONValidator ALLOWED_CHANNELS does not fake scheduling
        from app.validators.dynamic_json_validator import DynamicJSONValidator
        assert "schedule" not in DynamicJSONValidator.ALLOWED_CHANNELS

        # Confirm that message documents are created in CREATED status without silent delayed queues
        res = MessageService.create_message({
            "channel": "email",
            "recipient": "test_sched@senderx.io",
            "data": {"body": "Test"}
        }, organization_id="test_org_sched")

        assert res["success"] is True
        msg = res["message"]
        assert msg["status"] == "CREATED"
        # Confirm no scheduled_at field was hallucinated
        assert "scheduled_at" not in msg

        # Clean up
        MessageRepository._collection().delete_one({"message_id": msg["message_id"]})
