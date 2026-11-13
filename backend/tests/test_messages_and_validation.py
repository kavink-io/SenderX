"""
SenderX Dynamic JSON Analyzer & Message Lifecycle Test Suite
"""

import uuid
import pytest
from unittest.mock import MagicMock
import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app
from app.validators.dynamic_json_validator import DynamicJSONValidator
from app.engine.status_manager import StatusManager
from app.modules.messages.service import MessageService
from app.modules.messages.repository import MessageRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()



def test_dynamic_json_analyzer_arbitrary_structures():
    """
    Requirement 7: Test arbitrary JSON structures with nested objects, arrays,
    nulls, integers, floats, booleans, and strings.
    """
    payload = {
        "channel": "email",
        "recipient": "user@example.com",
        "data": {
            "name": "Kavin",
            "age": 22,
            "rating": 4.95,
            "education": {
                "degree": "B.Tech",
                "department": "IT",
                "graduated": True
            },
            "skills": ["Python", "React", "MongoDB"],
            "notes": None,
            "metadata": {
                "tags": [{"key": "env", "value": "production"}],
                "active": True
            }
        }
    }

    result = DynamicJSONValidator.analyze(payload)
    assert result["valid"] is True
    assert result["errors"] == []
    analysis = result["analysis"]
    assert analysis is not None

    field_map = {item["field"]: item["type"] for item in analysis}
    assert field_map["channel"] == "string"
    assert field_map["recipient"] == "string"
    assert field_map["data.name"] == "string"
    assert field_map["data.age"] == "integer"
    assert field_map["data.rating"] == "float"
    assert field_map["data.education.graduated"] == "boolean"
    assert field_map["data.notes"] == "null"
    assert field_map["data.skills"] == "array"


def test_dynamic_json_analyzer_invalid_payloads():
    # Unsupported channel
    bad_channel = {"channel": "smoke_signals", "recipient": "test@test.com", "data": {"a": 1}}
    assert DynamicJSONValidator.analyze(bad_channel)["valid"] is False

    # Missing recipient
    no_recipient = {"channel": "email", "recipient": "", "data": {"a": 1}}
    assert DynamicJSONValidator.analyze(no_recipient)["valid"] is False

    # Empty data
    empty_data = {"channel": "email", "recipient": "test@test.com", "data": {}}
    assert DynamicJSONValidator.analyze(empty_data)["valid"] is False


def test_message_lifecycle_and_tenant_isolation(app):
    with app.app_context():
        org_a = f"org-a-{uuid.uuid4().hex[:6]}"
        org_b = f"org-b-{uuid.uuid4().hex[:6]}"

        payload = {
            "channel": "email",
            "provider": "mock",
            "recipient": "recipient@example.com",
            "data": {
                "subject": "Hello Tenant Isolation",
                "message": "Testing multi-tenant message isolation",
                "custom_dynamic_field": {"arbitrary": 12345}
            }
        }

        # 1. Create message for Org A
        res = MessageService.create_message(payload, organization_id=org_a)
        assert res["success"] is True
        msg_id = res["message"]["message_id"]

        try:
            # 2. Org A can retrieve message
            msg_a = MessageService.get_message(msg_id, organization_id=org_a)
            assert msg_a is not None
            assert msg_a["message_id"] == msg_id
            assert msg_a["organization_id"] == org_a
            assert msg_a["status"] == "CREATED"
            # Verify dynamic fields preserved
            assert msg_a["data"]["custom_dynamic_field"]["arbitrary"] == 12345

            # 3. Org B CANNOT retrieve Org A's message
            msg_b = MessageService.get_message(msg_id, organization_id=org_b)
            assert msg_b is None

            # 4. Valid status transition: CREATED -> VALIDATED -> QUEUED
            assert StatusManager.can_transition("CREATED", "VALIDATED") is True
            assert StatusManager.can_transition("VALIDATED", "QUEUED") is True
            assert StatusManager.can_transition("QUEUED", "PROCESSING") is True
            assert StatusManager.can_transition("PROCESSING", "SENT") is True

            # 5. Invalid status transition rejected
            assert StatusManager.can_transition("SENT", "PROCESSING") is False
            assert StatusManager.can_transition("CREATED", "SENT") is False

            # 6. Dead to Queued transition allowed for manual retry
            assert StatusManager.can_transition("DEAD", "QUEUED") is True

            # 7. Pagination and filtering
            list_res = MessageService.get_all_messages(organization_id=org_a, status="CREATED")
            assert len(list_res["items"]) >= 1
            assert list_res["pagination"]["total"] >= 1

        finally:
            MessageRepository._collection().delete_one({"message_id": msg_id})


def test_message_queue_api_successful_and_duplicate(app, client):
    """
    Test Task 2 requirements:
    - POST /api/v1/messages/<message_id>/queue
    - Successful queueing from CREATED
    - Returns message_id, status, and task_id
    - Rejects duplicate queue request with 409
    - Rejects invalid status transition with 400
    - Rejects cross-tenant access with 404
    """
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        role_id_a = str(uuid.uuid4())
        role_id_b = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Create Org A and User A
        OrganizationRepository.create({"organization_id": org_a, "name": "Org A", "slug": f"org-a-{suffix}", "status": "ACTIVE"})
        RoleRepository.create({"role_id": role_id_a, "organization_id": org_a, "name": "Msg Manager A", "scope": "ORGANIZATION", "permissions": ["organization:messages:manage", "organization:messages:create", "organization:messages:read"], "is_system_role": False})
        UserRepository.create({"user_id": user_a, "organization_id": org_a, "name": "User A", "email": f"user-a-{suffix}@test.io", "password_hash": password_hash, "role_ids": [role_id_a], "is_active": True})

        # Create Org B and User B
        OrganizationRepository.create({"organization_id": org_b, "name": "Org B", "slug": f"org-b-{suffix}", "status": "ACTIVE"})
        RoleRepository.create({"role_id": role_id_b, "organization_id": org_b, "name": "Msg Manager B", "scope": "ORGANIZATION", "permissions": ["organization:messages:manage", "organization:messages:create", "organization:messages:read"], "is_system_role": False})
        UserRepository.create({"user_id": user_b, "organization_id": org_b, "name": "User B", "email": f"user-b-{suffix}@test.io", "password_hash": password_hash, "role_ids": [role_id_b], "is_active": True})

        token_a = create_access_token(identity=user_a, additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a, "role_ids": [role_id_a], "email": f"user-a-{suffix}@test.io"})
        token_b = create_access_token(identity=user_b, additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b, "role_ids": [role_id_b], "email": f"user-b-{suffix}@test.io"})

        # Create message for Org A
        create_res = MessageService.create_message({
            "channel": "email",
            "provider": "mock",
            "recipient": "test@example.com",
            "data": {"subject": "Queue Test", "message": "Test Message"}
        }, organization_id=org_a)
        msg_id = create_res["message"]["message_id"]

        try:
            # 1. Cross-tenant access: Org B tries to queue Org A's message -> 404
            res_cross = client.post(f"/api/v1/messages/{msg_id}/queue", headers={"Authorization": f"Bearer {token_b}"})
            assert res_cross.status_code == 404
            assert res_cross.get_json()["success"] is False

            # 2. Successful queueing by Org A -> 200
            fake_task = MagicMock()
            fake_task.id = f"task-{uuid.uuid4().hex[:8]}"
            orig_send_task = app.celery.send_task
            app.celery.send_task = MagicMock(return_value=fake_task)

            try:
                res_queue = client.post(f"/api/v1/messages/{msg_id}/queue", headers={"Authorization": f"Bearer {token_a}"})
                assert res_queue.status_code == 200
                data_queue = res_queue.get_json()
                assert data_queue["success"] is True
                assert data_queue["message_id"] == msg_id
                assert data_queue["status"] == "QUEUED"
                assert data_queue["task_id"] == fake_task.id

                # Verify in DB
                msg_db = MessageRepository.find_by_id(msg_id, organization_id=org_a)
                assert msg_db["status"] == "QUEUED"

                # 3. Duplicate queue request -> 409 Conflict
                res_dup = client.post(f"/api/v1/messages/{msg_id}/queue", headers={"Authorization": f"Bearer {token_a}"})
                assert res_dup.status_code == 409
                assert res_dup.get_json()["success"] is False
                assert "already queued" in res_dup.get_json()["message"].lower()

                # 4. Invalid status queue request: change status to SENT then try to queue -> 400 Bad Request
                MessageRepository.update_status(msg_id, "PROCESSING", "QUEUED", organization_id=org_a)
                MessageRepository.update_status(msg_id, "SENT", "PROCESSING", organization_id=org_a)

                res_invalid = client.post(f"/api/v1/messages/{msg_id}/queue", headers={"Authorization": f"Bearer {token_a}"})
                assert res_invalid.status_code == 400
                assert res_invalid.get_json()["success"] is False
                assert "cannot queue message in status 'sent'" in res_invalid.get_json()["message"].lower()

            finally:
                app.celery.send_task = orig_send_task

        finally:
            MessageRepository._collection().delete_one({"message_id": msg_id})
            OrganizationRepository._collection().delete_many({"organization_id": {"$in": [org_a, org_b]}})
            RoleRepository._collection().delete_many({"organization_id": {"$in": [org_a, org_b]}})
            UserRepository._collection().delete_many({"organization_id": {"$in": [org_a, org_b]}})


def test_message_queue_api_dispatch_failure_rollback(app):
    """
    Test Task 2 requirements:
    - When Celery broker dispatch fails, message status is safely rolled back to CREATED
    - Returns 503 error
    """
    with app.app_context():
        org_id = f"org-rollback-{uuid.uuid4().hex[:6]}"
        create_res = MessageService.create_message({
            "channel": "email",
            "provider": "mock",
            "recipient": "rollback@example.com",
            "data": {"subject": "Rollback Test", "message": "Rollback Message"}
        }, organization_id=org_id)
        msg_id = create_res["message"]["message_id"]

        try:
            # Confirm initial status is CREATED
            msg = MessageRepository.find_by_id(msg_id, organization_id=org_id)
            assert msg["status"] == "CREATED"

            # Mock Celery send_task to simulate broker failure
            def raise_broker_error(*args, **kwargs):
                raise ConnectionError("RabbitMQ broker connection lost")

            orig_send_task = app.celery.send_task
            app.celery.send_task = MagicMock(side_effect=raise_broker_error)

            try:
                result = MessageService.queue_message(msg_id, organization_id=org_id)
                assert result["success"] is False
                assert result["status_code"] == 503
                assert "rolled back" in result["message"].lower()

                # Verify message status was rolled back to CREATED in the database
                refetched = MessageRepository.find_by_id(msg_id, organization_id=org_id)
                assert refetched["status"] == "CREATED"

            finally:
                app.celery.send_task = orig_send_task

        finally:
            MessageRepository._collection().delete_one({"message_id": msg_id})

