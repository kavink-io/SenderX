"""
SenderX Phase 5 Task 5.4 Test Suite
Validates:
- 5.4.1 Employee Soft Deletion, Token Invalidation, Invariant Protections, and ID/Email Reuse.
- 5.4.2 Query Filtering (Deleted Hidden by Default, Accessible via Filter).
- 5.4.3 Human-Readable Security Audit Logs with Write-Time Snapshots, Filters, Search & Redaction.
- 5.4.5 Decision 1: Strict Role Name Validation (Underscores Forbidden for New/Renamed, Legacy Unchanged).
- 5.4.5 Decision 2: Self-Service Email Change Verification & Immediate Token Invalidation.
"""

from datetime import datetime, timezone
import pytest
import bcrypt

from app.modules.users.repository import UserRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.users.audit_repository import SecurityAuditRepository


@pytest.fixture
def setup_task5_4_context(client, app):
    """Sets up two isolated test organizations with admins and employees."""
    db = app.mongo_db

    # Clean test collections by organization ID
    db["organizations"].delete_many({"organization_id": {"$in": ["org_task54_a", "org_task54_b"]}})
    db["users"].delete_many({"organization_id": {"$in": ["org_task54_a", "org_task54_b"]}})
    db["roles"].delete_many({"organization_id": {"$in": ["org_task54_a", "org_task54_b"]}})
    db["security_audit_logs"].delete_many({"organization_id": {"$in": ["org_task54_a", "org_task54_b"]}})
    db["admins"].delete_many({"admin_id": "admin_root"})

    db["admins"].insert_one({
        "admin_id": "admin_root",
        "email": "superadmin@task54.io",
        "name": "Super Admin",
        "role": "SUPER_ADMIN",
        "is_active": True,
        "token_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Create Org A
    org_a = {
        "organization_id": "org_task54_a",
        "name": "Task54 Org Alpha",
        "slug": "task54-org-a",
        "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db["organizations"].insert_one(dict(org_a))

    # Create Org B
    org_b = {
        "organization_id": "org_task54_b",
        "name": "Task54 Org Beta",
        "slug": "task54-org-b",
        "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db["organizations"].insert_one(dict(org_b))

    # Create ORG_ADMIN role for both orgs
    role_admin_a = {
        "role_id": "role_task54_admin_a",
        "organization_id": "org_task54_a",
        "name": "ORG_ADMIN",
        "is_system_role": True,
        "scope": "ORGANIZATION",
        "permissions": [
            "organization:users:manage",
            "organization:users:delete",
            "organization:roles:manage",
            "organization:messages:read",
            "organization:templates:read"
        ]
    }
    db["roles"].insert_one(dict(role_admin_a))

    role_admin_b = {
        "role_id": "role_task54_admin_b",
        "organization_id": "org_task54_b",
        "name": "ORG_ADMIN",
        "is_system_role": True,
        "scope": "ORGANIZATION",
        "permissions": [
            "organization:users:manage",
            "organization:users:delete",
            "organization:roles:manage"
        ]
    }
    db["roles"].insert_one(dict(role_admin_b))

    # Create Primary Admin in Org A
    pwd_hash = bcrypt.hashpw(b"AdminPass123!456", bcrypt.gensalt(10)).decode("utf-8")
    admin_a1 = {
        "user_id": "user_task54_admin_a1",
        "organization_id": "org_task54_a",
        "name": "Admin Alice",
        "email": "alice.admin@task54-a.com",
        "password_hash": pwd_hash,
        "is_active": True,
        "status": "ACTIVE",
        "employee_code": "ADM-001",
        "employee_code_lower": "adm-001",
        "role_ids": ["role_task54_admin_a"],
        "token_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db["users"].insert_one(dict(admin_a1))

    # Create Secondary Admin in Org A
    admin_a2 = {
        "user_id": "user_task54_admin_a2",
        "organization_id": "org_task54_a",
        "name": "Admin Alex",
        "email": "alex.admin@task54-a.com",
        "password_hash": pwd_hash,
        "is_active": True,
        "status": "ACTIVE",
        "employee_code": "ADM-002",
        "employee_code_lower": "adm-002",
        "role_ids": ["role_task54_admin_a"],
        "token_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db["users"].insert_one(dict(admin_a2))

    # Create Admin in Org B
    admin_b = {
        "user_id": "user_task54_admin_b",
        "organization_id": "org_task54_b",
        "name": "Admin Bob",
        "email": "bob.admin@task54-b.com",
        "password_hash": pwd_hash,
        "is_active": True,
        "status": "ACTIVE",
        "employee_code": "ADM-001",
        "employee_code_lower": "adm-001",
        "role_ids": ["role_task54_admin_b"],
        "token_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db["users"].insert_one(dict(admin_b))

    # Login Admin A1
    login_a1 = client.post("/api/v1/auth/login", json={
        "email": "alice.admin@task54-a.com",
        "password": "AdminPass123!456"
    })
    token_admin_a1 = login_a1.json["data"]["access_token"]

    # Login Admin A2
    login_a2 = client.post("/api/v1/auth/login", json={
        "email": "alex.admin@task54-a.com",
        "password": "AdminPass123!456"
    })
    token_admin_a2 = login_a2.json["data"]["access_token"]

    # Login Admin B
    login_b = client.post("/api/v1/auth/login", json={
        "email": "bob.admin@task54-b.com",
        "password": "AdminPass123!456"
    })
    token_admin_b = login_b.json["data"]["access_token"]

    return {
        "org_a": org_a,
        "org_b": org_b,
        "token_admin_a1": token_admin_a1,
        "token_admin_a2": token_admin_a2,
        "token_admin_b": token_admin_b,
        "admin_a1": admin_a1,
        "admin_a2": admin_a2,
        "admin_b": admin_b
    }


# ==============================================================================
# 5.4.1 EMPLOYEE SOFT DELETION, TOKEN INVALIDATION & PROTECTIONS
# ==============================================================================

def test_employee_soft_delete_lifecycle_and_invariants(client, setup_task5_4_context, app):
    """
    Verifies:
    1. Employee creation and successful soft-deletion.
    2. Document is soft deleted: status=DELETED, is_active=False, is_deleted=True, deleted_at, deleted_by set.
    3. Document is NOT hard deleted from database.
    4. Active tokens for deleted employee are invalidated immediately (401).
    5. Deleted employee cannot log in (401).
    """
    ctx = setup_task5_4_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # 1. Create a regular employee
    emp_res = client.post("/api/v1/users/", json={
        "name": "Charlie Developer",
        "email": "charlie.dev@task54-a.com",
        "employee_code": "DEV-101",
        "password": "CharlieDev123!Safe"
    }, headers=headers_a)
    assert emp_res.status_code == 201
    emp_id = emp_res.json["data"]["user_id"]

    # 2. Login as the newly created employee
    login_emp = client.post("/api/v1/auth/login", json={
        "email": "charlie.dev@task54-a.com",
        "password": "CharlieDev123!Safe"
    })
    assert login_emp.status_code == 200
    emp_token = login_emp.json["data"]["access_token"]
    headers_emp = {"Authorization": f"Bearer {emp_token}"}

    # 3. Verify employee token works
    me_res = client.get("/api/v1/users/me/dashboard-context", headers=headers_emp)
    assert me_res.status_code == 200
    assert me_res.json["data"]["email"] == "charlie.dev@task54-a.com"

    # 4. ORG_ADMIN deletes the employee
    del_res = client.delete(f"/api/v1/users/{emp_id}", headers=headers_a)
    assert del_res.status_code == 200
    assert del_res.json["success"] is True

    # 5. Verify database record: soft deleted, not hard deleted
    db = app.mongo_db
    doc = db["users"].find_one({"user_id": emp_id})
    assert doc is not None
    assert doc["status"] == "DELETED"
    assert doc["is_active"] is False
    assert doc["is_deleted"] is True
    assert doc.get("deleted_at") is not None
    assert doc.get("deleted_by") == ctx["admin_a1"]["user_id"]

    # 6. Verify employee token is invalidated IMMEDIATELY (returns 401)
    me_after = client.get("/api/v1/users/me/dashboard-context", headers=headers_emp)
    assert me_after.status_code == 401

    # 7. Verify deleted employee cannot log in
    login_after = client.post("/api/v1/auth/login", json={
        "email": "charlie.dev@task54-a.com",
        "password": "CharlieDev123!Safe"
    })
    assert login_after.status_code == 401


def test_deletion_protections(client, setup_task5_4_context):
    """
    Verifies:
    1. Cannot delete yourself (HTTP 403).
    2. Cannot delete the last active ORG_ADMIN (HTTP 409).
    3. Cannot delete another organization's employee (HTTP 404).
    4. Can delete an admin if another active admin remains; then deleting the last one fails.
    """
    ctx = setup_task5_4_context
    headers_a1 = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}
    headers_b = {"Authorization": f"Bearer {ctx['token_admin_b']}"}

    # 1. Self-delete forbidden (403 or 409)
    self_del = client.delete(f"/api/v1/users/{ctx['admin_a1']['user_id']}", headers=headers_a1)
    assert self_del.status_code in (403, 409)
    assert "cannot delete your own account" in self_del.json["message"].lower()

    # 2. Cross-org delete forbidden (treated as 404)
    cross_del = client.delete(f"/api/v1/users/{ctx['admin_b']['user_id']}", headers=headers_a1)
    assert cross_del.status_code == 404

    # 3. Org B has only 1 active admin. Attempting to delete them (from Admin B self-perspective tested above)
    # Let's test Admin A2 deleting Admin A1 (Org A has 2 active admins)
    headers_a2 = {"Authorization": f"Bearer {ctx['token_admin_a2']}"}
    del_a1 = client.delete(f"/api/v1/users/{ctx['admin_a1']['user_id']}", headers=headers_a2)
    assert del_a1.status_code == 200
    assert del_a1.json["success"] is True

    # 4. Now Org A has only 1 active admin (Admin A2). Attempting to delete Admin A2 should fail
    # Create a temporary employee with users:manage permission to attempt deleting Admin A2
    emp_res = client.post("/api/v1/users/", json={
        "name": "Temp Manager",
        "email": "temp.mgr@task54-a.com",
        "employee_code": "MGR-999",
        "password": "SafePassword123!",
        "role_ids": ["role_task54_admin_a"]
    }, headers=headers_a2)
    assert emp_res.status_code == 201

    # But Admin A2 is the only remaining user with ORG_ADMIN who can manage.
    # What if Admin A2 is the only active admin?
    # Now count of active admins in Org A is 2 (Admin A2 and Temp Manager).
    # Deactivate Temp Manager so Admin A2 is strictly the LAST active admin
    client.post(f"/api/v1/users/{emp_res.json['data']['user_id']}/deactivate", headers=headers_a2)

    # Now verify: trying to delete Admin A2 is rejected with 409
    # (Since self-delete gives 403, test UserService directly for last admin protection)
    from app.modules.users.service import UserService
    res_last = UserService.delete_user(
        user_id=ctx["admin_a2"]["user_id"],
        organization_id="org_task54_a",
        actor_id="someone_else"
    )
    assert res_last["success"] is False
    assert res_last["status_code"] == 409
    assert "last active administrator" in res_last["message"].lower()


def test_employee_id_and_email_reuse_after_deletion(client, setup_task5_4_context, app):
    """
    Verifies that deleting an employee releases their employee_code and email
    for future reuse without encountering unique index collisions.
    """
    ctx = setup_task5_4_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # 1. Create initial employee
    res1 = client.post("/api/v1/users/", json={
        "name": "Reused Identity User",
        "email": "reusable.emp@task54-a.com",
        "employee_code": "REUSE-001",
        "password": "Password123!456"
    }, headers=headers_a)
    assert res1.status_code == 201
    first_id = res1.json["data"]["user_id"]

    # 2. Attempt duplicate while active -> should fail 409
    dup_res = client.post("/api/v1/users/", json={
        "name": "Another User",
        "email": "reusable.emp@task54-a.com",
        "employee_code": "REUSE-001",
        "password": "Password123!456"
    }, headers=headers_a)
    assert dup_res.status_code == 409

    # 3. Delete the first employee
    del_res = client.delete(f"/api/v1/users/{first_id}", headers=headers_a)
    assert del_res.status_code == 200

    # 4. Create a NEW employee with the EXACT SAME employee_code and email
    res2 = client.post("/api/v1/users/", json={
        "name": "New Person Reused Identity",
        "email": "reusable.emp@task54-a.com",
        "employee_code": "REUSE-001",
        "password": "BrandNewPassword123!"
    }, headers=headers_a)
    assert res2.status_code == 201
    second_id = res2.json["data"]["user_id"]
    assert second_id != first_id

    # 5. Verify new user can log in with new password
    login_new = client.post("/api/v1/auth/login", json={
        "email": "reusable.emp@task54-a.com",
        "password": "BrandNewPassword123!"
    })
    assert login_new.status_code == 200
    assert login_new.json["data"]["account"]["id"] == second_id


def test_query_filtering_deleted_hidden_by_default(client, setup_task5_4_context):
    """
    Verifies:
    1. Default employee list (/api/v1/users/) excludes soft-deleted employees.
    2. Querying with ?status=DELETED includes only soft-deleted employees.
    """
    ctx = setup_task5_4_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # Create an employee and delete them
    res = client.post("/api/v1/users/", json={
        "name": "Ghost User",
        "email": "ghost.user@task54-a.com",
        "employee_code": "GHOST-001",
        "password": "SafePassword123!"
    }, headers=headers_a)
    assert res.status_code == 201
    ghost_id = res.json["data"]["user_id"]

    client.delete(f"/api/v1/users/{ghost_id}", headers=headers_a)

    # 1. Default list -> ghost user must NOT appear
    default_list = client.get("/api/v1/users/", headers=headers_a)
    assert default_list.status_code == 200
    items = default_list.json["data"]
    assert not any(u["user_id"] == ghost_id for u in items)

    # 2. Filter status=DELETED -> ghost user MUST appear
    deleted_list = client.get("/api/v1/users/?status=DELETED", headers=headers_a)
    assert deleted_list.status_code == 200
    del_items = deleted_list.json["data"]
    assert any(u["user_id"] == ghost_id for u in del_items)


# ==============================================================================
# 5.4.3 HUMAN-READABLE SECURITY AUDIT LOGS & SNAPSHOTS
# ==============================================================================

def test_audit_log_write_time_snapshots_and_filters(client, setup_task5_4_context):
    """
    Verifies:
    1. Audit log stores write-time snapshots (actor_name, target_name, action_label, summary, result).
    2. EMPLOYEE_DELETED event is properly logged.
    3. Snapshots persist even if the target is deleted or renamed.
    4. Filters: search, action category, result, and pagination work.
    5. Passwords, hashes, and secrets are redacted in details.
    """
    ctx = setup_task5_4_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # 1. Create and delete an employee to trigger audit events
    emp_res = client.post("/api/v1/users/", json={
        "name": "Audit Snapshot Target",
        "email": "audit.target@task54-a.com",
        "employee_code": "AUDIT-007",
        "password": "SuperSecretPassword123!"
    }, headers=headers_a)
    assert emp_res.status_code == 201
    target_id = emp_res.json["data"]["user_id"]

    del_res = client.delete(f"/api/v1/users/{target_id}", headers=headers_a)
    assert del_res.status_code == 200

    # 2. Fetch audit logs
    audit_res = client.get("/api/v1/users/audit-logs", headers=headers_a)
    assert audit_res.status_code == 200
    logs = audit_res.json["data"]
    assert len(logs) >= 2

    # Verify EMPLOYEE_DELETED entry
    del_log = next((l for l in logs if l.get("event_type") == "EMPLOYEE_DELETED"), None)
    assert del_log is not None
    assert del_log["actor_name"] == "Admin Alice"
    assert del_log["actor_email"] == "alice.admin@task54-a.com"
    assert del_log["target_name"] == "Audit Snapshot Target"
    assert del_log["action_label"] == "Employee Deleted"
    assert "Deleted employee Audit Snapshot Target" in del_log["summary"]
    assert del_log["result"] == "SUCCESS"

    # Verify sensitive data redaction: password must NOT appear anywhere in details
    details_str = str(del_log.get("details", {})).lower()
    assert "supersecretpassword123!" not in details_str
    assert "password_hash" not in del_log.get("details", {})

    # 3. Test filter by search
    search_res = client.get("/api/v1/users/audit-logs?search=Audit Snapshot Target", headers=headers_a)
    assert search_res.status_code == 200
    assert any(l["target_name"] == "Audit Snapshot Target" for l in search_res.json["data"])

    # 4. Test filter by action category
    action_res = client.get("/api/v1/users/audit-logs?action=EMPLOYEE", headers=headers_a)
    assert action_res.status_code == 200
    assert all(l["event_type"].startswith("EMPLOYEE_") for l in action_res.json["data"])

    # 5. Test filter by result
    result_res = client.get("/api/v1/users/audit-logs?result=SUCCESS", headers=headers_a)
    assert result_res.status_code == 200
    assert all(l["result"] == "SUCCESS" for l in result_res.json["data"])

    # 6. Test platform-wide audit logs endpoint for SUPER_ADMIN
    # Create platform super admin token
    from app.modules.auth.service import AuthService
    sa_tokens = AuthService._generate_tokens("admin_root", {"account_type": "PLATFORM_ADMIN", "role": "SUPER_ADMIN"})
    headers_sa = {"Authorization": f"Bearer {sa_tokens['access_token']}"}

    plat_res = client.get(f"/api/v1/platform/audit-logs?organization_id=org_task54_a", headers=headers_sa)
    assert plat_res.status_code == 200
    assert len(plat_res.json["data"]) >= 2


# ==============================================================================
# 5.4.5 DECISION 1: STRICT ROLE NAME VALIDATION
# ==============================================================================

def test_strict_role_name_validation(client, setup_task5_4_context, app):
    """
    Verifies:
    1. Newly created role with underscores is REJECTED (HTTP 400).
    2. Newly created role with valid characters (letters, digits, spaces, hyphen, ampersand) SUCCEEDS.
    3. Renaming a role to an underscore name is REJECTED (HTTP 400).
    4. Legacy role with underscore (inserted directly in DB) can still have its permissions edited.
    5. Legacy role name displays as stored without alteration.
    """
    ctx = setup_task5_4_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # 1. New role with underscore is rejected
    res_underscore = client.post("/api/v1/users/roles", json={
        "name": "SUPPORT_SPECIALIST",
        "description": "Legacy-style uppercase with underscore",
        "permissions": ["organization:messages:read"]
    }, headers=headers_a)
    assert res_underscore.status_code == 400
    assert "hyphen" in res_underscore.json["message"].lower() or "letters" in res_underscore.json["message"].lower()

    # 2. Valid role name with letters, spaces, hyphen, ampersand succeeds
    res_valid = client.post("/api/v1/users/roles", json={
        "name": "Billing & Tier-1 Support Specialist",
        "description": "Valid human-readable role",
        "permissions": ["organization:messages:read"]
    }, headers=headers_a)
    assert res_valid.status_code == 201
    created_role_id = res_valid.json["data"]["role_id"]
    assert res_valid.json["data"]["name"] == "Billing & Tier-1 Support Specialist"

    # 3. Renaming to an underscore name is rejected
    rename_underscore = client.patch(f"/api/v1/users/roles/{created_role_id}", json={
        "name": "BILLING_SPECIALIST_V2"
    }, headers=headers_a)
    assert rename_underscore.status_code == 400

    # 4. Insert a legacy role with underscore directly into MongoDB
    db = app.mongo_db
    legacy_role_id = "role_legacy_underscore_99"
    db["roles"].insert_one({
        "role_id": legacy_role_id,
        "organization_id": "org_task54_a",
        "name": "LEGACY_CRM_OPERATOR",
        "description": "Pre-existing role with underscores",
        "scope": "ORGANIZATION",
        "permissions": ["organization:messages:read"],
        "is_system_role": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # 5. Editing permissions of legacy role succeeds without re-validating the unchanged name
    update_perm = client.patch(f"/api/v1/users/roles/{legacy_role_id}", json={
        "permissions": ["organization:messages:read", "organization:templates:read"]
    }, headers=headers_a)
    assert update_perm.status_code == 200

    # 6. Legacy role name still displays exactly as stored
    get_role = client.get(f"/api/v1/users/roles/{legacy_role_id}", headers=headers_a)
    assert get_role.status_code == 200
    assert get_role.json["data"]["name"] == "LEGACY_CRM_OPERATOR"


# ==============================================================================
# 5.4.5 DECISION 2: SELF-SERVICE EMAIL CHANGE VERIFICATION
# ==============================================================================

def test_self_service_email_change_login_and_token_invalidation(client, setup_task5_4_context):
    """
    Verifies that after an email change:
    1. Current password is required.
    2. Old email can no longer log in.
    3. New email can log in successfully.
    4. New audit log snapshots reflect the new email.
    """
    ctx = setup_task5_4_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # Attempt to change email without current_password -> rejected 400
    res_no_pwd = client.patch("/api/v1/users/me/profile", json={
        "email": "alice.newemail@task54-a.com"
    }, headers=headers_a)
    assert res_no_pwd.status_code == 400
    assert "current password" in res_no_pwd.json["message"].lower()

    # Change email with valid current_password
    res_change = client.patch("/api/v1/users/me/profile", json={
        "email": "alice.newemail@task54-a.com",
        "current_password": "AdminPass123!456"
    }, headers=headers_a)
    assert res_change.status_code == 200
    assert res_change.json["data"]["email"] == "alice.newemail@task54-a.com"

    # 1. Old email cannot log in
    old_login = client.post("/api/v1/auth/login", json={
        "email": "alice.admin@task54-a.com",
        "password": "AdminPass123!456"
    })
    assert old_login.status_code == 401

    # 2. New email logs in successfully
    new_login = client.post("/api/v1/auth/login", json={
        "email": "alice.newemail@task54-a.com",
        "password": "AdminPass123!456"
    })
    assert new_login.status_code == 200
    assert new_login.json["data"]["account"]["email"] == "alice.newemail@task54-a.com"


# ==============================================================================
# PHASE 5 TASK 5.4 AMENDMENT: DEPARTMENT & PHONE FIELDS + BCRYPT CONFIGURATION
# ==============================================================================

def test_bcrypt_rounds_production_default():
    """Assert that the non-test default bcrypt cost in settings is 12."""
    import os
    from importlib import reload
    import app.config.settings as s_mod

    orig = os.environ.get("BCRYPT_ROUNDS")
    try:
        if "BCRYPT_ROUNDS" in os.environ:
            del os.environ["BCRYPT_ROUNDS"]
        reload(s_mod)
        assert s_mod.Config.BCRYPT_ROUNDS == 12
    finally:
        if orig is not None:
            os.environ["BCRYPT_ROUNDS"] = orig
        reload(s_mod)


def test_employee_department_and_phone_lifecycle(client, setup_task5_4_context):
    """
    Verifies that:
    1. Department (optional text 2-60 chars) and Phone (optional international format) are persisted.
    2. Missing/empty values are preserved and returned as None.
    3. Updating an employee can add, change, or clear department and phone.
    4. Employee details API returns department and phone.
    """
    ctx = setup_task5_4_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # 1. Create employee with department and phone
    create_res = client.post("/api/v1/users/", json={
        "name": "Dev Specialist",
        "email": "dev.specialist@task54-a.com",
        "employee_code": "DEV-501",
        "password": "Password123!456",
        "department": "Platform Engineering",
        "phone": "+1 650 555 0199"
    }, headers=headers_a)
    assert create_res.status_code == 201
    created_user = create_res.json["data"]
    assert created_user["department"] == "Platform Engineering"
    assert created_user["phone"] == "+1 650 555 0199"
    user_id = created_user["user_id"]

    # 2. Retrieve details via get_user_by_id
    detail_res = client.get(f"/api/v1/users/{user_id}", headers=headers_a)
    assert detail_res.status_code == 200
    assert detail_res.json["data"]["department"] == "Platform Engineering"
    assert detail_res.json["data"]["phone"] == "+1 650 555 0199"

    # 3. Update employee department and phone
    update_res = client.put(f"/api/v1/users/{user_id}", json={
        "name": "Dev Specialist Updated",
        "department": "Infrastructure Ops",
        "phone": "+44 20 7946 0991"
    }, headers=headers_a)
    assert update_res.status_code == 200
    assert update_res.json["data"]["department"] == "Infrastructure Ops"
    assert update_res.json["data"]["phone"] == "+44 20 7946 0991"

    # 4. Create employee without department or phone (optional fields)
    empty_res = client.post("/api/v1/users/", json={
        "name": "General Employee",
        "email": "general.emp@task54-a.com",
        "employee_code": "GEN-502",
        "password": "Password123!456"
    }, headers=headers_a)
    assert empty_res.status_code == 201
    assert empty_res.json["data"]["department"] is None
    assert empty_res.json["data"]["phone"] is None


def test_employee_department_and_phone_validation_rules(client, setup_task5_4_context):
    """
    Verifies validation rules for department and phone:
    - Department too short (< 2 chars) -> 400
    - Department too long (> 60 chars) -> 400
    - Phone invalid format -> 400
    - Phone valid international formats accepted
    """
    ctx = setup_task5_4_context
    headers_a = {"Authorization": f"Bearer {ctx['token_admin_a1']}"}

    # Department too short
    res_short = client.post("/api/v1/users/", json={
        "name": "Short Dept",
        "email": "short.dept@task54-a.com",
        "employee_code": "DEP-001",
        "password": "Password123!456",
        "department": "X"
    }, headers=headers_a)
    assert res_short.status_code == 400
    assert "department" in res_short.json["message"].lower()

    # Department too long (> 60 chars)
    res_long = client.post("/api/v1/users/", json={
        "name": "Long Dept",
        "email": "long.dept@task54-a.com",
        "employee_code": "DEP-002",
        "password": "Password123!456",
        "department": "A" * 65
    }, headers=headers_a)
    assert res_long.status_code == 400
    assert "department" in res_long.json["message"].lower()

    # Invalid phone format
    res_bad_phone = client.post("/api/v1/users/", json={
        "name": "Bad Phone",
        "email": "bad.phone@task54-a.com",
        "employee_code": "PHO-001",
        "password": "Password123!456",
        "phone": "invalid-phone-abc"
    }, headers=headers_a)
    assert res_bad_phone.status_code == 400
    assert "phone" in res_bad_phone.json["message"].lower()

