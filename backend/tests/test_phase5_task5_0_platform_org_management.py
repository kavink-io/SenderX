"""
SenderX Phase 5 Task 5.0: Platform Admin Organization Management Test Suite

Tests:
1. Organization creation via Platform Admin API.
2. MongoDB document structure: name, slug, status, organization_id, admin user with ORG_ADMIN role.
3. Organization listing with pagination (page, limit, total, total_pages).
4. Search by organization name (case-insensitive, partial matching).
5. Search by organization slug (case-insensitive, partial matching).
6. Filter by organization status (ACTIVE vs INACTIVE).
7. Organization details retrieval (GET /organizations/<id>) with admin contact and counts.
8. Status toggle (PATCH /organizations/<id>/status).
9. Security & RBAC:
   - Only SUPER_ADMIN can list all organizations.
   - ORG_ADMIN is forbidden from platform listing (403).
   - EMPLOYEE is forbidden from platform listing (403).
   - Only SUPER_ADMIN can create organizations via platform API.
   - Cross-tenant isolation preserved.
"""

import uuid
import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.auth.repository import AuthRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
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
def platform_test_context(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]

        # 1. Super Admin
        super_admin_id = f"super_admin_{suffix}"
        AuthRepository.create_admin({
            "admin_id": super_admin_id,
            "email": f"super_{suffix}@senderx.io",
            "password_hash": "dummy_hash",
            "role": "SUPER_ADMIN",
            "is_active": True
        })

        token_super = create_access_token(
            identity=super_admin_id,
            additional_claims={
                "account_type": "PLATFORM_ADMIN",
                "role": "SUPER_ADMIN",
                "email": f"super_{suffix}@senderx.io"
            }
        )

        # 2. Organization Admin
        org_id = f"org_{suffix}"
        OrganizationRepository.create({
            "organization_id": org_id,
            "name": f"Platform Context Corp {suffix}",
            "slug": f"plat-corp-{suffix}",
            "status": "ACTIVE"
        })

        all_perms = list(UserService.ALLOWED_ORGANIZATION_PERMISSIONS)
        admin_role_id = f"role_admin_{suffix}"
        RoleRepository.create({
            "role_id": admin_role_id,
            "organization_id": org_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "is_system_role": True,
            "permissions": all_perms
        })

        org_admin = UserRepository.create({
            "user_id": f"org_admin_{suffix}",
            "organization_id": org_id,
            "name": "Org Admin User",
            "email": f"orgadmin_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "role_ids": [admin_role_id],
            "role_assignments": [{"role_id": admin_role_id, "role_name": "ORG_ADMIN"}],
            "is_active": True
        })

        token_org_admin = create_access_token(
            identity=org_admin["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_id,
                "role": "ORG_ADMIN",
                "is_org_admin": True,
                "permissions": all_perms
            }
        )

        # 3. Regular Employee
        dev_user = UserRepository.create({
            "user_id": f"dev_{suffix}",
            "organization_id": org_id,
            "name": "Developer Employee",
            "email": f"dev_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "role_ids": [],
            "role_assignments": [],
            "is_active": True
        })

        token_dev = create_access_token(
            identity=dev_user["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_id,
                "role": "DEVELOPER",
                "is_org_admin": False,
                "permissions": ["organization:messages:read"]
            }
        )

        return {
            "suffix": suffix,
            "org_id": org_id,
            "super_headers": {"Authorization": f"Bearer {token_super}"},
            "org_admin_headers": {"Authorization": f"Bearer {token_org_admin}"},
            "dev_headers": {"Authorization": f"Bearer {token_dev}"}
        }


# ============================================================================
# 1. Organization Creation & MongoDB Verification
# ============================================================================
def test_super_admin_create_organization(app, client, platform_test_context):
    headers = platform_test_context["super_headers"]
    suffix = uuid.uuid4().hex[:6]

    payload = {
        "name": f"Enterprise Test {suffix}",
        "slug": f"ent-test-{suffix}",
        "admin_name": f"Admin Ent {suffix}",
        "admin_email": f"admin_ent_{suffix}@enterprisetest.io",
        "admin_password": "Password123!@#"
    }

    res = client.post("/api/v1/organizations/", json=payload, headers=headers)
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True
    data = body["data"]

    org_id = data["organization_id"]
    assert data["organization_name"] == payload["name"]
    assert data["slug"] == payload["slug"]
    assert data["admin"]["email"] == payload["admin_email"]
    assert data["admin"]["role"] == "ORG_ADMIN"

    # Verify MongoDB record directly
    with app.app_context():
        org_doc = OrganizationRepository.find_by_id(org_id)
        assert org_doc is not None
        assert org_doc["name"] == payload["name"]
        assert org_doc["slug"] == payload["slug"]
        assert org_doc["status"] == "ACTIVE"
        assert "created_at" in org_doc

        # Verify admin user in MongoDB
        admin_user = UserRepository.find_by_email(payload["admin_email"])
        assert admin_user is not None
        assert admin_user["organization_id"] == org_id
        assert admin_user["is_active"] is True


# ============================================================================
# 2. Organization Listing & Pagination
# ============================================================================
def test_list_organizations_pagination(client, platform_test_context):
    headers = platform_test_context["super_headers"]

    # Page 1 with limit 10
    res = client.get("/api/v1/organizations/?page=1&limit=10", headers=headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert len(body["data"]) <= 10
    assert "pagination" in body
    p = body["pagination"]
    assert p["page"] == 1
    assert p["limit"] == 10
    assert p["total"] >= 1
    assert p["total_pages"] >= 1

    # Items must be sorted newest first
    items = body["data"]
    if len(items) >= 2:
        assert items[0]["created_at"] >= items[1]["created_at"]


# ============================================================================
# 3. Search by Organization Name & Slug
# ============================================================================
def test_search_organization_name_and_slug(client, platform_test_context):
    headers = platform_test_context["super_headers"]
    suffix = uuid.uuid4().hex[:6]

    # Create target org with distinct name and slug
    client.post("/api/v1/organizations/", json={
        "name": f"UniqueSearchQueryCompany {suffix}",
        "slug": f"unique-slug-{suffix}",
        "admin_name": "Search Admin",
        "admin_email": f"search_admin_{suffix}@query.io",
        "admin_password": "Password123!@#"
    }, headers=headers)

    # Search by partial name (case-insensitive)
    name_res = client.get(f"/api/v1/organizations/?search=uniquesearchquerycompany", headers=headers)
    assert name_res.status_code == 200
    name_body = name_res.get_json()
    assert any(o["slug"] == f"unique-slug-{suffix}" for o in name_body["data"])

    # Search by slug
    slug_res = client.get(f"/api/v1/organizations/?search=unique-slug-{suffix}", headers=headers)
    assert slug_res.status_code == 200
    slug_body = slug_res.get_json()
    assert len(slug_body["data"]) == 1
    assert slug_body["data"][0]["slug"] == f"unique-slug-{suffix}"

    # Search for non-existent org
    none_res = client.get("/api/v1/organizations/?search=NON_EXISTENT_NAME_QUERY_9999", headers=headers)
    assert none_res.status_code == 200
    assert len(none_res.get_json()["data"]) == 0
    assert none_res.get_json()["pagination"]["total"] == 0


# ============================================================================
# 4. Status Filtering (ACTIVE vs INACTIVE)
# ============================================================================
def test_status_filtering(client, platform_test_context):
    headers = platform_test_context["super_headers"]
    suffix = uuid.uuid4().hex[:6]

    # Create org to deactivate
    create_res = client.post("/api/v1/organizations/", json={
        "name": f"Deactivation Target {suffix}",
        "slug": f"deact-target-{suffix}",
        "admin_name": "Deact Admin",
        "admin_email": f"deact_admin_{suffix}@target.io",
        "admin_password": "Password123!@#"
    }, headers=headers)
    org_id = create_res.get_json()["data"]["organization_id"]

    # Deactivate org
    deact_res = client.patch(f"/api/v1/organizations/{org_id}/status", json={"status": "INACTIVE"}, headers=headers)
    assert deact_res.status_code == 200
    assert deact_res.get_json()["data"]["status"] == "INACTIVE"

    # Filter ACTIVE only -> should not contain deactivated org
    active_res = client.get(f"/api/v1/organizations/?search=deact-target-{suffix}&status=ACTIVE", headers=headers)
    assert active_res.status_code == 200
    assert len(active_res.get_json()["data"]) == 0

    # Filter INACTIVE only -> should find the deactivated org
    inactive_res = client.get(f"/api/v1/organizations/?search=deact-target-{suffix}&status=INACTIVE", headers=headers)
    assert inactive_res.status_code == 200
    assert len(inactive_res.get_json()["data"]) == 1
    assert inactive_res.get_json()["data"][0]["status"] == "INACTIVE"

    # Reactivate org
    react_res = client.patch(f"/api/v1/organizations/{org_id}/status", json={"status": "ACTIVE"}, headers=headers)
    assert react_res.status_code == 200
    assert react_res.get_json()["data"]["status"] == "ACTIVE"


# ============================================================================
# 5. Organization Details Endpoint
# ============================================================================
def test_get_organization_details(client, platform_test_context):
    headers = platform_test_context["super_headers"]
    suffix = uuid.uuid4().hex[:6]

    create_res = client.post("/api/v1/organizations/", json={
        "name": f"Details Target {suffix}",
        "slug": f"details-target-{suffix}",
        "admin_name": f"Detail Admin {suffix}",
        "admin_email": f"details_{suffix}@target.io",
        "admin_password": "Password123!@#"
    }, headers=headers)
    org_id = create_res.get_json()["data"]["organization_id"]

    res = client.get(f"/api/v1/organizations/{org_id}", headers=headers)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["organization_id"] == org_id
    assert data["name"] == f"Details Target {suffix}"
    assert data["slug"] == f"details-target-{suffix}"
    assert data["status"] == "ACTIVE"
    assert data["user_count"] >= 1
    assert "admin" in data
    assert data["admin"]["email"] == f"details_{suffix}@target.io"


# ============================================================================
# 6. Security & RBAC Enforcement
# ============================================================================
def test_security_rbac_restrictions(client, platform_test_context):
    org_admin_headers = platform_test_context["org_admin_headers"]
    dev_headers = platform_test_context["dev_headers"]
    org_id = platform_test_context["org_id"]

    # 1. ORG_ADMIN forbidden from platform listing
    res1 = client.get("/api/v1/organizations/", headers=org_admin_headers)
    assert res1.status_code == 403
    assert "Platform administrator access required" in res1.get_json()["message"]

    # 2. EMPLOYEE forbidden from platform listing
    res2 = client.get("/api/v1/organizations/", headers=dev_headers)
    assert res2.status_code == 403

    # 3. ORG_ADMIN forbidden from platform organization creation
    res3 = client.post("/api/v1/organizations/", json={
        "name": "Unauthorized Org",
        "slug": "unauth-org",
        "admin_name": "Admin",
        "admin_email": "admin@unauth.com",
        "admin_password": "Password123!@#"
    }, headers=org_admin_headers)
    assert res3.status_code == 403

    # 4. ORG_ADMIN forbidden from getting another organization by ID via platform endpoint
    res4 = client.get(f"/api/v1/organizations/{org_id}", headers=org_admin_headers)
    assert res4.status_code == 403

    # 5. ORG_ADMIN forbidden from updating status
    res5 = client.patch(f"/api/v1/organizations/{org_id}/status", json={"status": "INACTIVE"}, headers=org_admin_headers)
    assert res5.status_code == 403

    # 6. ORG_ADMIN CAN access their own organization via /current
    res6 = client.get("/api/v1/organizations/current", headers=org_admin_headers)
    assert res6.status_code == 200
    assert res6.get_json()["data"]["organization_id"] == org_id
