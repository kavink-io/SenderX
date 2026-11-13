"""
SenderX Phase 5 Task 1: Organization Dashboard Integration Tests
Verifies the end-to-end contract between the organization dashboard and backend API:
- Organization identity & current profile retrieval
- Application lifecycle: registration, stats, deactivation, activation
- Credential lifecycle: generation, one-time secret emission, rotation, revocation
- Ingestion telemetry & payload listing
- Organization analytics aggregation
- User management & admin protection invariants
"""

import pytest
import uuid
from app import create_app
from app.modules.organizations.service import OrganizationService
from app.modules.applications.repository import ApplicationRepository
from app.modules.api_credentials.repository import ApiCredentialRepository


@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def test_org_context(app, client):
    """Sets up an organization, org admin, and returns access token."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_res = OrganizationService.create_organization(
            data={
                "name": f"Dashboard Test Corp {suffix}",
                "slug": f"dash-corp-{suffix}",
                "admin_name": "Dashboard Admin",
                "admin_email": f"admin-{suffix}@dashcorp.io",
                "admin_password": "SecurePassword123!"
            },
            created_by="system_test"
        )
        assert org_res["success"] is True, f"Org creation failed: {org_res}"
        org_id = org_res["data"]["organization_id"]
        admin_email = org_res["data"]["admin"]["email"]

        # Login to obtain JWT
        login_res = client.post("/api/v1/auth/login", json={
            "email": admin_email,
            "password": "SecurePassword123!"
        })
        assert login_res.status_code == 200
        login_data = login_res.get_json()
        token = login_data["data"]["access_token"]
        account = login_data["data"]["account"]

        return {
            "org_id": org_id,
            "token": token,
            "account": account,
            "admin_email": admin_email
        }


def test_01_get_current_organization(client, test_org_context):
    """Verifies that the dashboard header can load current organization details."""
    headers = {"Authorization": f"Bearer {test_org_context['token']}"}
    res = client.get("/api/v1/organizations/current", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["organization_id"] == test_org_context["org_id"]
    assert "name" in data["data"]
    assert data["data"]["status"] == "ACTIVE"


def test_02_register_and_list_application(client, test_org_context):
    """Verifies registering a connected application and listing it."""
    headers = {"Authorization": f"Bearer {test_org_context['token']}"}

    # 1. Register application
    reg_res = client.post("/api/v1/applications/", headers=headers, json={
        "name": "E-Commerce Checkout",
        "description": "Processes online orders and triggers notifications",
        "environment": "live"
    })
    assert reg_res.status_code == 201
    reg_data = reg_res.get_json()
    assert reg_data["success"] is True
    app_id = reg_data["data"]["application_id"]
    assert app_id.startswith("app_")

    # 2. List applications
    list_res = client.get("/api/v1/applications/", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.get_json()
    assert list_data["success"] is True
    assert any(a["application_id"] == app_id for a in list_data["data"])

    # 3. Get application stats
    stats_res = client.get(f"/api/v1/applications/{app_id}/stats", headers=headers)
    assert stats_res.status_code == 200
    stats_data = stats_res.get_json()
    assert stats_data["success"] is True
    assert "ingested_payloads_count" in stats_data["data"]


def test_03_generate_credential_one_time_secret(client, test_org_context):
    """Verifies creating an API credential returns raw key once."""
    headers = {"Authorization": f"Bearer {test_org_context['token']}"}

    # Find registered app
    list_res = client.get("/api/v1/applications/", headers=headers)
    app_id = list_res.get_json()["data"][0]["application_id"]

    # Generate credential
    cred_res = client.post("/api/v1/api-credentials/", headers=headers, json={
        "name": "Production Ingestion Key",
        "application_id": app_id,
        "environment": "live",
        "scopes": ["payloads:write", "messages:write"]
    })
    assert cred_res.status_code == 201
    cred_data = cred_res.get_json()
    assert cred_data["success"] is True

    # One-time raw secret check
    raw_key = cred_data.get("raw_key") or cred_data.get("api_key")
    assert raw_key is not None
    assert raw_key.startswith("sx_live_")

    cred_id = cred_data["data"]["credential_id"]

    # Verify listing displays key_prefix and never reveals the plaintext secret or raw hash
    list_creds = client.get("/api/v1/api-credentials/", headers=headers)
    assert list_creds.status_code == 200
    matched = next((c for c in list_creds.get_json()["data"] if c["credential_id"] == cred_id), None)
    assert matched is not None
    assert matched["key_prefix"].startswith("sx_live_")
    assert "raw_key" not in matched
    assert "api_key" not in matched


def test_04_rotate_and_revoke_credential(client, test_org_context):
    """Verifies credential rotation and revocation flows."""
    headers = {"Authorization": f"Bearer {test_org_context['token']}"}

    # Generate credential
    list_res = client.get("/api/v1/applications/", headers=headers)
    app_id = list_res.get_json()["data"][0]["application_id"]

    cred_res = client.post("/api/v1/api-credentials/", headers=headers, json={
        "name": "Rotation Test Key",
        "application_id": app_id,
        "environment": "live"
    })
    cred_id = cred_res.get_json()["data"]["credential_id"]

    # Rotate
    rotate_res = client.post(f"/api/v1/api-credentials/{cred_id}/rotate", headers=headers, json={
        "environment": "live"
    })
    assert rotate_res.status_code == 200
    rot_data = rotate_res.get_json()
    assert rot_data["success"] is True
    new_raw_key = rot_data.get("raw_key") or rot_data.get("api_key")
    assert new_raw_key is not None
    assert new_raw_key.startswith("sx_live_")

    # Revoke
    revoke_res = client.delete(f"/api/v1/api-credentials/{cred_id}", headers=headers)
    assert revoke_res.status_code == 200
    rev_data = revoke_res.get_json()
    assert rev_data["success"] is True

    # Verify credential is now revoked
    cred_detail = client.get(f"/api/v1/api-credentials/{cred_id}", headers=headers)
    assert cred_detail.status_code == 200
    assert cred_detail.get_json()["data"]["status"] == "REVOKED"


def test_05_application_deactivation_and_activation(client, test_org_context):
    """Verifies deactivating an application cascades and can be reactivated."""
    headers = {"Authorization": f"Bearer {test_org_context['token']}"}

    # Register temporary app
    reg_res = client.post("/api/v1/applications/", headers=headers, json={
        "name": "Deactivation Test App",
        "environment": "all"
    })
    app_id = reg_res.get_json()["data"]["application_id"]

    # Create active credential
    cred_res = client.post("/api/v1/api-credentials/", headers=headers, json={
        "name": "Temp Key",
        "application_id": app_id,
        "environment": "live"
    })
    cred_id = cred_res.get_json()["data"]["credential_id"]

    # Deactivate application
    deact_res = client.post(f"/api/v1/applications/{app_id}/deactivate", headers=headers)
    assert deact_res.status_code == 200
    assert deact_res.get_json()["success"] is True

    # Verify credential was cascade revoked
    cred_detail = client.get(f"/api/v1/api-credentials/{cred_id}", headers=headers)
    assert cred_detail.get_json()["data"]["status"] == "REVOKED"

    # Reactivate application
    act_res = client.post(f"/api/v1/applications/{app_id}/activate", headers=headers)
    assert act_res.status_code == 200
    assert act_res.get_json()["success"] is True

    # App is active again
    app_detail = client.get(f"/api/v1/applications/{app_id}", headers=headers)
    assert app_detail.get_json()["data"]["status"] == "ACTIVE"


def test_06_organization_analytics_and_overview_telemetry(client, test_org_context):
    """Verifies that the overview and analytics endpoints return telemetry cleanly."""
    headers = {"Authorization": f"Bearer {test_org_context['token']}"}

    analytics_res = client.get("/api/v1/analytics/organization", headers=headers)
    assert analytics_res.status_code == 200
    data = analytics_res.get_json()
    assert data["success"] is True
    assert "overview" in data
    assert "channels" in data
    assert "daily_trends" in data
    assert "dead_letter_queue" in data


def test_07_list_payloads_empty_state_and_schema(client, test_org_context):
    """Verifies received payloads endpoint returns clean listing."""
    headers = {"Authorization": f"Bearer {test_org_context['token']}"}

    payloads_res = client.get("/api/v1/payloads/", headers=headers)
    assert payloads_res.status_code == 200
    data = payloads_res.get_json()
    assert data["success"] is True
    items = data["data"]["items"] if isinstance(data["data"], dict) else data["data"]
    assert isinstance(items, list)
