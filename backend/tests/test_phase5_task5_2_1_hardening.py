"""
SenderX Phase 5 Task 5.2.1: Acceptance Hardening Test Suite

Tests:
1. Role change takes effect immediately with the OLD token (old permissions 403, new permissions 200).
2. User deactivation takes effect immediately with the OLD token (returns 401).
3. Organization deactivation takes effect immediately with the OLD token (returns 403).
4. Platform Admin deactivation takes effect immediately with the OLD token (returns 401).
5. Platform Admin role downgrade takes effect immediately with the OLD token (returns 403).
6. Employee code edge cases:
   - Whitespace trimming
   - Case-insensitive duplicate rejection within an org
   - Max length validation (> 40 chars returns 400)
   - Min length validation (< 3 chars returns 400)
   - Allowed character validation (rejects invalid punctuation/spaces)
   - Legacy users with missing/null employee_code (sparse/partial index allows multiple nulls)
   - Same employee code in two different organizations permitted (201 in both)
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


@pytest.fixture
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def hardening_context(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]

        # 1. Platform Super Admin
        admin_id = f"adm_h_{suffix}"
        admin_email = f"admin_h_{suffix}@senderx.io"
        AuthRepository.create_admin({
            "admin_id": admin_id,
            "email": admin_email,
            "name": "Hardening Platform Admin",
            "password_hash": "dummy_hash",
            "role": "SUPER_ADMIN",
            "is_active": True
        })

        # 2. Org A and Org B
        org_a_id = f"org_a_{suffix}"
        org_b_id = f"org_b_{suffix}"
        OrganizationRepository.create({
            "organization_id": org_a_id,
            "name": f"Hardening Org Alpha {suffix}",
            "slug": f"alpha-h-{suffix}",
            "status": "ACTIVE"
        })
        OrganizationRepository.create({
            "organization_id": org_b_id,
            "name": f"Hardening Org Beta {suffix}",
            "slug": f"beta-h-{suffix}",
            "status": "ACTIVE"
        })

        # 3. Roles in Org A
        role_admin_a = f"role_adm_a_{suffix}"
        role_msg_a = f"role_msg_a_{suffix}"
        role_tpl_a = f"role_tpl_a_{suffix}"

        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "is_system_role": True,
            "permissions": list(UserService.ALLOWED_ORGANIZATION_PERMISSIONS)
        })
        RoleRepository.create({
            "role_id": role_msg_a,
            "organization_id": org_a_id,
            "name": "MESSAGE_OPERATOR",
            "scope": "ORGANIZATION",
            "is_system_role": False,
            "permissions": ["organization:messages:read"]
        })
        RoleRepository.create({
            "role_id": role_tpl_a,
            "organization_id": org_a_id,
            "name": "TEMPLATE_EDITOR",
            "scope": "ORGANIZATION",
            "is_system_role": False,
            "permissions": ["organization:templates:read"]
        })

        # 4. Org Admin A User
        admin_a = UserRepository.create({
            "user_id": f"usr_adm_a_{suffix}",
            "organization_id": org_a_id,
            "name": "Org A Admin",
            "email": f"orgadmin_a_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "role_ids": [role_admin_a],
            "employee_code": f"ADM-{suffix.upper()}",
            "is_active": True
        })

        # 5. Org Admin B User
        role_admin_b = f"role_adm_b_{suffix}"
        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b_id,
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "is_system_role": True,
            "permissions": list(UserService.ALLOWED_ORGANIZATION_PERMISSIONS)
        })
        admin_b = UserRepository.create({
            "user_id": f"usr_adm_b_{suffix}",
            "organization_id": org_b_id,
            "name": "Org B Admin",
            "email": f"orgadmin_b_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "role_ids": [role_admin_b],
            "employee_code": f"ADM-B-{suffix.upper()}",
            "is_active": True
        })

        # 6. Employee in Org A (starts with MESSAGE_OPERATOR)
        emp_user = UserRepository.create({
            "user_id": f"emp_a_{suffix}",
            "organization_id": org_a_id,
            "name": "Employee Alice",
            "email": f"alice_{suffix}@test.io",
            "password_hash": "dummy_hash",
            "role_ids": [role_msg_a],
            "role_assignments": [{"role_id": role_msg_a, "application_id": None}],
            "employee_code": f"EMP-ALICE-{suffix.upper()}",
            "is_active": True
        })

        # Generate JWT tokens
        token_super = create_access_token(
            identity=admin_id,
            additional_claims={"account_type": "PLATFORM_ADMIN", "role": "SUPER_ADMIN", "email": admin_email}
        )
        token_admin_a = create_access_token(
            identity=admin_a["user_id"],
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a_id, "role_ids": [role_admin_a]}
        )
        token_admin_b = create_access_token(
            identity=admin_b["user_id"],
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b_id, "role_ids": [role_admin_b]}
        )
        token_emp_a = create_access_token(
            identity=emp_user["user_id"],
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a_id, "role_ids": [role_msg_a]}
        )

        return {
            "suffix": suffix,
            "admin_id": admin_id,
            "org_a_id": org_a_id,
            "org_b_id": org_b_id,
            "role_admin_a": role_admin_a,
            "role_msg_a": role_msg_a,
            "role_tpl_a": role_tpl_a,
            "emp_user_id": emp_user["user_id"],
            "token_super": token_super,
            "token_admin_a": token_admin_a,
            "token_admin_b": token_admin_b,
            "token_emp_a": token_emp_a,
        }


# ============================================================================
# 1. IMMEDIATE ROLE CHANGE WITH OLD TOKEN
# ============================================================================

def test_role_change_immediate_with_old_token(client, hardening_context, app):
    """
    Employee Alice starts with role MESSAGE_OPERATOR.
    1. Using token_emp_a, GET /messages succeeds (200), GET /templates fails (403).
    2. Admin updates Alice's role to TEMPLATE_EDITOR in MongoDB.
    3. Without re-authenticating (using the OLD token_emp_a):
       - GET /messages immediately returns 403 (revoked).
       - GET /templates immediately returns 200 (granted).
    """
    old_token = hardening_context["token_emp_a"]
    headers = {"Authorization": f"Bearer {old_token}"}
    emp_id = hardening_context["emp_user_id"]
    org_id = hardening_context["org_a_id"]
    role_tpl = hardening_context["role_tpl_a"]

    # Initial permissions
    res_msg1 = client.get("/api/v1/messages/", headers=headers)
    assert res_msg1.status_code == 200

    res_tpl1 = client.get("/api/v1/templates/", headers=headers)
    assert res_tpl1.status_code == 403

    # Org Admin reassigns Alice's role to TEMPLATE_EDITOR in DB
    with app.app_context():
        UserRepository.update_user(emp_id, org_id, {
            "role_ids": [role_tpl],
            "role_assignments": [{"role_id": role_tpl, "application_id": None}]
        })

    # Immediately on the next request using the exact same OLD token:
    res_msg2 = client.get("/api/v1/messages/", headers=headers)
    assert res_msg2.status_code == 403, "Old permission was not immediately revoked!"

    res_tpl2 = client.get("/api/v1/templates/", headers=headers)
    assert res_tpl2.status_code == 200, "New permission was not immediately granted!"


# ============================================================================
# 2. USER DEACTIVATION WITH OLD TOKEN
# ============================================================================

def test_user_deactivation_immediate_with_old_token(client, hardening_context, app):
    """
    When an organization user is deactivated in MongoDB (is_active = False),
    subsequent requests using their OLD active token must immediately return 401.
    """
    old_token = hardening_context["token_emp_a"]
    headers = {"Authorization": f"Bearer {old_token}"}
    emp_id = hardening_context["emp_user_id"]
    org_id = hardening_context["org_a_id"]

    # Deactivate user in MongoDB
    with app.app_context():
        UserRepository.update_user(emp_id, org_id, {"is_active": False})

    # Request with OLD token must be rejected with 401
    res = client.get("/api/v1/users/me/dashboard-context", headers=headers)
    assert res.status_code == 401
    assert "inactive" in res.get_json()["message"].lower()

    # Protected route with require_permissions must also reject with 401
    res2 = client.get("/api/v1/templates/", headers=headers)
    assert res2.status_code == 401

    # Reactivate user for subsequent tests
    with app.app_context():
        UserRepository.update_user(emp_id, org_id, {"is_active": True})


# ============================================================================
# 3. ORGANIZATION DEACTIVATION WITH OLD TOKEN
# ============================================================================

def test_organization_deactivation_immediate_with_old_token(client, hardening_context, app):
    """
    When an organization's status is changed to INACTIVE or SUSPENDED,
    all members' subsequent requests with their OLD active tokens must immediately return 403.
    """
    token_admin_a = hardening_context["token_admin_a"]
    headers_admin = {"Authorization": f"Bearer {token_admin_a}"}
    org_id = hardening_context["org_a_id"]

    # Org Admin can access routes when ACTIVE
    res_before = client.get("/api/v1/users/", headers=headers_admin)
    assert res_before.status_code == 200

    # Deactivate organization in MongoDB
    with app.app_context():
        OrganizationRepository.update(org_id, {"status": "INACTIVE"})

    # Immediately with the OLD token:
    res_after = client.get("/api/v1/users/", headers=headers_admin)
    assert res_after.status_code == 403
    assert "inactive" in res_after.get_json()["message"].lower()

    # Dashboard context also returns 403
    res_ctx = client.get("/api/v1/users/me/dashboard-context", headers=headers_admin)
    assert res_ctx.status_code == 403

    # Restore organization to ACTIVE
    with app.app_context():
        OrganizationRepository.update(org_id, {"status": "ACTIVE"})


# ============================================================================
# 4. PLATFORM ADMIN DEACTIVATION & ROLE DOWNGRADE WITH OLD TOKEN
# ============================================================================

def test_platform_admin_deactivation_and_role_downgrade(client, hardening_context, app):
    """
    When a platform administrator is deactivated or downgraded in MongoDB,
    subsequent requests using their OLD active token must immediately reflect the DB change.
    """
    token_super = hardening_context["token_super"]
    headers = {"Authorization": f"Bearer {token_super}"}
    admin_id = hardening_context["admin_id"]

    # 1. Super Admin route succeeds
    res1 = client.get("/api/v1/organizations/", headers=headers)
    assert res1.status_code == 200

    # 2. Downgrade admin role to VIEWER in DB
    with app.app_context():
        AuthRepository._collection().update_one({"admin_id": admin_id}, {"$set": {"role": "VIEWER"}})

    # Calling super-admin-only route with OLD token immediately returns 403
    res_downgraded = client.post("/api/v1/organizations/", json={"name": "Test Org"}, headers=headers)
    assert res_downgraded.status_code == 403

    # 3. Deactivate platform admin in DB
    with app.app_context():
        AuthRepository._collection().update_one({"admin_id": admin_id}, {"$set": {"is_active": False}})

    # Calling any admin route with OLD token immediately returns 401
    res_deact = client.get("/api/v1/organizations/", headers=headers)
    assert res_deact.status_code == 401
    assert "inactive" in res_deact.get_json()["message"].lower()

    # Restore admin
    with app.app_context():
        AuthRepository._collection().update_one({"admin_id": admin_id}, {"$set": {"is_active": True, "role": "SUPER_ADMIN"}})


# ============================================================================
# 5. EMPLOYEE CODE EDGE CASES
# ============================================================================

class TestEmployeeCodeEdgeCases:

    def test_whitespace_trimming(self, client, hardening_context):
        """Whitespace surrounding an employee code must be stripped and saved clean."""
        headers = {"Authorization": f"Bearer {hardening_context['token_admin_a']}"}
        suffix = hardening_context["suffix"]

        res = client.post("/api/v1/users/", json={
            "name": "Whitespace Employee",
            "email": f"ws_{suffix}@test.io",
            "password": "Password123456!",
            "employee_code": "   EMP-TRIM-001   ",
            "role_ids": []
        }, headers=headers)
        assert res.status_code == 201
        data = res.get_json()["data"]
        assert data["employee_code"] == "EMP-TRIM-001"

    def test_case_insensitive_duplicate_within_org(self, client, hardening_context):
        """
        Creating an employee with a code differing only in case from an existing one
        within the same organization must be rejected with 409 Conflict.
        """
        headers = {"Authorization": f"Bearer {hardening_context['token_admin_a']}"}
        suffix = hardening_context["suffix"]

        # Create first with uppercase
        res1 = client.post("/api/v1/users/", json={
            "name": "Case Base Employee",
            "email": f"case1_{suffix}@test.io",
            "password": "Password123456!",
            "employee_code": f"CASE-DUP-{suffix.upper()}",
            "role_ids": []
        }, headers=headers)
        assert res1.status_code == 201

        # Attempt to create duplicate with lowercase
        res2 = client.post("/api/v1/users/", json={
            "name": "Case Duplicate Employee",
            "email": f"case2_{suffix}@test.io",
            "password": "Password123456!",
            "employee_code": f"case-dup-{suffix.lower()}",
            "role_ids": []
        }, headers=headers)
        assert res2.status_code == 409
        assert "already exists" in res2.get_json()["message"].lower()

    def test_max_and_min_length_boundaries(self, client, hardening_context):
        """Length must be between 3 and 40 characters."""
        headers = {"Authorization": f"Bearer {hardening_context['token_admin_a']}"}
        suffix = hardening_context["suffix"]

        # Too short (< 3 chars)
        res_short = client.post("/api/v1/users/", json={
            "name": "Short ID",
            "email": f"short_{suffix}@test.io",
            "password": "Password123456!",
            "employee_code": "AB",
            "role_ids": []
        }, headers=headers)
        assert res_short.status_code == 400
        assert "between 3 and 40 characters" in res_short.get_json()["message"]

        # Too long (> 40 chars)
        long_code = "EMP-" + "X" * 38  # 42 chars
        res_long = client.post("/api/v1/users/", json={
            "name": "Long ID",
            "email": f"long_{suffix}@test.io",
            "password": "Password123456!",
            "employee_code": long_code,
            "role_ids": []
        }, headers=headers)
        assert res_long.status_code == 400
        assert "between 3 and 40 characters" in res_long.get_json()["message"]

        # Exactly 40 characters is valid
        exact_40 = "EMP-" + "A" * 36  # 40 chars
        res_40 = client.post("/api/v1/users/", json={
            "name": "Exact 40 ID",
            "email": f"exact40_{suffix}@test.io",
            "password": "Password123456!",
            "employee_code": exact_40,
            "role_ids": []
        }, headers=headers)
        assert res_40.status_code == 201
        assert res_40.get_json()["data"]["employee_code"] == exact_40

    def test_allowed_character_validation(self, client, hardening_context):
        """Employee code must contain only uppercase letters, numbers, and hyphens."""
        headers = {"Authorization": f"Bearer {hardening_context['token_admin_a']}"}
        suffix = hardening_context["suffix"]

        invalid_codes = [
            "EMP_UNDERSCORE",      # underscores disallowed
            "EMP.DOT.001",         # dots disallowed
            "EMP@SPECIAL!",        # special characters disallowed
            "-LEADING-HYPHEN",     # cannot start with hyphen
            "TRAILING-HYPHEN-",    # cannot end with hyphen
            "DOUBLE--HYPHEN",      # double hyphens disallowed
        ]
        for inv_code in invalid_codes:
            res = client.post("/api/v1/users/", json={
                "name": "Invalid Code User",
                "email": f"inv_{uuid.uuid4().hex[:6]}@test.io",
                "password": "Password123456!",
                "employee_code": inv_code,
                "role_ids": []
            }, headers=headers)
            assert res.status_code == 400, f"Expected 400 for code '{inv_code}', got {res.status_code}"

    def test_same_code_in_two_different_orgs_permitted(self, client, hardening_context):
        """
        The exact same employee_code can exist in two different organizations.
        Both creations must succeed with HTTP 201.
        """
        headers_a = {"Authorization": f"Bearer {hardening_context['token_admin_a']}"}
        headers_b = {"Authorization": f"Bearer {hardening_context['token_admin_b']}"}
        shared_code = f"SHARED-GLOBAL-{hardening_context['suffix'].upper()}"

        # Create in Org A
        res_a = client.post("/api/v1/users/", json={
            "name": "Shared User Org A",
            "email": f"shared_a_{hardening_context['suffix']}@test.io",
            "password": "Password123456!",
            "employee_code": shared_code,
            "role_ids": []
        }, headers=headers_a)
        assert res_a.status_code == 201
        assert res_a.get_json()["data"]["employee_code"] == shared_code

        # Create in Org B with same employee_code
        res_b = client.post("/api/v1/users/", json={
            "name": "Shared User Org B",
            "email": f"shared_b_{hardening_context['suffix']}@test.io",
            "password": "Password123456!",
            "employee_code": shared_code,
            "role_ids": []
        }, headers=headers_b)
        assert res_b.status_code == 201
        assert res_b.get_json()["data"]["employee_code"] == shared_code

    def test_legacy_users_with_missing_employee_code_index_integrity(self, app, hardening_context):
        """
        Directly creates multiple legacy user documents in MongoDB without employee_code
        (or employee_code = None). The unique partial index must allow multiple null/missing documents.
        """
        with app.app_context():
            org_id = hardening_context["org_a_id"]
            suffix = uuid.uuid4().hex[:6]

            # Insert first legacy user without employee_code
            u1 = UserRepository.create({
                "user_id": f"leg1_{suffix}",
                "organization_id": org_id,
                "name": "Legacy User One",
                "email": f"leg1_{suffix}@test.io",
                "password_hash": "dummy",
                "role_ids": []
            })
            assert u1 is not None

            # Insert second legacy user without employee_code in the same organization
            u2 = UserRepository.create({
                "user_id": f"leg2_{suffix}",
                "organization_id": org_id,
                "name": "Legacy User Two",
                "email": f"leg2_{suffix}@test.io",
                "password_hash": "dummy",
                "role_ids": []
            })
            assert u2 is not None

            # Both documents exist simultaneously without unique index conflict
            found1 = UserRepository.find_by_id(u1["user_id"])
            found2 = UserRepository.find_by_id(u2["user_id"])
            assert found1 is not None
            assert found2 is not None
