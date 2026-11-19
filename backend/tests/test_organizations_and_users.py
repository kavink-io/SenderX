"""
SenderX Organizations, Users & Roles Test Suite
"""

import uuid
import pytest

from app import create_app
from app.modules.organizations.service import OrganizationService
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.service import UserService
from app.modules.users.repository import UserRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


def test_create_organization_and_auto_org_admin(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        slug = f"org-test-{suffix}"
        admin_email = f"orgadmin-{suffix}@test.io"

        data = {
            "name": f"Test Organization {suffix}",
            "slug": slug,
            "admin_name": "Org Admin User",
            "admin_email": admin_email,
            "admin_password": "OrgAdminSecretPassword123!"
        }

        res = OrganizationService.create_organization(data, created_by="super-admin-id")
        assert res["success"] is True
        org_id = res["data"]["organization_id"]

        try:
            # 1. Verify organization exists and is ACTIVE
            org = OrganizationRepository.find_by_id(org_id)
            assert org is not None
            assert org["slug"] == slug
            assert org["status"] == "ACTIVE"

            # 2. Verify ORG_ADMIN role was automatically created
            roles = RoleRepository.find_by_organization(org_id)
            assert len(roles) >= 1
            org_admin_role = next((r for r in roles if r["name"] == "ORG_ADMIN"), None)
            assert org_admin_role is not None
            assert org_admin_role["is_system_role"] is True
            assert "organization:users:manage" in org_admin_role["permissions"]

            # 3. Verify user was created with ORG_ADMIN role
            user = UserRepository.find_by_email(admin_email)
            assert user is not None
            assert user["organization_id"] == org_id
            assert org_admin_role["role_id"] in user["role_ids"]

            # 4. Verify duplicate slug rejected
            dup_res = OrganizationService.create_organization(data, created_by="super-admin-id")
            assert dup_res["success"] is False
            assert "already exists" in dup_res["message"].lower()

            # 5. Create additional organization user
            user_data = {
                "name": "Staff Member",
                "email": f"staff-{suffix}@test.io",
                "password": "StaffMemberPassword123!",
                "employee_code": f"EMP-{suffix.upper()}",
                "role_ids": [org_admin_role["role_id"]]
            }
            new_user_res = UserService.create_user(user_data, organization_id=org_id)
            assert new_user_res["success"] is True

            # 6. Create custom role with allowed permissions
            role_data = {
                "name": "Support Staff",
                "permissions": ["organization:messages:read", "organization:dead_letters:read"]
            }
            custom_role_res = UserService.create_role(role_data, organization_id=org_id)
            assert custom_role_res["success"] is True
            assert custom_role_res["data"]["is_system_role"] is False

            # 7. Reject wildcard permissions (privilege escalation prevention)
            wildcard_role_data = {
                "name": "Super Hacker",
                "permissions": ["*"]
            }
            wild_res = UserService.create_role(wildcard_role_data, organization_id=org_id)
            assert wild_res["success"] is False
            assert "wildcard" in wild_res["message"].lower()

        finally:
            OrganizationRepository._collection().delete_one({"organization_id": org_id})
            UserRepository._collection().delete_many({"organization_id": org_id})
            RoleRepository._collection().delete_many({"organization_id": org_id})
