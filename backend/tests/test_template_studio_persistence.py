import uuid
import pytest
import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.templates.repository import TemplateRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def studio_setup(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())
        role_a = str(uuid.uuid4())
        role_ro_a = str(uuid.uuid4())
        role_b = str(uuid.uuid4())
        user_a = str(uuid.uuid4())
        user_ro_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())

        pwd_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Studio Test Org A {suffix}",
            "slug": f"studio-org-a-{suffix}",
            "status": "ACTIVE",
        })
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Studio Test Org B {suffix}",
            "slug": f"studio-org-b-{suffix}",
            "status": "ACTIVE",
        })

        admin_perms = [
            "organization:templates:create",
            "organization:templates:read",
            "organization:templates:manage",
            "organization:messages:create",
            "organization:messages:read",
        ]
        RoleRepository.create({
            "role_id": role_a,
            "organization_id": org_a,
            "name": "Studio Admin A",
            "scope": "ORGANIZATION",
            "permissions": admin_perms,
            "is_system_role": False,
        })
        RoleRepository.create({
            "role_id": role_ro_a,
            "organization_id": org_a,
            "name": "Studio ReadOnly A",
            "scope": "ORGANIZATION",
            "permissions": ["organization:templates:read"],
            "is_system_role": False,
        })
        RoleRepository.create({
            "role_id": role_b,
            "organization_id": org_b,
            "name": "Studio Admin B",
            "scope": "ORGANIZATION",
            "permissions": admin_perms,
            "is_system_role": False,
        })

        UserRepository.create({
            "user_id": user_a,
            "organization_id": org_a,
            "name": "Studio User A",
            "email": f"studio-a-{suffix}@test.io",
            "password_hash": pwd_hash,
            "role_ids": [role_a],
            "is_active": True,
        })
        UserRepository.create({
            "user_id": user_ro_a,
            "organization_id": org_a,
            "name": "Studio Reader A",
            "email": f"studio-ro-a-{suffix}@test.io",
            "password_hash": pwd_hash,
            "role_ids": [role_ro_a],
            "is_active": True,
        })
        UserRepository.create({
            "user_id": user_b,
            "organization_id": org_b,
            "name": "Studio User B",
            "email": f"studio-b-{suffix}@test.io",
            "password_hash": pwd_hash,
            "role_ids": [role_b],
            "is_active": True,
        })

        token_a = create_access_token(
            identity=user_a,
            additional_claims={
                "organization_id": org_a,
                "account_type": "ORGANIZATION_USER",
                "permissions": admin_perms,
            },
        )
        token_ro_a = create_access_token(
            identity=user_ro_a,
            additional_claims={
                "organization_id": org_a,
                "account_type": "ORGANIZATION_USER",
                "permissions": ["organization:templates:read"],
            },
        )
        token_b = create_access_token(
            identity=user_b,
            additional_claims={
                "organization_id": org_b,
                "account_type": "ORGANIZATION_USER",
                "permissions": admin_perms,
            },
        )

        return {
            "org_a": org_a,
            "org_b": org_b,
            "token_a": token_a,
            "token_ro_a": token_ro_a,
            "token_b": token_b,
            "suffix": suffix,
        }


def test_1_create_draft_with_studio_variables_and_css(client, app, studio_setup):
    """1, 6, 7. Create a DRAFT template with Studio dynamic variables, HTML, CSS, and retrieve it."""
    token = studio_setup["token_a"]
    org_a = studio_setup["org_a"]

    payload = {
        "name": f"Welcome Onboarding {uuid.uuid4().hex[:6]}",
        "description": "Onboarding email from Studio",
        "subject": "Welcome to {{ company }}, {{ name }}!",
        "category": "marketing",
        "channel": "email",
        "html_body": "<div class='card'><h1>Hello {{ name }}</h1><p>Email: {{ email }}</p><a href='{{ activation_link }}'>Verify</a></div>",
        "css": ".card { padding: 24px; background-color: #ffffff; }",
        "variables": [
            {"name": "company", "type": "text", "required": True},
            {"name": "name", "type": "text", "required": True},
            {"name": "email", "type": "text", "required": False},
            {"name": "activation_link", "type": "url", "required": True},
        ],
        "status": "DRAFT",
    }

    res = client.post("/api/v1/templates/", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["success"] is True
    created = body["data"]
    tid = created["template_id"]
    assert tid.startswith("tmpl-")
    assert created["status"] == "DRAFT"
    assert created["organization_id"] == org_a
    assert created["category"] == "marketing"
    assert created["html_body"] == payload["html_body"]
    assert created["css"] == payload["css"]
    assert len(created["variables"]) == 4

    # Verify list endpoint returns both data.items and top-level items
    list_res = client.get("/api/v1/templates/?page=1&limit=20", headers={"Authorization": f"Bearer {token}"})
    assert list_res.status_code == 200
    list_json = list_res.get_json()
    assert list_json["success"] is True
    assert any(t["template_id"] == tid for t in list_json["data"]["items"])
    assert any(t["template_id"] == tid for t in list_json["items"])

    # Verify get by id retrieves persisted HTML, CSS, subject, category, variables
    get_res = client.get(f"/api/v1/templates/{tid}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    fetched = get_res.get_json()["data"]
    assert fetched["html_body"] == payload["html_body"]
    assert fetched["css"] == payload["css"]
    assert fetched["subject"] == payload["subject"]
    assert fetched["category"] == "marketing"
    assert fetched["status"] == "DRAFT"


def test_2_update_existing_draft_without_duplication(client, app, studio_setup):
    """2, 7. Updating an existing draft updates it in-place in DB without creating duplicates."""
    token = studio_setup["token_a"]
    org_a = studio_setup["org_a"]
    tmpl_name = f"Editable Draft {uuid.uuid4().hex[:6]}"

    create_res = client.post(
        "/api/v1/templates/",
        json={
            "name": tmpl_name,
            "subject": "Initial Subject {{ name }}",
            "category": "transactional",
            "html_body": "<p>Initial draft for {{ name }}</p>",
            "css": "p { color: #333333; }",
            "variables": [{"name": "name", "type": "text", "required": True}],
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 201
    tid = create_res.get_json()["data"]["template_id"]

    # Update via PUT using Studio payload (including html_content/css_content remap check)
    upd_res = client.put(
        f"/api/v1/templates/{tid}",
        json={
            "name": tmpl_name,
            "subject": "Updated Subject {{ name }} at {{ company }}",
            "category": "system",
            "html_content": "<div class='wrap'><p>Updated draft for {{ name }} ({{ company }})</p></div>",
            "css_content": ".wrap { background-color: #f8fafc; }",
            "variables": [
                {"name": "name", "type": "text", "required": True},
                {"name": "company", "type": "text", "required": True},
            ],
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upd_res.status_code == 200, upd_res.get_json()
    updated = upd_res.get_json()["data"]
    assert updated["template_id"] == tid
    assert updated["status"] == "DRAFT"
    assert updated["category"] == "system"
    assert updated["subject"] == "Updated Subject {{ name }} at {{ company }}"
    assert "Updated draft for {{ name }}" in updated["html_body"]
    assert updated["css"] == ".wrap { background-color: #f8fafc; }"

    with app.app_context():
        count = TemplateRepository._collection().count_documents({
            "organization_id": org_a,
            "name": tmpl_name,
            "status": {"$ne": "DELETED"},
        })
        assert count == 1


def test_3_save_and_publish_valid_template_and_dispatch_workflow(client, studio_setup):
    """3. Save & Publish persists status=PUBLISHED, publication metadata, and works in email dispatch."""
    token = studio_setup["token_a"]

    # Case A: Direct create with status=PUBLISHED (Save & Publish on new template)
    pub_name = f"Direct Published {uuid.uuid4().hex[:6]}"
    create_pub_res = client.post(
        "/api/v1/templates/",
        json={
            "name": pub_name,
            "subject": "Activate {{ company }} account",
            "category": "transactional",
            "html_body": "<div class='box'><p>Hi {{ name }}, click <a href='{{ activation_link }}'>here</a>.</p></div>",
            "css": ".box { padding: 20px; }",
            "variables": [
                {"name": "company", "type": "text", "required": True},
                {"name": "name", "type": "text", "required": True},
                {"name": "activation_link", "type": "url", "required": True},
            ],
            "status": "PUBLISHED",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_pub_res.status_code == 201, create_pub_res.get_json()
    pub_doc = create_pub_res.get_json()["data"]
    tid = pub_doc["template_id"]
    assert pub_doc["status"] == "PUBLISHED"
    assert pub_doc.get("published_at") is not None
    assert pub_doc.get("published_by") is not None

    # Filter list by status=PUBLISHED
    list_pub = client.get("/api/v1/templates/?status=PUBLISHED", headers={"Authorization": f"Bearer {token}"})
    assert list_pub.status_code == 200
    assert any(t["template_id"] == tid for t in list_pub.get_json()["data"]["items"])

    # Verify available to existing email-sending workflow (MessageService.create_message via /messages/)
    msg_res = client.post(
        "/api/v1/messages/",
        json={
            "channel": "email",
            "recipient": "customer@example.com",
            "template_id": tid,
            "template_variables": {
                "company": "Acme Corp",
                "name": "Alex",
                "activation_link": "https://example.com/activate",
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert msg_res.status_code in (200, 201), msg_res.get_json()
    msg_data = msg_res.get_json()["data"]["message"]
    assert msg_data["data"]["subject"] == "Activate Acme Corp account"
    assert "Hi Alex" in msg_data["data"]["html"]

    # Case B: Draft -> Edit -> Publish via POST /publish with status=PUBLISHED
    draft_res = client.post(
        "/api/v1/templates/",
        json={
            "name": f"Draft Then Publish {uuid.uuid4().hex[:6]}",
            "subject": "Welcome {{ name }}",
            "html_body": "<p>Hello {{ name }}</p>",
            "variables": [{"name": "name", "type": "text", "required": True}],
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    draft_tid = draft_res.get_json()["data"]["template_id"]
    post_pub = client.post(
        f"/api/v1/templates/{draft_tid}/publish",
        json={"status": "PUBLISHED"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert post_pub.status_code == 200
    assert post_pub.get_json()["data"]["status"] == "PUBLISHED"
    assert post_pub.get_json()["data"].get("published_at") is not None


def test_4_and_5_reject_invalid_templates_and_missing_fields(client, studio_setup):
    """4, 5. Reject XSS/dangerous markup, CSS expression(), syntax errors, and missing name or subject."""
    token = studio_setup["token_a"]

    # Missing template name
    no_name = client.post(
        "/api/v1/templates/",
        json={"subject": "Valid Subject", "html_body": "<p>Hello</p>"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert no_name.status_code == 400
    assert no_name.get_json()["success"] is False

    # Missing subject for email template
    no_subj = client.post(
        "/api/v1/templates/",
        json={"name": "Missing Subject Template", "subject": "   ", "html_body": "<p>Hello</p>"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert no_subj.status_code == 400
    assert no_subj.get_json()["success"] is False

    # Dangerous script tag on Save & Publish must be rejected before saving
    xss_name = f"XSS Rejected {uuid.uuid4().hex[:6]}"
    xss_res = client.post(
        "/api/v1/templates/",
        json={
            "name": xss_name,
            "subject": "Unsafe",
            "html_body": "<p>Hi</p><script>alert(1)</script>",
            "status": "PUBLISHED",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert xss_res.status_code == 422
    assert xss_res.get_json()["success"] is False

    # Verify it was NOT saved to DB
    list_res = client.get(f"/api/v1/templates/?search={xss_name}", headers={"Authorization": f"Bearer {token}"})
    assert len(list_res.get_json()["data"]["items"]) == 0

    # Malicious CSS expression() rejected
    css_res = client.post(
        "/api/v1/templates/",
        json={
            "name": f"Bad CSS {uuid.uuid4().hex[:6]}",
            "subject": "Unsafe CSS",
            "html_body": "<p>Hi</p>",
            "css": "div { width: expression(alert(1)); }",
            "status": "PUBLISHED",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert css_res.status_code == 422

    # Unclosed Jinja syntax rejected
    jinja_res = client.post(
        "/api/v1/templates/",
        json={
            "name": f"Bad Jinja {uuid.uuid4().hex[:6]}",
            "subject": "Broken {{",
            "html_body": "<p>Hi</p>",
            "status": "PUBLISHED",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert jinja_res.status_code == 400


def test_8_and_9_organization_isolation_and_unauthorized_access(client, studio_setup):
    """8, 9. Prevent cross-organization reads/edits/publishes/deletes and reject unauthorized access."""
    token_a = studio_setup["token_a"]
    token_ro_a = studio_setup["token_ro_a"]
    token_b = studio_setup["token_b"]

    # Org A creates a template
    res_a = client.post(
        "/api/v1/templates/",
        json={
            "name": f"Org A Secret Template {uuid.uuid4().hex[:6]}",
            "subject": "Private A",
            "html_body": "<p>Private to Org A</p>",
            "status": "DRAFT",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_a.status_code == 201
    tid_a = res_a.get_json()["data"]["template_id"]

    # Org B cannot read, update, publish, or delete Org A's template
    assert client.get(f"/api/v1/templates/{tid_a}", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404
    assert client.put(
        f"/api/v1/templates/{tid_a}",
        json={"subject": "Hijacked"},
        headers={"Authorization": f"Bearer {token_b}"},
    ).status_code == 404
    assert client.post(
        f"/api/v1/templates/{tid_a}/publish",
        json={"status": "PUBLISHED"},
        headers={"Authorization": f"Bearer {token_b}"},
    ).status_code == 404
    assert client.delete(f"/api/v1/templates/{tid_a}", headers={"Authorization": f"Bearer {token_b}"}).status_code == 404

    # Unauthenticated request rejected (401)
    assert client.post("/api/v1/templates/", json={"name": "NoAuth", "subject": "S", "html_body": "<p>x</p>"}).status_code == 401
    assert client.get("/api/v1/templates/").status_code == 401

    # Read-only user cannot create, update, publish, or delete (403)
    assert client.post(
        "/api/v1/templates/",
        json={"name": "Forbidden", "subject": "S", "html_body": "<p>x</p>"},
        headers={"Authorization": f"Bearer {token_ro_a}"},
    ).status_code == 403
    assert client.put(
        f"/api/v1/templates/{tid_a}",
        json={"subject": "Forbidden Edit"},
        headers={"Authorization": f"Bearer {token_ro_a}"},
    ).status_code == 403
    assert client.delete(
        f"/api/v1/templates/{tid_a}",
        headers={"Authorization": f"Bearer {token_ro_a}"},
    ).status_code == 403
