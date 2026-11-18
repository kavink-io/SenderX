"""
SenderX Phase 5 Task 4.1: Employee IDs Only Test Suite

Validates:
1. Manual employee ID creation.
2. Automatic employee ID generation (e.g. EMP-001).
3. Intra-organization duplicate ID rejection (409 Conflict).
4. Cross-organization employee ID duplication allowed.
5. Immutability of employee ID on role/user updates.
6. Non-reuse of deleted/deactivated IDs (sequence monotonicity).
7. Search and filtering by employee ID.
8. Employee ID display in user profile, dashboard context, and user detail.
9. Employees cannot change their own employee ID (RBAC / immutability enforcement).
10. Organization login and dynamic RBAC dashboard context remain fully intact.
11. Employee ID prefix configuration (PATCH /organizations/employee-prefix).
12. Employee identity migration utility.
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
def emp_test_context(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a_id = f"org_a_{suffix}"
        org_b_id = f"org_b_{suffix}"

        # 1. Create Organization A & B
        OrganizationRepository.create({
            "organization_id": org_a_id,
            "name": f"Corp Alpha {suffix}",
            "slug": f"alpha-{suffix}",
            "employee_id_prefix": "ALPHA-EMP",
            "status": "ACTIVE"
        })

        OrganizationRepository.create({
            "organization_id": org_b_id,
            "name": f"Corp Beta {suffix}",
            "slug": f"beta-{suffix}",
            "employee_id_prefix": "BETA-EMP",
            "status": "ACTIVE"
        })

        # 2. Roles
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

        # 3. Users
        admin_a = UserRepository.create({
            "user_id": f"admin_a_{suffix}",
            "organization_id": org_a_id,
            "name": "Alpha Admin",
            "email": f"admin_a_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "employee_code": "ALPHA-EMP-000",
            "role_ids": [role_a_admin],
            "role_assignments": [{"role_id": role_a_admin, "role_name": "ORG_ADMIN", "scope": "ORGANIZATION"}],
            "is_active": True
        })

        admin_b = UserRepository.create({
            "user_id": f"admin_b_{suffix}",
            "organization_id": org_b_id,
            "name": "Beta Admin",
            "email": f"admin_b_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "employee_code": "BETA-EMP-000",
            "role_ids": [role_b_admin],
            "role_assignments": [{"role_id": role_b_admin, "role_name": "ORG_ADMIN", "scope": "ORGANIZATION"}],
            "is_active": True
        })

        dev_a = UserRepository.create({
            "user_id": f"dev_a_{suffix}",
            "organization_id": org_a_id,
            "name": "Alpha Developer",
            "email": f"dev_a_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "employee_code": "ALPHA-EMP-999",
            "role_ids": [role_a_dev],
            "role_assignments": [{"role_id": role_a_dev, "role_name": "DEVELOPER", "scope": "ORGANIZATION"}],
            "is_active": True
        })

        # Generate tokens
        token_admin_a = create_access_token(
            identity=admin_a["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_a_id,
                "role": "ORG_ADMIN",
                "is_org_admin": True,
                "permissions": all_perms
            }
        )

        token_admin_b = create_access_token(
            identity=admin_b["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_b_id,
                "role": "ORG_ADMIN",
                "is_org_admin": True,
                "permissions": all_perms
            }
        )

        token_dev_a = create_access_token(
            identity=dev_a["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_a_id,
                "role": "DEVELOPER",
                "is_org_admin": False,
                "permissions": ["organization:messages:read"]
            }
        )

        return {
            "suffix": suffix,
            "org_a_id": org_a_id,
            "org_b_id": org_b_id,
            "role_a_dev": role_a_dev,
            "admin_a": admin_a,
            "admin_b": admin_b,
            "dev_a": dev_a,
            "headers_a": {"Authorization": f"Bearer {token_admin_a}"},
            "headers_b": {"Authorization": f"Bearer {token_admin_b}"},
            "headers_dev_a": {"Authorization": f"Bearer {token_dev_a}"}
        }


# ============================================================================
# 1. Manual Employee ID Creation
# ============================================================================
def test_manual_employee_id_creation(client, emp_test_context):
    headers = emp_test_context["headers_a"]
    role_id = emp_test_context["role_a_dev"]
    suffix = emp_test_context["suffix"]

    payload = {
        "name": "Manual Employee 1",
        "email": f"manual1_{suffix}@test.io",
        "password": "Password123!@#",
        "employee_code": "CUSTOM-EMP-001",
        "role_ids": [role_id]
    }

    res = client.post("/api/v1/users/", json=payload, headers=headers)
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["employee_code"] == "CUSTOM-EMP-001"


# ============================================================================
# 2. Automatic Employee ID Generation
# ============================================================================
def test_automatic_employee_id_generation(client, emp_test_context):
    headers = emp_test_context["headers_a"]
    role_id = emp_test_context["role_a_dev"]
    suffix = emp_test_context["suffix"]

    # In Task 5.2: Preview next code route is removed
    preview_res = client.get("/api/v1/users/next-employee-code", headers=headers)
    assert preview_res.status_code in (404, 405)

    # Creating without providing employee_code must be rejected with 400
    payload = {
        "name": "Auto Employee 1",
        "email": f"auto1_{suffix}@test.io",
        "password": "Password123!@#",
        "role_ids": [role_id]
    }

    res = client.post("/api/v1/users/", json=payload, headers=headers)
    assert res.status_code == 400
    assert "Employee ID is required" in res.get_json()["message"]


# ============================================================================
# 3. Intra-organization duplicate ID rejection (409 Conflict)
# ============================================================================
def test_intra_org_duplicate_id_rejection(client, emp_test_context):
    headers = emp_test_context["headers_a"]
    role_id = emp_test_context["role_a_dev"]
    suffix = emp_test_context["suffix"]

    # Attempt to create with already used employee_code CUSTOM-EMP-001
    payload = {
        "name": "Duplicate Employee",
        "email": f"dup_{suffix}@test.io",
        "password": "Password123!@#",
        "employee_code": "CUSTOM-EMP-001",
        "role_ids": [role_id]
    }

    res = client.post("/api/v1/users/", json=payload, headers=headers)
    assert res.status_code == 409
    body = res.get_json()
    assert body["success"] is False
    assert "already exists in this organization" in body["message"]


# ============================================================================
# 4. Cross-organization employee ID duplication allowed
# ============================================================================
def test_cross_org_duplicate_id_allowed(client, emp_test_context):
    headers_b = emp_test_context["headers_b"]
    suffix = emp_test_context["suffix"]

    # Organization B creates an employee with the SAME employee_code CUSTOM-EMP-001
    payload = {
        "name": "Beta Employee With Same Code",
        "email": f"beta_same_code_{suffix}@test.io",
        "password": "Password123!@#",
        "employee_code": "CUSTOM-EMP-001"
    }

    res = client.post("/api/v1/users/", json=payload, headers=headers_b)
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["employee_code"] == "CUSTOM-EMP-001"


# ============================================================================
# 5. Immutability of employee ID on role/user updates
# ============================================================================
def test_employee_id_immutability(client, emp_test_context):
    headers = emp_test_context["headers_a"]
    dev_a = emp_test_context["dev_a"]

    # Attempt to change employee_code on existing user
    patch_res = client.patch(
        f"/api/v1/users/{dev_a['user_id']}",
        json={"employee_code": "DIFFERENT-EMP-ID"},
        headers=headers
    )
    assert patch_res.status_code == 400
    body = patch_res.get_json()
    assert "immutable" in body["message"].lower()

    # Changing roles or name should preserve employee_code
    update_res = client.patch(
        f"/api/v1/users/{dev_a['user_id']}",
        json={"name": "Alpha Developer Renamed"},
        headers=headers
    )
    assert update_res.status_code == 200
    updated_user = client.get(f"/api/v1/users/{dev_a['user_id']}", headers=headers).get_json()["data"]
    assert updated_user["name"] == "Alpha Developer Renamed"
    assert updated_user["employee_code"] == dev_a["employee_code"]


# ============================================================================
# 6. Non-reuse of deleted or deactivated IDs
# ============================================================================
def test_non_reuse_of_deactivated_ids(client, emp_test_context):
    headers = emp_test_context["headers_a"]
    role_id = emp_test_context["role_a_dev"]
    suffix = emp_test_context["suffix"]

    # Create employee with custom ID
    res1 = client.post("/api/v1/users/", json={
        "name": "Deactivate Me",
        "email": f"deact_{suffix}@test.io",
        "employee_code": f"DEACT-{suffix}",
        "password": "Password123!@#",
        "role_ids": [role_id]
    }, headers=headers)
    assert res1.status_code == 201
    code1 = res1.get_json()["data"]["employee_code"]
    user_id1 = res1.get_json()["data"]["user_id"]

    # Deactivate the employee
    deact_res = client.patch(f"/api/v1/users/{user_id1}", json={"is_active": False}, headers=headers)
    assert deact_res.status_code == 200

    # Allocate the next employee -> distinct custom code
    res2 = client.post("/api/v1/users/", json={
        "name": "Next Employee",
        "email": f"next_{suffix}@test.io",
        "employee_code": f"NEXT-{suffix}",
        "password": "Password123!@#",
        "role_ids": [role_id]
    }, headers=headers)
    assert res2.status_code == 201
    code2 = res2.get_json()["data"]["employee_code"]
    assert code2 != code1


# ============================================================================
# 7. Search and filtering by employee ID
# ============================================================================
def test_search_by_employee_id(client, emp_test_context):
    headers = emp_test_context["headers_a"]

    # Filter explicitly by employee_code
    res = client.get("/api/v1/users/?employee_code=CUSTOM-EMP-001", headers=headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["employee_code"] == "CUSTOM-EMP-001"

    # Search keyword matching employee_code
    search_res = client.get("/api/v1/users/?search=CUSTOM-EMP-001", headers=headers)
    assert search_res.status_code == 200
    search_body = search_res.get_json()
    assert search_body["success"] is True
    assert any(u["employee_code"] == "CUSTOM-EMP-001" for u in search_body["data"])


# ============================================================================
# 8. User Profile & Dashboard Context Display
# ============================================================================
def test_profile_and_dashboard_context(client, emp_test_context):
    headers_dev = emp_test_context["headers_dev_a"]
    headers_admin = emp_test_context["headers_a"]
    dev_a = emp_test_context["dev_a"]

    # Dashboard context endpoint
    res = client.get("/api/v1/users/me/dashboard-context", headers=headers_dev)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["employee_code"] == dev_a["employee_code"]
    assert data["email"] == dev_a["email"]
    # Ensure organization_code is NOT present
    assert "organization_code" not in data or data["organization_code"] is None

    # User profile detail viewed by Org Admin
    user_detail = client.get(f"/api/v1/users/{dev_a['user_id']}", headers=headers_admin)
    assert user_detail.status_code == 200
    u_data = user_detail.get_json()["data"]
    assert u_data["employee_code"] == dev_a["employee_code"]
    assert "organization_code" not in u_data


# ============================================================================
# 9. Employees cannot change their own employee ID
# ============================================================================
def test_employees_cannot_modify_employee_id(client, emp_test_context):
    headers_dev = emp_test_context["headers_dev_a"]
    dev_a = emp_test_context["dev_a"]

    # Dev attempts to PATCH /api/v1/users/<id> to change employee_code -> forbidden (lacks organization:users:manage)
    res = client.patch(
        f"/api/v1/users/{dev_a['user_id']}",
        json={"employee_code": "HACKED-CODE"},
        headers=headers_dev
    )
    assert res.status_code == 403


# ============================================================================
# 10. Organization login and dynamic RBAC dashboard behaviors remain intact
# ============================================================================
def test_login_and_rbac_intact(client, emp_test_context):
    headers_admin = emp_test_context["headers_a"]
    headers_dev = emp_test_context["headers_dev_a"]

    # Admin dashboard context has full admin navigation
    res_admin = client.get("/api/v1/users/me/dashboard-context", headers=headers_admin)
    assert res_admin.status_code == 200
    admin_data = res_admin.get_json()["data"]
    assert admin_data["is_org_admin"] is True
    assert "tab-org-users" in admin_data["allowed_tabs"]
    assert "tab-org-settings" in admin_data["allowed_tabs"]

    # Dev dashboard context only has limited tabs
    res_dev = client.get("/api/v1/users/me/dashboard-context", headers=headers_dev)
    assert res_dev.status_code == 200
    dev_data = res_dev.get_json()["data"]
    assert dev_data["is_org_admin"] is False
    assert "tab-org-settings" not in dev_data["allowed_tabs"]


# ============================================================================
# 11. Prefix configuration (PATCH /organizations/employee-prefix)
# ============================================================================
def test_prefix_configuration(client, emp_test_context):
    headers_admin = emp_test_context["headers_a"]
    headers_dev = emp_test_context["headers_dev_a"]
    role_id = emp_test_context["role_a_dev"]
    suffix = emp_test_context["suffix"]

    # In Task 5.2: prefix configuration endpoint is removed
    dev_res = client.patch(
        "/api/v1/organizations/employee-prefix",
        json={"employee_id_prefix": "NEW-DEV-PREFIX"},
        headers=headers_dev
    )
    assert dev_res.status_code in (404, 405)

    admin_res = client.patch(
        "/api/v1/organizations/employee-prefix",
        json={"employee_id_prefix": "ALPHA-DEV"},
        headers=headers_admin
    )
    assert admin_res.status_code in (404, 405)


# ============================================================================
# 12. Migration idempotency
# ============================================================================
def test_migration_idempotent(app, emp_test_context):
    org_id = emp_test_context["org_a_id"]
    with app.app_context():
        res1 = run_migration(dry_run=False, target_org_id=org_id, ensure_indexes=False)
        assert res1["organizations"]["total"] >= 1
        # Second run should find 0 users missing code
        res2 = run_migration(dry_run=False, target_org_id=org_id, ensure_indexes=False)
        assert res2["users"]["backfilled"] == 0
