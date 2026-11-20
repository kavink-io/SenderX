"""
Phase 5 Task 5.3 Test Suite:
- Organization Account Self-Service Profile
- Organization Change Requests (Creation, Cancellation, Super Admin Approval/Rejection)
- Super Admin Organization Deletion (Soft Delete & Cascade Deactivations)
- Self-Role Protection (403 on self-role/scope changes)
- Human-Readable Role Names (Spaces, Hyphens, Ampersands, Case-Insensitive Uniqueness)
- Password Change & Token Invalidation
"""

import uuid
import pytest
from app import create_app
from app.modules.auth.service import AuthService
from app.modules.organizations.service import OrganizationService
from app.modules.users.service import UserService
from app.modules.users.repository import UserRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.organizations.change_request_repository import OrganizationChangeRequestRepository


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with app.app_context():
            yield c


def _create_super_admin(client):
    suffix = uuid.uuid4().hex[:6]
    email = f"superadmin_{suffix}@senderx.io"
    password = "SuperSecretPassword123!"
    admin_id = str(uuid.uuid4())
    import bcrypt
    from datetime import datetime, timezone
    client.application.mongo_db["admins"].insert_one({
        "admin_id": admin_id,
        "name": f"Super Admin {suffix}",
        "email": email,
        "password_hash": bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8"),
        "role": "SUPER_ADMIN",
        "is_active": True,
        "token_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    data = res.get_json()
    return {
        "admin_id": admin_id,
        "email": email,
        "password": password,
        "token": data["data"]["access_token"]
    }


def _create_test_org(client, super_admin_token, suffix=None):
    s = suffix or uuid.uuid4().hex[:6]
    name = f"Test Org {s}"
    slug = f"test-org-{s}"
    admin_email = f"orgadmin_{s}@tenant.io"
    admin_password = "OrgAdminPassword123!"
    employee_code = f"EMP-{s.upper()}"

    res = client.post(
        "/api/v1/organizations/",
        headers={"Authorization": f"Bearer {super_admin_token}"},
        json={
            "name": name,
            "slug": slug,
            "admin_name": f"Admin {s}",
            "admin_email": admin_email,
            "admin_password": admin_password,
            "employee_code": employee_code
        }
    )
    assert res.status_code == 201, res.get_data(as_text=True)
    org_data = res.get_json()["data"]

    # Login as org admin
    login_res = client.post("/api/v1/auth/login", json={"email": admin_email, "password": admin_password})
    assert login_res.status_code == 200, login_res.get_data(as_text=True)
    login_data = login_res.get_json()["data"]

    return {
        "organization_id": org_data["organization_id"],
        "name": name,
        "slug": slug,
        "admin_id": org_data["admin"]["user_id"],
        "admin_email": admin_email,
        "admin_password": admin_password,
        "employee_code": employee_code,
        "token": login_data["access_token"]
    }


def test_org_admin_self_service_profile_update(client):
    sa = _create_super_admin(client)
    org = _create_test_org(client, sa["token"])
    headers = {"Authorization": f"Bearer {org['token']}"}

    # 1. Update own name
    res = client.patch("/api/v1/users/me/profile", headers=headers, json={"name": "Updated Admin Name"})
    assert res.status_code == 200, res.get_data(as_text=True)
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["name"] == "Updated Admin Name"
    assert "password_hash" not in body["data"]

    # 2. Email change without current password should fail
    res = client.patch("/api/v1/users/me/profile", headers=headers, json={"email": "newemail@tenant.io"})
    assert res.status_code == 400
    assert "Current password is required" in res.get_json()["message"]

    # 3. Email change with wrong current password should fail
    res = client.patch("/api/v1/users/me/profile", headers=headers, json={
        "email": "newemail@tenant.io",
        "current_password": "WrongPassword999!"
    })
    assert res.status_code == 400
    assert "Incorrect current password" in res.get_json()["message"]

    # 4. Email change with correct current password succeeds
    new_email = f"new_{uuid.uuid4().hex[:6]}@tenant.io"
    res = client.patch("/api/v1/users/me/profile", headers=headers, json={
        "email": new_email,
        "current_password": org["admin_password"]
    })
    assert res.status_code == 200, res.get_data(as_text=True)
    assert res.get_json()["data"]["email"] == new_email


def test_org_admin_cannot_change_organization_name_or_slug_directly(client):
    sa = _create_super_admin(client)
    org = _create_test_org(client, sa["token"])
    headers = {"Authorization": f"Bearer {org['token']}"}

    # In user profile endpoint
    res1 = client.patch("/api/v1/users/me/profile", headers=headers, json={"organization_name": "Hacked Corp"})
    assert res1.status_code == 403
    assert "Direct organization name or slug changes are not permitted" in res1.get_json()["message"]

    res2 = client.patch("/api/v1/users/me/profile", headers=headers, json={"slug": "hacked-slug"})
    assert res2.status_code == 403
    assert "Direct organization name or slug changes are not permitted" in res2.get_json()["message"]

    # In organization endpoint
    res3 = client.patch("/api/v1/organizations/current", headers=headers, json={"name": "Hacked Org"})
    assert res3.status_code == 403

    res4 = client.patch(f"/api/v1/organizations/{org['organization_id']}", headers=headers, json={"name": "Hacked Org"})
    assert res4.status_code == 403


def test_password_change_invalidates_all_previous_tokens(client):
    sa = _create_super_admin(client)
    org = _create_test_org(client, sa["token"])
    old_token = org["token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    # Verify old token works currently
    ctx_res = client.get("/api/v1/users/me/dashboard-context", headers=old_headers)
    assert ctx_res.status_code == 200

    new_password = "BrandNewSuperPassword123!"

    # Change password
    res = client.patch("/api/v1/users/me/profile", headers=old_headers, json={
        "current_password": org["admin_password"],
        "new_password": new_password
    })
    assert res.status_code == 200, res.get_data(as_text=True)
    res_data = res.get_json()["data"]
    assert "access_token" in res_data
    new_token = res_data["access_token"]
    assert new_token != old_token

    # Verify that the OLD token is now immediately rejected with 401!
    old_call = client.get("/api/v1/users/me/dashboard-context", headers=old_headers)
    assert old_call.status_code == 401
    assert "Session expired or password changed" in old_call.get_json()["message"]

    old_users_call = client.get("/api/v1/users/", headers=old_headers)
    assert old_users_call.status_code == 401

    # Verify that login with OLD password fails
    bad_login = client.post("/api/v1/auth/login", json={"email": org["admin_email"], "password": org["admin_password"]})
    assert bad_login.status_code in (400, 401)

    # Verify that login with NEW password succeeds
    good_login = client.post("/api/v1/auth/login", json={"email": org["admin_email"], "password": new_password})
    assert good_login.status_code == 200

    # Fresh token works
    new_headers = {"Authorization": f"Bearer {new_token}"}
    new_call = client.get("/api/v1/users/me/dashboard-context", headers=new_headers)
    assert new_call.status_code == 200


def test_organization_change_request_full_lifecycle(client):
    sa = _create_super_admin(client)
    org = _create_test_org(client, sa["token"])
    org_headers = {"Authorization": f"Bearer {org['token']}"}
    sa_headers = {"Authorization": f"Bearer {sa['token']}"}

    # 1. Validation: Submission without reason must be rejected
    bad_sub1 = client.post("/api/v1/organizations/change-requests", headers=org_headers, json={
        "requested_name": "New Name Without Reason"
    })
    assert bad_sub1.status_code == 400

    # 2. Validation: Submission without requested_name and without requested_slug rejected
    bad_sub2 = client.post("/api/v1/organizations/change-requests", headers=org_headers, json={
        "reason": "Just a reason with no change target"
    })
    assert bad_sub2.status_code == 400

    # 3. Successful submission
    req_slug = f"acme-brand-{uuid.uuid4().hex[:6]}"
    sub_res = client.post("/api/v1/organizations/change-requests", headers=org_headers, json={
        "requested_name": "Acme Brand Global",
        "requested_slug": req_slug,
        "reason": "Rebranding initiative for Q4 corporate expansion."
    })
    assert sub_res.status_code == 201, sub_res.get_data(as_text=True)
    req_data = sub_res.get_json()["data"]
    request_id = req_data["request_id"]
    assert req_data["status"] == "PENDING"
    assert req_data["requested_name"] == "Acme Brand Global"
    assert req_data["requested_slug"] == req_slug

    # 4. Attempting another submission while PENDING must be rejected with 409
    dup_sub = client.post("/api/v1/organizations/change-requests", headers=org_headers, json={
        "requested_name": "Another Name",
        "reason": "Another request while one is pending"
    })
    assert dup_sub.status_code == 409
    assert "already pending" in dup_sub.get_json()["message"]

    # 5. List org change requests
    list_res = client.get("/api/v1/organizations/change-requests", headers=org_headers)
    assert list_res.status_code == 200
    items = list_res.get_json()["items"]
    assert any(r["request_id"] == request_id for r in items)

    # 6. Cancel pending request
    cancel_res = client.post(f"/api/v1/organizations/change-requests/{request_id}/cancel", headers=org_headers)
    assert cancel_res.status_code == 200

    # 7. Now another request can be submitted
    new_sub = client.post("/api/v1/organizations/change-requests", headers=org_headers, json={
        "requested_name": "Acme Final Name",
        "requested_slug": req_slug,
        "reason": "Submitted after cancellation of previous request."
    })
    assert new_sub.status_code == 201
    new_request_id = new_sub.get_json()["data"]["request_id"]

    # 8. Super Admin lists change requests
    platform_list = client.get("/api/v1/platform/change-requests", headers=sa_headers)
    assert platform_list.status_code == 200
    p_items = platform_list.get_json()["items"]
    assert any(r["request_id"] == new_request_id for r in p_items)

    # 9. Super Admin approves change request
    approve_res = client.post(f"/api/v1/platform/change-requests/{new_request_id}/approve", headers=sa_headers)
    assert approve_res.status_code == 200

    # 10. Verify organization updated in DB
    updated_org = OrganizationRepository.find_by_id(org["organization_id"])
    assert updated_org["name"] == "Acme Final Name"
    assert updated_org["slug"] == req_slug
    assert updated_org["organization_id"] == org["organization_id"]  # Preserved _id & ID!


def test_change_request_approval_duplicate_slug_conflict(client):
    sa = _create_super_admin(client)
    org1 = _create_test_org(client, sa["token"])
    org2 = _create_test_org(client, sa["token"])
    org1_headers = {"Authorization": f"Bearer {org1['token']}"}
    sa_headers = {"Authorization": f"Bearer {sa['token']}"}

    target_slug = f"shared-slug-{uuid.uuid4().hex[:6]}"

    # Org1 requests target_slug
    sub1 = client.post("/api/v1/organizations/change-requests", headers=org1_headers, json={
        "requested_slug": target_slug,
        "reason": "Wanting target slug"
    })
    assert sub1.status_code == 201
    req1_id = sub1.get_json()["data"]["request_id"]

    # Meanwhile, an admin updates Org2's slug directly in DB or another approval takes target_slug
    OrganizationRepository.update(org2["organization_id"], {"slug": target_slug})

    # Now Super Admin attempts to approve Org1's request for target_slug
    approve_res = client.post(f"/api/v1/platform/change-requests/{req1_id}/approve", headers=sa_headers)
    assert approve_res.status_code == 409
    assert "already in use" in approve_res.get_json()["message"]


def test_change_request_rejection_requires_reason(client):
    sa = _create_super_admin(client)
    org = _create_test_org(client, sa["token"])
    org_headers = {"Authorization": f"Bearer {org['token']}"}
    sa_headers = {"Authorization": f"Bearer {sa['token']}"}

    sub = client.post("/api/v1/organizations/change-requests", headers=org_headers, json={
        "requested_name": "Rejectable Name",
        "reason": "Request to test rejection"
    })
    assert sub.status_code == 201
    req_id = sub.get_json()["data"]["request_id"]

    # Reject without reason: fails
    rej_fail = client.post(f"/api/v1/platform/change-requests/{req_id}/reject", headers=sa_headers, json={})
    assert rej_fail.status_code == 400
    assert "Rejection reason is required" in rej_fail.get_json()["message"]

    # Reject with reason: succeeds
    rej_ok = client.post(f"/api/v1/platform/change-requests/{req_id}/reject", headers=sa_headers, json={
        "rejection_reason": "Requested branding infringes on trademark policy."
    })
    assert rej_ok.status_code == 200

    # Verify status is REJECTED
    req_doc = OrganizationChangeRequestRepository.find_by_id(req_id)
    assert req_doc["status"] == "REJECTED"
    assert req_doc["rejection_reason"] == "Requested branding infringes on trademark policy."


def test_cross_org_change_request_denial(client):
    sa = _create_super_admin(client)
    org1 = _create_test_org(client, sa["token"])
    org2 = _create_test_org(client, sa["token"])
    org1_headers = {"Authorization": f"Bearer {org1['token']}"}
    org2_headers = {"Authorization": f"Bearer {org2['token']}"}

    # Org1 creates change request
    sub = client.post("/api/v1/organizations/change-requests", headers=org1_headers, json={
        "requested_name": "Org 1 Rename",
        "reason": "Legitimate reason"
    })
    assert sub.status_code == 201
    req1_id = sub.get_json()["data"]["request_id"]

    # Org2 attempts to cancel Org1's request: must be rejected with 404 (cross-tenant denial)
    cancel_attempt = client.post(f"/api/v1/organizations/change-requests/{req1_id}/cancel", headers=org2_headers)
    assert cancel_attempt.status_code == 404

    # Org2 cannot see Org1's change requests
    org2_list = client.get("/api/v1/organizations/change-requests", headers=org2_headers)
    assert org2_list.status_code == 200
    assert not any(r["request_id"] == req1_id for r in org2_list.get_json()["items"])


def test_self_role_protection_for_org_admin_and_employees(client):
    sa = _create_super_admin(client)
    org = _create_test_org(client, sa["token"])
    headers = {"Authorization": f"Bearer {org['token']}"}

    # Create a custom role to attempt self-assignment
    custom_role = RoleRepository.create({
        "role_id": str(uuid.uuid4()),
        "organization_id": org["organization_id"],
        "name": "Custom Role Test",
        "scope": "ORGANIZATION",
        "permissions": ["organization:messages:read"],
        "is_system_role": False
    })

    # 1. ORG_ADMIN attempts to modify own role via PATCH /api/v1/users/<id>
    res1 = client.patch(
        f"/api/v1/users/{org['admin_id']}",
        headers=headers,
        json={"role_ids": [custom_role["role_id"]]}
    )
    assert res1.status_code == 403, res1.get_data(as_text=True)
    assert "You cannot modify your own roles" in res1.get_json()["message"]

    # 2. ORG_ADMIN attempts to modify own role via POST /api/v1/users/<id>/roles
    res2 = client.post(
        f"/api/v1/users/{org['admin_id']}/roles",
        headers=headers,
        json={"role_ids": [custom_role["role_id"]]}
    )
    assert res2.status_code == 403
    assert "You cannot modify your own roles" in res2.get_json()["message"]

    # 3. Create regular employee
    emp_res = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "name": "Jane Employee",
            "email": f"emp_{uuid.uuid4().hex[:6]}@tenant.io",
            "employee_code": f"EMP-{uuid.uuid4().hex[:6].upper()}",
            "role_ids": [custom_role["role_id"]]
        }
    )
    assert emp_res.status_code == 201
    emp_data = emp_res.get_json()["data"]

    # ORG_ADMIN CAN update other employee's roles
    update_emp = client.post(
        f"/api/v1/users/{emp_data['user_id']}/roles",
        headers=headers,
        json={"role_ids": [custom_role["role_id"]]}
    )
    assert update_emp.status_code == 200

    # Employee logs in
    with client.application.app_context():
        import bcrypt
        UserRepository._collection().update_one({"user_id": emp_data["user_id"]}, {"$set": {
            "status": "ACTIVE",
            "is_active": True,
            "password_hash": bcrypt.hashpw(b"EmployeePassword123!", bcrypt.gensalt(rounds=4)).decode("utf-8")
        }})
    emp_login = client.post("/api/v1/auth/login", json={
        "email": emp_data["email"],
        "password": "EmployeePassword123!"
    })
    emp_token = emp_login.get_json()["data"]["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # Employee cannot change own roles
    emp_self = client.patch(
        f"/api/v1/users/{emp_data['user_id']}",
        headers=emp_headers,
        json={"role_ids": [custom_role["role_id"]]}
    )
    assert emp_self.status_code == 403


def test_human_readable_role_names(client):
    sa = _create_super_admin(client)
    org = _create_test_org(client, sa["token"])
    headers = {"Authorization": f"Bearer {org['token']}"}

    # 1. Normal human-readable name with spaces
    res1 = client.post("/api/v1/users/roles", headers=headers, json={
        "name": "Backend Development",
        "description": "Backend services and queue management",
        "permissions": ["organization:messages:read", "organization:messages:create"]
    })
    assert res1.status_code == 201, res1.get_data(as_text=True)
    assert res1.get_json()["data"]["name"] == "Backend Development"

    # 2. Allowed special characters: hyphens and ampersands
    res2 = client.post("/api/v1/users/roles", headers=headers, json={
        "name": "Marketing & Communications - Level 1",
        "permissions": ["organization:templates:read"]
    })
    assert res2.status_code == 201
    assert res2.get_json()["data"]["name"] == "Marketing & Communications - Level 1"

    # 3. Repeated spaces should be trimmed and collapsed
    res3 = client.post("/api/v1/users/roles", headers=headers, json={
        "name": "   Quality   Assurance   Tester   ",
        "permissions": ["organization:messages:read"]
    })
    assert res3.status_code == 201
    assert res3.get_json()["data"]["name"] == "Quality Assurance Tester"

    # 4. Case-insensitive duplicate name within the same organization must be rejected
    dup_res = client.post("/api/v1/users/roles", headers=headers, json={
        "name": "backend development",  # Lowercase version of "Backend Development"
        "permissions": ["organization:messages:read"]
    })
    assert dup_res.status_code == 409
    assert "already exists in this organization" in dup_res.get_json()["message"]

    # 5. Invalid characters rejected
    inv_res = client.post("/api/v1/users/roles", headers=headers, json={
        "name": "Hacker <script>alert(1)</script>",
        "permissions": ["organization:messages:read"]
    })
    assert inv_res.status_code == 400


def test_organization_deletion_soft_delete_and_cascade(client):
    sa = _create_super_admin(client)
    org = _create_test_org(client, sa["token"])
    sa_headers = {"Authorization": f"Bearer {sa['token']}"}

    org_id = org["organization_id"]
    org_slug = org["slug"]

    # 1. Get deletion summary
    sum_res = client.get(f"/api/v1/organizations/{org_id}/deletion-summary", headers=sa_headers)
    assert sum_res.status_code == 200, sum_res.get_data(as_text=True)
    summary = sum_res.get_json()["data"]
    assert summary["slug"] == org_slug
    assert summary["users_count"] >= 1

    # 2. Deletion without confirm_slug must be rejected
    del_fail1 = client.post(f"/api/v1/organizations/{org_id}/delete", headers=sa_headers, json={})
    assert del_fail1.status_code == 400

    # 3. Deletion with incorrect confirm_slug must be rejected
    del_fail2 = client.post(f"/api/v1/organizations/{org_id}/delete", headers=sa_headers, json={
        "confirm_slug": "wrong-slug"
    })
    assert del_fail2.status_code == 400

    # 4. Deletion with correct confirm_slug succeeds
    del_ok = client.post(f"/api/v1/organizations/{org_id}/delete", headers=sa_headers, json={
        "confirm_slug": org_slug
    })
    assert del_ok.status_code == 200
    assert del_ok.get_json()["data"]["status"] == "DELETED"

    # 5. Verify database state
    org_doc = OrganizationRepository.find_by_id(org_id)
    assert org_doc["status"] == "DELETED"
    assert org_doc.get("deleted_at") is not None

    admin_doc = UserRepository.find_by_id(org["admin_id"])
    assert admin_doc["is_active"] is False

    # 6. Verify deleted organization users CANNOT log in!
    login_res = client.post("/api/v1/auth/login", json={
        "email": org["admin_email"],
        "password": org["admin_password"]
    })
    assert login_res.status_code in (401, 403)
    assert "inactive or unavailable" in login_res.get_json()["message"]

    # 7. Organization listing: default excludes DELETED, filter with status=DELETED returns it
    default_list = client.get("/api/v1/organizations/", headers=sa_headers)
    assert default_list.status_code == 200
    assert not any(o["organization_id"] == org_id for o in default_list.get_json()["data"])

    deleted_list = client.get("/api/v1/organizations/?status=DELETED", headers=sa_headers)
    assert deleted_list.status_code == 200
    assert any(o["organization_id"] == org_id for o in deleted_list.get_json()["data"])
