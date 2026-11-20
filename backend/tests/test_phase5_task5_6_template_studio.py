"""
SenderX Phase 5 Task 5.6: Email Template Studio & Incoming Payload Security Integration Tests
Tests for:
- 5.6.1 New Template Studio lifecycle (create draft, preview, validate, publish, duplicate, versioning)
- 5.6.2 Starter layout endpoint and compatibility checks
- 5.6.3 Save-time security rejections (script tags, event handlers, protocols, CSS imports, undeclared variables)
- 5.6.4 Case-insensitive name uniqueness per organization and tenant isolation (HTTP 404 cross-org)
- 5.6.5 Safe injection of incoming API variables (escaping, strict mode, format validation, CR/LF rejection)
- 5.6.6 Incoming payload HTML/CSS checks (contains_markup flag, dangerous payload rejection, template vs raw html conflict)
- 5.6.7 Security audit logging with human-readable template names and action labels
"""

import uuid
import pytest
import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app
from app.config.settings import Config
from app.modules.templates.service import TemplateService
from app.modules.templates.repository import TemplateRepository
from app.modules.messages.service import MessageService
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
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
def test_setup(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())

        role_admin_a = str(uuid.uuid4())
        role_admin_b = str(uuid.uuid4())

        user_admin_a = str(uuid.uuid4())
        user_admin_b = str(uuid.uuid4())

        rounds = getattr(Config, "BCRYPT_ROUNDS", 4)
        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(rounds)).decode("utf-8")

        # Org A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Template Studio Org A {suffix}",
            "slug": f"tmpl-studio-a-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a,
            "name": "Org Admin A",
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

        UserRepository.create({
            "user_id": user_admin_a,
            "organization_id": org_a,
            "employee_code": f"EMP-A-{suffix}",
            "employee_code_lower": f"emp-a-{suffix}",
            "name": "Admin User A",
            "email": f"admin-a-{suffix}@senderx.test",
            "password_hash": password_hash,
            "role_ids": [role_admin_a],
            "is_active": True,
            "status": "ACTIVE"
        })

        # Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Template Studio Org B {suffix}",
            "slug": f"tmpl-studio-b-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b,
            "name": "Org Admin B",
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

        UserRepository.create({
            "user_id": user_admin_b,
            "organization_id": org_b,
            "employee_code": f"EMP-B-{suffix}",
            "employee_code_lower": f"emp-b-{suffix}",
            "name": "Admin User B",
            "email": f"admin-b-{suffix}@senderx.test",
            "password_hash": password_hash,
            "role_ids": [role_admin_b],
            "is_active": True,
            "status": "ACTIVE"
        })

        token_a = create_access_token(
            identity=user_admin_a,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a}
        )

        token_b = create_access_token(
            identity=user_admin_b,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b}
        )

        return {
            "org_a": org_a,
            "org_b": org_b,
            "user_a": user_admin_a,
            "user_b": user_admin_b,
            "token_a": token_a,
            "token_b": token_b
        }


def test_starter_layout_endpoint(client, test_setup):
    """GET /api/v1/email-templates/starter-layout returns responsive table starter code."""
    res = client.get(
        "/api/v1/email-templates/starter-layout",
        headers={"Authorization": f"Bearer {test_setup['token_a']}"}
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "html" in data
    assert "css" in data
    assert "variables" in data
    # Enforce standard starter variables
    var_names = [v["name"] for v in data["variables"]]
    expected_vars = [
        "subject", "preheader", "brand_name", "brand_color", "logo_url",
        "recipient_name", "heading", "body_lines", "cta_text", "cta_url", "footer_text"
    ]
    for ev in expected_vars:
        assert ev in var_names


def test_validate_endpoint_valid_and_warnings(client, test_setup):
    """POST /api/v1/email-templates/validate checks safety and client compatibility without saving."""
    payload = {
        "html": "<table width='600'><tr><td class='header'>Hello {{ user_name }}</td></tr></table>",
        "css": ".header { color: #333333; display: flex; }",  # flexbox should generate compatibility warning
        "variables": [{"name": "user_name", "required": True, "type": "string"}]
    }
    res = client.post(
        "/api/v1/email-templates/validate",
        headers={"Authorization": f"Bearer {test_setup['token_a']}"},
        json=payload
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["isValid"] is True
    assert "user_name" in data["detected_variables"]
    # Check that compatibility warning was detected for display: flex
    flex_warn = any("flexbox" in w.lower() for w in data["warnings"])
    assert flex_warn is True


def test_validate_endpoint_catches_security_threats(client, test_setup):
    """POST /api/v1/email-templates/validate flags dangerous scripts and undeclared variables."""
    payload = {
        "html": "<div><script>alert(1)</script>Hello {{ undeclared_var }}</div>",
        "css": "body { background: url('http://insecure.test/bg.png'); }",
        "variables": []
    }
    res = client.post(
        "/api/v1/email-templates/validate",
        headers={"Authorization": f"Bearer {test_setup['token_a']}"},
        json=payload
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["isValid"] is False
    assert len(data["errors"]) >= 2  # script tag and undeclared variable


def test_preview_endpoint_with_sample_values(client, test_setup):
    """POST /api/v1/email-templates/preview renders HTML with inlined styles and sample values."""
    payload = {
        "html": "<table width='600'><tr><td class='title'>Welcome {{ customer_name }}!</td></tr></table>",
        "css": ".title { color: #1e40af; font-weight: bold; }",
        "variables": [{"name": "customer_name", "required": True}],
        "sample_data": {"customer_name": "Alice Wonderland"}
    }
    res = client.post(
        "/api/v1/email-templates/preview",
        headers={"Authorization": f"Bearer {test_setup['token_a']}"},
        json=payload
    )
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "rendered_html" in data
    assert "plain_text" in data
    assert "Alice Wonderland" in data["rendered_html"]
    assert "color: #1e40af" in data["rendered_html"]


def test_template_crud_publish_duplicate_versioning(client, test_setup):
    """
    Complete lifecycle:
    1. Create draft template with compiled_html and plain_text
    2. Case-insensitive uniqueness enforcement (409)
    3. Publish template (status ACTIVE)
    4. Duplicate template (new DRAFT with copy name)
    5. Edit ACTIVE template (bumps version and stores snapshot)
    """
    token = test_setup["token_a"]

    # 1. Create draft
    create_payload = {
        "name": "Monthly Account Statement",
        "category": "ACCOUNT",
        "description": "Monthly breakdown statement for account holders",
        "subject": "Statement for {{ month_name }}",
        "html": "<table width='600'><tr><td>Statement for {{ month_name }} - Total: {{ amount }}</td></tr></table>",
        "css": "table { max-width: 600px; font-family: sans-serif; }",
        "variables": [
            {"name": "month_name", "required": True, "type": "string", "example_value": "November"},
            {"name": "amount", "required": True, "type": "string", "example_value": "$125.00"}
        ]
    }
    res = client.post("/api/v1/email-templates", headers={"Authorization": f"Bearer {token}"}, json=create_payload)
    assert res.status_code == 201
    created = res.get_json()["data"]
    template_id = created["template_id"]
    assert created["name"] == "Monthly Account Statement"
    assert created["status"] == "DRAFT"
    assert created["version"] == 1
    assert "compiled_html" in created
    assert "plain_text_body" in created

    # 2. Case-insensitive uniqueness: creating "monthly account statement" in same org must return 409
    dup_payload = dict(create_payload)
    dup_payload["name"] = "MONTHLY ACCOUNT STATEMENT"
    res_dup = client.post("/api/v1/email-templates", headers={"Authorization": f"Bearer {token}"}, json=dup_payload)
    assert res_dup.status_code == 409

    # 3. Publish template
    res_pub = client.post(f"/api/v1/email-templates/{template_id}/publish", headers={"Authorization": f"Bearer {token}"})
    assert res_pub.status_code == 200
    pub_data = res_pub.get_json()["data"]
    assert pub_data["status"] == "ACTIVE"

    # 4. Duplicate template
    res_dupl = client.post(f"/api/v1/email-templates/{template_id}/duplicate", headers={"Authorization": f"Bearer {token}"})
    assert res_dupl.status_code == 201
    dupl_data = res_dupl.get_json()["data"]
    assert dupl_data["status"] == "DRAFT"
    assert dupl_data["template_id"] != template_id
    assert "Copy" in dupl_data["name"]

    # 5. Edit ACTIVE template -> bumps version to 2 and snapshots v1
    update_payload = {
        "html": "<table width='600'><tr><td>Updated statement for {{ month_name }}: {{ amount }}</td></tr></table>"
    }
    res_upd = client.put(f"/api/v1/email-templates/{template_id}", headers={"Authorization": f"Bearer {token}"}, json=update_payload)
    assert res_upd.status_code == 200
    upd_data = res_upd.get_json()["data"]
    assert upd_data["version"] == 2

    # Verify version history snapshot exists
    res_versions = client.get(f"/api/v1/email-templates/{template_id}/versions", headers={"Authorization": f"Bearer {token}"})
    assert res_versions.status_code == 200
    versions = res_versions.get_json()["data"]
    assert len(versions) >= 2
    assert versions[0]["version"] == 2
    assert versions[0]["is_current"] is True
    assert versions[1]["version"] == 1
    assert versions[1]["is_current"] is False


def test_tenant_isolation_and_cross_org_denial(client, test_setup):
    """
    Org B cannot see or manipulate Org A's template (returns 404).
    Org B can create a template with the exact same name as Org A.
    """
    token_a = test_setup["token_a"]
    token_b = test_setup["token_b"]

    # Create template in Org A
    res_a = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Shared Name Test",
            "subject": "Hello",
            "html": "<table width='600'><tr><td>Org A Content</td></tr></table>",
            "css": "table { color: red; }",
            "variables": []
        }
    )
    assert res_a.status_code == 201
    tmpl_a_id = res_a.get_json()["data"]["template_id"]

    # Org B trying to read Org A template returns 404
    res_cross = client.get(f"/api/v1/email-templates/{tmpl_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_cross.status_code == 404

    # Org B can create template with same name "Shared Name Test"
    res_b = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token_b}"},
        json={
            "name": "Shared Name Test",
            "subject": "Hello Org B",
            "html": "<table width='600'><tr><td>Org B Content</td></tr></table>",
            "css": "table { color: blue; }",
            "variables": []
        }
    )
    assert res_b.status_code == 201


def test_save_time_rejections_and_undeclared_variables(client, test_setup):
    """
    Enforces save-time validation:
    - `<script>` tag returns 422
    - `onclick` event handler returns 422
    - Undeclared Jinja variable returns 422
    """
    token = test_setup["token_a"]

    # Script tag
    res_script = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Malicious Script Template",
            "subject": "Insecure",
            "html": "<table width='600'><tr><td><script>alert(1)</script></td></tr></table>",
            "css": "",
            "variables": []
        }
    )
    assert res_script.status_code == 422

    # Event handler
    res_onclick = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Malicious Event Template",
            "subject": "Insecure",
            "html": "<table width='600'><tr><td onclick='bad()'>Click Me</td></tr></table>",
            "css": "",
            "variables": []
        }
    )
    assert res_onclick.status_code == 422

    # Undeclared variable in HTML
    res_undeclared = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Undeclared Var Template",
            "subject": "Subject",
            "html": "<table width='600'><tr><td>Hello {{ missing_var }}</td></tr></table>",
            "css": "",
            "variables": []  # missing_var not declared!
        }
    )
    assert res_undeclared.status_code == 422
    assert "missing_var" in res_undeclared.get_json()["message"]


def test_message_dispatch_conflicts_and_safe_variables(client, test_setup):
    """
    Verifies message sending safety:
    1. Supplying template_id AND raw html returns 422
    2. Missing required variable returns 422
    3. Strict mode rejects unknown variable with 422
    4. Malicious variable value is HTML escaped in output
    5. URL variable non-https returns 422
    6. CR/LF in subject returns 422
    """
    token = test_setup["token_a"]
    org_id = test_setup["org_a"]

    # Create and publish a test template
    create_res = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Dispatch Safe Test {uuid.uuid4().hex[:6]}",
            "subject": "Notice for {{ user_name }}",
            "html": "<table width='600'><tr><td>User: {{ user_name }} | Link: <a href='{{ profile_url }}'>Profile</a></td></tr></table>",
            "css": "table { color: #111; }",
            "variables": [
                {"name": "user_name", "required": True, "type": "string"},
                {"name": "profile_url", "required": True, "type": "url"}
            ],
            "strict_variables": True
        }
    )
    assert create_res.status_code == 201
    tmpl_id = create_res.get_json()["data"]["template_id"]
    client.post(f"/api/v1/email-templates/{tmpl_id}/publish", headers={"Authorization": f"Bearer {token}"})

    # 1. Conflict: template_id AND html provided
    res_conflict = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipient": "dispatch-test@example.com",
            "channel": "EMAIL",
            "subject": "Conflict Test",
            "template_id": tmpl_id,
            "html": "<p>Raw HTML conflict</p>",
            "variables": {"user_name": "Bob", "profile_url": "https://example.com/bob"}
        }
    )
    assert res_conflict.status_code == 422

    # 2. Missing required variable (profile_url omitted)
    res_missing = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipient": "dispatch-test@example.com",
            "channel": "EMAIL",
            "template_id": tmpl_id,
            "variables": {"user_name": "Bob"}
        }
    )
    assert res_missing.status_code in [400, 422]
    assert "profile_url" in res_missing.get_json()["message"]

    # 3. Strict mode: unknown variable supplied
    res_unknown = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipient": "dispatch-test@example.com",
            "channel": "EMAIL",
            "template_id": tmpl_id,
            "variables": {
                "user_name": "Bob",
                "profile_url": "https://example.com/bob",
                "malicious_unknown": "injection"
            }
        }
    )
    assert res_unknown.status_code == 422

    # 4. URL format validation: non-https URL rejected
    res_bad_url = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipient": "dispatch-test@example.com",
            "channel": "EMAIL",
            "template_id": tmpl_id,
            "variables": {
                "user_name": "Bob",
                "profile_url": "http://insecure-http.example.com"
            }
        }
    )
    assert res_bad_url.status_code == 422

    # 5. CR/LF injection in variable used in subject rejected
    res_crlf = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipient": "dispatch-test@example.com",
            "channel": "EMAIL",
            "template_id": tmpl_id,
            "variables": {
                "user_name": "Bob\r\nBcc: evil@attacker.com",
                "profile_url": "https://example.com/bob"
            }
        }
    )
    assert res_crlf.status_code == 422

    # 6. Malicious script in variable value is rendered as escaped text
    res_xss = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipient": "dispatch-test@example.com",
            "channel": "EMAIL",
            "template_id": tmpl_id,
            "variables": {
                "user_name": "<script>alert('xss')</script>",
                "profile_url": "https://example.com/bob"
            }
        }
    )
    # Message creation succeeds because variable value is safely escaped
    assert res_xss.status_code in [200, 201, 202]
    msg_resp = res_xss.get_json()["data"]
    msg_id = msg_resp.get("message_id") or msg_resp.get("message", {}).get("message_id")
    assert msg_id is not None

    # Verify rendered content from service
    with client.application.app_context():
        msg_doc = client.application.mongo_db["messages"].find_one({"message_id": msg_id})
        assert msg_doc is not None
        # Must NOT contain raw unescaped script tag in rendered_content
        data_block = msg_doc.get("data") or {}
        rendered = data_block.get("html") or data_block.get("message") or msg_doc.get("rendered_content") or ""
        assert "<script>alert('xss')</script>" not in rendered
        assert "&lt;script&gt;" in rendered or "alert(&#x27;xss&#x27;)" in rendered or "alert(&#39;xss&#39;)" in rendered


def test_incoming_payload_markup_detection_and_dangerous_rejection(client, test_setup):
    """
    5.6.5 Incoming payload HTML checks:
    - String containing HTML markup (e.g. <b>Alert</b>) flags contains_markup: True
    - Dangerous payload with <script> tag without declared template rejected with 422
    """
    token = test_setup["token_a"]

    # 1. Markup detected in content
    res_markup = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipient": "markup-test@example.com",
            "channel": "EMAIL",
            "subject": "System Status Update",
            "content": "Attention: <b>Server maintenance</b> is scheduled."
        }
    )
    assert res_markup.status_code in [200, 201, 202]
    markup_data = res_markup.get_json()["data"]
    msg_id = markup_data.get("message_id") or markup_data.get("message", {}).get("message_id")
    assert msg_id is not None

    with client.application.app_context():
        msg_doc = client.application.mongo_db["messages"].find_one({"message_id": msg_id})
        assert msg_doc.get("contains_markup") is True

    # 2. Dangerous raw payload with script tag rejected
    res_dangerous = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipient": "dangerous-test@example.com",
            "channel": "EMAIL",
            "subject": "Hello",
            "content": "Malicious payload: <script>document.cookie</script>"
        }
    )
    assert res_dangerous.status_code == 422


def test_audit_logging_with_friendly_template_names(client, test_setup):
    """5.6.3 / 5.6.7 Verifies audit entries contain template names and human-readable action labels."""
    token = test_setup["token_a"]
    name = f"Audit Monitored Template {uuid.uuid4().hex[:6]}"

    # Create template
    res = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "subject": "Audit Check",
            "html": "<table width='600'><tr><td>Audit content</td></tr></table>",
            "css": "table { color: #000; }",
            "variables": []
        }
    )
    assert res.status_code == 201
    tmpl_id = res.get_json()["data"]["template_id"]

    # Check audit log in database
    with client.application.app_context():
        db = client.application.mongo_db
        audit_entry = db["security_audit_logs"].find_one({"target_id": tmpl_id, "event_type": "EMAIL_TEMPLATE_CREATED"})
        assert audit_entry is not None
        assert audit_entry.get("target_name") == name
        assert audit_entry.get("action_label") == "Created Email Template"


# ==============================================================================
# 5.6.1 ACCEPTANCE HARDENING TESTS
# ==============================================================================

def test_template_rate_limiting_preview_and_validate(client, test_setup):
    """5.6.1 Item 4: Rate limit /email-templates/preview and /validate per user with clear 429 message."""
    token = test_setup["token_a"]
    user_id = test_setup["user_a"]

    # Clear keys first for deterministic test run
    redis_client = getattr(client.application, "redis_client", None)
    if redis_client:
        redis_client.delete(f"ratelimit:template_preview:{user_id}")
        redis_client.delete(f"ratelimit:template_validate:{user_id}")

    # Test preview rate limiting by configuring a tight limit temporarily
    with client.application.app_context():
        client.application.config["RATE_LIMIT_TEMPLATE_PREVIEW_RPM"] = 2
        client.application.config["RATE_LIMIT_TEMPLATE_VALIDATE_RPM"] = 2

    # Request 1: OK
    r1 = client.post(
        "/api/v1/email-templates/preview",
        headers={"Authorization": f"Bearer {token}"},
        json={"subject": "Preview 1", "html_body": "<p>Hello</p>"}
    )
    assert r1.status_code in [200, 400]

    # Request 2: OK
    r2 = client.post(
        "/api/v1/email-templates/preview",
        headers={"Authorization": f"Bearer {token}"},
        json={"subject": "Preview 2", "html_body": "<p>Hello</p>"}
    )
    assert r2.status_code in [200, 400]

    # Request 3: 429 Rate Limit Exceeded
    r3 = client.post(
        "/api/v1/email-templates/preview",
        headers={"Authorization": f"Bearer {token}"},
        json={"subject": "Preview 3", "html_body": "<p>Hello</p>"}
    )
    assert r3.status_code == 429
    assert "Rate limit exceeded" in r3.get_json()["message"]
    assert "Retry-After" in r3.headers

    # Validate endpoint rate limit
    v1 = client.post(
        "/api/v1/email-templates/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Valid 1", "subject": "V1", "html_body": "<p>Hi</p>"}
    )
    assert v1.status_code == 200

    v2 = client.post(
        "/api/v1/email-templates/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Valid 2", "subject": "V2", "html_body": "<p>Hi</p>"}
    )
    assert v2.status_code == 200

    v3 = client.post(
        "/api/v1/email-templates/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Valid 3", "subject": "V3", "html_body": "<p>Hi</p>"}
    )
    assert v3.status_code == 429
    assert "Rate limit exceeded" in v3.get_json()["message"]

    # Reset config limits and clean keys
    with client.application.app_context():
        client.application.config["RATE_LIMIT_TEMPLATE_PREVIEW_RPM"] = 60
        client.application.config["RATE_LIMIT_TEMPLATE_VALIDATE_RPM"] = 60
    if redis_client:
        redis_client.delete(f"ratelimit:template_preview:{user_id}")
        redis_client.delete(f"ratelimit:template_validate:{user_id}")


def test_template_description_crud_and_validation(client, test_setup):
    """5.6.1 Item 5: Description (max 300) exists in model, create/update API, list, and details."""
    token = test_setup["token_a"]
    name = f"Description Test {uuid.uuid4().hex[:6]}"
    desc = "This is a detailed transactional email template for order dispatch notifications."

    # 1. Create with description
    res = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "description": desc,
            "subject": "Order Shipped",
            "html": "<table width='600'><tr><td>Your order is on the way!</td></tr></table>",
            "css": "",
            "variables": []
        }
    )
    assert res.status_code == 201
    tmpl = res.get_json()["data"]
    assert tmpl.get("description") == desc
    tmpl_id = tmpl["template_id"]

    # 2. Get by ID confirms description
    res_get = client.get(f"/api/v1/email-templates/{tmpl_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_get.status_code == 200
    assert res_get.get_json()["data"].get("description") == desc

    # 3. Update description
    new_desc = "Updated description within 300 characters."
    res_patch = client.patch(
        f"/api/v1/email-templates/{tmpl_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": new_desc}
    )
    assert res_patch.status_code == 200
    assert res_patch.get_json()["data"].get("description") == new_desc

    # 4. Description > 300 chars rejected
    too_long = "A" * 305
    res_fail = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": f"Too Long {uuid.uuid4().hex[:6]}",
            "description": too_long,
            "subject": "Fail",
            "html": "<p>Content</p>"
        }
    )
    assert res_fail.status_code == 400


def test_raw_html_sanitization_and_rejection_without_template(client, test_setup):
    """5.6.1 Item 6: Raw HTML on email channel without template_id is sanitized or rejected."""
    token = test_setup["token_a"]

    # 1. Reject script tag in raw HTML
    r_script = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "channel": "email",
            "recipient": "test-sec@example.com",
            "subject": "Raw HTML Test",
            "html": "<p>Hello</p><script>alert('xss')</script>"
        }
    )
    assert r_script.status_code == 422
    assert "Forbidden HTML tag '<script>'" in r_script.get_json()["message"] or "Script tag injection" in r_script.get_json()["message"]

    # 2. Reject event handlers in raw HTML
    r_event = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "channel": "email",
            "recipient": "test-sec@example.com",
            "subject": "Raw HTML Test",
            "html": "<p onclick='alert(1)'>Click me</p>"
        }
    )
    assert r_event.status_code == 422
    assert "Forbidden event handler" in r_event.get_json()["message"] or "Event handler" in r_event.get_json()["message"]

    # 3. Reject javascript: URL in raw HTML
    r_js = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "channel": "email",
            "recipient": "test-sec@example.com",
            "subject": "Raw HTML Test",
            "html": "<a href='javascript:evil()'>Click</a>"
        }
    )
    assert r_js.status_code == 422

    # 4. Safe rich HTML is accepted and sanitized
    r_safe = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "channel": "email",
            "recipient": "safe-html@example.com",
            "subject": "Safe HTML",
            "html": "<p style='color:blue;'>Welcome to <b>SenderX</b>! Visit <a href='https://senderx.io'>site</a>.</p>"
        }
    )
    assert r_safe.status_code in [200, 201, 202]


def test_dangerous_patterns_rejected_no_silent_send(client, test_setup):
    """5.6.1 Item 7: Header injection and non-https URL variables rejected with clear reason."""
    token = test_setup["token_a"]

    # 1. Header injection with CR/LF in subject
    r_header = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "channel": "email",
            "recipient": "header-test@example.com",
            "subject": "Important Notice\r\nBcc: hacker@evil.com\r\nSubject: Injected",
            "content": "Message content"
        }
    )
    assert r_header.status_code == 422
    assert "header injection blocked" in r_header.get_json()["message"]

    # 2. Template requiring https URL variable rejects non-https URL
    name = f"URL Var Template {uuid.uuid4().hex[:6]}"
    res_tmpl = client.post(
        "/api/v1/email-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "subject": "Link Email",
            "html": "<table width='600'><tr><td><a href='{{ action_url }}'>Action</a></td></tr></table>",
            "variables": [{"name": "action_url", "type": "url", "required": True}]
        }
    )
    assert res_tmpl.status_code == 201
    tmpl_id = res_tmpl.get_json()["data"]["template_id"]

    # Publish template so it is ACTIVE for messaging
    pub_res = client.post(
        f"/api/v1/email-templates/{tmpl_id}/publish",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert pub_res.status_code == 200

    # Send message with non-https URL -> rejected with 422
    r_bad_url = client.post(
        "/api/v1/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "channel": "email",
            "recipient": "url-test@example.com",
            "template_id": tmpl_id,
            "template_variables": {"action_url": "http://insecure-site.com"}
        }
    )
    assert r_bad_url.status_code == 422
    assert "absolute https:// URL" in r_bad_url.get_json()["message"]
