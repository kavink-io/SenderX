"""
SenderX Authentication & RBAC Test Suite
"""

import uuid
import pytest
import bcrypt

from app import create_app
from app.modules.auth.service import AuthService
from app.modules.auth.repository import AuthRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.service import OrganizationService
from app.modules.users.repository import UserRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


def test_platform_admin_login_success(app):
    with app.app_context():
        email = f"admin-{uuid.uuid4().hex[:6]}@senderx.io"
        password = "SecureAdminPassword123!"
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")

        admin_data = {
            "admin_id": str(uuid.uuid4()),
            "email": email,
            "password_hash": password_hash,
            "role": "SUPER_ADMIN",
            "is_active": True
        }
        AuthRepository.create_admin(admin_data)

        try:
            res = AuthService.login(email, password)
            assert res["success"] is True
            assert res["data"]["account"]["account_type"] == "PLATFORM_ADMIN"
            assert "access_token" in res["data"]
            assert "refresh_token" in res["data"]
        finally:
            AuthRepository._collection().delete_one({"email": email})


def test_login_invalid_credentials(app):
    with app.app_context():
        res = AuthService.login("nonexistent@senderx.io", "WrongPassword123!")
        assert res["success"] is False
        assert "invalid" in res["message"].lower()


def test_inactive_organization_user_blocked(app):
    with app.app_context():
        org_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        email = f"user-{uuid.uuid4().hex[:6]}@testorg.com"
        password = "UserPassword123!"
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")

        # Inactive org
        OrganizationRepository.create({
            "organization_id": org_id,
            "name": "Inactive Org",
            "slug": f"inactive-org-{uuid.uuid4().hex[:6]}",
            "status": "INACTIVE"
        })

        UserRepository.create({
            "user_id": user_id,
            "organization_id": org_id,
            "name": "Inactive Org User",
            "email": email,
            "password_hash": password_hash,
            "is_active": True
        })

        try:
            res = AuthService.login(email, password)
            assert res["success"] is False
            assert "inactive" in res["message"].lower() or "unavailable" in res["message"].lower()
        finally:
            OrganizationRepository._collection().delete_one({"organization_id": org_id})
            UserRepository._collection().delete_one({"user_id": user_id})
