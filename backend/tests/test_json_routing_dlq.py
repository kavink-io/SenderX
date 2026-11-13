"""
SenderX Phase 4, Task 2: JSON Routing, Immutable Payloads & DLQ Management Test Suite
Tests for:
1. Valid email routing
2. Valid SMS routing
3. Valid WhatsApp routing
4. Valid Teams routing
5. Missing channel moves to DLQ
6. Unsupported channel moves to DLQ
7. Invalid JSON structure & depth limits move to DLQ
8. Missing required fields move to DLQ
9. Original JSON remains unchanged after editing
10. Payload version history tracking
11. Unauthorized users cannot edit (RBAC)
12. Cross-organization access rejection (Multi-tenant isolation)
13. Invalid edited JSON cannot be dispatched
14. Editing alone does not dispatch (requires explicit retry)
15. Explicit retry dispatches valid payload
16. Duplicate retry idempotency (prevents duplicate dispatch)
17. Full audit trail logging
18. Production mock fallback rejection
19. DLQ direct payload edit and retry integration
"""

import copy
import json
import uuid
from unittest.mock import patch, MagicMock

import bcrypt
import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.payloads.repository import PayloadRepository
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.messages.repository import MessageRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def test_setup(app):
    """
    Sets up two isolated organizations (Org A and Org B)
    with admin, editor, and read-only users.
    """
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())

        role_admin_a = str(uuid.uuid4())
        role_readonly_a = str(uuid.uuid4())
        role_admin_b = str(uuid.uuid4())

        user_admin_a = str(uuid.uuid4())
        user_readonly_a = str(uuid.uuid4())
        user_admin_b = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Org A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Routing Org A {suffix}",
            "slug": f"route-org-a-{suffix}",
            "status": "ACTIVE"
        })

        # Role with full payload & DLQ permissions
        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a,
            "name": "Payload Admin A",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage",
                "organization:payloads:read",
                "organization:payloads:edit",
                "organization:payloads:validate",
                "organization:dlq:read",
                "organization:dlq:retry",
                "organization:dead_letters:read",
                "organization:dead_letters:manage"
            ],
            "is_system_role": False
        })

        # Role with read-only permissions
        RoleRepository.create({
            "role_id": role_readonly_a,
            "organization_id": org_a,
            "name": "Payload Viewer A",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:payloads:read",
                "organization:dlq:read",
                "organization:messages:read"
            ],
            "is_system_role": False
        })

        # Users for Org A
        UserRepository.create({
            "user_id": user_admin_a,
            "organization_id": org_a,
            "name": "Admin User A",
            "email": f"admin-a-{suffix}@routing.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_a],
            "is_active": True
        })

        UserRepository.create({
            "user_id": user_readonly_a,
            "organization_id": org_a,
            "name": "Viewer User A",
            "email": f"viewer-a-{suffix}@routing.io",
            "password_hash": password_hash,
            "role_ids": [role_readonly_a],
            "is_active": True
        })

        # Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Routing Org B {suffix}",
            "slug": f"route-org-b-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b,
            "name": "Payload Admin B",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage",
                "organization:payloads:read",
                "organization:payloads:edit",
                "organization:payloads:validate",
                "organization:dlq:read",
                "organization:dlq:retry"
            ],
            "is_system_role": False
        })

        UserRepository.create({
            "user_id": user_admin_b,
            "organization_id": org_b,
            "name": "Admin User B",
            "email": f"admin-b-{suffix}@routing.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_b],
            "is_active": True
        })

        token_admin_a = create_access_token(
            identity=user_admin_a,
            additional_claims={"account_type": "ORGANIZATION_USER"}
        )
        token_readonly_a = create_access_token(
            identity=user_readonly_a,
            additional_claims={"account_type": "ORGANIZATION_USER"}
        )
        token_admin_b = create_access_token(
            identity=user_admin_b,
            additional_claims={"account_type": "ORGANIZATION_USER"}
        )

        return {
            "org_a": org_a,
            "org_b": org_b,
            "user_admin_a": user_admin_a,
            "user_readonly_a": user_readonly_a,
            "user_admin_b": user_admin_b,
            "token_admin_a": token_admin_a,
            "token_readonly_a": token_readonly_a,
            "token_admin_b": token_admin_b,
            "headers_admin_a": {"Authorization": f"Bearer {token_admin_a}"},
            "headers_readonly_a": {"Authorization": f"Bearer {token_readonly_a}"},
            "headers_admin_b": {"Authorization": f"Bearer {token_admin_b}"}
        }


# ===========================================================================
# 1. CHANNEL ROUTING TESTS (Email, SMS, WhatsApp, Teams)
# ===========================================================================

def test_valid_email_routing(client, test_setup):
    headers = test_setup["headers_admin_a"]
    payload = {
        "channel": "email",
        "recipient": "kavin@example.com",
        "data": {
            "subject": "System Alert",
            "text": "Server memory is nominal."
        }
    }

    with patch("app.modules.messages.service.MessageService.queue_message") as mock_queue:
        mock_queue.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["status"] == "ROUTED"
        assert data["channel"] == "email"
        assert "payload_id" in data
        assert "message_id" in data
        mock_queue.assert_called_once()

    # Verify immutable original record exists
    payload_id = data["payload_id"]
    get_res = client.get(f"/api/v1/payloads/{payload_id}", headers=headers)
    assert get_res.status_code == 200
    record = get_res.get_json()["data"]
    assert record["original_payload"]["channel"] == "email"
    assert record["original_payload"]["recipient"] == "kavin@example.com"
    assert record["version"] == 1


def test_valid_sms_routing(client, test_setup):
    headers = test_setup["headers_admin_a"]
    payload = {
        "channel": "sms",
        "recipient": "+14155552671",
        "data": {
            "text": "Your verification code is 492011"
        }
    }

    with patch("app.modules.messages.service.MessageService.queue_message") as mock_queue:
        mock_queue.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["status"] == "ROUTED"
        assert data["channel"] == "sms"


def test_valid_whatsapp_routing(client, test_setup):
    headers = test_setup["headers_admin_a"]
    payload = {
        "channel": "whatsapp",
        "recipient": "+14155552671",
        "data": {
            "type": "text",
            "text": {
                "body": "Hello from SenderX WhatsApp!"
            }
        }
    }

    with patch("app.modules.messages.service.MessageService.queue_message") as mock_queue:
        mock_queue.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["status"] == "ROUTED"
        assert data["channel"] == "whatsapp"


def test_valid_teams_routing(client, test_setup):
    headers = test_setup["headers_admin_a"]
    payload = {
        "channel": "teams",
        "recipient": "chat:19:meeting_abcdef123456@thread.v2",
        "data": {
            "text": "Daily scrum notes updated."
        }
    }

    with patch("app.modules.messages.service.MessageService.queue_message") as mock_queue:
        mock_queue.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["status"] == "ROUTED"
        # Channel alias normalized
        assert data["channel"] == "teams"


# ===========================================================================
# 2. DLQ INTEGRATION ON ROUTING & VALIDATION FAILURES
# ===========================================================================

def test_missing_channel_moves_to_dlq(client, test_setup):
    headers = test_setup["headers_admin_a"]
    payload = {
        "recipient": "client@domain.com",
        "data": {"text": "No channel specified"}
    }

    res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["status"] == "IN_DLQ"
    assert data["failure_code"] == "MISSING_CHANNEL"
    assert "Channel is missing" in data["message"]

    # Verify document exists in dead_letters collection
    payload_id = data["payload_id"]
    dlq_res = client.get(f"/api/v1/dead-letters/organization/{payload_id}", headers=headers)
    assert dlq_res.status_code == 200
    dlq_entry = dlq_res.get_json()["data"]
    assert dlq_entry is not None
    assert dlq_entry["failure_code"] == "MISSING_CHANNEL"
    assert dlq_entry["dead_letter_status"] == "PENDING_REVIEW"


def test_unsupported_channel_moves_to_dlq(client, test_setup):
    headers = test_setup["headers_admin_a"]
    payload = {
        "channel": "carrier_pigeon",
        "recipient": "rooftop",
        "data": {"note": "fly fast"}
    }

    res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert data["status"] == "IN_DLQ"
    assert data["failure_code"] == "UNSUPPORTED_CHANNEL"

    # Confirm in DLQ
    dlq_res = client.get(f"/api/v1/dead-letters/organization/{data['payload_id']}", headers=headers)
    assert dlq_res.status_code == 200
    dlq_entry = dlq_res.get_json()["data"]
    assert dlq_entry is not None
    assert dlq_entry["failure_code"] == "UNSUPPORTED_CHANNEL"


def test_invalid_json_structure_and_depth_limits(client, test_setup):
    headers = test_setup["headers_admin_a"]

    # 1. Non-dict root
    res1 = client.post("/api/v1/payloads/ingest", json=["not", "a", "dict"], headers=headers)
    assert res1.status_code == 400
    assert res1.get_json()["failure_code"] == "INVALID_JSON_STRUCTURE"

    # 2. Deeply nested JSON (> 20 levels)
    deep_dict = {"channel": "email", "recipient": "test@test.com", "data": {"text": "deep"}}
    curr = deep_dict
    for i in range(25):
        curr["nested"] = {}
        curr = curr["nested"]

    res2 = client.post("/api/v1/payloads/ingest", json=deep_dict, headers=headers)
    assert res2.status_code == 400
    assert res2.get_json()["failure_code"] == "JSON_NESTING_TOO_DEEP"


def test_missing_required_fields_moves_to_dlq(client, test_setup):
    headers = test_setup["headers_admin_a"]

    # Missing recipient
    payload_no_recip = {
        "channel": "email",
        "data": {"subject": "Test", "text": "Missing recipient"}
    }
    res = client.post("/api/v1/payloads/ingest", json=payload_no_recip, headers=headers)
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "IN_DLQ"
    assert data["failure_code"] == "MISSING_REQUIRED_FIELDS"

    # Missing data
    payload_no_data = {
        "channel": "email",
        "recipient": "kavin@example.com"
    }
    res2 = client.post("/api/v1/payloads/ingest", json=payload_no_data, headers=headers)
    assert res2.status_code == 400
    assert res2.get_json()["failure_code"] == "MISSING_REQUIRED_FIELDS"


# ===========================================================================
# 3. IMMUTABILITY, VERSIONING & EDITING
# ===========================================================================

def test_original_json_remains_unchanged_after_editing(client, test_setup):
    headers = test_setup["headers_admin_a"]

    # Ingest a payload with a bad channel
    initial_payload = {
        "channel": "bad_channel",
        "recipient": "+14155552671",
        "data": {"text": "Original text"}
    }
    res = client.post("/api/v1/payloads/ingest", json=initial_payload, headers=headers)
    assert res.status_code == 400
    payload_id = res.get_json()["payload_id"]

    # Edit the payload to fix the channel
    edited_payload = {
        "channel": "sms",
        "recipient": "+14155552671",
        "data": {"text": "Edited text for SMS"}
    }
    edit_res = client.put(
        f"/api/v1/payloads/{payload_id}",
        json={"payload": edited_payload, "reason": "Corrected channel to sms"},
        headers=headers
    )
    assert edit_res.status_code == 200
    edit_data = edit_res.get_json()
    assert edit_data["success"] is True
    assert edit_data["validation"]["valid"] is True

    # Retrieve payload and assert original_payload is 100% UNCHANGED
    get_res = client.get(f"/api/v1/payloads/{payload_id}", headers=headers)
    doc = get_res.get_json()["data"]

    # ORIGINAL PAYLOAD STILL CONTAINS bad_channel!
    assert doc["original_payload"]["channel"] == "bad_channel"
    assert doc["original_payload"]["data"]["text"] == "Original text"

    # CURRENT PAYLOAD HAS THE UPDATED VERSION
    assert doc["current_payload"]["channel"] == "sms"
    assert doc["current_payload"]["data"]["text"] == "Edited text for SMS"
    assert doc["version"] == 2


def test_payload_version_history(client, test_setup):
    headers = test_setup["headers_admin_a"]

    # Ingest v1
    res = client.post("/api/v1/payloads/ingest", json={"channel": "sms", "recipient": "bad_recip", "data": {"text": "v1"}}, headers=headers)
    payload_id = res.get_json()["payload_id"]

    # Edit to v2
    client.put(f"/api/v1/payloads/{payload_id}", json={"payload": {"channel": "sms", "recipient": "+14155552671", "data": {"text": "v2"}}, "reason": "Fix recipient"}, headers=headers)

    # Edit to v3
    client.put(f"/api/v1/payloads/{payload_id}", json={"payload": {"channel": "sms", "recipient": "+14155552671", "data": {"text": "v3 updated"}}, "reason": "Update body"}, headers=headers)

    hist_res = client.get(f"/api/v1/payloads/{payload_id}/versions", headers=headers)
    assert hist_res.status_code == 200
    data = hist_res.get_json()
    assert data["current_version"] == 3
    versions = data["versions"]
    assert len(versions) == 3

    assert versions[0]["version"] == 1
    assert versions[0]["payload"]["data"]["text"] == "v1"

    assert versions[1]["version"] == 2
    assert versions[1]["reason"] == "Fix recipient"
    assert versions[1]["created_by"] == test_setup["user_admin_a"]

    assert versions[2]["version"] == 3
    assert versions[2]["reason"] == "Update body"


# ===========================================================================
# 4. SECURITY & RBAC PERMISSIONS
# ===========================================================================

def test_unauthorized_users_cannot_edit(client, test_setup):
    headers_viewer = test_setup["headers_readonly_a"]
    headers_admin = test_setup["headers_admin_a"]

    # Admin creates payload
    res = client.post("/api/v1/payloads/ingest", json={"channel": "sms", "recipient": "none", "data": {"text": "init"}}, headers=headers_admin)
    payload_id = res.get_json()["payload_id"]

    # Viewer (no organization:payloads:edit) attempts to edit
    edit_res = client.put(
        f"/api/v1/payloads/{payload_id}",
        json={"payload": {"channel": "sms", "recipient": "+14155552671", "data": {"text": "hacked"}}},
        headers=headers_viewer
    )
    assert edit_res.status_code == 403
    assert "You do not have permission" in edit_res.get_json()["message"]


def test_cross_organization_access_is_rejected(client, test_setup):
    headers_org_a = test_setup["headers_admin_a"]
    headers_org_b = test_setup["headers_admin_b"]

    # Org A creates a payload
    res = client.post("/api/v1/payloads/ingest", json={"channel": "email", "recipient": "secret@a.io", "data": {"subject": "A", "text": "secret"}}, headers=headers_org_a)
    payload_id = res.get_json()["payload_id"]

    # Org B user attempts to GET Org A payload
    get_res = client.get(f"/api/v1/payloads/{payload_id}", headers=headers_org_b)
    assert get_res.status_code == 404

    # Org B user attempts to edit Org A payload
    edit_res = client.put(f"/api/v1/payloads/{payload_id}", json={"payload": {"channel": "sms"}}, headers=headers_org_b)
    assert edit_res.status_code == 404

    # Org B user attempts to retry Org A payload
    retry_res = client.post(f"/api/v1/payloads/{payload_id}/retry", headers=headers_org_b)
    assert retry_res.status_code == 404


# ===========================================================================
# 5. PRE-DISPATCH VALIDATION & EXPLICIT RETRY DISPATCH
# ===========================================================================

def test_editing_alone_does_not_dispatch(client, test_setup):
    headers = test_setup["headers_admin_a"]

    # Ingest bad payload
    res = client.post("/api/v1/payloads/ingest", json={"channel": "unknown", "recipient": "x", "data": {"text": "x"}}, headers=headers)
    payload_id = res.get_json()["payload_id"]

    # Edit to valid payload
    with patch("app.modules.messages.service.MessageService.create_message") as mock_create:
        edit_res = client.put(
            f"/api/v1/payloads/{payload_id}",
            json={"payload": {"channel": "email", "recipient": "test@domain.com", "data": {"subject": "S", "text": "B"}}, "reason": "Fix"},
            headers=headers
        )
        assert edit_res.status_code == 200
        # CRUCIAL: create_message MUST NOT BE CALLED ON EDIT!
        mock_create.assert_not_called()

    # Payload status must be EDITED, NOT DISPATCHED
    get_res = client.get(f"/api/v1/payloads/{payload_id}", headers=headers)
    assert get_res.get_json()["data"]["status"] == "EDITED"


def test_invalid_edited_json_cannot_be_dispatched(client, test_setup):
    headers = test_setup["headers_admin_a"]

    # Ingest bad payload
    res = client.post("/api/v1/payloads/ingest", json={"channel": "bad", "recipient": "x", "data": {"text": "x"}}, headers=headers)
    payload_id = res.get_json()["payload_id"]

    # Edit to another invalid payload (still invalid channel)
    client.put(
        f"/api/v1/payloads/{payload_id}",
        json={"payload": {"channel": "still_bad", "recipient": "x", "data": {"text": "y"}}, "reason": "Attempt"},
        headers=headers
    )

    # Attempt to retry -> REJECTED
    retry_res = client.post(f"/api/v1/payloads/{payload_id}/retry", headers=headers)
    assert retry_res.status_code == 400
    assert "Cannot dispatch payload" in retry_res.get_json()["message"]


def test_explicit_retry_dispatches_valid_payload_and_duplicate_retry_fails(client, test_setup):
    headers = test_setup["headers_admin_a"]

    # Ingest bad payload
    res = client.post("/api/v1/payloads/ingest", json={"channel": "missing", "recipient": "none", "data": {"text": "none"}}, headers=headers)
    payload_id = res.get_json()["payload_id"]

    # Edit to a valid email payload
    valid_edit = {
        "channel": "email",
        "recipient": "verified@destination.com",
        "data": {
            "subject": "Verified Retry Subject",
            "text": "Payload was edited and verified."
        }
    }
    client.put(f"/api/v1/payloads/{payload_id}", json={"payload": valid_edit, "reason": "Fixed all fields"}, headers=headers)

    # Validate endpoint returns valid=True
    val_res = client.post(f"/api/v1/payloads/{payload_id}/validate", headers=headers)
    assert val_res.status_code == 200
    assert val_res.get_json()["valid"] is True

    # 1. Explicit retry dispatch -> SUCCESS
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_queue:
        mock_queue.return_value = {"success": True, "status": "QUEUED"}
        retry_res = client.post(f"/api/v1/payloads/{payload_id}/retry", headers=headers)
        assert retry_res.status_code == 200
        data = retry_res.get_json()
        assert data["success"] is True
        assert data["status"] == "DISPATCHED"
        assert "message_id" in data
        mock_queue.assert_called_once()

    # 2. Duplicate retry -> 409 Conflict (IDEMPOTENCY GUARD)
    dup_res = client.post(f"/api/v1/payloads/{payload_id}/retry", headers=headers)
    assert dup_res.status_code == 409
    assert "already been dispatched" in dup_res.get_json()["message"]


# ===========================================================================
# 6. AUDIT TRAIL & SENSITIVE CREDENTIAL SANITIZATION
# ===========================================================================

def test_audit_logs_are_recorded_and_credentials_sanitized(client, test_setup):
    headers = test_setup["headers_admin_a"]

    # Ingest payload containing secret token in data
    payload = {
        "channel": "email",
        "recipient": "client@domain.com",
        "data": {
            "subject": "Welcome",
            "text": "Hello",
            "api_key": "super_secret_key_12345",
            "password": "ClearTextPassword"
        }
    }
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_queue:
        mock_queue.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
        payload_id = res.get_json()["payload_id"]

    # Fetch audit trail
    audit_res = client.get(f"/api/v1/payloads/{payload_id}/audit", headers=headers)
    assert audit_res.status_code == 200
    trail = audit_res.get_json()["audit_trail"]
    assert len(trail) >= 2
    event_types = [entry["event_type"] for entry in trail]
    assert "REQUEST_RECEIVED" in event_types
    assert "ROUTED_TO_CHANNEL" in event_types

    # Fetch payload from GET endpoint and verify credentials are redacted
    get_res = client.get(f"/api/v1/payloads/{payload_id}", headers=headers)
    stored = get_res.get_json()["data"]
    orig_data = stored["original_payload"]["data"]
    assert orig_data["api_key"] == "[REDACTED]"
    assert orig_data["password"] == "[REDACTED]"


# ===========================================================================
# 7. PRODUCTION MOCK FALLBACK REJECTION & DLQ ROUTES INTEGRATION
# ===========================================================================

def test_production_mock_provider_fallback_rejected(app, client, test_setup):
    headers = test_setup["headers_admin_a"]
    orig_env = app.config.get("APP_ENV")
    app.config["APP_ENV"] = "production"

    try:
        mock_payload = {
            "channel": "email",
            "provider": "mock",
            "recipient": "user@corp.com",
            "data": {"subject": "Test", "text": "Mock"}
        }
        res = client.post("/api/v1/payloads/ingest", json=mock_payload, headers=headers)
        assert res.status_code == 400
        data = res.get_json()
        assert data["status"] == "IN_DLQ"
        assert "Mock provider is forbidden in production" in data["message"]
    finally:
        app.config["APP_ENV"] = orig_env


def test_dlq_direct_payload_edit_and_retry(client, test_setup):
    headers = test_setup["headers_admin_a"]

    # 1. Ingest invalid payload (moved to DLQ)
    bad_payload = {
        "channel": "unknown_channel",
        "recipient": "+14155552671",
        "data": {"text": "Needs fixing"}
    }
    res = client.post("/api/v1/payloads/ingest", json=bad_payload, headers=headers)
    payload_id = res.get_json()["payload_id"]

    # 2. View DLQ entry via /api/v1/dead-letters/organization/<id>
    dlq_res = client.get(f"/api/v1/dead-letters/organization/{payload_id}", headers=headers)
    assert dlq_res.status_code == 200
    dlq_doc = dlq_res.get_json()["data"]
    assert dlq_doc["dead_letter_status"] == "PENDING_REVIEW"
    assert dlq_doc["original_payload"]["channel"] == "unknown_channel"

    # 3. Edit payload directly through DLQ route /api/v1/dead-letters/organization/<id>/payload
    fixed_payload = {
        "channel": "sms",
        "recipient": "+14155552671",
        "data": {"text": "Fixed through DLQ route"}
    }
    edit_res = client.put(
        f"/api/v1/dead-letters/organization/{payload_id}/payload",
        json={"payload": fixed_payload, "reason": "Fixed via DLQ dashboard"},
        headers=headers
    )
    assert edit_res.status_code == 200

    # 4. Validate through DLQ route /api/v1/dead-letters/organization/<id>/validate
    val_res = client.post(f"/api/v1/dead-letters/organization/{payload_id}/validate", headers=headers)
    assert val_res.status_code == 200
    assert val_res.get_json()["valid"] is True

    # 5. Retry through DLQ route /api/v1/dead-letters/organization/<id>/retry
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_queue:
        mock_queue.return_value = {"success": True, "status": "QUEUED"}
        retry_res = client.post(f"/api/v1/dead-letters/organization/{payload_id}/retry", headers=headers)
        assert retry_res.status_code in (200, 202)
        assert retry_res.get_json()["status"] == "DISPATCHED"
