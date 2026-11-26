"""
SenderX Phase 4, Task 2.4: Comprehensive Security & Application Management Test Suite
Verifies:
1. Connected Application Lifecycle, Isolation, and Cascade Deactivation.
2. API Credential Environment Isolation (CRED-05).
3. Organization Administrator Protection & Invariant Preservation (OPS-01).
4. Redis Distributed Rate Limiting & Fail-Closed Behavior (CRED-06).
5. Legacy Payload Encryption Migration Service & Idempotency (ENC-05).
6. MultiFernet Encryption Key Rotation & Backward Decryption (ENC-06).
"""

from copy import deepcopy
import json
import os
import time
from unittest.mock import patch, MagicMock
import uuid

import bcrypt
from cryptography.fernet import Fernet
import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.api_credentials.models import generate_api_key, hash_api_key
from app.modules.api_credentials.rate_limiter import DistributedRateLimiter, RateLimiterError
from app.modules.api_credentials.repository import ApiCredentialRepository
from app.modules.api_credentials.service import ApiCredentialService
from app.modules.applications.models import ApplicationEnvironment, ApplicationStatus
from app.modules.applications.repository import ApplicationRepository
from app.modules.applications.service import ApplicationService
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.payloads.encryption import PayloadEncryption, PayloadEncryptionError
from app.modules.payloads.migration import PayloadMigrationService
from app.modules.payloads.repository import PayloadRepository
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def setup_context(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())

        role_admin_a = str(uuid.uuid4())
        role_admin_b = str(uuid.uuid4())

        user_admin_a1 = str(uuid.uuid4())
        user_admin_a2 = str(uuid.uuid4())
        user_admin_b = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Org A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Apps Org A {suffix}",
            "slug": f"apps-org-a-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:users:manage",
                "organization:roles:manage",
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage",
                "organization:configuration:manage",
                "organization:payloads:read",
                "organization:payloads:edit"
            ]
        })

        UserRepository.create({
            "user_id": user_admin_a1,
            "organization_id": org_a,
            "name": "Admin A1",
            "email": f"admin_a1_{suffix}@example.com",
            "password_hash": password_hash,
            "role_ids": [role_admin_a],
            "is_active": True
        })

        UserRepository.create({
            "user_id": user_admin_a2,
            "organization_id": org_a,
            "name": "Admin A2",
            "email": f"admin_a2_{suffix}@example.com",
            "password_hash": password_hash,
            "role_ids": [role_admin_a],
            "is_active": True
        })

        # Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Apps Org B {suffix}",
            "slug": f"apps-org-b-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:users:manage",
                "organization:roles:manage",
                "organization:messages:create",
                "organization:messages:read",
                "organization:configuration:manage"
            ]
        })

        UserRepository.create({
            "user_id": user_admin_b,
            "organization_id": org_b,
            "name": "Admin B",
            "email": f"admin_b_{suffix}@example.com",
            "password_hash": password_hash,
            "role_ids": [role_admin_b],
            "is_active": True
        })

        token_a1 = create_access_token(
            identity=user_admin_a1,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a}
        )
        token_a2 = create_access_token(
            identity=user_admin_a2,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a}
        )
        token_b = create_access_token(
            identity=user_admin_b,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b}
        )

        return {
            "org_a": org_a,
            "org_b": org_b,
            "user_admin_a1": user_admin_a1,
            "user_admin_a2": user_admin_a2,
            "user_admin_b": user_admin_b,
            "headers_a1": {"Authorization": f"Bearer {token_a1}"},
            "headers_a2": {"Authorization": f"Bearer {token_a2}"},
            "headers_b": {"Authorization": f"Bearer {token_b}"}
        }


# ===========================================================================
# 1. CONNECTED APPLICATION MANAGEMENT
# ===========================================================================

def test_application_registration_and_uniqueness(client, setup_context):
    """Test registering connected application, uniqueness per org, and cross-org allowance."""
    headers_a = setup_context["headers_a1"]
    headers_b = setup_context["headers_b"]

    app_name = f"Storefront Web {uuid.uuid4().hex[:6]}"

    # 1. Register application in Org A
    res = client.post(
        "/api/v1/applications/",
        json={"name": app_name, "description": "Main e-commerce storefront", "environment": "all"},
        headers=headers_a
    )
    assert res.status_code == 201
    data = res.get_json()["data"]
    app_id = data["application_id"]
    assert app_id.startswith("app_")
    assert data["name"] == app_name
    assert data["status"] == "ACTIVE"

    # 2. Duplicate name in Org A must be rejected with 409 Conflict
    res_dup = client.post(
        "/api/v1/applications/",
        json={"name": app_name, "description": "Duplicate attempt"},
        headers=headers_a
    )
    assert res_dup.status_code == 409
    assert "already exists" in res_dup.get_json()["message"]

    # 3. Same name in Org B must succeed (multi-tenant isolation)
    res_b = client.post(
        "/api/v1/applications/",
        json={"name": app_name, "description": "Org B storefront"},
        headers=headers_b
    )
    assert res_b.status_code == 201
    assert res_b.get_json()["data"]["application_id"] != app_id


def test_connected_applications_list_and_api_key_message_access(client, setup_context):
    """Application listing shape and external message create/status scope stay usable."""
    headers = setup_context["headers_a1"]
    organization_id = setup_context["org_a"]
    name = f"External Messaging App {uuid.uuid4().hex[:6]}"
    created = client.post(
        "/api/v1/applications/",
        json={"name": name, "environment": "all"},
        headers=headers,
    )
    assert created.status_code == 201
    app_id = created.get_json()["data"]["application_id"]

    listed = client.get("/api/v1/applications/?page=1&limit=100", headers=headers)
    assert listed.status_code == 200
    assert isinstance(listed.get_json()["data"], list)
    assert any(item["application_id"] == app_id for item in listed.get_json()["data"])

    credential = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": app_id, "name": "External client key"},
        headers=headers,
    )
    assert credential.status_code == 201
    api_key = credential.get_json()["data"]["api_key"]
    api_headers = {"X-API-Key": api_key}

    # Missing explicit routing must be rejected instead of falling back to email.
    missing_channel = client.post(
        "/api/v1/messages/",
        json={"recipient": "15551234567", "data": {"text": "hello"}},
        headers=api_headers,
    )
    assert missing_channel.status_code == 422
    assert "channel is required" in missing_channel.get_json()["message"]

    with patch("app.modules.messages.service.MessageService.create_message") as create_message:
        create_message.return_value = {"success": True, "message": {"message_id": "msg_api_key"}}
        response = client.post(
            "/api/v1/messages/",
            json={"channel": "whatsapp", "recipient": "15551234567", "data": {"text": "hello"}},
            headers=api_headers,
        )
        assert response.status_code == 201
        create_message.assert_called_once()
        assert create_message.call_args.args[0]["channel"] == "whatsapp"
        assert create_message.call_args.args[1] == organization_id
        assert create_message.call_args.kwargs["application_id"] == app_id

        mismatch = client.post(
            "/api/v1/messages/",
            json={"channel": "whatsapp", "application_id": "another-app", "recipient": "15551234567", "data": {"text": "hello"}},
            headers=api_headers,
        )
        assert mismatch.status_code == 403

    with patch("app.modules.messages.service.MessageService.get_message") as get_message:
        get_message.return_value = {"message_id": "msg_api_key", "organization_id": organization_id, "application_id": app_id}
        status = client.get("/api/v1/messages/msg_api_key", headers=api_headers)
        assert status.status_code == 200
        assert get_message.call_args.kwargs["user_application_ids"] == [app_id]

    create_only = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": app_id, "name": "Create only", "scopes": ["messages:create"]},
        headers=headers,
    ).get_json()["data"]["api_key"]
    denied_status = client.get("/api/v1/messages/msg_api_key", headers={"X-API-Key": create_only})
    assert denied_status.status_code == 403
    assert "messages:read" in denied_status.get_json()["missing_scopes"]

    invalid_scopes = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": app_id, "name": "Invalid scope", "scopes": ["organization:configuration:manage"]},
        headers=headers,
    )
    assert invalid_scopes.status_code == 400

    # Exercise the external ingestion path into the existing WhatsApp engine.
    # Queueing is mocked; this verifies routing and persistence, not Meta delivery.
    whatsapp_payload = {
        "channel": "whatsapp",
        "recipient": "+14155552671",
        "data": {"type": "text", "text": {"body": "Application API test"}},
    }
    with patch("app.modules.messages.service.MessageService.queue_message") as queue_message:
        queue_message.return_value = {"success": True, "status": "QUEUED"}
        routed = client.post("/api/v1/payloads/ingest", json=whatsapp_payload, headers=api_headers)
    assert routed.status_code == 201
    route_data = routed.get_json()
    assert route_data["status"] == "ROUTED" and route_data["channel"] == "whatsapp"
    message_id = route_data["message_id"]
    status = client.get(f"/api/v1/messages/{message_id}", headers=api_headers)
    assert status.status_code == 200
    assert status.get_json()["data"]["application_id"] == app_id

    # Key material is never present in the credential listing response.
    listed_creds = client.get("/api/v1/api-credentials/", headers=headers).get_json()["data"]
    assert all("key_hash" not in item and "api_key" not in item and "raw_key" not in item for item in listed_creds)
    used_credential = next(item for item in listed_creds if item["credential_id"] == credential.get_json()["data"]["credential_id"])
    assert used_credential["last_used_at"]


def test_application_soft_delete_revokes_keys_and_retains_record(client, setup_context, app):
    headers = setup_context["headers_a1"]
    org_id = setup_context["org_a"]
    registered = client.post(
        "/api/v1/applications/",
        json={"name": f"Delete Safely {uuid.uuid4().hex[:6]}", "environment": "all"},
        headers=headers,
    )
    app_id = registered.get_json()["data"]["application_id"]
    credential = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": app_id, "name": "Delete test key"},
        headers=headers,
    ).get_json()["data"]

    deleted = client.delete(f"/api/v1/applications/{app_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.get_json()["revoked_credentials_count"] == 1
    assert client.get(f"/api/v1/applications/{app_id}", headers=headers).status_code == 404
    assert client.post(f"/api/v1/applications/{app_id}/activate", headers=headers).status_code == 409
    assert client.get(f"/api/v1/api-credentials/{credential['credential_id']}", headers=headers).get_json()["data"]["status"] == "REVOKED"

    with app.app_context():
        # Soft deletion keeps data for audit/history and tenant-scoped recovery.
        doc = app.mongo_db["connected_applications"].find_one({"application_id": app_id, "organization_id": org_id})
        assert doc is not None and doc.get("deleted_at")
    visible_ids = [item["application_id"] for item in client.get("/api/v1/applications/", headers=headers).get_json()["data"]]
    assert app_id not in visible_ids

    # Another organization cannot delete or inspect this application.
    assert client.delete(f"/api/v1/applications/{app_id}", headers=setup_context["headers_b"]).status_code == 404


def test_application_lifecycle_and_cascade_deactivation(client, setup_context):
    """Test update, detail, stats, and cascade deactivation to active credentials."""
    headers = setup_context["headers_a1"]
    org_a = setup_context["org_a"]

    # 1. Create application
    reg_res = client.post(
        "/api/v1/applications/",
        json={"name": f"Mobile App {uuid.uuid4().hex[:6]}", "environment": "live"},
        headers=headers
    )
    assert reg_res.status_code == 201
    app_id = reg_res.get_json()["data"]["application_id"]

    # 2. Create API credential bound to this app
    cred_res = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": app_id, "name": "Mobile iOS Key", "environment": "live"},
        headers=headers
    )
    assert cred_res.status_code == 201
    raw_key = cred_res.get_json()["data"]["api_key"]
    cred_id = cred_res.get_json()["data"]["credential_id"]

    # 3. Authenticate with this key - should succeed
    with patch("app.modules.messages.service.MessageService.queue_message") as mock_q:
        mock_q.return_value = {"success": True, "status": "QUEUED"}
        ingest_res = client.post(
            "/api/v1/payloads/ingest",
            json={"channel": "email", "recipient": "test@example.com", "data": {"text": "Hello"}},
            headers={"X-API-Key": raw_key}
        )
        assert ingest_res.status_code == 201

    # 4. Check stats endpoint
    stats_res = client.get(f"/api/v1/applications/{app_id}/stats", headers=headers)
    assert stats_res.status_code == 200
    stats_data = stats_res.get_json()["data"]
    assert stats_data["total_credentials"] >= 1
    assert stats_data["active_credentials"] >= 1

    # 5. Deactivate application -> must cascade revoke all active credentials
    deact_res = client.post(f"/api/v1/applications/{app_id}/deactivate", headers=headers)
    assert deact_res.status_code == 200
    assert deact_res.get_json()["revoked_credentials_count"] >= 1

    # 6. Check credential status in DB -> REVOKED
    cred_check = client.get(f"/api/v1/api-credentials/{cred_id}", headers=headers)
    assert cred_check.status_code == 200
    assert cred_check.get_json()["data"]["status"] == "REVOKED"

    # 7. Ingestion attempt with revoked key must fail with 401
    failed_ingest = client.post(
        "/api/v1/payloads/ingest",
        json={"channel": "email", "recipient": "test@example.com", "data": {"text": "Hello"}},
        headers={"X-API-Key": raw_key}
    )
    assert failed_ingest.status_code == 401

    # 8. Attempt to generate new credential for deactivated app must fail
    bad_cred = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": app_id, "name": "Should Fail Key"},
        headers=headers
    )
    assert bad_cred.status_code == 400
    assert "inactive/deactivated" in bad_cred.get_json()["message"]


# ===========================================================================
# 2. ENVIRONMENT ISOLATION (CRED-05)
# ===========================================================================

def test_environment_isolation_enforcement(client, setup_context, app):
    """Test that live credentials fail in test env and test credentials fail in production env."""
    headers = setup_context["headers_a1"]

    # Register apps
    reg_res = client.post(
        "/api/v1/applications/",
        json={"name": f"Env App {uuid.uuid4().hex[:6]}", "environment": "all"},
        headers=headers
    )
    app_id = reg_res.get_json()["data"]["application_id"]

    # Create test key and live key
    live_res = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": app_id, "name": "Live Key", "environment": "live"},
        headers=headers
    )
    live_key = live_res.get_json()["data"]["api_key"]

    test_res = client.post(
        "/api/v1/api-credentials/",
        json={"application_id": app_id, "name": "Test Key", "environment": "test"},
        headers=headers
    )
    test_key = test_res.get_json()["data"]["api_key"]

    # In production environment: test credentials must be blocked with HTTP 403
    with patch.dict(app.config, {"APP_ENV": "production"}):
        res_prod_test = client.post(
            "/api/v1/payloads/ingest",
            json={"channel": "email", "recipient": "test@example.com", "data": {"text": "Test"}},
            headers={"X-API-Key": test_key}
        )
        assert res_prod_test.status_code == 403
        assert "Test credentials cannot be used in a production environment" in res_prod_test.get_json()["message"]

    # In test environment: live credentials must be blocked with HTTP 403
    with patch.dict(app.config, {"APP_ENV": "test"}):
        res_test_live = client.post(
            "/api/v1/payloads/ingest",
            json={"channel": "email", "recipient": "test@example.com", "data": {"text": "Test"}},
            headers={"X-API-Key": live_key}
        )
        assert res_test_live.status_code == 403
        assert "Live credentials cannot be used in a test environment" in res_test_live.get_json()["message"]


# ===========================================================================
# 3. ORGANIZATION ADMINISTRATOR PROTECTION (OPS-01)
# ===========================================================================

def test_administrator_self_deactivation_prevention(client, setup_context):
    """An administrator cannot deactivate their own account (HTTP 409)."""
    headers = setup_context["headers_a1"]
    admin_id = setup_context["user_admin_a1"]

    res = client.delete(f"/api/v1/users/{admin_id}", headers=headers)
    assert res.status_code == 409
    assert "cannot deactivate their own account" in res.get_json()["message"].lower()

    # Via PATCH /users/<id>
    res_patch = client.patch(
        f"/api/v1/users/{admin_id}",
        json={"is_active": False},
        headers=headers
    )
    assert res_patch.status_code == 409
    assert "cannot deactivate their own account" in res_patch.get_json()["message"].lower()


def test_last_active_administrator_invariant(app, setup_context):
    """The last active administrator in an organization cannot be deactivated (HTTP 409)."""
    with app.app_context():
        org_b = setup_context["org_b"]
        admin_b = setup_context["user_admin_b"]

        # In Org B, admin_b is the sole admin. Attempting to deactivate by a different actor must fail
        res = UserService.deactivate_user(admin_b, org_b, actor_id="different_actor_id")
        assert res["success"] is False
        assert res["status_code"] == 409
        assert "last active administrator" in res["message"].lower()


def test_multiple_administrators_deactivation_permitted(client, setup_context):
    """When multiple administrators exist, one admin can deactivate another admin."""
    headers_a1 = setup_context["headers_a1"]
    admin_a2 = setup_context["user_admin_a2"]

    # Admin A1 deactivates Admin A2 (since A1 is still active, remaining >= 1)
    res = client.delete(f"/api/v1/users/{admin_a2}", headers=headers_a1)
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Now Admin A2 is inactive. Admin A1 is now the sole active admin.
    # Attempting to deactivate Admin A1 must now be rejected!
    res_solo = client.delete(f"/api/v1/users/{setup_context['user_admin_a1']}", headers=headers_a1)
    assert res_solo.status_code == 409


# ===========================================================================
# 4. REDIS DISTRIBUTED RATE LIMITING (CRED-06)
# ===========================================================================

def test_distributed_rate_limiting_sliding_window(app):
    """Test sliding window rate limiting and Retry-After header."""
    with app.app_context():
        dim = "credential"
        ident = f"test_cred_{uuid.uuid4().hex[:6]}"
        DistributedRateLimiter.reset_key(dim, ident)

        # Allow 3 requests in a 10s window
        allowed_1, _ = DistributedRateLimiter.check_rate_limit(dim, ident, limit=3, window_seconds=10)
        allowed_2, _ = DistributedRateLimiter.check_rate_limit(dim, ident, limit=3, window_seconds=10)
        allowed_3, _ = DistributedRateLimiter.check_rate_limit(dim, ident, limit=3, window_seconds=10)
        assert allowed_1 and allowed_2 and allowed_3

        # 4th request must be rejected with retry_after > 0
        allowed_4, retry_after = DistributedRateLimiter.check_rate_limit(dim, ident, limit=3, window_seconds=10)
        assert allowed_4 is False
        assert retry_after > 0

        # Reset
        DistributedRateLimiter.reset_key(dim, ident)


def test_rate_limiter_fails_closed_in_production(app):
    """When Redis is unavailable in production, rate limiter must fail closed."""
    with app.app_context():
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=None):
            with patch.dict(app.config, {"APP_ENV": "production"}):
                with pytest.raises(RateLimiterError):
                    DistributedRateLimiter.check_rate_limit("credential", "test_id", limit=10)


# ===========================================================================
# 5. LEGACY PAYLOAD ENCRYPTION MIGRATION (ENC-05)
# ===========================================================================

def test_payload_encryption_migration_idempotent(app):
    """Test batch migration of legacy plaintext payloads with dry-run and roundtrip verification."""
    with app.app_context():
        db = app.mongo_db
        test_payload_id = f"legacy_payload_{uuid.uuid4().hex[:8]}"

        plaintext = {"sensitive_token": "secret_123", "order_id": 999}
        db["ingested_payloads"].insert_one({
            "payload_id": test_payload_id,
            "organization_id": "test_org",
            "original_payload": plaintext,
            "current_payload": plaintext,
            "status": "STORED"
        })

        # 1. Dry run: verify without modifying DB
        dry_res = PayloadMigrationService.migrate_legacy_payloads(batch_size=100, dry_run=True, collections=["ingested_payloads"])
        assert dry_res["dry_run"] is True
        assert dry_res["migrated"] >= 1
        raw_doc = db["ingested_payloads"].find_one({"payload_id": test_payload_id})
        assert raw_doc["original_payload"] == plaintext  # Unchanged in DB

        # 2. Live migration
        live_res = PayloadMigrationService.migrate_legacy_payloads(batch_size=100, dry_run=False, collections=["ingested_payloads"])
        assert live_res["dry_run"] is False
        assert live_res["migrated"] >= 1

        raw_migrated = db["ingested_payloads"].find_one({"payload_id": test_payload_id})
        assert raw_migrated["original_payload"]["_encrypted"] is True
        assert "ciphertext" in raw_migrated["original_payload"]

        # 3. Decrypt verified
        decrypted = PayloadEncryption.decrypt_dict(raw_migrated["original_payload"])
        assert decrypted == plaintext

        # 4. Clean up
        db["ingested_payloads"].delete_one({"payload_id": test_payload_id})


def test_disabling_plaintext_fallback_rejects_unencrypted(app):
    """When ALLOW_PLAINTEXT_PAYLOAD_FALLBACK is False, plaintext payload raises error."""
    with app.app_context():
        with patch.dict(app.config, {"ALLOW_PLAINTEXT_PAYLOAD_FALLBACK": False}):
            unencrypted = {"field": "value"}
            with pytest.raises(PayloadEncryptionError):
                PayloadEncryption.decrypt_dict(unencrypted)


# ===========================================================================
# 6. ENCRYPTION KEY ROTATION (ENC-06)
# ===========================================================================

def test_encryption_key_rotation_multifernet(app):
    """Test that MultiFernet can decrypt envelopes created with previous keys and re-encrypt with active key."""
    with app.app_context():
        old_key = Fernet.generate_key().decode("ascii")
        active_key = Fernet.generate_key().decode("ascii")

        # 1. Encrypt with old key directly
        old_fernet = Fernet(old_key.encode("ascii"))
        secret_dict = {"account_number": "1234-5678-9012", "amount": 5000}
        old_token = old_fernet.encrypt(json.dumps(secret_dict).encode("utf-8")).decode("ascii")
        envelope = {
            "_encrypted": True,
            "algorithm": "Fernet/AES-128-CBC+HMAC-SHA256",
            "key_version": "v1",
            "ciphertext": old_token
        }

        # 2. Configure PayloadEncryption with active_key as primary and old_key as previous
        with patch.dict(app.config, {
            "CREDENTIAL_ENCRYPTION_KEY": active_key,
            "CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS": [old_key],
            "CREDENTIAL_ENCRYPTION_KEY_VERSION": "v2"
        }):
            # MultiFernet decrypts old envelope seamlessly
            decrypted = PayloadEncryption.decrypt_dict(envelope)
            assert decrypted == secret_dict

            # Re-encrypt envelope under current active key (v2)
            new_envelope, was_rotated = PayloadEncryption.reencrypt_envelope(envelope)
            assert was_rotated is True
            assert new_envelope["key_version"] == "v2"

            # Primary key alone can now decrypt the new envelope
            active_fernet = Fernet(active_key.encode("ascii"))
            decrypted_new = json.loads(active_fernet.decrypt(new_envelope["ciphertext"].encode("ascii")).decode("utf-8"))
            assert decrypted_new == secret_dict
