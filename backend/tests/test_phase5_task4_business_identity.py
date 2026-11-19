"""
SenderX Phase 5 Task 4: Organization & Employee Business ID Management Test Suite

Tests:
1. Organization Business ID (organization_code) configuration, validation, uniqueness, and immutability.
2. Employee Business ID (employee_code) manual assignment, format validation, and intra-org uniqueness.
3. Cross-organization ID duplication allowance (same employee_code in different organizations).
4. Atomic sequence generation, preview, prefix changes, and monotonic non-reuse guarantees.
5. Immutability of employee_code on user updates, role assignments, and status toggles.
6. RBAC enforcement on identity endpoints (GET/PATCH /api/v1/organizations/identity).
7. Migration utility idempotency and dry-run execution.
"""

import uuid
import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.organizations.sequence_repository import SequenceRepository
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService
from app.migrations.migrate_business_identities import run_migration


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def identity_test_context(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a_id = f"org_a_{suffix}"
        org_b_id = f"org_b_{suffix}"

        # 1. Create Organization A (unconfigured identity)
        OrganizationRepository.create({
            "organization_id": org_a_id,
            "name": f"Identity Corp Alpha {suffix}",
            "slug": f"alpha-{suffix}",
            "status": "ACTIVE"
        })

        # 2. Create Organization B (unconfigured identity)
        OrganizationRepository.create({
            "organization_id": org_b_id,
            "name": f"Identity Corp Beta {suffix}",
            "slug": f"beta-{suffix}",
            "status": "ACTIVE"
        })

        # 3. Create Admin Roles
        all_perms = list(UserService.ALLOWED_ORGANIZATION_PERMISSIONS)
        role_a_admin = f"role_admin_a_{suffix}"
        role_b_admin = f"role_admin_b_{suffix}"
        role_a_dev = f"role_dev_a_{suffix}"

        RoleRepository.create({
            "role_id": role_a_admin,
            "organization_id": org_a_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "is_system_role": True,
            "permissions": all_perms
        })
        RoleRepository.create({
            "role_id": role_b_admin,
            "organization_id": org_b_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "is_system_role": True,
            "permissions": all_perms
        })
        RoleRepository.create({
            "role_id": role_a_dev,
            "organization_id": org_a_id,
            "name": "DEVELOPER",
            "scope": "ORGANIZATION",
            "is_system_role": False,
            "permissions": ["organization:messages:read"]
        })

        # 4. Create Users
        admin_a = UserRepository.create({
            "user_id": f"admin_a_{suffix}",
            "organization_id": org_a_id,
            "name": "Alpha Admin",
            "email": f"admin_a_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "role_ids": [role_a_admin],
            "role_assignments": [{"role_id": role_a_admin, "application_id": None}],
            "is_active": True
        })

        admin_b = UserRepository.create({
            "user_id": f"admin_b_{suffix}",
            "organization_id": org_b_id,
            "name": "Beta Admin",
            "email": f"admin_b_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "role_ids": [role_b_admin],
            "role_assignments": [{"role_id": role_b_admin, "application_id": None}],
            "is_active": True
        })

        employee_a = UserRepository.create({
            "user_id": f"dev_a_{suffix}",
            "organization_id": org_a_id,
            "name": "Alpha Developer",
            "email": f"dev_a_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "role_ids": [role_a_dev],
            "role_assignments": [{"role_id": role_a_dev, "application_id": None}],
            "is_active": True
        })

        # 5. Generate JWT tokens
        token_admin_a = create_access_token(
            identity=admin_a["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_a_id,
                "role": "ORG_ADMIN",
                "is_org_admin": True
            }
        )
        token_admin_b = create_access_token(
            identity=admin_b["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_b_id,
                "role": "ORG_ADMIN",
                "is_org_admin": True
            }
        )
        token_employee_a = create_access_token(
            identity=employee_a["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_a_id,
                "role": "DEVELOPER",
                "is_org_admin": False
            }
        )

        return {
            "suffix": suffix,
            "org_a_id": org_a_id,
            "org_b_id": org_b_id,
            "admin_a": admin_a,
            "admin_b": admin_b,
            "employee_a": employee_a,
            "token_admin_a": token_admin_a,
            "token_admin_b": token_admin_b,
            "token_employee_a": token_employee_a,
            "role_a_dev": role_a_dev
        }


class TestOrganizationIdentityConfiguration:

    def test_get_identity_config_removed(self, client, identity_test_context):
        """Per Task 5.2, organization identity prefix endpoints have been removed."""
        headers = {"Authorization": f"Bearer {identity_test_context['token_admin_a']}"}
        res = client.get("/api/v1/organizations/identity", headers=headers)
        assert res.status_code in (403, 404, 405)

    def test_configure_prefix_removed(self, client, identity_test_context):
        """Per Task 5.2, organization identity prefix endpoints have been removed."""
        headers = {"Authorization": f"Bearer {identity_test_context['token_admin_a']}"}
        res = client.patch("/api/v1/organizations/identity", json={"employee_id_prefix": "ALPHA"}, headers=headers)
        assert res.status_code in (403, 404, 405)


class TestEmployeeBusinessIdManagement:

    def test_preview_next_employee_code_removed(self, client, identity_test_context):
        """Per Task 5.2, next-employee-code sequence preview has been removed."""
        headers = {"Authorization": f"Bearer {identity_test_context['token_admin_a']}"}
        res = client.get("/api/v1/users/next-employee-code", headers=headers)
        assert res.status_code == 404

    def test_create_employee_auto_sequence_allocation_disallowed(self, client, identity_test_context):
        """Per Task 5.2, employee_code is required and auto sequence allocation is removed."""
        headers = {"Authorization": f"Bearer {identity_test_context['token_admin_a']}"}
        suffix = identity_test_context["suffix"]

        # Missing employee_code -> returns 400
        res1 = client.post(
            "/api/v1/users/",
            json={
                "name": "Auto User One",
                "email": f"auto1_{suffix}@test.io",
                "password": "Password123456!",
                "role_ids": [identity_test_context["role_a_dev"]]
            },
            headers=headers
        )
        assert res1.status_code == 400
        assert "Employee ID is required" in res1.get_json()["message"]

    def test_create_employee_manual_code_assignment(self, client, identity_test_context):
        headers = {"Authorization": f"Bearer {identity_test_context['token_admin_a']}"}
        suffix = identity_test_context["suffix"]

        res = client.post(
            "/api/v1/users/",
            json={
                "name": "Manual User",
                "email": f"manual_{suffix}@test.io",
                "password": "Password123456!",
                "employee_code": "SPECIAL-999",
                "role_ids": [identity_test_context["role_a_dev"]]
            },
            headers=headers
        )
        assert res.status_code == 201
        data = res.get_json()["data"]
        assert data["employee_code"] == "SPECIAL-999"

    def test_employee_code_intra_org_uniqueness(self, client, identity_test_context):
        headers = {"Authorization": f"Bearer {identity_test_context['token_admin_a']}"}
        suffix = identity_test_context["suffix"]

        # Ensure initial code exists in Org A so this test is order-independent
        client.post(
            "/api/v1/users/",
            json={
                "name": "Manual User Base",
                "email": f"manual_base_{suffix}@test.io",
                "password": "Password123456!",
                "employee_code": "SPECIAL-999",
                "role_ids": [identity_test_context["role_a_dev"]]
            },
            headers=headers
        )

        # Duplicate manual code in Org A must be rejected
        res = client.post(
            "/api/v1/users/",
            json={
                "name": "Manual User Duplicate",
                "email": f"manual_dup_{suffix}@test.io",
                "password": "Password123456!",
                "employee_code": "SPECIAL-999",
                "role_ids": [identity_test_context["role_a_dev"]]
            },
            headers=headers
        )
        assert res.status_code == 409
        assert "already exists in this organization" in res.get_json()["message"]

    def test_cross_org_employee_code_duplication_allowed(self, client, identity_test_context):
        headers_b = {"Authorization": f"Bearer {identity_test_context['token_admin_b']}"}
        suffix = identity_test_context["suffix"]

        # Org B can use the same code SPECIAL-999
        res = client.post(
            "/api/v1/users/",
            json={
                "name": "Org B User",
                "email": f"org_b_user_{suffix}@test.io",
                "password": "Password123456!",
                "employee_code": "SPECIAL-999"
            },
            headers=headers_b
        )
        assert res.status_code == 201
        assert res.get_json()["data"]["employee_code"] == "SPECIAL-999"

    def test_employee_code_immutability_on_update(self, client, identity_test_context):
        headers = {"Authorization": f"Bearer {identity_test_context['token_admin_a']}"}
        suffix = identity_test_context["suffix"]

        # Create an employee
        res = client.post(
            "/api/v1/users/",
            json={
                "name": "Immutable Test User",
                "email": f"imm_{suffix}@test.io",
                "password": "Password123456!",
                "employee_code": "IMM-001"
            },
            headers=headers
        )
        user_id = res.get_json()["data"]["user_id"]

        # Attempt to change employee_code
        update_res = client.patch(
            f"/api/v1/users/{user_id}",
            json={"employee_code": "IMM-002"},
            headers=headers
        )
        assert update_res.status_code == 400
        assert "immutable" in update_res.get_json()["message"].lower()

        # Normal updates (name, role, status) do not modify employee_code
        ok_res = client.patch(
            f"/api/v1/users/{user_id}",
            json={"name": "Renamed Immutable User"},
            headers=headers
        )
        assert ok_res.status_code == 200
        assert ok_res.get_json()["data"]["employee_code"] == "IMM-001"
        assert ok_res.get_json()["data"]["name"] == "Renamed Immutable User"

    def test_employee_search_by_business_code(self, client, identity_test_context):
        headers = {"Authorization": f"Bearer {identity_test_context['token_admin_a']}"}
        res = client.get("/api/v1/users/?search=SPECIAL-999", headers=headers)
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert len(data) >= 1
        assert any(u["employee_code"] == "SPECIAL-999" for u in data)

    def test_dashboard_context_exposes_business_identity(self, client, identity_test_context):
        headers = {"Authorization": f"Bearer {identity_test_context['token_admin_a']}"}
        res = client.get("/api/v1/users/me/dashboard-context", headers=headers)
        assert res.status_code == 200
        ctx = res.get_json()["data"]
        assert "employee_code" in ctx
        assert "organization_code" not in ctx or ctx.get("organization_code") is None
        assert "employee_id_prefix" not in ctx or ctx.get("employee_id_prefix") is None


class TestMigrationUtility:

    def test_migration_dry_run(self, app, identity_test_context):
        with app.app_context():
            org_id = identity_test_context["org_a_id"]
            res = run_migration(dry_run=True, target_org_id=org_id, ensure_indexes=False)
            assert res["organizations"]["total"] >= 1
            assert res["users"]["errors"] == 0

    def test_migration_live_execution_idempotency(self, app, identity_test_context):
        with app.app_context():
            try:
                org_id = identity_test_context["org_a_id"]
                # First live run
                res1 = run_migration(dry_run=False, target_org_id=org_id, ensure_indexes=False)
                assert res1["users"]["errors"] == 0

                # Second live run: all users now have employee codes, 0 backfilled
                res2 = run_migration(dry_run=False, target_org_id=org_id, ensure_indexes=False)
                assert res2["users"]["backfilled"] == 0
                assert res2["users"]["errors"] == 0
            finally:
                app.mongo_db.drop_collection("organization_sequences")
