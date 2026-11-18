import uuid
import pytest
from app import create_app
from app.modules.auth.repository import AuthRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.applications.repository import ApplicationRepository
from app.modules.auth.service import AuthService
from flask_jwt_extended import create_access_token


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def setup_tenants(app):
    """
    Creates two isolated organizations with:
    - Organization Admin accounts
    - Two connected applications in Org A
    - Two custom roles in Org A (Role A with messages:read, Role B with templates:read)
    - Test platform admin account
    """
    with app.app_context():
        # 1. Platform Super Admin
        admin_email = f"platform-admin-{uuid.uuid4().hex[:6]}@senderx.io"
        admin_doc = {
            "admin_id": str(uuid.uuid4()),
            "email": admin_email,
            "name": "Global Platform Admin",
            "password_hash": "$2b$12$e8Y5tG1e1b.0xH2g8i.0u.aFhWz1234567890123456789012",
            "role": "SUPER_ADMIN",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00Z"
        }
        AuthRepository.create_admin(admin_doc)
        AuthRepository.update_last_login(admin_doc["admin_id"])

        admin_token = create_access_token(
            identity=admin_doc["admin_id"],
            additional_claims={
                "account_type": "PLATFORM_ADMIN",
                "role": "SUPER_ADMIN",
                "email": admin_email
            }
        )

        # 2. Organization A
        org_a_id = str(uuid.uuid4())
        OrganizationRepository.create({
            "organization_id": org_a_id,
            "name": "Acme Corp Org A",
            "slug": f"acme-a-{uuid.uuid4().hex[:6]}",
            "status": "ACTIVE"
        })

        org_admin_role_a = RoleRepository.create({
            "role_id": str(uuid.uuid4()),
            "organization_id": org_a_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:users:manage",
                "organization:roles:manage",
                "organization:messages:read",
                "organization:messages:create",
                "organization:messages:manage",
                "organization:templates:read",
                "organization:templates:manage",
                "organization:configuration:manage"
            ],
            "is_system_role": True
        })

        org_admin_a = UserRepository.create({
            "user_id": str(uuid.uuid4()),
            "organization_id": org_a_id,
            "name": "Acme Admin",
            "email": f"admin-a-{uuid.uuid4().hex[:6]}@acme.com",
            "employee_code": "ACME-DIR-001",
            "password_hash": "$2b$12$e8Y5tG1e1b.0xH2g8i.0u.aFhWz1234567890123456789012",
            "role_ids": [org_admin_role_a["role_id"]],
            "role_assignments": [{"role_id": org_admin_role_a["role_id"], "application_id": None}],
            "is_active": True,
            "created_at": "2026-01-10T10:00:00Z"
        })
        UserRepository.update_user(org_admin_a["user_id"], org_a_id, {"last_login_at": "2026-02-01T12:00:00Z"})

        token_admin_a = create_access_token(
            identity=org_admin_a["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_a_id,
                "role_ids": [org_admin_role_a["role_id"]],
                "email": org_admin_a["email"]
            }
        )

        # 3. Organization B
        org_b_id = str(uuid.uuid4())
        OrganizationRepository.create({
            "organization_id": org_b_id,
            "name": "Beta Labs Org B",
            "slug": f"beta-b-{uuid.uuid4().hex[:6]}",
            "status": "ACTIVE"
        })

        org_admin_role_b = RoleRepository.create({
            "role_id": str(uuid.uuid4()),
            "organization_id": org_b_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:users:manage",
                "organization:roles:manage",
                "organization:messages:read"
            ],
            "is_system_role": True
        })

        org_admin_b = UserRepository.create({
            "user_id": str(uuid.uuid4()),
            "organization_id": org_b_id,
            "name": "Beta Admin",
            "email": f"admin-b-{uuid.uuid4().hex[:6]}@beta.com",
            "employee_code": "BETA-HEAD-001",
            "password_hash": "$2b$12$e8Y5tG1e1b.0xH2g8i.0u.aFhWz1234567890123456789012",
            "role_ids": [org_admin_role_b["role_id"]],
            "role_assignments": [{"role_id": org_admin_role_b["role_id"], "application_id": None}],
            "is_active": True,
            "created_at": "2026-01-15T10:00:00Z"
        })

        token_admin_b = create_access_token(
            identity=org_admin_b["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_b_id,
                "role_ids": [org_admin_role_b["role_id"]],
                "email": org_admin_b["email"]
            }
        )

        # 4. Connected Apps in Org A
        app1 = ApplicationRepository.create({
            "application_id": str(uuid.uuid4()),
            "organization_id": org_a_id,
            "name": "Billing Service",
            "environment": "live",
            "status": "ACTIVE"
        })
        app2 = ApplicationRepository.create({
            "application_id": str(uuid.uuid4()),
            "organization_id": org_a_id,
            "name": "Marketing Portal",
            "environment": "live",
            "status": "ACTIVE"
        })

        # 5. Roles in Org A
        # Role A: messages:read only
        role_a = RoleRepository.create({
            "role_id": str(uuid.uuid4()),
            "organization_id": org_a_id,
            "name": "MessageAuditor",
            "scope": "ORGANIZATION",
            "permissions": ["organization:messages:read"],
            "application_id": None,
            "is_system_role": False
        })

        # Role B: templates:read only (does NOT have messages:read)
        role_b = RoleRepository.create({
            "role_id": str(uuid.uuid4()),
            "organization_id": org_a_id,
            "name": "TemplateDesigner",
            "scope": "ORGANIZATION",
            "permissions": ["organization:templates:read"],
            "application_id": None,
            "is_system_role": False
        })

        return {
            "platform_admin": admin_doc,
            "admin_token": admin_token,
            "org_a": org_a_id,
            "admin_a": org_admin_a,
            "token_admin_a": token_admin_a,
            "org_b": org_b_id,
            "admin_b": org_admin_b,
            "token_admin_b": token_admin_b,
            "app1": app1,
            "app2": app2,
            "role_a": role_a,
            "role_b": role_b
        }


# ============================================================================
# 1. EMPLOYEE ID: MANUAL ENTRY ONLY TESTS
# ============================================================================

def test_manual_employee_id_creation_success(client, setup_tenants):
    """Admin manually enters custom employee ID (e.g. TECH-999) -> created successfully."""
    ctx = setup_tenants
    headers = {"Authorization": f"Bearer {ctx['token_admin_a']}"}

    res = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "name": "Alice Developer",
            "email": f"alice-{uuid.uuid4().hex[:6]}@acme.com",
            "employee_code": "TECH-999",
            "password": "Password1234!@",
            "role_ids": [ctx["role_a"]["role_id"]]
        }
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["employee_code"] == "TECH-999"
    assert body["data"]["name"] == "Alice Developer"


def test_missing_employee_id_rejected(client, setup_tenants):
    """Attempting to create an employee without an employee ID must return 400 Bad Request."""
    ctx = setup_tenants
    headers = {"Authorization": f"Bearer {ctx['token_admin_a']}"}

    # Case A: employee_code is None / omitted
    res = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "name": "Bob Tester",
            "email": f"bob-{uuid.uuid4().hex[:6]}@acme.com",
            "password": "Password1234!@",
            "role_ids": [ctx["role_a"]["role_id"]]
        }
    )
    assert res.status_code == 400
    assert "Employee ID is required" in res.get_json()["message"]

    # Case B: employee_code is empty string or spaces
    res2 = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "name": "Bob Tester",
            "email": f"bob2-{uuid.uuid4().hex[:6]}@acme.com",
            "employee_code": "   ",
            "password": "Password1234!@",
            "role_ids": [ctx["role_a"]["role_id"]]
        }
    )
    assert res2.status_code == 400
    assert "Employee ID is required" in res2.get_json()["message"]


def test_duplicate_employee_id_rejected_in_same_org(client, setup_tenants):
    """Duplicate employee ID within the same organization must return 409 Conflict."""
    ctx = setup_tenants
    headers = {"Authorization": f"Bearer {ctx['token_admin_a']}"}

    # First user
    res1 = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "name": "Charlie First",
            "email": f"charlie1-{uuid.uuid4().hex[:6]}@acme.com",
            "employee_code": "CORP-101",
            "password": "Password1234!@",
            "role_ids": [ctx["role_a"]["role_id"]]
        }
    )
    assert res1.status_code == 201

    # Second user in same org with same ID -> 409
    res2 = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "name": "Charlie Second",
            "email": f"charlie2-{uuid.uuid4().hex[:6]}@acme.com",
            "employee_code": "CORP-101",
            "password": "Password1234!@",
            "role_ids": [ctx["role_a"]["role_id"]]
        }
    )
    assert res2.status_code == 409
    assert "already exists in this organization" in res2.get_json()["message"]


def test_same_employee_id_accepted_in_different_orgs(client, setup_tenants):
    """The same employee ID may exist in different organizations without conflict."""
    ctx = setup_tenants
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a']}"}
    headers_b = {"Authorization": f"Bearer {ctx['token_admin_b']}"}

    # Create employee with ID SHARED-DEV-777 in Org A
    res_a = client.post(
        "/api/v1/users/",
        headers=headers_a,
        json={
            "name": "Dev in Org A",
            "email": f"dev-a-{uuid.uuid4().hex[:6]}@acme.com",
            "employee_code": "SHARED-DEV-777",
            "password": "Password1234!@",
            "role_ids": [ctx["role_a"]["role_id"]]
        }
    )
    assert res_a.status_code == 201
    assert res_a.get_json()["data"]["employee_code"] == "SHARED-DEV-777"

    # Create employee with same ID SHARED-DEV-777 in Org B -> must succeed (201)
    res_b = client.post(
        "/api/v1/users/",
        headers=headers_b,
        json={
            "name": "Dev in Org B",
            "email": f"dev-b-{uuid.uuid4().hex[:6]}@beta.com",
            "employee_code": "SHARED-DEV-777",
            "password": "Password1234!@"
        }
    )
    assert res_b.status_code == 201
    assert res_b.get_json()["data"]["employee_code"] == "SHARED-DEV-777"


def test_employee_id_preserved_on_role_change_and_update(client, setup_tenants):
    """Existing employee ID is strictly preserved when employee roles or details are updated."""
    ctx = setup_tenants
    headers = {"Authorization": f"Bearer {ctx['token_admin_a']}"}

    # Create employee
    res = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "name": "David Engineer",
            "email": f"david-{uuid.uuid4().hex[:6]}@acme.com",
            "employee_code": "ENG-500",
            "password": "Password1234!@",
            "role_ids": [ctx["role_a"]["role_id"]]
        }
    )
    assert res.status_code == 201
    user_id = res.get_json()["data"]["user_id"]

    # Update role to Role B
    patch_res = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={
            "name": "David Senior Engineer",
            "role_ids": [ctx["role_b"]["role_id"]]
        }
    )
    assert patch_res.status_code == 200
    updated_data = patch_res.get_json()["data"]
    assert updated_data["name"] == "David Senior Engineer"
    # Employee ID must be preserved
    assert updated_data["employee_code"] == "ENG-500"


def test_employee_id_immutability(client, setup_tenants):
    """Attempting to change an existing employee ID returns 400 Immutable."""
    ctx = setup_tenants
    headers = {"Authorization": f"Bearer {ctx['token_admin_a']}"}

    res = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "name": "Eva Staff",
            "email": f"eva-{uuid.uuid4().hex[:6]}@acme.com",
            "employee_code": "STAFF-01",
            "password": "Password1234!@",
            "role_ids": [ctx["role_a"]["role_id"]]
        }
    )
    user_id = res.get_json()["data"]["user_id"]

    # Attempt to change employee ID
    alter_res = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"employee_code": "DIFFERENT-ID-02"}
    )
    assert alter_res.status_code == 400
    assert "Employee ID is immutable" in alter_res.get_json()["message"]


# ============================================================================
# 2. ROLE CHANGE & IMMEDIATE PERMISSION SYNCHRONIZATION TESTS
# ============================================================================

def test_role_change_permission_replacement_immediate(client, setup_tenants):
    """
    Test permission synchronization:
    1. Employee created with Role A (has organization:messages:read).
    2. Employee accesses /messages/ -> 200 OK.
    3. Org Admin reassigns employee to Role B (has organization:templates:read, NOT messages:read).
    4. On the VERY NEXT request with the existing employee token:
       - /messages/ returns 403 Forbidden.
       - /templates/ returns 200 OK.
    """
    ctx = setup_tenants
    admin_headers = {"Authorization": f"Bearer {ctx['token_admin_a']}"}

    # 1. Create employee with Role A
    emp_email = f"emp-sync-{uuid.uuid4().hex[:6]}@acme.com"
    create_res = client.post(
        "/api/v1/users/",
        headers=admin_headers,
        json={
            "name": "Sync Tester",
            "email": emp_email,
            "employee_code": "SYNC-001",
            "password": "Password1234!@",
            "role_ids": [ctx["role_a"]["role_id"]]
        }
    )
    assert create_res.status_code == 201
    emp_id = create_res.get_json()["data"]["user_id"]

    # Log in as employee and get access token
    with client.application.app_context():
        emp_token = create_access_token(
            identity=emp_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": ctx["org_a"],
                "role_ids": [ctx["role_a"]["role_id"]],
                "email": emp_email
            }
        )
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # 2. Initial state: Role A grants messages:read, denies templates:read
    msg_res1 = client.get("/api/v1/messages/", headers=emp_headers)
    assert msg_res1.status_code == 200

    tpl_res1 = client.get("/api/v1/templates/", headers=emp_headers)
    assert tpl_res1.status_code == 403

    # 3. Org Admin changes employee role to Role B
    assign_res = client.post(
        f"/api/v1/users/{emp_id}/roles",
        headers=admin_headers,
        json={"role_ids": [ctx["role_b"]["role_id"]]}
    )
    assert assign_res.status_code == 200

    # 4. Immediate synchronization test using the EXACT SAME TOKEN:
    # messages:read must be DENIED immediately (403)
    msg_res2 = client.get("/api/v1/messages/", headers=emp_headers)
    assert msg_res2.status_code == 403
    assert "missing_permissions" in msg_res2.get_json()

    # templates:read must be GRANTED immediately (200)
    tpl_res2 = client.get("/api/v1/templates/", headers=emp_headers)
    assert tpl_res2.status_code == 200

    # Verify dashboard-context endpoint also reflects the new role and permissions immediately
    ctx_res = client.get("/api/v1/users/me/dashboard-context", headers=emp_headers)
    assert ctx_res.status_code == 200
    ctx_data = ctx_res.get_json()["data"]
    assert "organization:templates:read" in ctx_data["effective_permissions"]
    assert "organization:messages:read" not in ctx_data["effective_permissions"]


def test_application_scope_synchronization(client, setup_tenants):
    """
    Test application-scoped role changes:
    1. Employee assigned Role A scoped to App 1.
    2. Request targeting App 1 succeeds; request targeting App 2 is denied.
    3. Reassign employee scope to App 2.
    4. Target App 1 is now denied; target App 2 succeeds immediately.
    """
    ctx = setup_tenants
    admin_headers = {"Authorization": f"Bearer {ctx['token_admin_a']}"}

    # Create employee scoped to App 1
    emp_email = f"app-scoped-{uuid.uuid4().hex[:6]}@acme.com"
    create_res = client.post(
        "/api/v1/users/",
        headers=admin_headers,
        json={
            "name": "App Scope Tester",
            "email": emp_email,
            "employee_code": "SCOPE-001",
            "password": "Password1234!@",
            "role_assignments": [
                {"role_id": ctx["role_a"]["role_id"], "application_id": ctx["app1"]["application_id"]}
            ]
        }
    )
    assert create_res.status_code == 201
    emp_id = create_res.get_json()["data"]["user_id"]

    with client.application.app_context():
        emp_token = create_access_token(
            identity=emp_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": ctx["org_a"],
                "role_ids": [ctx["role_a"]["role_id"]],
                "email": emp_email
            }
        )
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # Targeting App 1 -> 200 OK
    res_app1 = client.get(f"/api/v1/messages/?application_id={ctx['app1']['application_id']}", headers=emp_headers)
    assert res_app1.status_code == 200

    # Targeting App 2 -> 403 Forbidden (employee only scoped to App 1)
    res_app2 = client.get(f"/api/v1/messages/?application_id={ctx['app2']['application_id']}", headers=emp_headers)
    assert res_app2.status_code == 403

    # Admin changes scope from App 1 to App 2
    update_res = client.post(
        f"/api/v1/users/{emp_id}/roles",
        headers=admin_headers,
        json={
            "role_assignments": [
                {"role_id": ctx["role_a"]["role_id"], "application_id": ctx["app2"]["application_id"]}
            ]
        }
    )
    assert update_res.status_code == 200

    # Now targeting App 1 must be DENIED (403)
    res_app1_after = client.get(f"/api/v1/messages/?application_id={ctx['app1']['application_id']}", headers=emp_headers)
    assert res_app1_after.status_code == 403

    # Now targeting App 2 must SUCCEED (200)
    res_app2_after = client.get(f"/api/v1/messages/?application_id={ctx['app2']['application_id']}", headers=emp_headers)
    assert res_app2_after.status_code == 200


def test_cross_organization_role_assignment_rejected(client, setup_tenants):
    """Admin in Org A cannot assign a role belonging to Org B to an employee."""
    ctx = setup_tenants
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a']}"}

    # Create role in Org B
    with client.application.app_context():
        role_b_custom = RoleRepository.create({
            "role_id": str(uuid.uuid4()),
            "organization_id": ctx["org_b"],
            "name": "OrgBSecretRole",
            "scope": "ORGANIZATION",
            "permissions": ["organization:messages:read"],
            "is_system_role": False
        })

    # Attempt to assign Org B role to Org A user
    res = client.post(
        "/api/v1/users/",
        headers=headers_a,
        json={
            "name": "Intruder",
            "email": f"intruder-{uuid.uuid4().hex[:6]}@acme.com",
            "employee_code": "INTR-001",
            "password": "Password1234!@",
            "role_ids": [role_b_custom["role_id"]]
        }
    )
    assert res.status_code == 400
    assert "does not belong to your organization" in res.get_json()["message"]


def test_last_active_admin_protection_preserved(client, setup_tenants):
    """Cannot strip ORG_ADMIN privileges from the only active administrator in the organization."""
    ctx = setup_tenants
    headers = {"Authorization": f"Bearer {ctx['token_admin_a']}"}
    admin_id = ctx["admin_a"]["user_id"]

    # Attempt to reassign Org Admin to read-only Role A
    res = client.post(
        f"/api/v1/users/{admin_id}/roles",
        headers=headers,
        json={"role_ids": [ctx["role_a"]["role_id"]]}
    )
    assert res.status_code == 409
    assert "last active administrator" in res.get_json()["message"]


# ============================================================================
# 3. SUPER ADMIN PROFILE TESTS
# ============================================================================

def test_super_admin_profile_retrieval(client, setup_tenants):
    """Platform Super Admin calls /api/v1/auth/me -> returns complete profile data."""
    ctx = setup_tenants
    headers = {"Authorization": f"Bearer {ctx['admin_token']}"}

    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True

    data = body["data"]
    assert data["account_type"] == "PLATFORM_ADMIN"
    assert data["role"] == "SUPER_ADMIN"
    assert data["email"] == ctx["platform_admin"]["email"]
    assert data["name"] == "Global Platform Admin"
    assert data["status"] == "ACTIVE"
    assert data["created_at"] is not None
    assert data["last_login"] is not None
    assert data["last_login_at"] is not None


def test_super_admin_profile_contains_no_sensitive_secrets(client, setup_tenants):
    """Super Admin profile response must NEVER leak password hashes or secrets."""
    ctx = setup_tenants
    headers = {"Authorization": f"Bearer {ctx['admin_token']}"}

    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.get_json()["data"]

    assert "password_hash" not in data
    assert "password" not in data
    assert "secret" not in data
    assert "private_key" not in data
    assert "token" not in data


def test_org_admin_and_employee_profile_preserved(client, setup_tenants):
    """Existing ORG_ADMIN and EMPLOYEE accounts continue to retrieve their full profile and context cleanly."""
    ctx = setup_tenants

    # 1. ORG_ADMIN
    headers_admin = {"Authorization": f"Bearer {ctx['token_admin_a']}"}
    res_admin = client.get("/api/v1/auth/me", headers=headers_admin)
    assert res_admin.status_code == 200
    admin_data = res_admin.get_json()["data"]
    assert admin_data["account_type"] == "ORGANIZATION_USER"
    assert admin_data["is_org_admin"] is True
    assert admin_data["employee_code"] == "ACME-DIR-001"
    assert admin_data["name"] == "Acme Admin"
    assert admin_data["status"] == "ACTIVE"
    assert admin_data["organization_id"] == ctx["org_a"]

    # 2. EMPLOYEE
    headers_admin_b = {"Authorization": f"Bearer {ctx['token_admin_b']}"}
    res_emp_create = client.post(
        "/api/v1/users/",
        headers=headers_admin_b,
        json={
            "name": "Jane Employee",
            "email": f"jane-{uuid.uuid4().hex[:6]}@beta.com",
            "employee_code": "BETA-STAFF-12",
            "password": "Password1234!@"
        }
    )
    assert res_emp_create.status_code == 201
    jane_id = res_emp_create.get_json()["data"]["user_id"]

    with client.application.app_context():
        jane_token = create_access_token(
            identity=jane_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": ctx["org_b"],
                "email": f"jane@{uuid.uuid4().hex[:6]}.com"
            }
        )
    res_jane = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {jane_token}"})
    assert res_jane.status_code == 200
    jane_data = res_jane.get_json()["data"]
    assert jane_data["account_type"] == "ORGANIZATION_USER"
    assert jane_data["is_org_admin"] is False
    assert jane_data["employee_code"] == "BETA-STAFF-12"
    assert jane_data["status"] == "ACTIVE"
    assert "password_hash" not in jane_data
