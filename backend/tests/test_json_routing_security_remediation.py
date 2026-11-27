"""
SenderX Phase 4, Task 2.2: JSON Routing & DLQ Security Remediation Test Suite
Verifies all findings from SEC-01 through SEC-04, ARCH-01 through ARCH-03, and TEST-01:
1. Supplied API keys are encrypted at rest and never returned by API responses.
2. API credential verification authenticates valid keys (both live and test).
3. Revoked API credentials reject requests with HTTP 401.
4. Replaced API credentials: old key rejected, replacement accepted.
5. Ingestion with valid API key automatically binds organization_id and application_id from credential record.
6. Ingestion rejecting client spoofing (X-Application-ID header or JSON field differing from credential binding) with HTTP 403.
7. Unauthenticated ingestion attempts rejected with HTTP 401.
8. DLQ single item read redacts passwords, tokens, API keys, and sensitive data.
9. DLQ list read redacts sensitive data across all returned items.
10. Payload at rest in MongoDB contains authenticated ciphertext, not plaintext original_payload or current_payload.
11. Corrupted ciphertext fails closed (PayloadEncryptionError) and does not return plaintext.
12. Attempt to edit payload in DISPATCHED status returns HTTP 409 Conflict.
13. Attempt to edit payload in DISPATCHING status returns HTTP 409 Conflict.
14. DLQ record transitions to RESOLVED status with resolved_at timestamp when routing payload is successfully retried.
15. Microsoft Teams messages ingested with channel 'teams', 'microsoft_teams', or 'msteams' all normalize to canonical 'teams' and maintain consistency across storage.
"""

from copy import deepcopy
import json
import uuid
from unittest.mock import patch

import bcrypt
import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.api_credentials.models import hash_api_key
from app.modules.api_credentials.repository import ApiCredentialRepository
from app.modules.applications.repository import ApplicationRepository
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.messages.repository import MessageRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.payloads.encryption import PayloadEncryption, PayloadEncryptionError
from app.modules.payloads.models import PayloadStatus
from app.modules.payloads.repository import PayloadRepository
from app.modules.users.repository import UserRepository


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
        role_admin_b = str(uuid.uuid4())

        user_admin_a = str(uuid.uuid4())
        user_admin_b = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Org A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Security Org A {suffix}",
            "slug": f"sec-org-a-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a,
            "name": "Security Admin A",
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
                "organization:dead_letters:manage",
                "organization:api_credentials:manage",
                "organization:api_credentials:read",
                "organization:configuration:manage"
            ]
        })

        UserRepository.create({
            "user_id": user_admin_a,
            "organization_id": org_a,
            "email": f"admin_a_{suffix}@example.com",
            "password_hash": password_hash,
            "first_name": "Admin",
            "last_name": "A",
            "role_ids": [role_admin_a],
            "is_active": True
        })

        # Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Security Org B {suffix}",
            "slug": f"sec-org-b-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b,
            "name": "Security Admin B",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:payloads:read",
                "organization:dlq:read",
                "organization:dead_letters:read",
                "organization:api_credentials:manage",
                "organization:api_credentials:read",
                "organization:configuration:manage"
            ]
        })

        UserRepository.create({
            "user_id": user_admin_b,
            "organization_id": org_b,
            "email": f"admin_b_{suffix}@example.com",
            "password_hash": password_hash,
            "first_name": "Admin",
            "last_name": "B",
            "role_ids": [role_admin_b],
            "is_active": True
        })

        token_admin_a = create_access_token(
            identity=user_admin_a,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a}
        )
        token_admin_b = create_access_token(
            identity=user_admin_b,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b}
        )

        # Pre-register connected applications for test scenarios (clean existing first)
        app_ids = [
            "app_checkout", "app_testing", "app_to_revoke",
            "app_rotation", "app_bound_context", "legit_app"
        ]
        ApplicationRepository._collection().delete_many({"application_id": {"$in": app_ids}})
        for app_id, app_name in [
            ("app_checkout", f"Checkout Application {suffix}"),
            ("app_testing", f"Testing Application {suffix}"),
            ("app_to_revoke", f"Revoke App {suffix}"),
            ("app_rotation", f"Rotation App {suffix}"),
            ("app_bound_context", f"Bound Context App {suffix}"),
            ("legit_app", f"Legitimate App {suffix}")
        ]:
            ApplicationRepository.create({
                "application_id": app_id,
                "organization_id": org_a,
                "name": app_name,
                "description": "Pre-registered for test",
                "environment": "all",
                "status": "ACTIVE",
                "created_by": user_admin_a
            })

        return {
            "org_a": org_a,
            "org_b": org_b,
            "user_admin_a": user_admin_a,
            "user_admin_b": user_admin_b,
            "headers_admin_a": {"Authorization": f"Bearer {token_admin_a}"},
            "headers_admin_b": {"Authorization": f"Bearer {token_admin_b}"}
        }


# ===========================================================================
# 1. API CREDENTIALS (SEC-01)
# ===========================================================================

def test_api_credential_registration_encrypts_key_and_redacts_responses(client, test_setup, app):
    """Scenario 1: supplied keys are encrypted at rest and never returned."""
    headers = test_setup["headers_admin_a"]
    org_id = test_setup["org_a"]
    raw_api_key = f"client-supplied-{uuid.uuid4().hex}"

    missing_key_res = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": "app_checkout", "name": "Missing value"},
        headers=headers,
    )
    assert missing_key_res.status_code == 400

    create_res = client.post(
        "/api/v1/api-credentials/",
        json={
            "application_id": "app_checkout",
            "name": "Checkout API Key",
            "environment": "live",
            "api_key": raw_api_key,
        },
        headers=headers
    )
    assert create_res.status_code == 201
    created_data = create_res.get_json()["data"]
    assert "api_key" not in created_data
    assert "raw_key" not in create_res.get_json()
    credential_id = created_data["credential_id"]

    duplicate_res = client.post(
        "/api/v1/api-credentials/",
        json={
            "application_id": "app_testing",
            "name": "Duplicate Key",
            "environment": "live",
            "api_key": raw_api_key,
        },
        headers=headers,
    )
    assert duplicate_res.status_code == 409

    get_res = client.get(f"/api/v1/api-credentials/{credential_id}", headers=headers)
    assert get_res.status_code == 200
    retrieved_data = get_res.get_json()["data"]
    assert "api_key" not in retrieved_data
    assert "key_hash" not in retrieved_data
    assert retrieved_data["key_prefix"] == "••••••••"
    assert retrieved_data["application_id"] == "app_checkout"
    assert retrieved_data["organization_id"] == org_id
    cross_tenant = client.get(
        f"/api/v1/api-credentials/{credential_id}",
        headers=test_setup["headers_admin_b"],
    )
    assert cross_tenant.status_code == 404
    cross_tenant_update = client.patch(
        f"/api/v1/api-credentials/{credential_id}",
        headers=test_setup["headers_admin_b"],
        json={"name": "Unauthorized"},
    )
    assert cross_tenant_update.status_code == 404
    cross_tenant_delete = client.delete(
        f"/api/v1/api-credentials/{credential_id}",
        headers=test_setup["headers_admin_b"],
    )
    assert cross_tenant_delete.status_code == 404

    with app.app_context():
        raw_doc = app.mongo_db["api_credentials"].find_one({"credential_id": credential_id})
        assert raw_doc is not None
        assert raw_doc["key_hash"] == hash_api_key(raw_api_key)
        assert "api_key" not in raw_doc
        assert raw_doc["key_encrypted"]["_encrypted"] is True
        assert raw_api_key not in str(raw_doc["key_encrypted"])
        assert PayloadEncryption.decrypt_dict(raw_doc["key_encrypted"]) == {"api_key": raw_api_key}


def test_api_credential_verification_live_and_test(client, test_setup):
    """Scenario 2: API credential verification authenticates both live and test keys."""
    headers = test_setup["headers_admin_a"]

    test_key = f"external-test-{uuid.uuid4().hex}"
    create_test = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": "app_testing", "name": "Test Key", "environment": "test", "api_key": test_key},
        headers=headers
    )
    assert create_test.status_code == 201

    # Ingest using test API key
    payload = {
        "channel": "email",
        "recipient": "kavin@example.com",
        "data": {"subject": "Test Key Ingestion", "text": "Testing external app"}
    }
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
        mock_q.return_value = {"success": True, "status": "QUEUED"}
        res = client.post(
            "/api/v1/payloads/ingest",
            json=payload,
            headers={"X-API-Key": test_key}
        )
        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["status"] == "ROUTED"


def test_revoked_api_credentials_reject_401(client, test_setup):
    """Scenario 3: Revoked API credentials reject requests with HTTP 401."""
    headers = test_setup["headers_admin_a"]

    api_key = f"external-delete-{uuid.uuid4().hex}"
    create_res = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": "app_to_revoke", "name": "Delete Test", "environment": "live", "api_key": api_key},
        headers=headers
    )
    cred_id = create_res.get_json()["data"]["credential_id"]

    del_res = client.delete(f"/api/v1/api-credentials/{cred_id}", headers=headers)
    assert del_res.status_code == 200

    # Ingestion attempt using revoked key
    res = client.post(
        "/api/v1/payloads/ingest",
        json={"channel": "email", "recipient": "kavin@example.com", "data": {"text": "Revoked"}},
        headers={"X-API-Key": api_key}
    )
    assert res.status_code == 401
    assert "Invalid or revoked API key" in res.get_json()["message"]
    assert client.get(f"/api/v1/api-credentials/{cred_id}", headers=headers).status_code == 404

    other_key = f"external-survivor-{uuid.uuid4().hex}"
    other_credential = client.post(
        "/api/v1/api-credentials/",
        json={
            "application_id": "app_to_revoke",
            "name": "Unaffected key",
            "environment": "live",
            "api_key": other_key,
        },
        headers=headers,
    )
    assert other_credential.status_code == 201
    other_id = other_credential.get_json()["data"]["credential_id"]
    assert client.get(f"/api/v1/api-credentials/{other_id}", headers=headers).status_code == 200


def test_replaced_api_credentials_metadata_preserves_secret(client, test_setup, app):
    """Scenario 4: Metadata edits preserve keys; replacement invalidates the old value."""
    headers = test_setup["headers_admin_a"]

    old_key = f"external-old-{uuid.uuid4().hex}"
    create_res = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": "app_rotation", "name": "Replacement Test", "environment": "live", "api_key": old_key},
        headers=headers
    )
    assert create_res.status_code == 201
    cred_id = create_res.get_json()["data"]["credential_id"]

    with app.app_context():
        original_doc = app.mongo_db["api_credentials"].find_one({"credential_id": cred_id})
        original_hash = original_doc["key_hash"]
        original_envelope = original_doc["key_encrypted"]

    metadata_res = client.patch(
        f"/api/v1/api-credentials/{cred_id}",
        headers=headers,
        json={"name": "Metadata Updated", "description": "Metadata only"},
    )
    assert metadata_res.status_code == 200
    with app.app_context():
        metadata_doc = app.mongo_db["api_credentials"].find_one({"credential_id": cred_id})
        assert metadata_doc["key_hash"] == original_hash
        assert metadata_doc["key_encrypted"] == original_envelope

    new_key = f"external-new-{uuid.uuid4().hex}"
    replace_res = client.patch(
        f"/api/v1/api-credentials/{cred_id}",
        headers=headers,
        json={"api_key": new_key},
    )
    assert replace_res.status_code == 200
    assert "api_key" not in replace_res.get_json()["data"]
    assert new_key != old_key
    with app.app_context():
        replacement_doc = app.mongo_db["api_credentials"].find_one({"credential_id": cred_id})
        assert replacement_doc["key_hash"] != original_hash
        assert PayloadEncryption.decrypt_dict(replacement_doc["key_encrypted"]) == {"api_key": new_key}

    # Old key fails
    payload = {"channel": "email", "recipient": "kavin@example.com", "data": {"text": "Rotate"}}
    old_res = client.post("/api/v1/payloads/ingest", json=payload, headers={"X-API-Key": old_key})
    assert old_res.status_code == 401

    # New key succeeds
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
        mock_q.return_value = {"success": True, "status": "QUEUED"}
        new_res = client.post("/api/v1/payloads/ingest", json=payload, headers={"X-API-Key": new_key})
        assert new_res.status_code == 201


def test_ingestion_binds_org_and_app_from_credential(client, test_setup, app):
    """Scenario 5: Ingestion with valid API key automatically binds organization_id and application_id."""
    headers = test_setup["headers_admin_a"]
    org_id = test_setup["org_a"]

    api_key = f"external-bound-{uuid.uuid4().hex}"
    create_res = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": "app_bound_context", "name": "Binding Test", "environment": "live", "api_key": api_key},
        headers=headers
    )

    payload = {
        "channel": "email",
        "recipient": "kavin@example.com",
        "data": {"subject": "Binding Check", "text": "Binding body"}
    }
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
        mock_q.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers={"X-API-Key": api_key})
        assert res.status_code == 201
        payload_id = res.get_json()["payload_id"]

    # Verify stored document has verified organization_id and application_id
    with app.app_context():
        record = PayloadRepository.find_by_id(payload_id, organization_id=org_id)
        assert record is not None
        assert record["organization_id"] == org_id
        assert record["application_id"] == "app_bound_context"


def test_ingestion_rejects_client_spoofing_403(client, test_setup):
    """Scenario 6: Ingestion rejecting client spoofing (X-Application-ID header or JSON field differing) with HTTP 403."""
    headers = test_setup["headers_admin_a"]

    api_key = f"external-legit-{uuid.uuid4().hex}"
    create_res = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": "legit_app", "name": "Spoof Test", "environment": "live", "api_key": api_key},
        headers=headers
    )

    # 1. Spoofed header
    res1 = client.post(
        "/api/v1/payloads/ingest",
        json={"channel": "email", "recipient": "kavin@example.com", "data": {"text": "spoof"}},
        headers={"X-API-Key": api_key, "X-Application-ID": "malicious_spoofed_app"}
    )
    assert res1.status_code == 403
    assert "Application ID mismatch" in res1.get_json()["message"]

    # 2. Spoofed JSON body
    res2 = client.post(
        "/api/v1/payloads/ingest",
        json={
            "application_id": "malicious_spoofed_app",
            "channel": "email",
            "recipient": "kavin@example.com",
            "data": {"text": "spoof"}
        },
        headers={"X-API-Key": api_key}
    )
    assert res2.status_code == 403
    assert "Application ID mismatch" in res2.get_json()["message"]


def test_unauthenticated_ingestion_rejected_401(client):
    """Scenario 7: Unauthenticated ingestion attempts rejected with HTTP 401."""
    res = client.post(
        "/api/v1/payloads/ingest",
        json={"channel": "email", "recipient": "kavin@example.com", "data": {"text": "unauth"}}
    )
    assert res.status_code == 401


# ===========================================================================
# 2. SENSITIVE DATA REDACTION IN DLQ (SEC-02)
# ===========================================================================

def test_dlq_single_item_read_redacts_sensitive_data(client, test_setup):
    """Scenario 8: DLQ single item read redacts passwords, tokens, API keys, and sensitive data."""
    headers = test_setup["headers_admin_a"]

    # Ingest a payload with an unsupported channel and sensitive fields
    payload = {
        "channel": "unsupported_channel",
        "recipient": "kavin@example.com",
        "data": {
            "password": "SuperSecretPassword123!",
            "api_key": "raw_sensitive_api_key_value",
            "auth_token": "bearer 1234567890abcdef",
            "nested": {
                "secret": "top_secret_code",
                "client_secret": "my_client_secret"
            },
            "public_field": "visible_debug_info"
        }
    }
    res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
    assert res.status_code == 400
    payload_id = res.get_json()["payload_id"]

    # Retrieve DLQ item via GET /organization/<id>
    dlq_res = client.get(f"/api/v1/dead-letters/organization/{payload_id}", headers=headers)
    assert dlq_res.status_code == 200
    dlq_data = dlq_res.get_json()["data"]

    # Assert structural debugging fields remain intact
    assert dlq_data["status"] == "DEAD"
    assert dlq_data["dead_letter_status"] == "PENDING_REVIEW"
    assert dlq_data["failure_code"] == "UNSUPPORTED_CHANNEL"

    # Assert sensitive values are strictly redacted in data, original_payload, current_payload
    for block_name in ("data", "original_payload", "current_payload"):
        block = dlq_data.get(block_name, {})
        inner_data = block.get("data", block) if block_name != "data" else block
        assert inner_data.get("password") == "[REDACTED]"
        assert inner_data.get("api_key") == "[REDACTED]"
        assert inner_data.get("auth_token") == "[REDACTED]"
        assert inner_data.get("nested", {}).get("secret") == "[REDACTED]"
        assert inner_data.get("nested", {}).get("client_secret") == "[REDACTED]"
        assert inner_data.get("public_field") == "visible_debug_info"


def test_dlq_list_read_redacts_sensitive_data(client, test_setup):
    """Scenario 9: DLQ list read redacts sensitive data across all returned items."""
    headers = test_setup["headers_admin_a"]

    # Ingest a DLQ item to ensure test is fully self-contained and parallel-safe
    payload = {
        "channel": "unsupported_channel",
        "recipient": "kavin@example.com",
        "data": {
            "password": "SuperSecretPassword123!",
            "api_key": "raw_sensitive_api_key_value",
            "auth_token": "bearer 1234567890abcdef",
            "nested": {
                "secret": "top_secret_code",
                "client_secret": "my_client_secret"
            }
        }
    }
    client.post("/api/v1/payloads/ingest", json=payload, headers=headers)

    list_res = client.get("/api/v1/dead-letters/organization", headers=headers)
    assert list_res.status_code == 200
    items = list_res.get_json()["data"]
    assert len(items) > 0

    for item in items:
        # Check that no sensitive strings leak into returned items
        item_str = json.dumps(item)
        assert "SuperSecretPassword123!" not in item_str
        assert "raw_sensitive_api_key_value" not in item_str
        assert "my_client_secret" not in item_str


# ===========================================================================
# 3. PAYLOAD ENCRYPTION AT REST (SEC-03)
# ===========================================================================

def test_payload_at_rest_encrypted_in_mongodb(client, test_setup, app):
    """Scenario 10: Payload at rest in MongoDB contains authenticated ciphertext, not plaintext."""
    headers = test_setup["headers_admin_a"]
    org_id = test_setup["org_a"]

    payload = {
        "channel": "email",
        "recipient": "kavin@example.com",
        "data": {
            "subject": "Confidential Message",
            "body": "This text must be encrypted at rest in MongoDB."
        }
    }
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
        mock_q.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
        assert res.status_code == 201
        payload_id = res.get_json()["payload_id"]

    # 1. Inspect raw MongoDB document in ingested_payloads
    with app.app_context():
        raw_doc = app.mongo_db["ingested_payloads"].find_one({"payload_id": payload_id})
        assert raw_doc is not None

        # Verify original_payload is an authenticated encryption envelope
        orig_envelope = raw_doc["original_payload"]
        assert orig_envelope.get("_encrypted") is True
        assert "ciphertext" in orig_envelope
        assert "This text must be encrypted at rest" not in str(orig_envelope)

        # Verify current_payload is encrypted
        curr_envelope = raw_doc["current_payload"]
        assert curr_envelope.get("_encrypted") is True
        assert "ciphertext" in curr_envelope

        # Verify versions array payload is encrypted
        version_payload = raw_doc["versions"][0]["payload"]
        assert version_payload.get("_encrypted") is True

        # 2. Transparent decryption through repository
        decrypted = PayloadRepository.find_by_id(payload_id, organization_id=org_id)
        assert decrypted["original_payload"]["data"]["body"] == "This text must be encrypted at rest in MongoDB."
        assert decrypted["current_payload"]["data"]["body"] == "This text must be encrypted at rest in MongoDB."


def test_corrupted_ciphertext_fails_closed(client, test_setup, app):
    """Scenario 11: Corrupted ciphertext fails closed (PayloadEncryptionError) and does not return plaintext."""
    headers = test_setup["headers_admin_a"]
    org_id = test_setup["org_a"]

    payload = {
        "channel": "email",
        "recipient": "kavin@example.com",
        "data": {"subject": "Integrity Test", "body": "Integrity content"}
    }
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
        mock_q.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
        payload_id = res.get_json()["payload_id"]

    with app.app_context():
        # Tamper directly with the ciphertext in MongoDB
        app.mongo_db["ingested_payloads"].update_one(
            {"payload_id": payload_id},
            {"$set": {"original_payload.ciphertext": "invalid_tampered_ciphertext_token"}}
        )

        # Fails closed by raising PayloadEncryptionError
        with pytest.raises(PayloadEncryptionError):
            PayloadRepository.find_by_id(payload_id, organization_id=org_id)


# ===========================================================================
# 4. PREVENT POST-DISPATCH EDITING & DUPLICATE DISPATCH (SEC-04)
# ===========================================================================

def test_edit_dispatched_payload_returns_409(client, test_setup, app):
    """Scenario 12: Attempt to edit payload in DISPATCHED status returns HTTP 409 Conflict."""
    headers = test_setup["headers_admin_a"]
    org_id = test_setup["org_a"]

    # Ingest a payload and set status to DISPATCHED
    payload = {
        "channel": "email",
        "recipient": "kavin@example.com",
        "data": {"subject": "Dispatched Msg", "body": "Already sent"}
    }
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
        mock_q.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
        payload_id = res.get_json()["payload_id"]

    with app.app_context():
        PayloadRepository.update_status(payload_id, new_status=PayloadStatus.DISPATCHED, organization_id=org_id)

    # Attempt to edit dispatched payload
    edit_res = client.put(
        f"/api/v1/payloads/{payload_id}",
        json={"payload": {"channel": "email", "recipient": "new@example.com", "data": {"text": "edited"}}},
        headers=headers
    )
    assert edit_res.status_code == 409
    assert "Dispatched payloads are immutable" in edit_res.get_json()["message"]


def test_edit_dispatching_payload_returns_409(client, test_setup, app):
    """Scenario 13: Attempt to edit payload in DISPATCHING status returns HTTP 409 Conflict."""
    headers = test_setup["headers_admin_a"]
    org_id = test_setup["org_a"]

    payload = {
        "channel": "email",
        "recipient": "kavin@example.com",
        "data": {"subject": "Dispatching Msg", "body": "Sending now"}
    }
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
        mock_q.return_value = {"success": True, "status": "QUEUED"}
        res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
        payload_id = res.get_json()["payload_id"]

    with app.app_context():
        PayloadRepository.update_status(payload_id, new_status=PayloadStatus.DISPATCHING, organization_id=org_id)

    edit_res = client.put(
        f"/api/v1/payloads/{payload_id}",
        json={"payload": {"channel": "email", "recipient": "new@example.com", "data": {"text": "edited"}}},
        headers=headers
    )
    assert edit_res.status_code == 409
    assert "Dispatched payloads are immutable" in edit_res.get_json()["message"]


# ===========================================================================
# 5. DLQ RESOLUTION & CHANNEL NORMALIZATION (ARCH-01, ARCH-02)
# ===========================================================================

def test_dlq_transitions_to_resolved_on_retry(client, test_setup, app):
    """Scenario 14: DLQ record transitions to RESOLVED status with resolved_at timestamp on successful retry."""
    headers = test_setup["headers_admin_a"]
    org_id = test_setup["org_a"]

    # Ingest bad channel to force to DLQ
    payload = {
        "channel": "invalid_channel_x",
        "recipient": "+14155552671",
        "data": {"text": "DLQ resolution test"}
    }
    res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
    assert res.status_code == 400
    payload_id = res.get_json()["payload_id"]

    # Verify DLQ document is initially PENDING_REVIEW
    with app.app_context():
        dlq_entry = DeadLetterRepository.find_by_message_id(payload_id, organization_id=org_id)
        assert dlq_entry is not None
        assert dlq_entry["dead_letter_status"] == "PENDING_REVIEW"

    # Edit payload to valid channel and data
    edit_res = client.put(
        f"/api/v1/payloads/{payload_id}",
        json={
            "payload": {
                "channel": "sms",
                "recipient": "+14155552671",
                "data": {"text": "Valid SMS text"}
            },
            "reason": "Fix invalid channel"
        },
        headers=headers
    )
    assert edit_res.status_code == 200

    # Retry payload
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
        mock_q.return_value = {"success": True, "status": "QUEUED"}
        retry_res = client.post(f"/api/v1/payloads/{payload_id}/retry", headers=headers)
        assert retry_res.status_code == 200

    # Verify DLQ record transitions to RESOLVED with resolved_at timestamp
    with app.app_context():
        resolved_dlq = DeadLetterRepository.find_by_message_id(payload_id, organization_id=org_id)
        assert resolved_dlq is not None
        assert resolved_dlq["dead_letter_status"] == "RESOLVED"
        assert "resolved_at" in resolved_dlq
        assert resolved_dlq["resolved_at"] is not None
        assert "resolved_message_id" in resolved_dlq


def test_channel_normalization_teams(client, test_setup, app):
    """Scenario 15: Teams messages with 'teams', 'microsoft_teams', or 'msteams' normalize to canonical 'teams'."""
    headers = test_setup["headers_admin_a"]
    org_id = test_setup["org_a"]

    aliases = ["teams", "microsoft_teams", "msteams"]

    for channel_variant in aliases:
        payload = {
            "channel": channel_variant,
            "recipient": "chat:19:meeting_norm@thread.v2",
            "data": {"text": f"Testing channel normalization for {channel_variant}"}
        }
        with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
            mock_q.return_value = {"success": True, "status": "QUEUED"}
            res = client.post("/api/v1/payloads/ingest", json=payload, headers=headers)
            assert res.status_code == 201
            data = res.get_json()
            assert data["channel"] == "teams"
            payload_id = data["payload_id"]

        # Check repository retrieval
        with app.app_context():
            record = PayloadRepository.find_by_id(payload_id, organization_id=org_id)
            assert record["channel"] == "teams"
            assert record["current_payload"]["channel"] == "teams"
            # original_payload immutably preserves the exact variant sent
            assert record["original_payload"]["channel"] == channel_variant
