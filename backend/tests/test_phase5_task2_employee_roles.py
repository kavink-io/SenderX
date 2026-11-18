"""
SenderX Phase 5 Task 2: Employee Management & Application-Scoped Role Assignment Test Suite

Verifies:
1. Employee creation and listing with search and filters.
2. Custom role creation, modification, and safe deletion invariants.
3. Role assignment with application scopes.
4. Backend enforcement of application-scoped permissions (require_permissions).
5. Cross-organization isolation and access rejection.
6. Privilege escalation prevention (non-admin access, wildcard permissions rejection).
7. Last active administrator protection and self-deactivation prevention.
8. Role removal and permission revocation.
9. Comprehensive security audit logging for employee and role operations.
"""

import uuid
import bcrypt
import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.applications.repository import ApplicationRepository
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService
from app.modules.users.audit_repository import SecurityAuditRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def setup_org_context(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = f"org_a_{suffix}"
        org_b = f"org_b_{suffix}"

        # 1. Create Organization A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Enterprise Org A {suffix}",
            "slug": f"org-a-{suffix}",
            "status": "ACTIVE"
        })

        # 2. Create Organization B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Enterprise Org B {suffix}",
            "slug": f"org-b-{suffix}",
            "status": "ACTIVE"
        })

        # 3. Create ORG_ADMIN roles
        admin_role_a = f"role_admin_a_{suffix}"
        admin_role_b = f"role_admin_b_{suffix}"
        
        all_perms = list(UserService.ALLOWED_ORGANIZATION_PERMISSIONS)
        RoleRepository.create({
            "role_id": admin_role_a,
            "organization_id": org_a,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "is_system_role": True,
            "permissions": all_perms
        })
        RoleRepository.create({
            "role_id": admin_role_b,
            "organization_id": org_b,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "is_system_role": True,
            "permissions": all_perms
        })

        # 4. Create Connected Applications in Org A
        app_crm = f"app_crm_{suffix}"
        app_hrms = f"app_hrms_{suffix}"
        ApplicationRepository.create({
            "application_id": app_crm,
            "organization_id": org_a,
            "name": "CRM Website",
            "environment": "live",
            "status": "ACTIVE"
        })
        ApplicationRepository.create({
            "application_id": app_hrms,
            "organization_id": org_a,
            "name": "HRMS Portal",
            "environment": "live",
            "status": "ACTIVE"
        })

        # 5. Create Connected Application in Org B
        app_b_crm = f"app_b_crm_{suffix}"
        ApplicationRepository.create({
            "application_id": app_b_crm,
            "organization_id": org_b,
            "name": "Org B App",
            "environment": "live",
            "status": "ACTIVE"
        })

        # 6. Create Admin Users
        pwd_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")
        admin_user_a1 = f"user_admin_a1_{suffix}"
        admin_user_a2 = f"user_admin_a2_{suffix}"
        admin_user_b = f"user_admin_b_{suffix}"

        UserRepository.create({
            "user_id": admin_user_a1,
            "organization_id": org_a,
            "name": "Primary Admin A",
            "email": f"admin_a1_{suffix}@orga.com",
            "password_hash": pwd_hash,
            "role_ids": [admin_role_a],
            "role_assignments": [{"role_id": admin_role_a, "application_id": None}],
            "is_active": True
        })
        UserRepository.create({
            "user_id": admin_user_a2,
            "organization_id": org_a,
            "name": "Secondary Admin A",
            "email": f"admin_a2_{suffix}@orga.com",
            "password_hash": pwd_hash,
            "role_ids": [admin_role_a],
            "role_assignments": [{"role_id": admin_role_a, "application_id": None}],
            "is_active": True
        })
        UserRepository.create({
            "user_id": admin_user_b,
            "organization_id": org_b,
            "name": "Admin B",
            "email": f"admin_b_{suffix}@orgb.com",
            "password_hash": pwd_hash,
            "role_ids": [admin_role_b],
            "role_assignments": [{"role_id": admin_role_b, "application_id": None}],
            "is_active": True
        })

        # 7. Generate JWT access tokens
        token_admin_a1 = create_access_token(
            identity=admin_user_a1,
            additional_claims={"account_type": "ORGANIZATION_USER", "role": "ORG_ADMIN"}
        )
        token_admin_a2 = create_access_token(
            identity=admin_user_a2,
            additional_claims={"account_type": "ORGANIZATION_USER", "role": "ORG_ADMIN"}
        )
        token_admin_b = create_access_token(
            identity=admin_user_b,
            additional_claims={"account_type": "ORGANIZATION_USER", "role": "ORG_ADMIN"}
        )

        ctx = {
            "org_a": org_a,
            "org_b": org_b,
            "admin_role_a": admin_role_a,
            "admin_role_b": admin_role_b,
            "app_crm": app_crm,
            "app_hrms": app_hrms,
            "app_b_crm": app_b_crm,
            "admin_user_a1": admin_user_a1,
            "admin_user_a2": admin_user_a2,
            "admin_user_b": admin_user_b,
            "token_admin_a1": token_admin_a1,
            "token_admin_a2": token_admin_a2,
            "token_admin_b": token_admin_b,
        }

        yield ctx

        # Teardown
        OrganizationRepository._collection().delete_many({"organization_id": {"$in": [org_a, org_b]}})
        RoleRepository._collection().delete_many({"organization_id": {"$in": [org_a, org_b]}})
        ApplicationRepository._collection().delete_many({"organization_id": {"$in": [org_a, org_b]}})
        UserRepository._collection().delete_many({"organization_id": {"$in": [org_a, org_b]}})
        SecurityAuditRepository._collection().delete_many({"organization_id": {"$in": [org_a, org_b]}})


def test_employee_creation_and_listing(client, setup_org_context):
    ctx = setup_org_context
    headers = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # 1. Create custom role for testing
    role_res = client.post("/api/v1/users/roles", json={
        "name": "SUPPORT_SPECIALIST",
        "description": "Customer support role",
        "permissions": ["organization:messages:read", "organization:templates:read"]
    }, headers=headers)
    assert role_res.status_code == 201
    support_role_id = role_res.json["data"]["role_id"]

    # 2. Add employee with application scope
    emp_res = client.post("/api/v1/users/", json={
        "name": "Alice Support",
        "email": "alice.support@orga.com",
        "password": "StrongPassword123!",
        "role_ids": [support_role_id],
        "role_assignments": [{"role_id": support_role_id, "application_id": ctx["app_crm"]}]
    }, headers=headers)
    assert emp_res.status_code == 201
    emp_data = emp_res.json["data"]
    emp_id = emp_data["user_id"]
    assert emp_data["name"] == "Alice Support"
    assert emp_data["role_assignments"][0]["application_id"] == ctx["app_crm"]

    # 3. List employees with filters
    list_res = client.get(f"/api/v1/users/?search=Alice", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json["total_count"] == 1
    assert list_res.json["data"][0]["user_id"] == emp_id

    # Filter by application scope
    app_filter_res = client.get(f"/api/v1/users/?application_id={ctx['app_crm']}", headers=headers)
    assert app_filter_res.status_code == 200
    assert any(u["user_id"] == emp_id for u in app_filter_res.json["data"])

    # Filter by non-matching application scope
    hrms_filter_res = client.get(f"/api/v1/users/?application_id={ctx['app_hrms']}", headers=headers)
    assert hrms_filter_res.status_code == 200
    assert not any(u["user_id"] == emp_id for u in hrms_filter_res.json["data"])

    # 4. Get employee details
    detail_res = client.get(f"/api/v1/users/{emp_id}", headers=headers)
    assert detail_res.status_code == 200
    detail_data = detail_res.json["data"]
    assert detail_data["email"] == "alice.support@orga.com"
    assert len(detail_data["roles"]) == 1
    assert detail_data["roles"][0]["role_id"] == support_role_id
    assert detail_data["roles"][0]["application_id"] == ctx["app_crm"]
    assert detail_data["roles"][0]["application_name"] == "CRM Website"


def test_custom_role_lifecycle_and_safe_deletion(client, setup_org_context):
    ctx = setup_org_context
    headers = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # 1. Create custom role
    create_res = client.post("/api/v1/users/roles", json={
        "name": "ANALYST_TEMPORARY",
        "description": "Temporary analytics viewer",
        "permissions": ["organization:analytics:read"]
    }, headers=headers)
    assert create_res.status_code == 201
    temp_role_id = create_res.json["data"]["role_id"]

    # 2. Reject wildcard permissions
    wildcard_res = client.post("/api/v1/users/roles", json={
        "name": "HACKER_ROLE",
        "permissions": ["*"]
    }, headers=headers)
    assert wildcard_res.status_code == 400
    assert "wildcard" in wildcard_res.json["message"].lower()

    # 3. Create employee assigned to this role
    emp_res = client.post("/api/v1/users/", json={
        "name": "Bob Analyst",
        "email": "bob.analyst@orga.com",
        "password": "StrongPassword123!",
        "role_ids": [temp_role_id]
    }, headers=headers)
    assert emp_res.status_code == 201
    bob_id = emp_res.json["data"]["user_id"]

    # 4. Safe deletion invariant: Role CANNOT be deleted while assigned to active employee
    del_res = client.delete(f"/api/v1/users/roles/{temp_role_id}", headers=headers)
    assert del_res.status_code == 409
    assert "active employee" in del_res.json["message"].lower()

    # 5. System role CANNOT be deleted
    sys_del_res = client.delete(f"/api/v1/users/roles/{ctx['admin_role_a']}", headers=headers)
    assert sys_del_res.status_code == 403
    assert "system role" in sys_del_res.json["message"].lower()

    # 6. Reassign employee Bob to another role, then delete the role
    assign_res = client.post(f"/api/v1/users/{bob_id}/roles", json={
        "role_assignments": []
    }, headers=headers)
    assert assign_res.status_code == 200

    # Now deletion should SUCCEED
    del_success = client.delete(f"/api/v1/users/roles/{temp_role_id}", headers=headers)
    assert del_success.status_code == 200
    assert del_success.json["success"] is True

    # Confirm role no longer exists
    get_deleted = client.get(f"/api/v1/users/roles/{temp_role_id}", headers=headers)
    assert get_deleted.status_code == 404


def test_application_scoped_permissions_enforcement(client, setup_org_context, app):
    """
    CRITICAL TEST:
    Verifies that application-scoped permissions are enforced in backend require_permissions:
    - User assigned CRM-scoped permissions CAN access CRM resources.
    - User assigned CRM-scoped permissions CANNOT access HRMS resources.
    - User assigned Organization-wide permissions CAN access any application.
    """
    ctx = setup_org_context
    headers_admin = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # 1. Create a role with template/message permissions
    role_res = client.post("/api/v1/users/roles", json={
        "name": "CRM_TEMPLATE_MANAGER",
        "description": "Manages CRM communication templates",
        "permissions": ["organization:templates:read", "organization:templates:create"]
    }, headers=headers_admin)
    assert role_res.status_code == 201
    crm_role_id = role_res.json["data"]["role_id"]

    # 2. Create scoped employee: assigned ONLY to app_crm
    emp_res = client.post("/api/v1/users/", json={
        "name": "Scoped Specialist Charlie",
        "email": "charlie.crm@orga.com",
        "password": "StrongPassword123!",
        "role_assignments": [{"role_id": crm_role_id, "application_id": ctx["app_crm"]}]
    }, headers=headers_admin)
    assert emp_res.status_code == 201
    charlie_id = emp_res.json["data"]["user_id"]

    with app.app_context():
        token_charlie = create_access_token(
            identity=charlie_id,
            additional_claims={"account_type": "ORGANIZATION_USER", "role": "CRM_TEMPLATE_MANAGER"}
        )

    headers_crm = {
        "Authorization": f"Bearer {token_charlie}",
        "X-Application-ID": ctx["app_crm"]
    }
    headers_hrms = {
        "Authorization": f"Bearer {token_charlie}",
        "X-Application-ID": ctx["app_hrms"]
    }

    # 3. Access with CRM Application scope -> SUCCEEDS (HTTP 200)
    res_crm = client.get("/api/v1/templates/", headers=headers_crm)
    assert res_crm.status_code == 200

    # 4. Access targeting HRMS Application scope -> FORBIDDEN (HTTP 403)
    res_hrms = client.get("/api/v1/templates/", headers=headers_hrms)
    assert res_hrms.status_code == 403
    assert "not have permission" in res_hrms.json["message"].lower() or "insufficient" in res_hrms.json["message"].lower()

    # 5. Access with organization-wide admin -> SUCCEEDS on both CRM and HRMS
    admin_crm_res = client.get("/api/v1/templates/", headers={
        "Authorization": f"Bearer {ctx['token_admin_a1']}",
        "X-Application-ID": ctx["app_crm"]
    })
    assert admin_crm_res.status_code == 200

    admin_hrms_res = client.get("/api/v1/templates/", headers={
        "Authorization": f"Bearer {ctx['token_admin_a1']}",
        "X-Application-ID": ctx["app_hrms"]
    })
    assert admin_hrms_res.status_code == 200


def test_cross_organization_isolation(client, setup_org_context):
    ctx = setup_org_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}
    headers_b = {"Authorization": f"Bearer {ctx['token_admin_b']}"}

    # 1. Admin A cannot view user in Org B
    res = client.get(f"/api/v1/users/{ctx['admin_user_b']}", headers=headers_a)
    assert res.status_code == 404

    # 2. Admin A cannot deactivate user in Org B
    res_deact = client.delete(f"/api/v1/users/{ctx['admin_user_b']}", headers=headers_a)
    assert res_deact.status_code == 404

    # 3. Admin A cannot assign Org B role to Org A user
    assign_res = client.post(f"/api/v1/users/{ctx['admin_user_a2']}/roles", json={
        "role_assignments": [{"role_id": ctx["admin_role_b"], "application_id": None}]
    }, headers=headers_a)
    assert assign_res.status_code == 400
    assert "does not belong" in assign_res.json["message"].lower() or "not found" in assign_res.json["message"].lower()

    # 4. Admin A cannot assign Org A user to Org B application
    assign_app_res = client.post(f"/api/v1/users/{ctx['admin_user_a2']}/roles", json={
        "role_assignments": [{"role_id": ctx["admin_role_a"], "application_id": ctx["app_b_crm"]}]
    }, headers=headers_a)
    assert assign_app_res.status_code == 400
    assert "does not belong" in assign_app_res.json["message"].lower() or "not found" in assign_app_res.json["message"].lower()


def test_last_admin_protection_and_self_deactivation(client, setup_org_context):
    ctx = setup_org_context
    headers_a1 = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}
    headers_a2 = {"Authorization": f"Bearer {ctx['token_admin_a2']}"}

    # 1. Admin A1 cannot deactivate their own account (Self-deactivation rejection)
    self_res = client.delete(f"/api/v1/users/{ctx['admin_user_a1']}", headers=headers_a1)
    assert self_res.status_code == 409
    assert "cannot deactivate their own account" in self_res.json["message"].lower()

    # 2. Admin A1 can deactivate Admin A2 (since A1 is still active)
    deact_a2_res = client.delete(f"/api/v1/users/{ctx['admin_user_a2']}", headers=headers_a1)
    assert deact_a2_res.status_code == 200

    # 3. Now A1 is the ONLY active admin in Org A.
    # Attempting to deactivate A1 via any request by another actor MUST fail with 409 (last active admin protection)
    service_res = UserService.deactivate_user(ctx["admin_user_a1"], ctx["org_a"], actor_id="different_actor")
    assert service_res["status_code"] == 409
    assert "last active administrator" in service_res["message"].lower()

    # 4. Attempting to strip ORG_ADMIN role from the last active admin must fail
    strip_admin_res = client.post(f"/api/v1/users/{ctx['admin_user_a1']}/roles", json={
        "role_assignments": []
    }, headers=headers_a1)
    assert strip_admin_res.status_code == 409
    assert "last active administrator" in strip_admin_res.json["message"].lower()

    # 5. Reactivate Admin A2
    react_res = client.post(f"/api/v1/users/{ctx['admin_user_a2']}/activate", headers=headers_a1)
    assert react_res.status_code == 200


def test_security_audit_logging(client, setup_org_context):
    ctx = setup_org_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # 1. Fetch audit logs for Org A
    audit_res = client.get("/api/v1/users/audit-logs", headers=headers_a)
    assert audit_res.status_code == 200
    logs = audit_res.json["data"]
    assert len(logs) > 0

    # Verify event types logged
    event_types = {l["event_type"] for l in logs}
    assert "USER_CREATED" in event_types or "ROLE_CREATED" in event_types or "ROLE_ASSIGNED" in event_types

    # 2. Verify audit logs are scoped to organization
    for log in logs:
        assert log["organization_id"] == ctx["org_a"]
