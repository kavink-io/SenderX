import pytest
import uuid
import bcrypt
from app import create_app
from app.modules.users.service import UserService
from app.modules.users.repository import UserRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.applications.repository import ApplicationRepository
from app.modules.organizations.role_repository import RoleRepository
from flask_jwt_extended import create_access_token


@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def setup_tenancy(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_id = f"org_test_{suffix}"
        OrganizationRepository.create({
            "organization_id": org_id,
            "name": f"Identity Test Org {suffix}",
            "slug": f"identity-test-{suffix}",
            "status": "ACTIVE"
        })

        # 1. ORG_ADMIN Role
        admin_role = RoleRepository.create({
            "role_id": f"role_admin_{suffix}",
            "organization_id": org_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "is_system_role": True,
            "permissions": list(UserService.ALLOWED_ORGANIZATION_PERMISSIONS)
        })

        # 2. Connected Applications
        crm_app = ApplicationRepository.create({
            "application_id": f"app_crm_{suffix}",
            "organization_id": org_id,
            "name": "CRM Application",
            "environment": "live",
            "status": "ACTIVE"
        })

        hrms_app = ApplicationRepository.create({
            "application_id": f"app_hrms_{suffix}",
            "organization_id": org_id,
            "name": "HRMS Application",
            "environment": "live",
            "status": "ACTIVE"
        })

        # 3. Custom Roles
        marketing_role = RoleRepository.create({
            "role_id": f"role_mkt_{suffix}",
            "organization_id": org_id,
            "name": "Marketing Specialist",
            "description": "Marketing messaging and analytics",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:read",
                "organization:messages:create",
                "organization:analytics:read"
            ],
            "is_predefined": False
        })

        hr_role = RoleRepository.create({
            "role_id": f"role_hr_{suffix}",
            "organization_id": org_id,
            "name": "HR Specialist",
            "description": "HR notifications only",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:read"
            ],
            "is_predefined": False
        })

        pwd_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Admin User
        admin_user = UserRepository.create({
            "user_id": f"usr_adm_{suffix}",
            "email": f"admin_{suffix}@example.com",
            "name": "Org Admin User",
            "password_hash": pwd_hash,
            "organization_id": org_id,
            "account_type": "ORGANIZATION_USER",
            "status": "ACTIVE",
            "is_active": True,
            "role_ids": [admin_role["role_id"]],
            "role_assignments": [
                {"role_id": admin_role["role_id"], "application_id": None}
            ]
        })

        # Marketing Employee (CRM Scoped)
        mkt_user = UserRepository.create({
            "user_id": f"usr_mkt_{suffix}",
            "email": f"mkt_{suffix}@example.com",
            "name": "Marketing Employee",
            "password_hash": pwd_hash,
            "organization_id": org_id,
            "account_type": "ORGANIZATION_USER",
            "status": "ACTIVE",
            "is_active": True,
            "role_ids": [marketing_role["role_id"]],
            "role_assignments": [
                {"role_id": marketing_role["role_id"], "application_id": crm_app["application_id"]}
            ]
        })

        # HR Employee (HRMS Scoped)
        hr_user = UserRepository.create({
            "user_id": f"usr_hr_{suffix}",
            "email": f"hr_{suffix}@example.com",
            "name": "HR Employee",
            "password_hash": pwd_hash,
            "organization_id": org_id,
            "account_type": "ORGANIZATION_USER",
            "status": "ACTIVE",
            "is_active": True,
            "role_ids": [hr_role["role_id"]],
            "role_assignments": [
                {"role_id": hr_role["role_id"], "application_id": hrms_app["application_id"]}
            ]
        })

        # Employee with Missing/No Roles
        norole_user = UserRepository.create({
            "user_id": f"usr_norole_{suffix}",
            "email": f"norole_{suffix}@example.com",
            "name": "No Role Employee",
            "password_hash": pwd_hash,
            "organization_id": org_id,
            "account_type": "ORGANIZATION_USER",
            "status": "ACTIVE",
            "is_active": True,
            "role_ids": [],
            "role_assignments": []
        })

        # Second Org for Cross-Org Isolation Testing
        other_org_id = f"org_other_{suffix}"
        OrganizationRepository.create({
            "organization_id": other_org_id,
            "name": f"Other Org {suffix}",
            "slug": f"other-{suffix}",
            "status": "ACTIVE"
        })
        other_user = UserRepository.create({
            "user_id": f"usr_other_{suffix}",
            "email": f"other_{suffix}@example.com",
            "name": "Other Org User",
            "password_hash": pwd_hash,
            "organization_id": other_org_id,
            "account_type": "ORGANIZATION_USER",
            "status": "ACTIVE",
            "is_active": True,
            "role_ids": [],
            "role_assignments": []
        })

        return {
            "suffix": suffix,
            "org_id": org_id,
            "other_org_id": other_org_id,
            "admin_user": admin_user,
            "mkt_user": mkt_user,
            "hr_user": hr_user,
            "norole_user": norole_user,
            "other_user": other_user,
            "admin_role": admin_role,
            "marketing_role": marketing_role,
            "hr_role": hr_role,
            "crm_app": crm_app,
            "hrms_app": hrms_app
        }


def make_token(app, user):
    with app.app_context():
        return create_access_token(
            identity=user["user_id"],
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": user["organization_id"],
                "role_ids": user.get("role_ids", []),
                "email": user["email"]
            }
        )


# Test 1: Organization Admin role display and claims
def test_org_admin_role_display_and_claims(app, setup_tenancy):
    t = setup_tenancy
    with app.app_context():
        ctx = UserService.get_dashboard_context(t["admin_user"]["user_id"], t["org_id"])
        assert ctx["success"] is True
        data = ctx["data"]
        assert data["is_org_admin"] is True
        assert data["account_type"] == "ORGANIZATION_USER"
        assert len(data["roles"]) == 1
        assert data["roles"][0]["name"] == "ORG_ADMIN"
        assert len(data["effective_permissions"]) == len(UserService.ALLOWED_ORGANIZATION_PERMISSIONS)
        assert "tab-org-users" in data["allowed_tabs"]
        assert "tab-org-settings" in data["allowed_tabs"]


# Test 2: Employee custom role display
def test_employee_custom_role_display(app, setup_tenancy):
    t = setup_tenancy
    with app.app_context():
        ctx = UserService.get_dashboard_context(t["mkt_user"]["user_id"], t["org_id"])
        assert ctx["success"] is True
        data = ctx["data"]
        assert data["is_org_admin"] is False
        assert data["account_type"] == "ORGANIZATION_USER"
        assert len(data["roles"]) == 1
        assert data["roles"][0]["name"] == "Marketing Specialist"
        assert "tab-org-users" not in data["allowed_tabs"]
        assert "tab-org-settings" not in data["allowed_tabs"]
        assert "tab-org-overview" in data["allowed_tabs"]


# Test 3: Multiple assigned roles
def test_multiple_assigned_roles(app, setup_tenancy):
    t = setup_tenancy
    user_id = t["mkt_user"]["user_id"]
    with app.app_context():
        # Assign both marketing and hr roles
        UserRepository.update_user(user_id, t["org_id"], {
            "role_ids": [t["marketing_role"]["role_id"], t["hr_role"]["role_id"]],
            "role_assignments": [
                {"role_id": t["marketing_role"]["role_id"], "application_id": t["crm_app"]["application_id"]},
                {"role_id": t["hr_role"]["role_id"], "application_id": t["hrms_app"]["application_id"]}
            ]
        })
        user = UserRepository.find_by_id(user_id, organization_id=t["org_id"])
        ctx = UserService.get_dashboard_context(user_id, t["org_id"])
        assert ctx["success"] is True
        data = ctx["data"]
        role_names = [r["name"] for r in data["roles"]]
        assert "Marketing Specialist" in role_names
        assert "HR Specialist" in role_names
        assert len(data["role_assignments"]) == 2


# Test 4: Application scope display
def test_application_scope_display(app, setup_tenancy):
    t = setup_tenancy
    with app.app_context():
        ctx = UserService.get_dashboard_context(t["hr_user"]["user_id"], t["org_id"])
        assert ctx["success"] is True
        data = ctx["data"]
        assert len(data["assigned_applications"]) == 1
        assert data["assigned_applications"][0]["name"] == "HRMS Application"
        assert data["assigned_applications"][0]["application_id"] == t["hrms_app"]["application_id"]
        # Ensure CRM Application is NOT present
        app_ids = [a["application_id"] for a in data["assigned_applications"]]
        assert t["crm_app"]["application_id"] not in app_ids


# Test 5: Effective permission calculation
def test_effective_permission_calculation(app, setup_tenancy):
    t = setup_tenancy
    with app.app_context():
        ctx = UserService.get_dashboard_context(t["hr_user"]["user_id"], t["org_id"])
        data = ctx["data"]
        # HR user only has organization:messages:read
        assert data["effective_permissions"] == ["organization:messages:read"]
        # Must not have create or admin permissions
        assert "organization:messages:create" not in data["effective_permissions"]
        assert "organization:users:manage" not in data["effective_permissions"]


# Test 6: Missing role handling (never converts to ORG_ADMIN)
def test_missing_role_handling(app, setup_tenancy):
    t = setup_tenancy
    with app.app_context():
        ctx = UserService.get_dashboard_context(t["norole_user"]["user_id"], t["org_id"])
        assert ctx["success"] is True
        data = ctx["data"]
        # Must strictly be False, never default to ORG_ADMIN
        assert data["is_org_admin"] is False
        assert data["roles"] == []
        assert data["role_assignments"] == []
        assert data["assigned_applications"] == []
        assert data["effective_permissions"] == []
        # Only base tab allowed
        assert data["allowed_tabs"] == ["tab-org-overview"]


# Test 7: Employee profile API response
def test_employee_profile_api_response(client, app, setup_tenancy):
    t = setup_tenancy
    admin_token = make_token(app, t["admin_user"])
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.get(f"/api/v1/users/{t['hr_user']['user_id']}", headers=headers)
    assert res.status_code == 200
    res_data = res.get_json()
    assert res_data["success"] is True
    user_info = res_data["data"]
    assert user_info["email"] == t["hr_user"]["email"]
    assert len(user_info["role_assignments"]) == 1
    assert user_info["role_assignments"][0]["role_name"] == "HR Specialist"
    assert user_info["role_assignments"][0]["application_id"] == t["hrms_app"]["application_id"]


# Test 8: Cross-organization isolation
def test_cross_organization_isolation(client, app, setup_tenancy):
    t = setup_tenancy
    other_token = make_token(app, t["other_user"])
    headers = {"Authorization": f"Bearer {other_token}"}

    # Attempt to query dashboard context of Org A while authenticated as Org B user
    # Endpoint uses get_jwt_identity() -> finds user in DB -> gets their own organization_id
    res = client.get("/api/v1/users/me/dashboard-context", headers=headers)
    assert res.status_code == 200
    res_data = res.get_json()["data"]
    # Must only return other_org_id, never Org A's ID
    assert res_data["organization_id"] == t["other_org_id"]
    assert res_data["organization_id"] != t["org_id"]

    # Attempt to read Org A user with Org B token
    res_cross = client.get(f"/api/v1/users/{t['admin_user']['user_id']}", headers=headers)
    assert res_cross.status_code in (403, 404)
