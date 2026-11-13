"""
SenderX Phase 3, Task 2: Email Template Management and Engine Test Suite
Tests for:
- Template CRUD operations
- Tenant isolation and name collision checks
- RBAC permissions (organization:templates:read vs organization:templates:manage)
- Sandboxed Jinja2 rendering and SSTI security prevention
- Variable validation and live preview generation
- Version management (snapshot preservation, version bump on ACTIVE edits)
- Duplication and archiving workflows
- Message Engine integration with template resolution, validation, and audit snapshots
- Backward compatibility for messages without templates
"""

import uuid
import pytest
import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.templates.service import TemplateService
from app.modules.templates.repository import TemplateRepository
from app.modules.messages.service import MessageService
from app.modules.messages.repository import MessageRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def test_setup(app):
    """
    Sets up two isolated organizations: Org A and Org B,
    along with roles for manage vs read-only permissions and users.
    """
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())

        role_admin_a = str(uuid.uuid4())
        role_readonly_a = str(uuid.uuid4())
        role_admin_b = str(uuid.uuid4())

        user_admin_a = str(uuid.uuid4())
        user_readonly_a = str(uuid.uuid4())
        user_admin_b = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Create Org A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Template Org A {suffix}",
            "slug": f"tmpl-org-a-{suffix}",
            "status": "ACTIVE"
        })

        # Role with manage permissions
        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a,
            "name": "Template Manager A",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:templates:read",
                "organization:templates:manage",
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage"
            ],
            "is_system_role": False
        })

        # Role with read-only permissions
        RoleRepository.create({
            "role_id": role_readonly_a,
            "organization_id": org_a,
            "name": "Template Viewer A",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:templates:read"
            ],
            "is_system_role": False
        })

        UserRepository.create({
            "user_id": user_admin_a,
            "organization_id": org_a,
            "name": "Admin User A",
            "email": f"admin-a-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_a],
            "is_active": True
        })

        UserRepository.create({
            "user_id": user_readonly_a,
            "organization_id": org_a,
            "name": "Readonly User A",
            "email": f"readonly-a-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_readonly_a],
            "is_active": True
        })

        # Create Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Template Org B {suffix}",
            "slug": f"tmpl-org-b-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b,
            "name": "Template Manager B",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:templates:read",
                "organization:templates:manage",
                "organization:messages:create",
                "organization:messages:read"
            ],
            "is_system_role": False
        })

        UserRepository.create({
            "user_id": user_admin_b,
            "organization_id": org_b,
            "name": "Admin User B",
            "email": f"admin-b-{suffix}@test.io",
            "password_hash": password_hash,
            "role_ids": [role_admin_b],
            "is_active": True
        })

        # Generate JWT tokens
        token_admin_a = create_access_token(
            identity=user_admin_a,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a}
        )
        token_readonly_a = create_access_token(
            identity=user_readonly_a,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a}
        )
        token_admin_b = create_access_token(
            identity=user_admin_b,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b}
        )

        return {
            "org_a": org_a,
            "org_b": org_b,
            "token_admin_a": token_admin_a,
            "token_readonly_a": token_readonly_a,
            "token_admin_b": token_admin_b,
            "suffix": suffix
        }


# ===========================================================================
# 1. TEMPLATE CRUD & VALIDATION
# ===========================================================================

def test_template_create_and_get(client, test_setup):
    token = test_setup["token_admin_a"]

    payload = {
        "name": "Welcome Onboarding",
        "description": "Standard onboarding email for new users",
        "category": "transactional",
        "subject": "Welcome to {{ company_name }}, {{ user_name }}!",
        "header": "<header><h2>{{ company_name }}</h2></header>",
        "html_body": "<p>Hello {{ user_name }},</p><p>Your account is ready. Your verification code is <strong>{{ code }}</strong>.</p>",
        "plain_text_body": "Hello {{ user_name }},\nYour account is ready. Your verification code is {{ code }}.",
        "footer": "<footer>Sent by {{ company_name }} Support</footer>",
        "variables": [
            {"name": "company_name", "required": False, "default": "SenderX", "sample_value": "Acme Corp"},
            {"name": "user_name", "required": True, "sample_value": "Alice"},
            {"name": "code", "required": True, "sample_value": "987654"}
        ]
    }

    # 1. Create template
    res = client.post("/api/v1/templates/", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    body = res.get_json()
    assert body["success"] is True
    data = body["data"]
    template_id = data["template_id"]
    assert template_id.startswith("tmpl-")
    assert data["version"] == 1
    assert data["status"] == "DRAFT"
    assert data["name"] == "Welcome Onboarding"
    assert len(data["variables"]) == 3

    # 2. Get template by ID
    get_res = client.get(f"/api/v1/templates/{template_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    get_body = get_res.get_json()
    assert get_body["success"] is True
    assert get_body["data"]["template_id"] == template_id
    assert get_body["data"]["subject"] == payload["subject"]


def test_template_name_uniqueness_within_org_and_cross_org(client, test_setup):
    token_a = test_setup["token_admin_a"]
    token_b = test_setup["token_admin_b"]

    payload = {
        "name": f"Unique Name {test_setup['suffix']}",
        "subject": "Test Subject",
        "html_body": "<p>Body</p>",
        "plain_text_body": "Body"
    }

    # 1. Create in Org A
    res_a = client.post("/api/v1/templates/", json=payload, headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 201

    # 2. Duplicate in Org A should fail with 409 Conflict
    res_a_dup = client.post("/api/v1/templates/", json=payload, headers={"Authorization": f"Bearer {token_a}"})
    assert res_a_dup.status_code == 409
    assert "already exists" in res_a_dup.get_json()["message"]

    # 3. Same name in Org B should SUCCEED (tenant isolation)
    res_b = client.post("/api/v1/templates/", json=payload, headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 201


def test_template_validation_errors(client, test_setup):
    token = test_setup["token_admin_a"]

    # Missing name
    res = client.post("/api/v1/templates/", json={"subject": "No Name"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400

    # Blank subject
    res = client.post("/api/v1/templates/", json={"name": "Blank Subject", "subject": "   "}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400

    # Invalid variable name (starts with digit or has dash)
    res = client.post("/api/v1/templates/", json={
        "name": "Invalid Var Name",
        "subject": "Subject",
        "variables": [{"name": "123-bad-var"}]
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400


# ===========================================================================
# 2. SSTI SECURITY & SANDBOXED RENDERING
# ===========================================================================

def test_ssti_security_prevention(client, test_setup):
    """
    Verify SandboxedEnvironment strictly blocks SSTI attacks:
    - __class__.__mro__
    - __builtins__
    - os.system
    """
    token = test_setup["token_admin_a"]

    # 1. Attempt to inject class navigation exploit in subject
    res1 = client.post("/api/v1/templates/", json={
        "name": "SSTI Exploit Subject",
        "subject": "{{ ''.__class__.__mro__[1].__subclasses__() }}",
        "html_body": "test"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 400
    assert "Unsafe expression" in res1.get_json()["message"] or "Security" in res1.get_json()["message"]

    # 2. Attempt to inject __builtins__ in HTML body
    res2 = client.post("/api/v1/templates/", json={
        "name": "SSTI Exploit Body",
        "subject": "Valid Subject",
        "html_body": "<p>{{ self.__init__.__globals__.__builtins__.__import__('os').system('id') }}</p>"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 400
    assert "Unsafe expression" in res2.get_json()["message"] or "Security" in res2.get_json()["message"]

    # 3. Jinja2 syntax error (unclosed block)
    res3 = client.post("/api/v1/templates/", json={
        "name": "Syntax Error Template",
        "subject": "Valid Subject",
        "html_body": "<p>{% if user_active %}Hello{% endif </p>"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res3.status_code == 400
    assert "Syntax error" in res3.get_json()["message"] or "syntax" in res3.get_json()["message"].lower()


# ===========================================================================
# 3. RBAC PERMISSIONS & TENANT ISOLATION
# ===========================================================================

def test_rbac_permissions(client, test_setup):
    token_readonly = test_setup["token_readonly_a"]

    # Read-only user can list templates
    list_res = client.get("/api/v1/templates/", headers={"Authorization": f"Bearer {token_readonly}"})
    assert list_res.status_code == 200

    # Read-only user CANNOT create a template (requires organization:templates:manage)
    create_res = client.post("/api/v1/templates/", json={
        "name": "Unauthorized Create",
        "subject": "Test"
    }, headers={"Authorization": f"Bearer {token_readonly}"})
    assert create_res.status_code == 403

    # Unauthenticated request rejected
    unauth_res = client.get("/api/v1/templates/")
    assert unauth_res.status_code == 401


def test_tenant_isolation(client, test_setup):
    token_a = test_setup["token_admin_a"]
    token_b = test_setup["token_admin_b"]

    # Org A creates a template
    res = client.post("/api/v1/templates/", json={
        "name": f"Org A Secret Template {uuid.uuid4().hex[:4]}",
        "subject": "Secret Subject",
        "html_body": "<p>Confidential Org A</p>"
    }, headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 201
    tmpl_id = res.get_json()["data"]["template_id"]

    # Org B attempts to read Org A's template -> 404
    get_res = client.get(f"/api/v1/templates/{tmpl_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert get_res.status_code == 404

    # Org B attempts to update Org A's template -> 404
    put_res = client.put(f"/api/v1/templates/{tmpl_id}", json={"name": "Hacked"}, headers={"Authorization": f"Bearer {token_b}"})
    assert put_res.status_code == 404

    # Org B attempts to preview Org A's template -> 404
    prev_res = client.post(f"/api/v1/templates/{tmpl_id}/preview", json={}, headers={"Authorization": f"Bearer {token_b}"})
    assert prev_res.status_code == 404

    # Org B attempts to delete Org A's template -> 404
    del_res = client.delete(f"/api/v1/templates/{tmpl_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert del_res.status_code == 404


# ===========================================================================
# 4. LIVE PREVIEW & VARIABLE HANDLING
# ===========================================================================

def test_live_preview_and_missing_variables(client, test_setup):
    token = test_setup["token_admin_a"]

    # Create template with required and default variables
    res = client.post("/api/v1/templates/", json={
        "name": f"Preview Test Template {uuid.uuid4().hex[:4]}",
        "subject": "Invoice for {{ client_name }}",
        "header": "=== INVOICE ===",
        "html_body": "<p>Amount: ${{ amount }}</p><p>Status: {{ status }}</p>",
        "plain_text_body": "Amount: ${{ amount }}\nStatus: {{ status }}",
        "footer": "Thank you for your business!",
        "variables": [
            {"name": "client_name", "required": True, "sample_value": "Global Corp"},
            {"name": "amount", "required": True, "sample_value": 1500},
            {"name": "status", "required": False, "default": "PAID"}
        ]
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    tmpl_id = res.get_json()["data"]["template_id"]

    # 1. Preview with complete sample data
    preview_res = client.post(f"/api/v1/templates/{tmpl_id}/preview", json={
        "sample_data": {
            "client_name": "Acme Industries",
            "amount": 2500,
            "status": "PENDING"
        }
    }, headers={"Authorization": f"Bearer {token}"})
    assert preview_res.status_code == 200
    pdata = preview_res.get_json()["data"]
    assert pdata["rendered_subject"] == "Invoice for Acme Industries"
    assert "$2500" in pdata["rendered_html"]
    assert "PENDING" in pdata["rendered_plain_text"]
    assert "=== INVOICE ===" in pdata["rendered_html"]
    assert len(pdata["missing_variables"]) == 0

    # 2. Preview with missing required variable (e.g. client_name missing from sample_data and sample_value omitted)
    # If sample_data is empty, sample_values from template definition are used
    preview_res2 = client.post(f"/api/v1/templates/{tmpl_id}/preview", json={"sample_data": {}}, headers={"Authorization": f"Bearer {token}"})
    assert preview_res2.status_code == 200
    pdata2 = preview_res2.get_json()["data"]
    assert pdata2["rendered_subject"] == "Invoice for Global Corp"


# ===========================================================================
# 5. VERSIONING, PUBLISHING, ARCHIVING & DUPLICATION
# ===========================================================================

def test_template_version_bump_on_active_edit(client, test_setup):
    token = test_setup["token_admin_a"]

    # 1. Create template (status: DRAFT, v1)
    res = client.post("/api/v1/templates/", json={
        "name": f"Versioned Template {uuid.uuid4().hex[:4]}",
        "subject": "Initial Subject v1",
        "html_body": "<p>Initial Body v1</p>",
        "plain_text_body": "Initial Body v1"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    tmpl_id = res.get_json()["data"]["template_id"]
    assert res.get_json()["data"]["version"] == 1
    assert res.get_json()["data"]["status"] == "DRAFT"

    # 2. Edit while DRAFT: version should remain 1
    upd_draft = client.put(f"/api/v1/templates/{tmpl_id}", json={
        "subject": "Draft Modified Subject"
    }, headers={"Authorization": f"Bearer {token}"})
    assert upd_draft.status_code == 200
    assert upd_draft.get_json()["data"]["version"] == 1

    # 3. Publish template -> transitions to ACTIVE
    pub_res = client.post(f"/api/v1/templates/{tmpl_id}/publish", headers={"Authorization": f"Bearer {token}"})
    assert pub_res.status_code == 200
    assert pub_res.get_json()["data"]["status"] == "ACTIVE"
    assert pub_res.get_json()["data"]["version"] == 1

    # 4. Update ACTIVE template content -> archives v1 and bumps to v2
    upd_active = client.put(f"/api/v1/templates/{tmpl_id}", json={
        "subject": "Published Updated Subject v2",
        "html_body": "<p>Updated Body v2</p>"
    }, headers={"Authorization": f"Bearer {token}"})
    assert upd_active.status_code == 200
    upd_body = upd_active.get_json()
    assert upd_body["version_incremented"] is True
    assert upd_body["data"]["version"] == 2
    assert upd_body["data"]["subject"] == "Published Updated Subject v2"

    # 5. Verify version history endpoint lists v1 (archived) and v2 (current)
    history_res = client.get(f"/api/v1/templates/{tmpl_id}/versions", headers={"Authorization": f"Bearer {token}"})
    assert history_res.status_code == 200
    hist = history_res.get_json()
    assert hist["total_versions"] == 2
    assert hist["current_version"] == 2

    # 6. Retrieve specific historical version v1
    v1_res = client.get(f"/api/v1/templates/{tmpl_id}/versions/1", headers={"Authorization": f"Bearer {token}"})
    assert v1_res.status_code == 200
    assert v1_res.get_json()["data"]["subject"] == "Draft Modified Subject"

    # 7. Duplicate template
    dup_res = client.post(f"/api/v1/templates/{tmpl_id}/duplicate", headers={"Authorization": f"Bearer {token}"})
    assert dup_res.status_code == 201
    dup_data = dup_res.get_json()["data"]
    assert dup_data["status"] == "DRAFT"
    assert dup_data["version"] == 1
    assert "Copy of" in dup_data["name"]

    # 8. Archive template
    arch_res = client.post(f"/api/v1/templates/{tmpl_id}/archive", headers={"Authorization": f"Bearer {token}"})
    assert arch_res.status_code == 200
    assert arch_res.get_json()["data"]["status"] == "ARCHIVED"


# ===========================================================================
# 6. MESSAGE ENGINE INTEGRATION WITH TEMPLATES
# ===========================================================================

def test_message_creation_with_template(client, test_setup, app):
    token = test_setup["token_admin_a"]
    org_a = test_setup["org_a"]

    with app.app_context():
        # 1. Create and publish a production email template
        t_res = client.post("/api/v1/templates/", json={
            "name": f"Password Reset Template {uuid.uuid4().hex[:4]}",
            "subject": "Reset your password for {{ service_name }}",
            "html_body": "<h2>Hi {{ user_name }},</h2><p>Click <a href='{{ reset_url }}'>here</a> to reset your password.</p>",
            "plain_text_body": "Hi {{ user_name }},\nReset your password: {{ reset_url }}",
            "variables": [
                {"name": "user_name", "required": True},
                {"name": "reset_url", "required": True},
                {"name": "service_name", "required": False, "default": "SenderX Auth"}
            ]
        }, headers={"Authorization": f"Bearer {token}"})
        assert t_res.status_code == 201
        tmpl_id = t_res.get_json()["data"]["template_id"]

        # If template is still DRAFT, message creation must fail
        msg_draft_fail = client.post("/api/v1/messages/", json={
            "channel": "email",
            "recipient": "kavin@example.com",
            "template_id": tmpl_id,
            "template_variables": {"user_name": "Kavin", "reset_url": "https://sx.io/reset/123"}
        }, headers={"Authorization": f"Bearer {token}"})
        assert msg_draft_fail.status_code == 400
        assert "not in ACTIVE status" in msg_draft_fail.get_json()["message"]

        # Publish template
        client.post(f"/api/v1/templates/{tmpl_id}/publish", headers={"Authorization": f"Bearer {token}"})

        # Missing required variable must fail
        msg_missing_var = client.post("/api/v1/messages/", json={
            "channel": "email",
            "recipient": "kavin@example.com",
            "template_id": tmpl_id,
            "template_variables": {"user_name": "Kavin"}  # missing reset_url
        }, headers={"Authorization": f"Bearer {token}"})
        assert msg_missing_var.status_code == 400
        assert "Missing required template variables" in msg_missing_var.get_json()["message"]

        # Cross-tenant template usage must fail
        token_b = test_setup["token_admin_b"]
        msg_cross_tenant = client.post("/api/v1/messages/", json={
            "channel": "email",
            "recipient": "kavin@example.com",
            "template_id": tmpl_id,
            "template_variables": {"user_name": "Kavin", "reset_url": "https://sx.io/reset/123"}
        }, headers={"Authorization": f"Bearer {token_b}"})
        assert msg_cross_tenant.status_code == 400
        assert "not found or belongs to another organization" in msg_cross_tenant.get_json()["message"]

        # Successful message creation with template
        msg_success = client.post("/api/v1/messages/", json={
            "channel": "email",
            "recipient": "kavin@example.com",
            "template_id": tmpl_id,
            "template_variables": {
                "user_name": "Kavin Vijay",
                "reset_url": "https://sx.io/reset/token456"
            }
        }, headers={"Authorization": f"Bearer {token}"})
        assert msg_success.status_code == 201
        m_body = msg_success.get_json()["data"]
        msg_doc = m_body["message"]

        # Verify rendered content injected into data
        assert msg_doc["data"]["subject"] == "Reset your password for SenderX Auth"
        assert "Hi Kavin Vijay," in msg_doc["data"]["html"]
        assert "https://sx.io/reset/token456" in msg_doc["data"]["body"]

        # Verify audit snapshot preserved in message
        assert msg_doc["template_id"] == tmpl_id
        assert msg_doc["template_version"] == 1
        assert msg_doc["template_snapshot"]["subject"] == "Reset your password for SenderX Auth"

        # Cleanup test message
        MessageRepository._collection().delete_one({"message_id": msg_doc["message_id"]})


def test_backward_compatibility_without_template(client, test_setup, app):
    """
    Ensure existing messages without templates continue working 100% identically.
    """
    token = test_setup["token_admin_a"]

    with app.app_context():
        msg_res = client.post("/api/v1/messages/", json={
            "channel": "email",
            "recipient": "standard@example.com",
            "provider": "mock",
            "data": {
                "subject": "Direct Message",
                "message": "Testing backward compatibility"
            }
        }, headers={"Authorization": f"Bearer {token}"})
        assert msg_res.status_code == 201
        msg_data = msg_res.get_json()["data"]["message"]
        assert msg_data["data"]["subject"] == "Direct Message"
        assert msg_data.get("template_id") is None

        MessageRepository._collection().delete_one({"message_id": msg_data["message_id"]})
