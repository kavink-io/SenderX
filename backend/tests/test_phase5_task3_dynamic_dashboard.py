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
            "name": f"Dynamic Test Org {suffix}",
            "slug": f"dynamic-test-{suffix}",
            "status": "ACTIVE"
        })

        # Predefined ORG_ADMIN role
        admin_role = RoleRepository.create({
            "role_id": f"role_admin_{suffix}",
            "organization_id": org_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "is_system_role": True,
            "permissions": list(UserService.ALLOWED_ORGANIZATION_PERMISSIONS)
        })

        # Create two separate applications
        crm_app = ApplicationRepository.create({
            "application_id": f"app_crm_{suffix}",
            "organization_id": org_id,
            "name": "CRM Portal",
            "environment": "live",
            "status": "ACTIVE"
        })

        hrms_app = ApplicationRepository.create({
            "application_id": f"app_hrms_{suffix}",
            "organization_id": org_id,
            "name": "HRMS Portal",
            "environment": "live",
            "status": "ACTIVE"
        })

        # Create CRM Role
        crm_role = RoleRepository.create({
            "role_id": f"role_crm_{suffix}",
            "organization_id": org_id,
            "name": f"CRM Specialist {suffix}",
            "description": "CRM messaging and analytics access",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:read",
                "organization:messages:create",
                "organization:analytics:read"
            ],
            "is_predefined": False
        })

        # Create HRMS Role
        hrms_role = RoleRepository.create({
            "role_id": f"role_hrms_{suffix}",
            "organization_id": org_id,
            "name": f"HRMS Specialist {suffix}",
            "description": "HRMS notifications only",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:read"
            ],
            "is_predefined": False
        })

        pwd_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # 1. Org Admin User
        admin_email = f"admin_{suffix}@senderx.io"
        admin_user = UserRepository.create({
            "user_id": f"usr_admin_{suffix}",
            "email": admin_email,
            "name": "Admin User",
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

        # 2. Marketing Employee (CRM Scoped)
        mkt_email = f"mkt_{suffix}@senderx.io"
        mkt_user = UserRepository.create({
            "user_id": f"usr_mkt_{suffix}",
            "email": mkt_email,
            "name": "Marketing User",
            "password_hash": pwd_hash,
            "organization_id": org_id,
            "account_type": "ORGANIZATION_USER",
            "status": "ACTIVE",
            "is_active": True,
            "role_ids": [crm_role["role_id"]],
            "role_assignments": [
                {"role_id": crm_role["role_id"], "application_id": crm_app["application_id"]}
            ]
        })

        # 3. HR Employee (HRMS Scoped)
        hr_email = f"hr_{suffix}@senderx.io"
        hr_user = UserRepository.create({
            "user_id": f"usr_hr_{suffix}",
            "email": hr_email,
            "name": "HR User",
            "password_hash": pwd_hash,
            "organization_id": org_id,
            "account_type": "ORGANIZATION_USER",
            "status": "ACTIVE",
            "is_active": True,
            "role_ids": [hrms_role["role_id"]],
            "role_assignments": [
                {"role_id": hrms_role["role_id"], "application_id": hrms_app["application_id"]}
            ]
        })

        return {
            "org_id": org_id,
            "crm_app": crm_app,
            "hrms_app": hrms_app,
            "crm_role": crm_role,
            "hrms_role": hrms_role,
            "admin_role": admin_role,
            "admin_user": admin_user,
            "mkt_user": mkt_user,
            "hr_user": hr_user
        }


def make_token(app, user):
    with app.app_context():
        # Get primary role name if available
        role_name = "ORG_ADMIN" if user.get("role_assignments") and any(r.get("role_id") == "ORG_ADMIN" or "admin" in str(r.get("role_id")).lower() for r in user.get("role_assignments", [])) else "EMPLOYEE"
        return create_access_token(
            identity=user["user_id"],
            additional_claims={
                "account_type": user["account_type"],
                "organization_id": user["organization_id"],
                "role": role_name,
                "email": user["email"]
            }
        )


# Scenario 1: ORG_ADMIN accesses organization administration
def test_scenario_1_org_admin_access(client, app, setup_tenancy):
    t = setup_tenancy
    token = make_token(app, t["admin_user"])
    headers = {"Authorization": f"Bearer {token}"}

    # List employees
    res_users = client.get("/api/v1/users/", headers=headers)
    assert res_users.status_code == 200

    # List roles
    res_roles = client.get("/api/v1/users/roles", headers=headers)
    assert res_roles.status_code == 200

    # List applications
    res_apps = client.get("/api/v1/applications/", headers=headers)
    assert res_apps.status_code == 200

    # List credentials
    res_creds = client.get("/api/v1/api-credentials/", headers=headers)
    assert res_creds.status_code == 200


# Scenario 2: Marketing employee cannot access HRMS-only modules
def test_scenario_2_marketing_cannot_access_hrms(client, app, setup_tenancy):
    t = setup_tenancy
    token = make_token(app, t["mkt_user"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Application-ID": t["hrms_app"]["application_id"]
    }

    # Attempt to send message to HRMS application
    res = client.post("/api/v1/messages/", headers=headers, json={
        "recipient": "+1234567890",
        "content": "Unauthorized dispatch to HRMS",
        "channel": "sms"
    })
    # Must be 403 Forbidden because marketing user's role is scoped to CRM only
    assert res.status_code == 403


# Scenario 3: HR employee cannot access CRM-only modules
def test_scenario_3_hr_cannot_access_crm(client, app, setup_tenancy):
    t = setup_tenancy
    token = make_token(app, t["hr_user"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Application-ID": t["crm_app"]["application_id"]
    }

    # Attempt to read CRM analytics (hr employee has no CRM permissions)
    res = client.get("/api/v1/analytics/organization", headers=headers)
    assert res.status_code == 403


# Scenario 4: Employee cannot view unassigned custom roles
def test_scenario_4_employee_cannot_manage_or_view_roles(client, app, setup_tenancy):
    t = setup_tenancy
    token = make_token(app, t["mkt_user"])
    headers = {"Authorization": f"Bearer {token}"}

    # Employees lacking organization:users:manage cannot list or create roles
    res = client.get("/api/v1/users/roles", headers=headers)
    assert res.status_code == 403

    res_post = client.post("/api/v1/users/roles", headers=headers, json={
        "name": "Hacker Role",
        "permissions": ["organization:users:manage"]
    })
    assert res_post.status_code == 403


# Scenario 5: Employee cannot access restricted APIs directly
def test_scenario_5_employee_cannot_access_restricted_apis(client, app, setup_tenancy):
    t = setup_tenancy
    token = make_token(app, t["mkt_user"])
    headers = {"Authorization": f"Bearer {token}"}

    # Direct API access to API credentials
    res_creds = client.get("/api/v1/api-credentials/", headers=headers)
    assert res_creds.status_code == 403

    # Direct API access to Users management
    res_users = client.get("/api/v1/users/", headers=headers)
    assert res_users.status_code == 403


# Scenario 6: Revoked permissions immediately stop granting access without DB reset
def test_scenario_6_revoked_permissions_immediate(client, app, setup_tenancy):
    t = setup_tenancy
    token = make_token(app, t["mkt_user"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Application-ID": t["crm_app"]["application_id"]
    }

    # Update role to remove messages:create permission
    with app.app_context():
        RoleRepository._collection().update_one(
            {"role_id": t["crm_role"]["role_id"]},
            {"$set": {"permissions": ["organization:messages:read"]}}
        )

    # Immediate request with unchanged JWT must fail with 403
    res = client.post("/api/v1/messages/", headers=headers, json={
        "recipient": "+1234567890",
        "content": "Post-revocation attempt",
        "channel": "sms"
    })
    assert res.status_code == 403


# Scenario 7: Deactivated employees cannot access the dashboard or APIs
def test_scenario_7_deactivated_employee_blocked(client, app, setup_tenancy):
    t = setup_tenancy
    token = make_token(app, t["mkt_user"])
    headers = {"Authorization": f"Bearer {token}"}

    # Deactivate the user
    with app.app_context():
        UserRepository.update_user(t["mkt_user"]["user_id"], t["org_id"], {
            "is_active": False,
            "status": "INACTIVE"
        })

    # API access must now be rejected
    res = client.get("/api/v1/users/me/dashboard-context", headers=headers)
    assert res.status_code == 401


# Scenario 8: Multiple assigned roles combine permissions only within authorized scopes
def test_scenario_8_multiple_roles_scoped_isolation(client, app, setup_tenancy):
    t = setup_tenancy
    user_id = t["mkt_user"]["user_id"]

    # Assign marketing user both CRM role (on CRM app) and HRMS role (on HRMS app)
    with app.app_context():
        # First ensure crm_role has messages:create
        RoleRepository._collection().update_one(
            {"role_id": t["crm_role"]["role_id"]},
            {"$set": {"permissions": ["organization:messages:read", "organization:messages:create"]}}
        )
        UserRepository.update_user(user_id, t["org_id"], {
            "is_active": True,
            "status": "ACTIVE",
            "role_assignments": [
                {"role_id": t["crm_role"]["role_id"], "application_id": t["crm_app"]["application_id"]},
                {"role_id": t["hrms_role"]["role_id"], "application_id": t["hrms_app"]["application_id"]}
            ]
        })

    token = make_token(app, t["mkt_user"])

    # On CRM app: can send messages (crm_role has messages:create)
    res_crm = client.post("/api/v1/messages/", headers={
        "Authorization": f"Bearer {token}",
        "X-Application-ID": t["crm_app"]["application_id"]
    }, json={"recipient": "+111111", "content": "CRM message", "channel": "sms"})
    assert res_crm.status_code in (200, 201, 400) # Reaches handler, not 403

    # On HRMS app: CANNOT send messages (hrms_role only has messages:read)
    res_hrms = client.post("/api/v1/messages/", headers={
        "Authorization": f"Bearer {token}",
        "X-Application-ID": t["hrms_app"]["application_id"]
    }, json={"recipient": "+111111", "content": "HRMS message", "channel": "sms"})
    assert res_hrms.status_code == 403


# Scenario 9: SUPER_ADMIN remains separate from ORG_ADMIN
def test_scenario_9_platform_admin_separation(client, app, setup_tenancy):
    t = setup_tenancy

    # Create a platform admin token
    with app.app_context():
        plat_token = create_access_token(
            identity="usr_platform_super",
            additional_claims={
                "account_type": "PLATFORM_ADMIN",
                "roles": ["SUPER_ADMIN"]
            }
        )

    headers = {"Authorization": f"Bearer {plat_token}"}

    # Platform admin cannot query org dashboard context endpoint (requires ORGANIZATION_USER)
    res = client.get("/api/v1/users/me/dashboard-context", headers=headers)
    assert res.status_code == 403


# Scenario 10: get_dashboard_context returns accurate navigation, allowed_tabs, allowed_widgets
def test_scenario_10_dashboard_context_accuracy(client, app, setup_tenancy):
    t = setup_tenancy

    with app.app_context():
        # 1. Admin context
        admin_ctx = UserService.get_dashboard_context(t["admin_user"]["user_id"], t["org_id"])
        assert admin_ctx["success"] is True
        data = admin_ctx["data"]
        assert data["is_org_admin"] is True
        assert "tab-org-users" in data["allowed_tabs"]
        assert "tab-org-credentials" in data["allowed_tabs"]
        assert "tab-org-applications" in data["allowed_tabs"]
        assert len(data["allowed_widgets"]) > 5

        # 2. Employee context (HR specialist - only scoped to HRMS)
        emp_ctx = UserService.get_dashboard_context(t["hr_user"]["user_id"], t["org_id"])
        assert emp_ctx["success"] is True
        emp_data = emp_ctx["data"]
        assert emp_data["is_org_admin"] is False
        # Employee should NOT have tabs that require ungranted permissions
        assert "tab-org-users" not in emp_data["allowed_tabs"]
        assert "tab-org-credentials" not in emp_data["allowed_tabs"]
        # Assigned applications must list HRMS Portal and NOT CRM Portal
        assigned_names = [a["name"] for a in emp_data["assigned_applications"]]
        assert "HRMS Portal" in assigned_names
        assert "CRM Portal" not in assigned_names
