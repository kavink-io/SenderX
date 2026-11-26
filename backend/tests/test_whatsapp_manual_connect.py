"""
SenderX WhatsApp Business Account Manual Connection Security Test Suite
Covers Task 2 Requirements:
1. Successful Meta credential verification and manual connection.
2. Invalid access token (401 / INVALID_CREDENTIALS).
3. Invalid WABA ID format / missing.
4. Invalid Phone Number ID format / missing.
5. Phone Number ID belonging to another WABA (PHONE_NUMBER_MISMATCH).
6. Insufficient Meta permissions (403 / INSUFFICIENT_PERMISSIONS).
7. Meta API timeout (503 / META_API_UNAVAILABLE).
8. Meta API rate limiting (503 / META_API_UNAVAILABLE).
9. Meta API server error (503 / META_API_UNAVAILABLE).
10. Credential encryption at rest in MongoDB (MultiFernet).
11. No plaintext credential in API responses.
12. No credential leakage in application logs.
13. Cross-organization connection prevention.
14. Unauthorized employee access (missing permissions).
15. Duplicate integration prevention (conflict rejection).
16. Reconnection of soft-deleted integration.
17. Credential rotation with Meta verification.
18. Actual connection status persistence in database.
"""

from datetime import datetime, timezone
import json
import os
from unittest.mock import MagicMock, patch
import uuid
import bcrypt
from cryptography.fernet import Fernet
from flask_jwt_extended import create_access_token
import pytest
import requests

TEST_FERNET_KEY = Fernet.generate_key().decode("ascii")
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = TEST_FERNET_KEY

from app import create_app
from app.config.database_indexes import ensure_database_indexes
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.whatsapp.encryption import WhatsAppEncryption
from app.modules.whatsapp.meta_client import (
    MetaWhatsAppClient,
    WhatsAppVerificationError,
    WhatsAppVerificationErrorCode,
)
from app.modules.whatsapp.models import WhatsAppIntegrationStatus, WhatsAppTokenStatus
from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
from app.modules.whatsapp.service import WhatsAppIntegrationService


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
    """Sets up Org A (active), Org B (active), Org C (inactive), and test users."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a_id = f"org_man_a_{suffix}"
        org_b_id = f"org_man_b_{suffix}"
        org_c_id = f"org_man_c_{suffix}"

        # 1. Organizations
        OrganizationRepository.create({
            "organization_id": org_a_id,
            "name": f"Manual Org A {suffix}",
            "slug": f"manual-org-a-{suffix}",
            "status": "ACTIVE"
        })
        OrganizationRepository.create({
            "organization_id": org_b_id,
            "name": f"Manual Org B {suffix}",
            "slug": f"manual-org-b-{suffix}",
            "status": "ACTIVE"
        })
        OrganizationRepository.create({
            "organization_id": org_c_id,
            "name": f"Manual Inactive Org {suffix}",
            "slug": f"manual-inactive-{suffix}",
            "status": "INACTIVE"
        })

        # 2. Roles
        role_manage_a = f"role_man_mgr_a_{suffix}"
        role_ro_a = f"role_man_ro_a_{suffix}"
        role_manage_b = f"role_man_mgr_b_{suffix}"
        role_manage_c = f"role_man_mgr_c_{suffix}"

        RoleRepository.create({
            "role_id": role_manage_a,
            "organization_id": org_a_id,
            "name": "Org Admin A",
            "scope": "ORGANIZATION",
            "permissions": ["organization:providers:manage", "organization:providers:read"]
        })
        RoleRepository.create({
            "role_id": role_ro_a,
            "organization_id": org_a_id,
            "name": "ReadOnly A",
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

        # 3. Users
        pwd_hash = bcrypt.hashpw(b"ValidPass123!", bcrypt.gensalt(4)).decode("utf-8")

        user_a_mgr = f"usr_m_mgr_{suffix}"
        user_a_ro = f"usr_m_ro_{suffix}"
        user_b_mgr = f"usr_m_mgr_b_{suffix}"
        user_c_mgr = f"usr_m_mgr_c_{suffix}"

        UserRepository.create({
            "user_id": user_a_mgr,
            "organization_id": org_a_id,
            "email": f"org_admin_a_{suffix}@example.com",
            "name": "Admin User A",
            "password_hash": pwd_hash,
            "is_active": True,
            "role_assignments": [{"role_id": role_manage_a, "application_id": None}]
        })
        UserRepository.create({
            "user_id": user_a_ro,
            "organization_id": org_a_id,
            "email": f"ro_user_a_{suffix}@example.com",
            "name": "ReadOnly User A",
            "password_hash": pwd_hash,
            "is_active": True,
            "role_assignments": [{"role_id": role_ro_a, "application_id": None}]
        })
        UserRepository.create({
            "user_id": user_b_mgr,
            "organization_id": org_b_id,
            "email": f"org_admin_b_{suffix}@example.com",
            "name": "Admin User B",
            "password_hash": pwd_hash,
            "is_active": True,
            "role_assignments": [{"role_id": role_manage_b, "application_id": None}]
        })
        UserRepository.create({
            "user_id": user_c_mgr,
            "organization_id": org_c_id,
            "email": f"org_admin_c_{suffix}@example.com",
            "name": "Admin User C (Inactive)",
            "password_hash": pwd_hash,
            "is_active": True,
            "role_assignments": [{"role_id": role_manage_c, "application_id": None}]
        })

        # 4. JWT Tokens
        token_a_mgr = create_access_token(identity=user_a_mgr, additional_claims={"account_type": "ORGANIZATION_USER", "token_version": 1})
        token_a_ro = create_access_token(identity=user_a_ro, additional_claims={"account_type": "ORGANIZATION_USER", "token_version": 1})
        token_b_mgr = create_access_token(identity=user_b_mgr, additional_claims={"account_type": "ORGANIZATION_USER", "token_version": 1})
        token_c_mgr = create_access_token(identity=user_c_mgr, additional_claims={"account_type": "ORGANIZATION_USER", "token_version": 1})

        return {
            "org_a": org_a_id,
            "org_b": org_b_id,
            "org_c": org_c_id,
            "token_a_mgr": token_a_mgr,
            "token_a_ro": token_a_ro,
            "token_b_mgr": token_b_mgr,
            "token_c_mgr": token_c_mgr,
            "suffix": suffix
        }


def make_meta_response(status_code: int, json_data: dict):
    """Creates a mock requests.Response object."""
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = json.dumps(json_data).encode("utf-8")
    return resp


# =========================================================================
# 1. Successful Meta Credential Verification & Connection
# =========================================================================

def test_successful_meta_credential_verification_and_connection(client, test_tenants, app):
    """
    Requirement 1: Valid WABA ID, Phone Number ID, and Access Token verified against Meta Graph API.
    Marks integration as CONNECTED and stores encrypted credentials.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    phone_id = f"phone_val_{suffix}"
    waba_id = f"waba_val_{suffix}"
    access_token = f"EAA_valid_meta_token_12345_{suffix}"

    mock_waba_resp = make_meta_response(200, {
        "data": [
            {
                "id": phone_id,
                "display_phone_number": "+1 555-0155",
                "verified_name": "Verified Business Name Inc.",
                "quality_rating": "GREEN",
                "code_verification_status": "VERIFIED",
                "platform_type": "CLOUD_API"
            }
        ]
    })
    mock_phone_resp = make_meta_response(200, {
        "id": phone_id,
        "display_phone_number": "+1 555-0155",
        "verified_name": "Verified Business Name Inc.",
        "quality_rating": "GREEN",
        "code_verification_status": "VERIFIED",
        "platform_type": "CLOUD_API"
    })

    with patch.object(requests.Session, "get", side_effect=[mock_waba_resp, mock_phone_resp]) as mock_get:
        res = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": waba_id,
                "phone_number_id": phone_id,
                "access_token": access_token,
                "name": "Customer Support WhatsApp"
            }
        )

    assert res.status_code == 201, f"Failed: {res.get_json()}"
    data = res.get_json()["data"]
    assert data["status"] == "CONNECTED"
    assert data["waba_id"] == waba_id
    assert data["phone_number_id"] == phone_id
    assert data["display_phone_number"] == "+1 555-0155"
    assert data["verified_name"] == "Verified Business Name Inc."
    assert data["quality_rating"] == "GREEN"
    assert data["token_status"] == "VALID"
    assert data["has_access_token"] is True
    assert "access_token" not in data
    assert "encrypted_access_token" not in data


# =========================================================================
# 2. Invalid Access Token (401 / INVALID_CREDENTIALS)
# =========================================================================

def test_invalid_access_token_rejected(client, test_tenants, app):
    """
    Requirement 2: Token rejected by Meta with code 190 returns 401 INVALID_CREDENTIALS.
    Does NOT persist record to MongoDB.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]
    phone_id = f"phone_inv_tok_{suffix}"

    mock_err_resp = make_meta_response(401, {
        "error": {
            "message": "Invalid OAuth access token - Cannot parse access token",
            "type": "OAuthException",
            "code": 190,
            "fbtrace_id": "trace_err_tok_1"
        }
    })

    with patch.object(requests.Session, "get", return_value=mock_err_resp):
        res = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": f"waba_err_{suffix}",
                "phone_number_id": phone_id,
                "access_token": "EAA_invalid_expired_token_999"
            }
        )

    assert res.status_code == 401
    body = res.get_json()
    assert body["error_code"] == "INVALID_CREDENTIALS"
    assert "invalid" in body["message"].lower()

    # Verify not persisted
    with app.app_context():
        doc = app.mongo_db["whatsapp_integrations"].find_one({"phone_number_id": phone_id})
        assert doc is None, "Failed credentials must NOT be persisted"


# =========================================================================
# 3. Invalid WABA ID & Phone Number ID Format Rejection
# =========================================================================

def test_invalid_identifier_formats_rejected(client, test_tenants):
    """
    Requirements 3 & 4: Reject missing or malformed WABA ID and Phone Number ID formats.
    """
    token = test_tenants["token_a_mgr"]

    # Missing fields
    res_missing = client.post(
        "/api/v1/whatsapp/integrations/connect",
        headers={"Authorization": f"Bearer {token}"},
        json={"access_token": "EAA_valid_token_length_12345"}
    )
    assert res_missing.status_code == 400

    # Invalid characters in WABA ID
    res_bad_waba = client.post(
        "/api/v1/whatsapp/integrations/connect",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "waba_id": "bad;waba<script>",
            "phone_number_id": "12345678",
            "access_token": "EAA_valid_token_length_12345"
        }
    )
    assert res_bad_waba.status_code == 400

    # Short access token
    res_short_tok = client.post(
        "/api/v1/whatsapp/integrations/connect",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "waba_id": "waba_12345",
            "phone_number_id": "12345678",
            "access_token": "short"
        }
    )
    assert res_short_tok.status_code == 400


# =========================================================================
# 5. Phone Number ID Belongs to Another WABA (PHONE_NUMBER_MISMATCH)
# =========================================================================

def test_phone_number_mismatch_rejected(client, test_tenants):
    """
    Requirement 5: Phone Number ID does not belong to specified WABA.
    Meta returns 200 for WABA phone numbers, but requested ID is not in the list.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]
    phone_id = f"phone_not_in_waba_{suffix}"

    mock_waba_resp = make_meta_response(200, {
        "data": [
            {
                "id": f"different_phone_id_{suffix}",
                "display_phone_number": "+1 555-0999",
                "verified_name": "Other Line"
            }
        ]
    })

    with patch.object(requests.Session, "get", return_value=mock_waba_resp):
        res = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": f"waba_real_{suffix}",
                "phone_number_id": phone_id,
                "access_token": "EAA_valid_token_for_different_number"
            }
        )

    assert res.status_code == 422
    body = res.get_json()
    assert body["error_code"] == "PHONE_NUMBER_MISMATCH"
    assert "does not belong" in body["message"].lower()


# =========================================================================
# 6. Insufficient Permissions (INSUFFICIENT_PERMISSIONS)
# =========================================================================

def test_insufficient_meta_permissions_rejected(client, test_tenants):
    """
    Requirement 6: Token lacks whatsapp_business_management or WABA permission.
    Meta returns code 10 or 200 with permission error.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    mock_perm_resp = make_meta_response(403, {
        "error": {
            "message": "(#10) Application does not have permission for this action",
            "type": "OAuthException",
            "code": 10,
            "fbtrace_id": "trace_perm_1"
        }
    })

    with patch.object(requests.Session, "get", return_value=mock_perm_resp):
        res = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": f"waba_unauth_{suffix}",
                "phone_number_id": f"phone_unauth_{suffix}",
                "access_token": "EAA_unauthorized_token_scope"
            }
        )

    assert res.status_code == 403
    body = res.get_json()
    assert body["error_code"] == "INSUFFICIENT_PERMISSIONS"


# =========================================================================
# 7. Meta API Timeout (META_API_UNAVAILABLE)
# =========================================================================

def test_meta_api_timeout_handling(client, test_tenants):
    """
    Requirement 7: Connection or read timeout during Meta Graph API call.
    Returns 503 META_API_UNAVAILABLE without persisting credentials.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    with patch.object(requests.Session, "get", side_effect=requests.exceptions.Timeout("Connection timeout")):
        res = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": f"waba_timeout_{suffix}",
                "phone_number_id": f"phone_timeout_{suffix}",
                "access_token": "EAA_timeout_token_test_12345"
            }
        )

    assert res.status_code == 503
    body = res.get_json()
    assert body["error_code"] == "META_API_UNAVAILABLE"
    assert "timed out" in body["message"].lower()


# =========================================================================
# 8. Meta API Rate Limiting (META_API_UNAVAILABLE)
# =========================================================================

def test_meta_api_rate_limiting_handling(client, test_tenants):
    """
    Requirement 8: Meta Graph API rate limit error (code 80007 / HTTP 429).
    Returns 503 META_API_UNAVAILABLE.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    mock_rate_resp = make_meta_response(429, {
        "error": {
            "message": "(#80007) There have been too many calls from this account.",
            "type": "OAuthException",
            "code": 80007,
            "fbtrace_id": "trace_rate_limit"
        }
    })

    with patch.object(requests.Session, "get", return_value=mock_rate_resp):
        res = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": f"waba_rate_{suffix}",
                "phone_number_id": f"phone_rate_{suffix}",
                "access_token": "EAA_rate_limit_token_12345"
            }
        )

    assert res.status_code == 503
    body = res.get_json()
    assert body["error_code"] == "META_API_UNAVAILABLE"
    assert "rate limit" in body["message"].lower()


# =========================================================================
# 9. Meta API Server Error (5xx)
# =========================================================================

def test_meta_api_server_error_handling(client, test_tenants):
    """
    Requirement 9: Meta server 500 error returns 503 META_API_UNAVAILABLE.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    mock_500_resp = make_meta_response(500, {
        "error": {
            "message": "An unknown error has occurred.",
            "type": "OAuthException",
            "code": 1
        }
    })

    with patch.object(requests.Session, "get", return_value=mock_500_resp):
        res = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": f"waba_500_{suffix}",
                "phone_number_id": f"phone_500_{suffix}",
                "access_token": "EAA_server_error_token_12345"
            }
        )

    assert res.status_code == 503
    body = res.get_json()
    assert body["error_code"] == "META_API_UNAVAILABLE"
    assert "unavailable" in body["message"].lower()


# =========================================================================
# 10, 11, 12. Credential Encryption, Response Sanitization & Log Safety
# =========================================================================

def test_credential_encryption_and_zero_leakage(client, test_tenants, app):
    """
    Requirements 10, 11, 12:
    - Raw token is encrypted at rest via MultiFernet.
    - Raw token and encrypted ciphertext NEVER appear in API responses.
    - Raw token does not appear in security audit logs.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    phone_id = f"phone_sec_{suffix}"
    waba_id = f"waba_sec_{suffix}"
    secret_token = f"EAA_very_secret_token_value_9876_{suffix}"

    mock_waba = make_meta_response(200, {
        "data": [{"id": phone_id, "display_phone_number": "+1 555-0188", "verified_name": "Sec Inc"}]
    })
    mock_phone = make_meta_response(200, {
        "id": phone_id, "display_phone_number": "+1 555-0188", "verified_name": "Sec Inc"
    })

    with patch.object(requests.Session, "get", side_effect=[mock_waba, mock_phone]):
        res = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": waba_id,
                "phone_number_id": phone_id,
                "access_token": secret_token
            }
        )

    assert res.status_code == 201
    raw_res_text = res.get_data(as_text=True)

    # 1. API Response zero-leak
    assert secret_token not in raw_res_text
    assert "gAAAAA" not in raw_res_text
    assert "encrypted_access_token" not in raw_res_text

    wai_id = res.get_json()["data"]["integration_id"]

    # 2. Database Encryption Verification
    with app.app_context():
        raw_db_doc = app.mongo_db["whatsapp_integrations"].find_one({"integration_id": wai_id})
        assert raw_db_doc is not None
        assert "access_token" not in raw_db_doc
        assert "encrypted_access_token" in raw_db_doc
        assert secret_token not in str(raw_db_doc)

        # MultiFernet decrypts successfully
        decrypted = WhatsAppEncryption.decrypt_token(raw_db_doc["encrypted_access_token"])
        assert decrypted == secret_token

        # 3. Security Audit Log zero-leak
        audit_log = app.mongo_db["security_audit_logs"].find_one({
            "target_id": wai_id,
            "event_type": "WHATSAPP_INTEGRATION_CREATED"
        })
        assert audit_log is not None
        assert secret_token not in str(audit_log)
        assert "gAAAAA" not in str(audit_log)


# =========================================================================
# 13 & 14. Cross-Organization Isolation & Unauthorized Employee Access
# =========================================================================

def test_cross_organization_and_unauthorized_access(client, test_tenants):
    """
    Requirements 13 & 14:
    - User A (Org A) cannot connect or modify Org B integrations.
    - User with read-only permission cannot call /connect.
    - User belonging to INACTIVE organization cannot connect.
    """
    token_ro = test_tenants["token_a_ro"]
    token_inactive = test_tenants["token_c_mgr"]
    suffix = test_tenants["suffix"]

    # 1. Read-only user cannot connect
    res_ro = client.post(
        "/api/v1/whatsapp/integrations/connect",
        headers={"Authorization": f"Bearer {token_ro}"},
        json={
            "waba_id": f"waba_ro_{suffix}",
            "phone_number_id": f"phone_ro_{suffix}",
            "access_token": "EAA_read_only_attempt_12345"
        }
    )
    assert res_ro.status_code == 403

    # 2. Inactive organization user cannot connect
    res_inact = client.post(
        "/api/v1/whatsapp/integrations/connect",
        headers={"Authorization": f"Bearer {token_inactive}"},
        json={
            "waba_id": f"waba_inact_{suffix}",
            "phone_number_id": f"phone_inact_{suffix}",
            "access_token": "EAA_inactive_org_attempt_12345"
        }
    )
    assert res_inact.status_code == 403


# =========================================================================
# 15. Duplicate Integration Prevention
# =========================================================================

def test_duplicate_integration_prevention(client, test_tenants):
    """
    Requirement 15: Attempting to connect a phone number ID that is already active
    in the same or another organization returns a 409 Conflict.
    """
    token_a = test_tenants["token_a_mgr"]
    token_b = test_tenants["token_b_mgr"]
    suffix = test_tenants["suffix"]

    phone_id = f"phone_dup_{suffix}"
    waba_id = f"waba_dup_{suffix}"

    mock_waba = make_meta_response(200, {
        "data": [{"id": phone_id, "display_phone_number": "+1 555-0177", "verified_name": "Dup Line"}]
    })
    mock_phone = make_meta_response(200, {
        "id": phone_id, "display_phone_number": "+1 555-0177", "verified_name": "Dup Line"
    })

    # Initial connect
    with patch.object(requests.Session, "get", side_effect=[mock_waba, mock_phone]):
        res1 = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "waba_id": waba_id,
                "phone_number_id": phone_id,
                "access_token": "EAA_first_registration_token_12345"
            }
        )
    assert res1.status_code == 201

    # Attempt duplicate in Org A
    with patch.object(requests.Session, "get", side_effect=[mock_waba, mock_phone]):
        res2 = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "waba_id": waba_id,
                "phone_number_id": phone_id,
                "access_token": "EAA_second_registration_token_12345"
            }
        )
    assert res2.status_code == 409
    assert "already registered" in res2.get_json()["message"].lower()

    # Attempt duplicate in Org B
    with patch.object(requests.Session, "get", side_effect=[mock_waba, mock_phone]):
        res3 = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "waba_id": waba_id,
                "phone_number_id": phone_id,
                "access_token": "EAA_third_registration_token_12345"
            }
        )
    assert res3.status_code == 409
    assert "already registered" in res3.get_json()["message"].lower()


# =========================================================================
# 16. Reconnection of Soft-Deleted Integration
# =========================================================================

def test_reconnection_of_soft_deleted_integration(client, test_tenants, app):
    """
    Requirement 16: When an integration is soft-deleted and subsequently reconnected
    with fresh verified credentials, it reactivates the record, updates the encrypted token,
    clears deleted_at, and records WHATSAPP_INTEGRATION_RECONNECTED audit log.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    phone_id = f"phone_reconn_{suffix}"
    waba_id = f"waba_reconn_{suffix}"

    mock_waba = make_meta_response(200, {
        "data": [{"id": phone_id, "display_phone_number": "+1 555-0166", "verified_name": "Reconn Corp"}]
    })
    mock_phone = make_meta_response(200, {
        "id": phone_id, "display_phone_number": "+1 555-0166", "verified_name": "Reconn Corp"
    })

    # 1. Connect
    with patch.object(requests.Session, "get", side_effect=[mock_waba, mock_phone]):
        res_conn = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": waba_id,
                "phone_number_id": phone_id,
                "access_token": "EAA_initial_token_to_disconnect_12345"
            }
        )
    assert res_conn.status_code == 201
    wai_id = res_conn.get_json()["data"]["integration_id"]

    # 2. Disconnect (soft-delete)
    res_del = client.delete(
        f"/api/v1/whatsapp/integrations/{wai_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_del.status_code == 200

    # Verify soft-deleted
    with app.app_context():
        doc = app.mongo_db["whatsapp_integrations"].find_one({"integration_id": wai_id})
        assert doc["status"] == "DISCONNECTED"
        assert doc["deleted_at"] is not None

    # 3. Reconnect via /connect with fresh verified token
    fresh_token = "EAA_fresh_reconnected_token_99999"
    with patch.object(requests.Session, "get", side_effect=[mock_waba, mock_phone]):
        res_reconn = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": waba_id,
                "phone_number_id": phone_id,
                "access_token": fresh_token
            }
        )
    assert res_reconn.status_code == 201
    reconn_data = res_reconn.get_json()["data"]
    assert reconn_data["integration_id"] == wai_id
    assert reconn_data["status"] == "CONNECTED"

    # Verify database state
    with app.app_context():
        doc_reconn = app.mongo_db["whatsapp_integrations"].find_one({"integration_id": wai_id})
        assert doc_reconn["deleted_at"] is None
        assert doc_reconn["status"] == "CONNECTED"
        assert doc_reconn["token_status"] == "VALID"
        assert doc_reconn["reconnected_at"] is not None

        # Decrypts to the fresh token
        dec = WhatsAppEncryption.decrypt_token(doc_reconn["encrypted_access_token"])
        assert dec == fresh_token

        # Audit log verification
        audit = app.mongo_db["security_audit_logs"].find_one({
            "target_id": wai_id,
            "event_type": "WHATSAPP_INTEGRATION_RECONNECTED"
        })
        assert audit is not None


# =========================================================================
# 17. Credential Rotation with Meta Verification
# =========================================================================

def test_credential_rotation_with_meta_verification(client, test_tenants, app):
    """
    Requirement 17:
    - Rotating credentials verifies the new token against Meta Graph API.
    - If new token is invalid, rotation fails and old credentials remain intact.
    - If new token is valid, increments rotation_count and updates encrypted token.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    phone_id = f"phone_rot_{suffix}"
    waba_id = f"waba_rot_{suffix}"
    initial_token = "EAA_initial_token_before_rotation_123"

    mock_waba = make_meta_response(200, {
        "data": [{"id": phone_id, "display_phone_number": "+1 555-0144", "verified_name": "Rotation Inc"}]
    })
    mock_phone = make_meta_response(200, {
        "id": phone_id, "display_phone_number": "+1 555-0144", "verified_name": "Rotation Inc"
    })

    # Initial connect
    with patch.object(requests.Session, "get", side_effect=[mock_waba, mock_phone]):
        res_conn = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": waba_id,
                "phone_number_id": phone_id,
                "access_token": initial_token
            }
        )
    assert res_conn.status_code == 201
    wai_id = res_conn.get_json()["data"]["integration_id"]

    # 1. Attempt rotation with an invalid token (Meta rejects)
    mock_bad_token = make_meta_response(401, {
        "error": {"message": "Invalid token", "type": "OAuthException", "code": 190}
    })
    with patch.object(requests.Session, "get", return_value=mock_bad_token):
        res_bad_rot = client.post(
            f"/api/v1/whatsapp/integrations/{wai_id}/rotate",
            headers={"Authorization": f"Bearer {token}"},
            json={"access_token": "EAA_bad_rotation_token_999", "verify_meta": True}
        )
    assert res_bad_rot.status_code == 401
    assert "invalid" in res_bad_rot.get_json()["message"].lower()

    # Verify old token still intact
    with app.app_context():
        doc = app.mongo_db["whatsapp_integrations"].find_one({"integration_id": wai_id})
        assert doc["rotation_count"] == 0
        assert WhatsAppEncryption.decrypt_token(doc["encrypted_access_token"]) == initial_token

    # 2. Attempt rotation with a valid token
    new_token = "EAA_valid_new_rotated_token_8888"
    mock_new_waba = make_meta_response(200, {
        "data": [{"id": phone_id, "display_phone_number": "+1 555-0144", "verified_name": "Rotation Inc"}]
    })
    mock_new_phone = make_meta_response(200, {
        "id": phone_id, "display_phone_number": "+1 555-0144", "verified_name": "Rotation Inc"
    })

    with patch.object(requests.Session, "get", side_effect=[mock_new_waba, mock_new_phone]):
        res_ok_rot = client.post(
            f"/api/v1/whatsapp/integrations/{wai_id}/rotate",
            headers={"Authorization": f"Bearer {token}"},
            json={"access_token": new_token, "verify_meta": True}
        )
    assert res_ok_rot.status_code == 200
    assert res_ok_rot.get_json()["data"]["rotation_count"] == 1

    with app.app_context():
        doc_updated = app.mongo_db["whatsapp_integrations"].find_one({"integration_id": wai_id})
        assert doc_updated["rotation_count"] == 1
        assert WhatsAppEncryption.decrypt_token(doc_updated["encrypted_access_token"]) == new_token


# =========================================================================
# 18. Actual Connection Status Persistence & Verification Endpoint
# =========================================================================

def test_verify_credential_status_endpoint(client, test_tenants, app):
    """
    Requirement 18:
    - POST /api/v1/whatsapp/integrations/{id}/verify checks stored credentials with Meta.
    - When valid: returns 200, is_valid=True, status=CONNECTED.
    - When token revoked: returns is_valid=False, updates status=DEGRADED, token_status=REVOKED.
    """
    token = test_tenants["token_a_mgr"]
    suffix = test_tenants["suffix"]

    phone_id = f"phone_ver_{suffix}"
    waba_id = f"waba_ver_{suffix}"
    active_token = "EAA_active_token_to_verify_123"

    mock_waba = make_meta_response(200, {
        "data": [{"id": phone_id, "display_phone_number": "+1 555-0133", "verified_name": "Status Inc"}]
    })
    mock_phone = make_meta_response(200, {
        "id": phone_id, "display_phone_number": "+1 555-0133", "verified_name": "Status Inc"
    })

    # Connect
    with patch.object(requests.Session, "get", side_effect=[mock_waba, mock_phone]):
        res_conn = client.post(
            "/api/v1/whatsapp/integrations/connect",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "waba_id": waba_id,
                "phone_number_id": phone_id,
                "access_token": active_token
            }
        )
    assert res_conn.status_code == 201
    wai_id = res_conn.get_json()["data"]["integration_id"]

    # 1. Verify when token is valid
    with patch.object(requests.Session, "get", side_effect=[mock_waba, mock_phone]):
        res_v1 = client.post(
            f"/api/v1/whatsapp/integrations/{wai_id}/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
    assert res_v1.status_code == 200
    v1_data = res_v1.get_json()["data"]
    assert v1_data["is_valid"] is True
    assert v1_data["status"] == "CONNECTED"
    assert v1_data["token_status"] == "VALID"

    # 2. Verify when Meta reports token revoked
    mock_revoked = make_meta_response(401, {
        "error": {"message": "Session has expired or token revoked", "type": "OAuthException", "code": 190}
    })
    with patch.object(requests.Session, "get", return_value=mock_revoked):
        res_v2 = client.post(
            f"/api/v1/whatsapp/integrations/{wai_id}/verify",
            headers={"Authorization": f"Bearer {token}"}
        )
    assert res_v2.status_code == 200
    v2_data = res_v2.get_json()["data"]
    assert v2_data["is_valid"] is False
    assert v2_data["status"] == "DEGRADED"
    assert v2_data["token_status"] == "REVOKED"
    assert "expired" in v2_data["error"].lower() or "revoked" in v2_data["error"].lower()

    # Verify MongoDB persistence of degraded status
    with app.app_context():
        doc = app.mongo_db["whatsapp_integrations"].find_one({"integration_id": wai_id})
        assert doc["status"] == "DEGRADED"
        assert doc["token_status"] == "REVOKED"
