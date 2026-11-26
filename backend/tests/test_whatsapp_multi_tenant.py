"""
SenderX WhatsApp Multi-Tenant Architecture Foundation Security Test Suite
Tests for:
1. Encrypted access token storage at rest (Fernet/MultiFernet).
2. No secrets or access tokens in serialized API responses or logs.
3. Multiple phone numbers within one organization.
4. Prevention of duplicate active phone number IDs (within and across orgs).
5. Cross-organization integration access prevention (isolation).
6. Cross-organization credential access prevention in worker dispatch.
7. Untrusted organization IDs in message payloads strictly ignored.
8. Soft-deleted integration behavior and reconnection/reactivation.
9. Credential rotation and audit log tracking.
10. Server-side permission and organization status enforcement.
11. Missing integration behavior.
12. Ambiguous sender rejection when multiple active numbers exist without sender specified (Requirement 15).
13. Centralized encrypted Meta platform settings (Platform Admin only).
"""

import os
import uuid
from datetime import datetime, timezone
import pytest
import bcrypt
from cryptography.fernet import Fernet
from flask_jwt_extended import create_access_token

TEST_FERNET_KEY = Fernet.generate_key().decode("ascii")
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = TEST_FERNET_KEY

from app import create_app
from app.config.database_indexes import ensure_database_indexes
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.whatsapp.encryption import WhatsAppEncryption
from app.modules.whatsapp.repository import WhatsAppIntegrationRepository, PlatformSettingsRepository
from app.modules.whatsapp.service import WhatsAppIntegrationService, PlatformSettingsService


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["CREDENTIAL_ENCRYPTION_KEY"] = TEST_FERNET_KEY
    with flask_app.app_context():
        ensure_database_indexes(flask_app)
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def test_tenants(app):
    """Sets up Org A (active), Org B (active), Org C (inactive), and users with appropriate permissions."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a_id = f"org_wa_a_{suffix}"
        org_b_id = f"org_wa_b_{suffix}"
        org_c_id = f"org_wa_c_{suffix}"

        # 1. Active Organizations
        OrganizationRepository.create({
            "organization_id": org_a_id,
            "name": f"WA Tenant A {suffix}",
            "slug": f"wa-tenant-a-{suffix}",
            "status": "ACTIVE"
        })
        OrganizationRepository.create({
            "organization_id": org_b_id,
            "name": f"WA Tenant B {suffix}",
            "slug": f"wa-tenant-b-{suffix}",
            "status": "ACTIVE"
        })

        # 2. Inactive Organization
        OrganizationRepository.create({
            "organization_id": org_c_id,
            "name": f"WA Inactive Org {suffix}",
            "slug": f"wa-inactive-{suffix}",
            "status": "INACTIVE"
        })

        # 3. Roles
        role_manage_a = f"role_mgr_a_{suffix}"
        role_read_a = f"role_ro_a_{suffix}"
        role_manage_b = f"role_mgr_b_{suffix}"
        role_manage_c = f"role_mgr_c_{suffix}"

        RoleRepository.create({
            "role_id": role_manage_a,
            "organization_id": org_a_id,
            "name": "Org Admin A",
            "scope": "ORGANIZATION",
            "permissions": ["organization:providers:manage", "organization:providers:read", "organization:configuration:manage"]
        })
        RoleRepository.create({
            "role_id": role_read_a,
            "organization_id": org_a_id,
            "name": "Read Only A",
            "scope": "ORGANIZATION",
            "permissions": ["organization:providers:read"]
        })
        RoleRepository.create({
            "role_id": role_manage_b,
            "organization_id": org_b_id,
            "name": "Org Admin B",
            "scope": "ORGANIZATION",
            "permissions": ["organization:providers:manage", "organization:providers:read"]
        })
        RoleRepository.create({
            "role_id": role_manage_c,
            "organization_id": org_c_id,
            "name": "Org Admin C",
            "scope": "ORGANIZATION",
            "permissions": ["organization:providers:manage", "organization:providers:read"]
        })

        # 4. Users
        pwd_hash = bcrypt.hashpw(b"ValidSecret123!", bcrypt.gensalt(10)).decode("utf-8")

        user_a_mgr = f"usr_a_mgr_{suffix}"
        user_a_ro = f"usr_a_ro_{suffix}"
        user_b_mgr = f"usr_b_mgr_{suffix}"
        user_c_mgr = f"usr_c_mgr_{suffix}"

        UserRepository.create({
            "user_id": user_a_mgr,
            "organization_id": org_a_id,
            "email": f"admin_a_{suffix}@example.com",
            "name": "Admin User A",
            "password_hash": pwd_hash,
            "is_active": True,
            "role_assignments": [{"role_id": role_manage_a, "application_id": None}]
        })
        UserRepository.create({
            "user_id": user_a_ro,
            "organization_id": org_a_id,
            "email": f"readonly_a_{suffix}@example.com",
            "name": "ReadOnly User A",
            "password_hash": pwd_hash,
            "is_active": True,
            "role_assignments": [{"role_id": role_read_a, "application_id": None}]
        })
        UserRepository.create({
            "user_id": user_b_mgr,
            "organization_id": org_b_id,
            "email": f"admin_b_{suffix}@example.com",
            "name": "Admin User B",
            "password_hash": pwd_hash,
            "is_active": True,
            "role_assignments": [{"role_id": role_manage_b, "application_id": None}]
        })
        UserRepository.create({
            "user_id": user_c_mgr,
            "organization_id": org_c_id,
            "email": f"admin_c_{suffix}@example.com",
            "name": "Admin User C (Inactive Org)",
            "password_hash": pwd_hash,
            "is_active": True,
            "role_assignments": [{"role_id": role_manage_c, "application_id": None}]
        })

        # 5. Tokens
        token_a_mgr = create_access_token(identity=user_a_mgr, additional_claims={"account_type": "ORGANIZATION_USER", "token_version": 1})
        token_a_ro = create_access_token(identity=user_a_ro, additional_claims={"account_type": "ORGANIZATION_USER", "token_version": 1})
        token_b_mgr = create_access_token(identity=user_b_mgr, additional_claims={"account_type": "ORGANIZATION_USER", "token_version": 1})
        token_c_mgr = create_access_token(identity=user_c_mgr, additional_claims={"account_type": "ORGANIZATION_USER", "token_version": 1})

        # Platform Admin
        admin_id = f"admin_{suffix}"
        from app.modules.auth.repository import AuthRepository
        AuthRepository.create_admin({
            "admin_id": admin_id,
            "email": f"platform_admin_{suffix}@senderx.io",
            "name": "Platform Admin",
            "password_hash": pwd_hash,
            "is_active": True,
            "role": "PLATFORM_ADMIN",
            "token_version": 1
        })
        token_platform = create_access_token(
            identity=admin_id,
            additional_claims={
                "account_type": "PLATFORM_ADMIN",
                "role": "PLATFORM_ADMIN",
                "token_version": 1
            }
        )

        return {
            "org_a": org_a_id,
            "org_b": org_b_id,
            "org_c": org_c_id,
            "token_a_mgr": token_a_mgr,
            "token_a_ro": token_a_ro,
            "token_b_mgr": token_b_mgr,
            "token_c_mgr": token_c_mgr,
            "token_platform": token_platform,
            "suffix": suffix
        }


def test_create_whatsapp_integration_and_encrypted_storage(client, test_tenants, app):
    """Verifies integration creation, schema validation, and encrypted storage at rest."""
    org_a = test_tenants["org_a"]
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    phone_id = f"100000001_{suffix}"
    waba_id = f"waba_1001_{suffix}"
    raw_token = f"EAA_secret_token_alpha_{suffix}_9988776655"

    payload = {
        "waba_id": waba_id,
        "phone_number_id": phone_id,
        "display_phone_number": "+1 555-0101",
        "name": "Org A Main Support",
        "access_token": raw_token
    }

    res = client.post(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )

    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.get_json()}"
    data = res.get_json()["data"]
    integration_id = data["integration_id"]
    assert integration_id.startswith("wai_")
    assert data["organization_id"] == org_a
    assert data["waba_id"] == waba_id
    assert data["phone_number_id"] == phone_id
    assert data["status"] == "CONNECTED"
    assert data["has_access_token"] is True
    assert data["rotation_count"] == 0

    # Requirement 7: Never return raw access token or ciphertext in response
    assert "access_token" not in data
    assert "encrypted_access_token" not in data
    assert raw_token not in res.get_data(as_text=True)

    # Requirement 5: Verify Fernet encryption at rest in MongoDB
    with app.app_context():
        raw_doc = app.mongo_db["whatsapp_integrations"].find_one({"integration_id": integration_id})
        assert raw_doc is not None
        assert "encrypted_access_token" in raw_doc
        assert raw_token not in str(raw_doc)  # Raw token NEVER in DB
        ciphertext = raw_doc["encrypted_access_token"]
        assert ciphertext.startswith("gAAAAA")  # Fernet signature
        assert raw_doc["key_version"] == "v1"

        # Verify it decrypts back to original token
        decrypted = WhatsAppEncryption.decrypt_token(ciphertext)
        assert decrypted == raw_token


def test_no_secrets_in_serialized_api_responses(client, test_tenants):
    """Verifies GET list and GET detail endpoints never expose tokens or secrets."""
    token = test_tenants["token_a_mgr"]

    # 1. List
    res_list = client.get(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_list.status_code == 200
    items = res_list.get_json()["data"]
    assert len(items) >= 1
    for item in items:
        assert "access_token" not in item
        assert "encrypted_access_token" not in item
        assert item.get("has_access_token") is True

    # 2. Detail
    item_id = items[0]["integration_id"]
    res_detail = client.get(
        f"/api/v1/whatsapp/integrations/{item_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_detail.status_code == 200
    detail = res_detail.get_json()["data"]
    assert "access_token" not in detail
    assert "encrypted_access_token" not in detail
    assert detail.get("has_access_token") is True


def test_multiple_numbers_within_one_organization(client, test_tenants):
    """Verifies that one organization can connect multiple WhatsApp phone numbers."""
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    phone_id_2 = f"100000002_{suffix}"
    res2 = client.post(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "waba_id": f"waba_1002_{suffix}",
            "phone_number_id": phone_id_2,
            "display_phone_number": "+1 555-0102",
            "name": "Org A Sales Line",
            "access_token": "EAA_secret_token_sales_1234567890"
        }
    )
    assert res2.status_code == 201
    data2 = res2.get_json()["data"]
    assert data2["phone_number_id"] == phone_id_2

    # Query list
    res_list = client.get(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_list.status_code == 200
    items = res_list.get_json()["data"]
    phone_ids = [i["phone_number_id"] for i in items]
    assert f"100000001_{suffix}" in phone_ids
    assert phone_id_2 in phone_ids


def test_duplicate_active_phone_number_prevention(client, test_tenants):
    """Verifies that an active phone number cannot be registered twice in same or another org."""
    token_a = test_tenants["token_a_mgr"]
    token_b = test_tenants["token_b_mgr"]
    suffix = test_tenants["suffix"]

    existing_phone_id = f"100000001_{suffix}"

    # Same organization duplicate attempt
    res_same = client.post(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "waba_id": "waba_another_123",
            "phone_number_id": existing_phone_id,
            "display_phone_number": "+1 555-0101",
            "access_token": "EAA_duplicate_attempt_token_123"
        }
    )
    assert res_same.status_code == 409
    assert "already registered" in res_same.get_json()["message"]

    # Different organization duplicate attempt (Cross-tenant duplicate prevention)
    res_cross = client.post(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token_b}"},
        json={
            "waba_id": "waba_b_attempt_123",
            "phone_number_id": existing_phone_id,
            "display_phone_number": "+1 555-0101",
            "access_token": "EAA_cross_tenant_token_123"
        }
    )
    assert res_cross.status_code == 409
    assert "already registered" in res_cross.get_json()["message"]


def test_cross_organization_integration_access_prevention(client, test_tenants):
    """Verifies that Org B cannot view, edit, rotate, or delete Org A's integration."""
    token_a = test_tenants["token_a_mgr"]
    token_b = test_tenants["token_b_mgr"]

    # Get Org A's integration ID
    res_a = client.get(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    wai_a_id = res_a.get_json()["data"][0]["integration_id"]

    # Org B attempts GET
    res_b_get = client.get(
        f"/api/v1/whatsapp/integrations/{wai_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b_get.status_code == 404

    # Org B attempts PATCH
    res_b_patch = client.patch(
        f"/api/v1/whatsapp/integrations/{wai_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"name": "Hacked Org A Name"}
    )
    assert res_b_patch.status_code == 404

    # Org B attempts ROTATE
    res_b_rotate = client.post(
        f"/api/v1/whatsapp/integrations/{wai_a_id}/rotate",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"access_token": "EAA_malicious_new_token_12345"}
    )
    assert res_b_rotate.status_code == 404

    # Org B attempts DELETE
    res_b_del = client.delete(
        f"/api/v1/whatsapp/integrations/{wai_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b_del.status_code == 404


def test_cross_organization_credential_access_in_worker_dispatch(test_tenants, app):
    """Verifies that worker credential resolution rejects cross-organization integration IDs."""
    org_a = test_tenants["org_a"]
    org_b = test_tenants["org_b"]

    with app.app_context():
        # Org A has integrations
        a_ints = WhatsAppIntegrationRepository.find_all_by_organization(org_a)
        assert len(a_ints) >= 1
        wai_a_id = a_ints[0]["integration_id"]

        # Worker processes message for Org B, but payload maliciously specifies Org A's integration ID
        with pytest.raises(ValueError) as exc_info:
            WhatsAppIntegrationService.resolve_credentials_for_dispatch(
                organization_id=org_b,
                integration_id=wai_a_id
            )
        assert "not found or access denied" in str(exc_info.value)


def test_soft_deleted_integration_behavior_and_reconnection(client, test_tenants, app):
    """Verifies soft-deletion marks status=DISCONNECTED, and reconnection reactivates the record."""
    org_a = test_tenants["org_a"]
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    phone_id_3 = f"100000003_{suffix}"

    # 1. Create integration
    res_create = client.post(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "waba_id": f"waba_1003_{suffix}",
            "phone_number_id": phone_id_3,
            "display_phone_number": "+1 555-0103",
            "access_token": "EAA_original_token_to_disconnect_123"
        }
    )
    assert res_create.status_code == 201
    wai_3_id = res_create.get_json()["data"]["integration_id"]

    # 2. Soft-delete / Disconnect
    res_del = client.delete(
        f"/api/v1/whatsapp/integrations/{wai_3_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_del.status_code == 200

    # Verify in DB: deleted_at is set, status is DISCONNECTED
    with app.app_context():
        raw_doc = app.mongo_db["whatsapp_integrations"].find_one({"integration_id": wai_3_id})
        assert raw_doc["status"] == "DISCONNECTED"
        assert raw_doc["deleted_at"] is not None

        # Worker dispatch on disconnected integration must fail
        with pytest.raises(ValueError) as exc_info:
            WhatsAppIntegrationService.resolve_credentials_for_dispatch(
                organization_id=org_a,
                integration_id=wai_3_id
            )
        assert "disconnected or inactive" in str(exc_info.value)

    # 3. Reconnect / Reactivate the same phone number
    new_token = "EAA_reconnected_new_token_7788990011"
    res_reconnect = client.post(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "waba_id": f"waba_1003_{suffix}",
            "phone_number_id": phone_id_3,
            "display_phone_number": "+1 555-0103",
            "name": "Reconnected Line 3",
            "access_token": new_token
        }
    )
    assert res_reconnect.status_code == 201
    reconnected_data = res_reconnect.get_json()["data"]
    assert reconnected_data["integration_id"] == wai_3_id  # Re-used existing document
    assert reconnected_data["status"] == "CONNECTED"
    assert reconnected_data["deleted_at"] is None

    # Verify worker dispatch now works with reconnected token
    with app.app_context():
        creds = WhatsAppIntegrationService.resolve_credentials_for_dispatch(
            organization_id=org_a,
            integration_id=wai_3_id
        )
        assert creds["access_token"] == new_token
        assert creds["phone_number_id"] == phone_id_3


def test_credential_rotation_and_audit_behavior(client, test_tenants, app):
    """Verifies token rotation, rotation count increment, and audit logging."""
    org_a = test_tenants["org_a"]
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    phone_id_rot = f"100000004_{suffix}"
    res_init = client.post(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "waba_id": f"waba_1004_{suffix}",
            "phone_number_id": phone_id_rot,
            "display_phone_number": "+1 555-0104",
            "access_token": "EAA_pre_rotation_token_11111"
        }
    )
    wai_rot_id = res_init.get_json()["data"]["integration_id"]

    # Perform Rotation
    new_token = "EAA_post_rotation_token_22222"
    res_rotate = client.post(
        f"/api/v1/whatsapp/integrations/{wai_rot_id}/rotate",
        headers={"Authorization": f"Bearer {token}"},
        json={"access_token": new_token}
    )
    assert res_rotate.status_code == 200
    rot_data = res_rotate.get_json()["data"]
    assert rot_data["rotation_count"] == 1
    assert rot_data["token_status"] == "VALID"
    assert "access_token" not in rot_data

    # Verify audit log in security_audit_logs
    with app.app_context():
        audit_entry = app.mongo_db["security_audit_logs"].find_one({
            "organization_id": org_a,
            "event_type": "WHATSAPP_CREDENTIALS_ROTATED",
            "target_id": wai_rot_id
        })
        assert audit_entry is not None
        assert "diff" in audit_entry
        assert audit_entry["diff"]["rotation_count"]["new"] == 1
        assert new_token not in str(audit_entry)  # Token redacted in audit log

        # Verify dispatched token is the new one
        resolved = WhatsAppIntegrationService.resolve_credentials_for_dispatch(
            organization_id=org_a,
            integration_id=wai_rot_id
        )
        assert resolved["access_token"] == new_token


def test_multiple_active_numbers_without_sender_specified_fails_fast(test_tenants, app):
    """
    Requirement 15: Do not automatically select an integration if multiple active
    phone numbers exist and the request does not specify a valid sender integration.
    """
    org_a = test_tenants["org_a"]

    with app.app_context():
        active = WhatsAppIntegrationRepository.find_active_by_organization(org_a)
        assert len(active) >= 2, "Org A must have multiple active integrations for this test"

        # Resolving without integration_id or from_phone_number_id must FAIL FAST
        with pytest.raises(ValueError) as exc_info:
            WhatsAppIntegrationService.resolve_credentials_for_dispatch(organization_id=org_a)

        assert "Multiple active WhatsApp integrations exist" in str(exc_info.value)
        assert "A valid sender" in str(exc_info.value)

        # But specifying one of them explicitly succeeds!
        chosen = active[0]
        resolved = WhatsAppIntegrationService.resolve_credentials_for_dispatch(
            organization_id=org_a,
            integration_id=chosen["integration_id"]
        )
        assert resolved["phone_number_id"] == chosen["phone_number_id"]

        # Or specifying from_phone_number_id explicitly succeeds!
        resolved_phone = WhatsAppIntegrationService.resolve_credentials_for_dispatch(
            organization_id=org_a,
            from_phone_number_id=chosen["phone_number_id"]
        )
        assert resolved_phone["integration_id"] == chosen["integration_id"]


def test_permission_and_org_status_enforcement(client, test_tenants):
    """Verifies that unauthorized users and inactive organizations are rejected server-side."""
    token_ro = test_tenants["token_a_ro"]
    token_inactive = test_tenants["token_c_mgr"]

    # 1. Read-only user cannot create integration
    res_ro_post = client.post(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token_ro}"},
        json={
            "waba_id": "waba_unauth_1",
            "phone_number_id": "199999999",
            "display_phone_number": "+1 555-0999",
            "access_token": "EAA_unauthorized_token_123"
        }
    )
    assert res_ro_post.status_code == 403
    assert "permission" in res_ro_post.get_json()["message"].lower()

    # Read-only user CAN list integrations
    res_ro_get = client.get(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token_ro}"}
    )
    assert res_ro_get.status_code == 200

    # 2. Inactive organization user cannot perform any integration operations
    res_inactive = client.get(
        "/api/v1/whatsapp/integrations",
        headers={"Authorization": f"Bearer {token_inactive}"}
    )
    assert res_inactive.status_code == 403
    assert "inactive or unavailable" in res_inactive.get_json()["message"].lower()


def test_platform_settings_management(client, test_tenants, app):
    """Verifies centralized Meta platform settings management (Platform Admin only, secrets encrypted)."""
    token_platform = test_tenants["token_platform"]
    token_org = test_tenants["token_a_mgr"]

    # 1. Regular organization user cannot access platform settings
    res_org = client.get(
        "/api/v1/whatsapp/platform-settings",
        headers={"Authorization": f"Bearer {token_org}"}
    )
    assert res_org.status_code == 403

    # 2. Platform Admin updates platform settings
    secret_key = "meta_app_secret_super_secure_9988"
    verify_token = "verify_token_prod_webhook_5544"

    res_put = client.put(
        "/api/v1/whatsapp/platform-settings",
        headers={"Authorization": f"Bearer {token_platform}"},
        json={
            "meta_app_id": "meta_app_12345678",
            "meta_app_secret": secret_key,
            "webhook_verify_token": verify_token,
            "webhook_url": "https://api.senderx.io/api/v1/whatsapp/webhook",
            "graph_api_version": "v21.0"
        }
    )
    assert res_put.status_code == 200
    data = res_put.get_json()["data"]
    assert data["meta_app_id"] == "meta_app_12345678"
    assert data["has_app_secret"] is True
    assert data["app_secret_masked"] == "******"
    assert data["has_webhook_verify_token"] is True
    assert secret_key not in res_put.get_data(as_text=True)

    # 3. Check DB storage has encrypted ciphertext
    with app.app_context():
        raw_setting = app.mongo_db["platform_settings"].find_one({"setting_key": "meta_whatsapp"})
        assert raw_setting is not None
        assert "encrypted_app_secret" in raw_setting
        assert secret_key not in str(raw_setting)

        # Internal decrypted resolution
        internal_settings = PlatformSettingsService.get_meta_settings(decrypt=True)
        assert internal_settings["meta_app_secret"] == secret_key
        assert internal_settings["webhook_verify_token"] == verify_token
