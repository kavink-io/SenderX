"""
Phase 6 Security Test Suite:
Provider & Channel Configuration Hardening, Anti-Escalation, Secret Preservation,
Cross-Tenant OAuth Protection, Application-Scoped RBAC Guards, Storage Boundary Isolation,
Email Header Injection Defense, and Channel Catalog Accuracy.

Runs strictly against isolated test DB / in-memory doubles without hitting live Meta,
Twilio, SendGrid, SES, or Microsoft Graph endpoints or sending real messages.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
import tempfile
import shutil
import time
import uuid

import bcrypt
from cryptography.fernet import Fernet
from flask_jwt_extended import create_access_token
import pytest

from app import create_app
from app.adapters.adapter_registry import AdapterRegistry
from app.adapters.email.sendgrid_adapter import SendGridAdapter
from app.adapters.email.ses_adapter import AmazonSESAdapter
from app.adapters.email.smtp_adapter import SMTPAdapter
from app.adapters.errors import ProviderResolutionError
from app.adapters.teams.teams_adapter import MicrosoftTeamsAdapter
from app.adapters.telegram.mock_adapter import MockTelegramAdapter
from app.adapters.whatsapp.cloud_adapter import WhatsAppCloudAdapter
from app.adapters.teams.teams_utils import generate_oauth_state
from app.modules.applications.repository import ApplicationRepository
from app.modules.auth.repository import AuthRepository
from app.modules.media.repository import MediaRepository
from app.modules.media.service import MediaService
from app.modules.media.storage.local_storage import LocalStorage
from app.modules.media.storage.base_storage import StorageSecurityError
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.organizations.service import OrganizationService
from app.modules.provider_config.service import ProviderConfigService
from app.modules.templates.repository import TemplateRepository
from app.modules.templates.service import TemplateService
from app.modules.users.repository import UserRepository
from app.modules.whatsapp.encryption import WhatsAppEncryption
from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
from app.queue.tasks import process_message


VALID_PDF_BYTES = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["APP_ENV"] = "test"
    temp_dir = tempfile.mkdtemp(prefix="senderx_phase6_media_")
    flask_app.config["MEDIA_LOCAL_STORAGE_DIR"] = temp_dir
    flask_app.config["STORAGE_BACKEND"] = "local"
    flask_app.config["MEDIA_STORAGE_BACKEND"] = "local"
    yield flask_app
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def phase6_env(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        pw_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(4)).decode("utf-8")

        org_a = f"p6-org-a-{suffix}"
        org_b = f"p6-org-b-{suffix}"
        for oid, name, slug in [
            (org_a, f"Phase6 Org A {suffix}", f"p6-org-a-{suffix}"),
            (org_b, f"Phase6 Org B {suffix}", f"p6-org-b-{suffix}"),
        ]:
            OrganizationRepository.create({
                "organization_id": oid,
                "name": name,
                "slug": slug,
                "status": "ACTIVE",
            })

        app_a = ApplicationRepository.create({
            "organization_id": org_a,
            "name": f"Phase6 App A {suffix}",
            "environment": "all",
            "status": "ACTIVE",
        })["application_id"]
        app_b = ApplicationRepository.create({
            "organization_id": org_a,
            "name": f"Phase6 App B {suffix}",
            "environment": "all",
            "status": "ACTIVE",
        })["application_id"]

        role_org_a = str(uuid.uuid4())
        RoleRepository.create({
            "role_id": role_org_a,
            "organization_id": org_a,
            "name": f"ORG_ADMIN_{suffix}",
            "scope": "ORGANIZATION",
            "permissions": list(OrganizationService.ORG_ADMIN_PERMISSIONS),
            "is_system_role": True,
        })

        role_org_b = str(uuid.uuid4())
        RoleRepository.create({
            "role_id": role_org_b,
            "organization_id": org_b,
            "name": f"ORG_ADMIN_B_{suffix}",
            "scope": "ORGANIZATION",
            "permissions": list(OrganizationService.ORG_ADMIN_PERMISSIONS),
            "is_system_role": True,
        })

        role_app_scoped = str(uuid.uuid4())
        RoleRepository.create({
            "role_id": role_app_scoped,
            "organization_id": org_a,
            "name": f"APP_MANAGER_{suffix}",
            "scope": "ORGANIZATION",
            "permissions": list(OrganizationService.ORG_ADMIN_PERMISSIONS),
        })

        user_org_a = str(uuid.uuid4())
        UserRepository.create({
            "user_id": user_org_a,
            "organization_id": org_a,
            "name": "Org A Admin",
            "email": f"org-a-{suffix}@p6.test",
            "password_hash": pw_hash,
            "role_ids": [role_org_a],
            "role_assignments": [{"role_id": role_org_a, "application_id": None}],
            "is_active": True,
        })

        user_org_b = str(uuid.uuid4())
        UserRepository.create({
            "user_id": user_org_b,
            "organization_id": org_b,
            "name": "Org B Admin",
            "email": f"org-b-{suffix}@p6.test",
            "password_hash": pw_hash,
            "role_ids": [role_org_b],
            "role_assignments": [{"role_id": role_org_b, "application_id": None}],
            "is_active": True,
        })

        user_app_a = str(uuid.uuid4())
        UserRepository.create({
            "user_id": user_app_a,
            "organization_id": org_a,
            "name": "App Scoped User A",
            "email": f"app-a-{suffix}@p6.test",
            "password_hash": pw_hash,
            "role_ids": [role_app_scoped],
            "role_assignments": [{"role_id": role_app_scoped, "application_id": app_a}],
            "is_active": True,
        })

        raw_key_a = f"sx_test_p6_{uuid.uuid4().hex}"
        app.mongo_db["api_credentials"].insert_one({
            "credential_id": f"cred_{uuid.uuid4().hex[:12]}",
            "organization_id": org_a,
            "application_id": app_a,
            "name": "Phase6 Key A",
            "key_hash": hashlib.sha256(raw_key_a.encode()).hexdigest(),
            "key_prefix": raw_key_a[:12],
            "environment": "test",
            "status": "ACTIVE",
            "scopes": ["messages:create", "messages:read", "messages:manage", "payloads:ingest"],
        })

        token_org_a = create_access_token(
            identity=user_org_a,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a, "token_version": 1},
        )
        token_org_b = create_access_token(
            identity=user_org_b,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b, "token_version": 1},
        )
        token_app_a = create_access_token(
            identity=user_app_a,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a, "token_version": 1},
        )

        yield {
            "org_a": org_a,
            "org_b": org_b,
            "app_a": app_a,
            "app_b": app_b,
            "user_org_a": user_org_a,
            "user_org_b": user_org_b,
            "user_app_a": user_app_a,
            "token_org_a": token_org_a,
            "token_org_b": token_org_b,
            "token_app_a": token_app_a,
            "api_key_a": raw_key_a,
        }


# ===========================================================================
# 1. PLATFORM FALLBACK ANTI-ESCALATION
# ===========================================================================

def test_client_cannot_enable_platform_fallback_via_message_or_payload(client, app, phase6_env):
    token = phase6_env["token_org_a"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Top-level body flag rejected
    res1 = client.post(
        "/api/v1/messages/",
        headers=headers,
        json={
            "channel": "email",
            "recipient": "user@example.test",
            "use_platform_provider": True,
            "data": {"subject": "Hi", "message": "Body"},
        },
    )
    assert res1.status_code == 403

    # 2. Nested data flag rejected
    res2 = client.post(
        "/api/v1/messages/",
        headers=headers,
        json={
            "channel": "email",
            "recipient": "user@example.test",
            "data": {"subject": "Hi", "message": "Body", "allow_platform_fallback": True},
        },
    )
    assert res2.status_code == 403

    # 3. Query param and header rejected
    res3 = client.post(
        "/api/v1/messages/?use_platform_provider=true",
        headers={**headers, "X-Allow-Platform-Fallback": "true"},
        json={
            "channel": "email",
            "recipient": "user@example.test",
            "data": {"subject": "Hi", "message": "Body"},
        },
    )
    assert res3.status_code == 403

    # 4. Payload ingestion rejects client platform fallback flags
    res4 = client.post(
        "/api/v1/payloads/ingest",
        headers={"X-API-Key": phase6_env["api_key_a"]},
        json={
            "channel": "email",
            "recipient": "user@example.test",
            "data": {"subject": "Hi", "message": "Body", "use_platform_provider": True},
        },
    )
    assert res4.status_code == 403


def test_celery_worker_ignores_untrusted_message_use_platform_provider_flag(app, phase6_env):
    with app.app_context():
        # Configure platform SendGrid
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "SG.platform_secret_key", "from_email": "platform@senderx.test"},
            organization_id=None,
        )
        # Grant authorized_platform_providers on org_b WITHOUT allow_platform_fallback org flag,
        # and try sneaking use_platform_provider=True on the message document.
        OrganizationRepository._collection().update_one(
            {"organization_id": phase6_env["org_b"]},
            {"$set": {"authorized_platform_providers": ["sendgrid"]}},
        )
        msg_id = f"msg-p6-escalation-{uuid.uuid4().hex[:8]}"
        app.mongo_db["messages"].insert_one({
            "message_id": msg_id,
            "organization_id": phase6_env["org_b"],
            "channel": "email",
            "provider": "sendgrid",
            "recipient": "victim@example.test",
            "use_platform_provider": True,
            "data": {"subject": "Test", "message": "Test body"},
            "status": "QUEUED",
            "retry_count": 0,
            "status_history": [],
        })

        res = process_message(msg_id)
        assert res["success"] is False
        assert res.get("error_code") == ProviderResolutionError.PROVIDER_NOT_CONFIGURED
        updated = app.mongo_db["messages"].find_one({"message_id": msg_id})
        assert updated["status"] == "FAILED"


# ===========================================================================
# 2. PROVIDER CONFIG SECRET PRESERVATION, ROTATION, LIFECYCLE & TEAMS OAUTH
# ===========================================================================

def test_provider_config_empty_secret_preserves_existing_and_initial_blank_fails(client, app, phase6_env):
    headers = {"Authorization": f"Bearer {phase6_env['token_org_a']}"}
    org_a = phase6_env["org_a"]

    # Initial create with blank secret fails
    bad = client.post(
        "/api/v1/provider-config/organization",
        headers=headers,
        json={"provider": "sendgrid", "credentials": {"api_key": "   ", "from_email": "notify@orga.test"}},
    )
    assert bad.status_code == 400

    # Valid initial create
    ok = client.post(
        "/api/v1/provider-config/organization",
        headers=headers,
        json={"provider": "sendgrid", "credentials": {"api_key": "SG.initial_secret_p6", "from_email": "notify@orga.test"}},
    )
    assert ok.status_code == 201

    # Partial update with empty api_key preserves existing encrypted secret
    upd = client.post(
        "/api/v1/provider-config/organization",
        headers=headers,
        json={"provider": "sendgrid", "credentials": {"api_key": "", "from_email": "updated@orga.test"}},
    )
    assert upd.status_code == 201

    with app.app_context():
        creds = ProviderConfigService.get_decrypted_configuration("sendgrid", organization_id=org_a)
        assert creds["api_key"] == "SG.initial_secret_p6"
        assert creds["from_email"] == "updated@orga.test"

    # Org B cannot see Org A's SendGrid config
    other = client.get(
        "/api/v1/provider-config/organization?provider=sendgrid",
        headers={"Authorization": f"Bearer {phase6_env['token_org_b']}"},
    )
    assert other.status_code == 404

    # Org A can delete/disconnect its provider config and secrets are removed
    del_res = client.delete("/api/v1/provider-config/organization/sendgrid", headers=headers)
    assert del_res.status_code == 200
    with app.app_context():
        doc = app.mongo_db["provider_configs"].find_one({"provider": "sendgrid", "organization_id": org_a})
        assert doc is not None
        assert doc["configured"] is False
        assert doc["disconnected"] is True
        assert "credentials" not in doc
        with pytest.raises(ProviderResolutionError) as exc_inact:
            ProviderConfigService.get_decrypted_configuration("sendgrid", organization_id=org_a)
        assert exc_inact.value.code == ProviderResolutionError.PROVIDER_INACTIVE


def test_provider_config_multifernet_rotation(app, phase6_env):
    old_key = Fernet.generate_key().decode("ascii")
    new_key = Fernet.generate_key().decode("ascii")

    orig_primary = app.config.get("CREDENTIAL_ENCRYPTION_KEY")
    orig_prev = app.config.get("CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS")
    try:
        with app.app_context():
            app.config["CREDENTIAL_ENCRYPTION_KEY"] = old_key
            app.config["CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS"] = ""
            ProviderConfigService.save_configuration(
                "smtp",
                {"smtp_host": "smtp.orga.test", "smtp_port": 587, "smtp_password": "pw_old_key", "from_email": "s@orga.test"},
                organization_id=phase6_env["org_a"],
            )

            # Rotate to new primary key while keeping old key in PREVIOUS_KEYS
            app.config["CREDENTIAL_ENCRYPTION_KEY"] = new_key
            app.config["CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS"] = old_key
            decrypted = ProviderConfigService.get_decrypted_configuration("smtp", organization_id=phase6_env["org_a"])
            assert decrypted["smtp_password"] == "pw_old_key"

            # Save partial update -> re-encrypts cleanly with new key
            ProviderConfigService.save_configuration(
                "smtp",
                {"smtp_host": "smtp2.orga.test"},
                organization_id=phase6_env["org_a"],
            )
            app.config["CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS"] = ""
            reencrypted = ProviderConfigService.get_decrypted_configuration("smtp", organization_id=phase6_env["org_a"])
            assert reencrypted["smtp_password"] == "pw_old_key"
            assert reencrypted["smtp_host"] == "smtp2.orga.test"
    finally:
        app.config["CREDENTIAL_ENCRYPTION_KEY"] = orig_primary
        app.config["CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS"] = orig_prev


def test_cross_tenant_teams_oauth_exchange_rejected_and_does_not_burn_state(client, app, phase6_env):
    org_a = phase6_env["org_a"]
    secret_key = app.config.get("SECRET_KEY")
    state = generate_oauth_state(org_a, secret_key=secret_key)

    with app.app_context():
        app.mongo_db["oauth_transactions"].insert_one({
            "state": state,
            "organization_id": org_a,
            "user_id": phase6_env["user_org_a"],
            "code_verifier": "verifier-123",
            "redirect_uri": "https://app.senderx.io/teams/callback",
            "status": "PENDING",
            "created_at": time.time(),
            "expires_at": time.time() + 600,
        })

    # Org B tries to exchange Org A's state
    res = client.post(
        "/api/v1/provider-config/teams/oauth/exchange",
        headers={"Authorization": f"Bearer {phase6_env['token_org_b']}"},
        json={"code": "fake-code", "state": state},
    )
    assert res.status_code == 403

    # Verify Org A's pending transaction was NOT consumed by Org B's attempt
    with app.app_context():
        tx = app.mongo_db["oauth_transactions"].find_one({"state": state})
        assert tx is not None
        assert tx["status"] == "PENDING"


# ===========================================================================
# 3. APPLICATION-SCOPED USER & API KEY RBAC ENFORCEMENT ON ORG-WIDE CONFIGS
# ===========================================================================

def test_application_scoped_user_and_api_key_blocked_from_org_wide_configs(client, app, phase6_env):
    app_headers = {"Authorization": f"Bearer {phase6_env['token_app_a']}"}
    key_headers = {"X-API-Key": phase6_env["api_key_a"]}

    # API key cannot access provider-config, whatsapp, templates, or media endpoints
    for method, url in [
        ("GET", "/api/v1/provider-config/organization"),
        ("GET", "/api/v1/whatsapp/integrations"),
        ("GET", "/api/v1/email-templates/"),
        ("GET", "/api/v1/media/"),
    ]:
        res = client.open(url, method=method, headers=key_headers)
        assert res.status_code in (401, 403)

    # Application-scoped user cannot read or manage org-wide provider configs or WhatsApp integrations
    for method, url, body in [
        ("GET", "/api/v1/provider-config/organization", None),
        ("POST", "/api/v1/provider-config/organization", {"provider": "sendgrid", "credentials": {"api_key": "k", "from_email": "a@b.c"}}),
        ("DELETE", "/api/v1/provider-config/organization/smtp", None),
        ("GET", "/api/v1/whatsapp/integrations", None),
        ("POST", "/api/v1/whatsapp/integrations", {"waba_id": "123456", "phone_number_id": "654321", "display_phone_number": "+15551112222", "access_token": "tok_1234567890"}),
    ]:
        kwargs = {"headers": app_headers}
        if body is not None:
            kwargs["json"] = body
        res = client.open(url, method=method, **kwargs)
        assert res.status_code == 403, f"Expected 403 for app-scoped user on {method} {url}, got {res.status_code}"

    # Seed one org-shared template and media item as Org Admin
    org_headers = {"Authorization": f"Bearer {phase6_env['token_org_a']}"}
    tmpl_res = client.post(
        "/api/v1/email-templates/",
        headers=org_headers,
        json={
            "name": f"Shared Template {uuid.uuid4().hex[:6]}",
            "subject": "Hello {{ name }}",
            "html_body": "<p>Hello {{ name }}</p>",
            "variables": [{"name": "name", "type": "text", "required": True}],
        },
    )
    assert tmpl_res.status_code == 201
    tmpl_id = tmpl_res.get_json()["data"]["template_id"]

    media_res = client.post(
        "/api/v1/media/upload",
        headers=org_headers,
        data={"file": (io.BytesIO(VALID_PDF_BYTES), "shared.pdf")},
        content_type="multipart/form-data",
    )
    assert media_res.status_code == 201
    media_id = media_res.get_json()["media"]["media_id"]

    # App-scoped user CAN read org-shared templates and media, CANNOT create/modify/delete them
    assert client.get(f"/api/v1/email-templates/{tmpl_id}", headers=app_headers).status_code == 200
    assert client.get(f"/api/v1/media/{media_id}", headers=app_headers).status_code == 200
    assert client.delete(f"/api/v1/email-templates/{tmpl_id}", headers=app_headers).status_code == 403
    assert client.post(f"/api/v1/email-templates/{tmpl_id}/publish", headers=app_headers).status_code == 403
    assert client.delete(f"/api/v1/media/{media_id}", headers=app_headers).status_code == 403
    assert client.post(
        "/api/v1/media/upload",
        headers=app_headers,
        data={"file": (io.BytesIO(VALID_PDF_BYTES), "app_try.pdf")},
        content_type="multipart/form-data",
    ).status_code == 403


# ===========================================================================
# 4. WHATSAPP SECRET MASKING, DUPLICATE PHONE BLOCK & STORAGE ISOLATION
# ===========================================================================

def test_whatsapp_integration_cross_org_isolation_and_secret_masking(client, app, phase6_env):
    headers_a = {"Authorization": f"Bearer {phase6_env['token_org_a']}"}
    headers_b = {"Authorization": f"Bearer {phase6_env['token_org_b']}"}
    phone_id = f"998877{uuid.uuid4().hex[:6]}"
    token_secret = "EAAG_PRIVATE_ORG_A_TOKEN_XYZ"

    create_res = client.post(
        "/api/v1/whatsapp/integrations",
        headers=headers_a,
        json={
            "waba_id": "WABA_P6_A",
            "phone_number_id": phone_id,
            "display_phone_number": "+15550192837",
            "access_token": token_secret,
        },
    )
    assert create_res.status_code == 201
    int_id = create_res.get_json()["data"]["integration_id"]
    assert token_secret not in json.dumps(create_res.get_json())
    assert "encrypted_access_token" not in create_res.get_json()["data"]

    # Org B cannot retrieve or update or delete Org A's integration
    assert client.get(f"/api/v1/whatsapp/integrations/{int_id}", headers=headers_b).status_code == 404
    assert client.patch(f"/api/v1/whatsapp/integrations/{int_id}", headers=headers_b, json={"name": "Hijack"}).status_code == 404
    assert client.delete(f"/api/v1/whatsapp/integrations/{int_id}", headers=headers_b).status_code == 404

    # Org B cannot register the same active phone_number_id
    dup_res = client.post(
        "/api/v1/whatsapp/integrations",
        headers=headers_b,
        json={
            "waba_id": "WABA_P6_B",
            "phone_number_id": phone_id,
            "display_phone_number": "+15550192837",
            "access_token": "EAAG_ORG_B_OTHER_TOKEN_1234",
        },
    )
    assert dup_res.status_code == 409


def test_storage_and_media_cross_tenant_protection(client, app, phase6_env):
    # Org A uploads PDF
    headers_a = {"Authorization": f"Bearer {phase6_env['token_org_a']}"}
    headers_b = {"Authorization": f"Bearer {phase6_env['token_org_b']}"}

    up = client.post(
        "/api/v1/media/upload",
        headers=headers_a,
        data={"file": (io.BytesIO(VALID_PDF_BYTES), "secret_contract.pdf")},
        content_type="multipart/form-data",
    )
    assert up.status_code == 201
    media_doc = up.get_json()["media"]
    media_id = media_doc["media_id"]

    # Org B cannot read, download, delete, or attach Org A's media
    assert client.get(f"/api/v1/media/{media_id}", headers=headers_b).status_code == 404
    assert client.get(f"/api/v1/media/{media_id}/download", headers=headers_b).status_code == 404
    assert client.delete(f"/api/v1/media/{media_id}", headers=headers_b).status_code == 404

    msg_attempt = client.post(
        "/api/v1/messages/",
        headers=headers_b,
        json={
            "channel": "email",
            "recipient": "person@orgb.test",
            "data": {"subject": "Doc", "message": "Attached", "media_ids": [media_id]},
        },
    )
    assert msg_attempt.status_code in (400, 403, 404, 422)

    # Storage layer rejects cross-org storage key passed into WhatsApp/Teams media lookup
    with app.app_context():
        storage = LocalStorage(base_dir=app.config["MEDIA_LOCAL_STORAGE_DIR"])
        with pytest.raises(StorageSecurityError):
            storage.get_bytes(media_doc["storage_key"], organization_id=phase6_env["org_b"])

        wa_adapter = WhatsAppCloudAdapter(access_token="mock-token-123456", phone_number_id="123456789")
        # Attempting to upload resolved_media with another tenant's storage_key fails to read bytes
        with pytest.raises(ValueError):
            wa_adapter.send({
                "organization_id": phase6_env["org_b"],
                "recipient": "+14155550101",
                "data": {
                    "type": "document",
                    "resolved_media": [{"storage_key": media_doc["storage_key"], "filename": "secret_contract.pdf", "mime_type": "application/pdf"}],
                },
            })


# ===========================================================================
# 5. EMAIL HEADER INJECTION & CHANNEL CATALOG HONESTY
# ===========================================================================

def test_email_adapters_block_crlf_and_protected_header_overrides():
    sg = SendGridAdapter(api_key="SG.test_key", from_email="sender@example.test")
    ses = AmazonSESAdapter(aws_access_key_id="AKIA_TEST", aws_secret_access_key="SEC_TEST", from_email="sender@example.test")
    smtp = SMTPAdapter(smtp_host="localhost", from_email="sender@example.test")

    for adapter in (sg, ses, smtp):
        # CRLF in subject
        with pytest.raises(ValueError, match="Illegal newline"):
            adapter.format_message({
                "recipient": "user@example.test",
                "data": {"subject": "Hello\r\nBcc: attacker@evil.test", "message": "Body"},
            })

        # Protected header override
        with pytest.raises(ValueError, match="cannot be overridden"):
            adapter.format_message({
                "recipient": "user@example.test",
                "data": {
                    "subject": "Hello",
                    "message": "Body",
                    "headers": {"Bcc": "attacker@evil.test"},
                },
            })

        # CRLF in custom header value
        with pytest.raises(ValueError, match="Illegal newline"):
            adapter.format_message({
                "recipient": "user@example.test",
                "data": {
                    "subject": "Hello",
                    "message": "Body",
                    "headers": {"X-Custom": "ok\nBcc: attacker@evil.test"},
                },
            })


def test_telegram_mock_only_catalog_and_adapter_boundary(client, app):
    res = client.get("/api/v1/channels/")
    assert res.status_code == 200
    channels = res.get_json()["data"]
    assert channels["telegram"]["status"] == "mock_only"
    assert channels["telegram"]["providers"] == ["mock"]
    assert channels["microsoft_teams"]["status"] == "available"

    with app.app_context():
        mock_tg = AdapterRegistry.get_adapter(provider="mock", channel="telegram")
        assert isinstance(mock_tg, MockTelegramAdapter)

        with pytest.raises(ProviderResolutionError):
            AdapterRegistry.get_adapter(provider="telegram_bot_api", channel="telegram", organization_id="org-any")


def test_app_scoped_user_blocked_from_other_application_routes(client, phase6_env):
    app_headers = {"Authorization": f"Bearer {phase6_env['token_app_a']}"}
    other_app = phase6_env["app_b"]

    assert client.get(f"/api/v1/applications/{other_app}", headers=app_headers).status_code == 403
    assert client.patch(f"/api/v1/applications/{other_app}", headers=app_headers, json={"name": "Hijack"}).status_code == 403
    assert client.post(f"/api/v1/applications/{other_app}/deactivate", headers=app_headers).status_code == 403
    assert client.delete(f"/api/v1/applications/{other_app}", headers=app_headers).status_code == 403


def test_storage_signed_url_and_sandboxed_email_render(app, phase6_env):
    from app.adapters.email.email_utils import render_template

    # SandboxedEnvironment prevents unsafe attribute traversal in email_utils.render_template
    rendered = render_template("{{ ''.__class__.__mro__ }}", {"name": "Alice"})
    assert "builtins" not in rendered and "object" not in rendered

    storage = LocalStorage(base_dir=app.config["MEDIA_LOCAL_STORAGE_DIR"])
    key = f"orgs/{phase6_env['org_a']}/2026/11/doc.pdf"
    with pytest.raises(StorageSecurityError):
        storage.generate_signed_url(key, organization_id=phase6_env["org_b"])
    signed = storage.generate_signed_url(key, organization_id=phase6_env["org_a"])
    assert "sig=" in signed
