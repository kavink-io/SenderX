"""
SenderX Provider Configuration Security & Multi-Tenant Test Suite
Tests:
- Unauthorized access rejection (401)
- Organization user access rejection for platform configs (403)
- SUPER_ADMIN authorized access for platform configs (200/201)
- Zero credential exposure in API responses
- Secure encrypted credential storage via Fernet
- Organization-scoped provider configuration isolation
"""

import uuid
import pytest
import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.auth.repository import AuthRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.provider_config.service import ProviderConfigService


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture
def test_context(app):
    suffix = uuid.uuid4().hex[:6]
    admin_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    role_id = str(uuid.uuid4())

    password_hash = bcrypt.hashpw(b"ValidPass1234!", bcrypt.gensalt(12)).decode("utf-8")

    with app.app_context():
        # 1. Super Admin
        AuthRepository.create_admin({
            "admin_id": admin_id,
            "email": f"superadmin-{suffix}@senderx.io",
            "password_hash": password_hash,
            "role": "SUPER_ADMIN",
            "is_active": True
        })

        # 2. Organization
        OrganizationRepository.create({
            "organization_id": org_id,
            "name": f"Test Org {suffix}",
            "slug": f"test-org-{suffix}",
            "status": "ACTIVE"
        })

        # 3. Organization Role with provider permissions
        RoleRepository.create({
            "role_id": role_id,
            "organization_id": org_id,
            "name": "Provider Admin",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:providers:manage",
                "organization:providers:read"
            ],
            "is_system_role": False
        })

        # 4. Organization User
        UserRepository.create({
            "user_id": user_id,
            "organization_id": org_id,
            "name": "Org User",
            "email": f"orguser-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_id],
            "is_active": True
        })

        # Generate JWT tokens
        admin_token = create_access_token(
            identity=admin_id,
            additional_claims={
                "account_type": "PLATFORM_ADMIN",
                "role": "SUPER_ADMIN",
                "email": f"superadmin-{suffix}@senderx.io"
            }
        )

        user_token = create_access_token(
            identity=user_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_id,
                "role_ids": [role_id],
                "email": f"orguser-{suffix}@test.io"
            }
        )

        yield {
            "admin_id": admin_id,
            "org_id": org_id,
            "user_id": user_id,
            "admin_token": admin_token,
            "user_token": user_token
        }

        # Cleanup
        AuthRepository._collection().delete_one({"admin_id": admin_id})
        OrganizationRepository._collection().delete_one({"organization_id": org_id})
        RoleRepository._collection().delete_one({"role_id": role_id})
        UserRepository._collection().delete_one({"user_id": user_id})
        app.mongo_db["provider_configs"].delete_many({
            "$or": [
                {"organization_id": org_id},
                {"provider": f"test-provider-{suffix}"}
            ]
        })


def test_unauthenticated_requests_rejected(client):
    """Unauthenticated requests must receive HTTP 401."""
    # POST without token
    res = client.post("/api/v1/provider-config/", json={"provider": "sendgrid", "credentials": {"api_key": "secret"}})
    assert res.status_code == 401

    # GET without token
    res = client.get("/api/v1/provider-config/")
    assert res.status_code == 401


def test_organization_user_blocked_from_platform_provider_config(client, test_context):
    """Organization users must be rejected from platform endpoints with HTTP 403."""
    headers = {"Authorization": f"Bearer {test_context['user_token']}"}

    # POST platform config with org token -> 403
    res = client.post(
        "/api/v1/provider-config/",
        headers=headers,
        json={"provider": "sendgrid", "credentials": {"api_key": "secret"}}
    )
    assert res.status_code == 403
    data = res.get_json()
    assert data["success"] is False
    assert "platform administrator access required" in data["message"].lower()

    # GET platform config with org token -> 403
    res = client.get("/api/v1/provider-config/", headers=headers)
    assert res.status_code == 403
    data = res.get_json()
    assert data["success"] is False
    assert "platform administrator access required" in data["message"].lower()


def test_super_admin_can_manage_platform_provider_config(client, test_context, app):
    """SUPER_ADMIN can configure platform provider and credentials are never exposed."""
    headers = {"Authorization": f"Bearer {test_context['admin_token']}"}
    provider_name = f"test-provider-{uuid.uuid4().hex[:6]}"
    secret_key = "SG.SUPER_SECRET_KEY_12345"

    # 1. Save platform config
    res = client.post(
        "/api/v1/provider-config/",
        headers=headers,
        json={
            "provider": provider_name,
            "credentials": {
                "api_key": secret_key,
                "from_email": "admin@senderx.io"
            }
        }
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True

    # 2. Get specific provider status
    res = client.get(f"/api/v1/provider-config/?provider={provider_name}", headers=headers)
    assert res.status_code == 200
    config_data = res.get_json()["data"]
    assert config_data["provider"] == provider_name
    assert config_data["configured"] is True
    assert config_data.get("updated_at")
    # Verify zero credentials exposure
    assert "credentials" not in config_data
    assert "api_key" not in str(res.get_json())
    assert secret_key not in str(res.get_json())

    # 3. Get all provider statuses
    res = client.get("/api/v1/provider-config/", headers=headers)
    assert res.status_code == 200
    all_configs = res.get_json()["data"]
    matched = next((c for c in all_configs if c["provider"] == provider_name), None)
    assert matched is not None
    assert "credentials" not in matched

    # 4. Verify secure encrypted storage in database
    with app.app_context():
        doc = app.mongo_db["provider_configs"].find_one({"provider": provider_name, "organization_id": None})
        assert doc is not None
        # Must be encrypted ciphertext, NOT plaintext
        assert doc["credentials"] != secret_key
        assert secret_key not in doc["credentials"]

        # Decrypt internal service test
        decrypted = ProviderConfigService.get_decrypted_configuration(provider_name)
        assert decrypted["api_key"] == secret_key


def test_organization_scoped_provider_config(client, test_context, app):
    """Organization users can manage their own provider config in isolation."""
    headers = {"Authorization": f"Bearer {test_context['user_token']}"}
    provider_name = f"test-provider-org-{uuid.uuid4().hex[:6]}"
    tenant_secret = "TENANT_SECRET_API_KEY_9999"

    # 1. Save org provider config
    res = client.post(
        "/api/v1/provider-config/organization",
        headers=headers,
        json={
            "provider": provider_name,
            "credentials": {
                "api_key": tenant_secret,
                "from_email": "tenant@test.io"
            }
        }
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["organization_id"] == test_context["org_id"]

    # 2. Get org provider config status
    res = client.get(f"/api/v1/provider-config/organization?provider={provider_name}", headers=headers)
    assert res.status_code == 200
    config_data = res.get_json()["data"]
    assert config_data["provider"] == provider_name
    assert config_data["configured"] is True
    assert "credentials" not in config_data
    assert tenant_secret not in str(res.get_json())

    rotated_secret = "TENANT_SECRET_API_KEY_ROTATED"
    update_res = client.post(
        "/api/v1/provider-config/organization",
        headers=headers,
        json={
            "provider": provider_name,
            "credentials": {"api_key": rotated_secret}
        }
    )
    assert update_res.status_code == 201

    # 3. Verify internal decryption is tenant-isolated
    with app.app_context():
        # Scoped to org
        decrypted_org = ProviderConfigService.get_decrypted_configuration(
            provider_name,
            organization_id=test_context["org_id"]
        )
        assert decrypted_org is not None
        assert decrypted_org["api_key"] == rotated_secret
        assert decrypted_org["from_email"] == "tenant@test.io"

        # Another org should not see it
        decrypted_other = ProviderConfigService.get_decrypted_configuration(
            provider_name,
            organization_id="other-org-id"
        )
        assert decrypted_other is None
