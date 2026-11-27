"""
Phase 1 Security & Backward-Compatibility Test Suite:
Multi-Tenant Provider Credential Isolation, Fail-Closed Resolution & MultiFernet Key Rotation.
Runs cleanly against isolated in-memory repositories (no real network/messages/live DB).
"""

import copy
import json
import os
import pytest
from cryptography.fernet import Fernet
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

from app.adapters.adapter_registry import AdapterRegistry
from app.adapters.errors import ProviderResolutionError
from app.adapters.email.sendgrid_adapter import SendGridAdapter
from app.adapters.sms.twilio_adapter import TwilioSMSAdapter
from app.adapters.teams.teams_adapter import MicrosoftTeamsAdapter
from app.adapters.whatsapp.cloud_adapter import WhatsAppCloudAdapter
from app.modules.provider_config.routes import provider_config_bp
from app.modules.provider_config.service import PlatformProviderPolicy, ProviderConfigService
from app.modules.whatsapp.encryption import WhatsAppEncryption
from app.modules.whatsapp.service import PlatformSettingsService, WhatsAppIntegrationService
from app.queue.tasks import process_message


class FakeCursor:
    """Minimal PyMongo cursor double supporting .sort(), .limit(), and iteration."""

    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, list):
            for field, order in reversed(key_or_list):
                self._docs.sort(key=lambda d: (d.get(field) is None, str(d.get(field, ""))), reverse=(order == -1))
        elif isinstance(key_or_list, str):
            self._docs.sort(
                key=lambda d: (d.get(key_or_list) is None, str(d.get(key_or_list, ""))),
                reverse=(direction == -1),
            )
        return self

    def limit(self, count):
        self._docs = self._docs[:count]
        return self

    def __iter__(self):
        return iter(self._docs)

    def __len__(self):
        return len(self._docs)


class FakeCollection:
    """Thread-safe minimal MongoDB collection double supporting query filters & updates."""

    def __init__(self, docs=None):
        self.docs = [copy.deepcopy(d) for d in (docs or [])]

    @staticmethod
    def _matches(doc, query):
        for key, val in (query or {}).items():
            if key == "$or":
                if not any(FakeCollection._matches(doc, branch) for branch in val):
                    return False
            elif isinstance(val, dict):
                if "$lt" in val:
                    if doc.get(key) is None or not (doc.get(key) < val["$lt"]):
                        return False
                if "$exists" in val:
                    exists = key in doc
                    if exists != bool(val["$exists"]):
                        return False
                if "$in" in val:
                    if doc.get(key) not in val["$in"]:
                        return False
                if "$ne" in val:
                    if doc.get(key) == val["$ne"]:
                        return False
            else:
                if doc.get(key) != val:
                    return False
        return True

    @staticmethod
    def _project(doc, projection):
        if doc is None or not projection:
            return copy.deepcopy(doc)
        include_fields = {k for k, v in projection.items() if v}
        exclude_fields = {k for k, v in projection.items() if v == 0}
        if include_fields:
            out = {k: copy.deepcopy(doc[k]) for k in include_fields if k in doc}
            if projection.get("_id", 1) != 0 and "_id" in doc:
                out["_id"] = doc["_id"]
            return out
        return {k: copy.deepcopy(v) for k, v in doc.items() if k not in exclude_fields}

    def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if self._matches(doc, query or {}):
                return self._project(doc, projection)
        return None

    def find(self, query=None, projection=None):
        return FakeCursor([
            self._project(doc, projection)
            for doc in self.docs
            if self._matches(doc, query or {})
        ])

    def update_one(self, query, update, upsert=False):
        class Result:
            def __init__(self, matched, modified):
                self.matched_count = matched
                self.modified_count = modified

        for idx, doc in enumerate(self.docs):
            if self._matches(doc, query):
                updated = copy.deepcopy(doc)
                if "$set" in update:
                    updated.update(copy.deepcopy(update["$set"]))
                if "$unset" in update:
                    for k in update["$unset"]:
                        updated.pop(k, None)
                if "$push" in update:
                    for k, v in update["$push"].items():
                        updated.setdefault(k, []).append(copy.deepcopy(v))
                self.docs[idx] = updated
                return Result(1, 1)

        if upsert:
            new_doc = {k: v for k, v in (query or {}).items() if not isinstance(v, dict)}
            if "$set" in update:
                new_doc.update(copy.deepcopy(update["$set"]))
            self.docs.append(new_doc)
            return Result(0, 1)

        return Result(0, 0)


class FakeMongoDB:
    def __init__(self):
        self.collections = {
            "provider_configs": FakeCollection(),
            "organizations": FakeCollection(),
            "whatsapp_integrations": FakeCollection(),
            "platform_settings": FakeCollection(),
            "messages": FakeCollection(),
            "users": FakeCollection(),
            "roles": FakeCollection(),
        }

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


def _build_isolated_app(primary_key=None, previous_keys=None):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["APP_ENV"] = "test"
    app.config["JWT_SECRET_KEY"] = "test-jwt-secret-key-32bytes-minimum"
    app.config["CREDENTIAL_ENCRYPTION_KEY"] = primary_key or Fernet.generate_key().decode("ascii")
    if previous_keys is not None:
        app.config["CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS"] = previous_keys
    app.mongo_db = FakeMongoDB()
    JWTManager(app)
    app.register_blueprint(provider_config_bp, url_prefix="/api/v1/provider-config")
    return app


def test_org_a_cannot_use_org_b_provider_credentials():
    app = _build_isolated_app()
    with app.app_context():
        app.mongo_db["organizations"].docs.extend([
            {"organization_id": "org-a", "name": "Org A", "status": "ACTIVE"},
            {"organization_id": "org-b", "name": "Org B", "status": "ACTIVE"},
        ])
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "SG.org_a_key", "from_email": "noreply@org-a.test"},
            organization_id="org-a",
        )
        ProviderConfigService.save_configuration(
            "twilio",
            {"account_sid": "AC_ORG_B_111111111111111111111111", "auth_token": "tok_b", "from_number": "+15005550006"},
            organization_id="org-b",
        )

        # Org A succeeds with its own SendGrid adapter
        sg = AdapterRegistry.get_adapter("sendgrid", channel="email", organization_id="org-a")
        assert isinstance(sg, SendGridAdapter)
        assert sg._api_key == "SG.org_a_key"

        # Org A MUST NOT resolve Org B's Twilio credentials
        with pytest.raises(ProviderResolutionError) as exc:
            AdapterRegistry.get_adapter("twilio", channel="sms", organization_id="org-a")
        assert exc.value.code == ProviderResolutionError.PROVIDER_NOT_CONFIGURED

        # Org B MUST NOT resolve Org A's SendGrid credentials
        with pytest.raises(ProviderResolutionError) as exc_b:
            AdapterRegistry.get_adapter("sendgrid", channel="email", organization_id="org-b")
        assert exc_b.value.code == ProviderResolutionError.PROVIDER_NOT_CONFIGURED


def test_missing_org_credentials_never_fallback_to_env(monkeypatch):
    app = _build_isolated_app()
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.global_platform_env_secret")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "global@platform.test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_GLOBAL_ENV")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "SECRET_GLOBAL_ENV")
    monkeypatch.setenv("AWS_SES_FROM_EMAIL", "global-ses@platform.test")
    monkeypatch.setenv("SMTP_HOST", "smtp.global.test")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "global-smtp@platform.test")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_GLOBAL_ENV")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "TOKEN_GLOBAL_ENV")
    monkeypatch.setenv("TWILIO_FROM_NUMBER", "+15005550009")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "EAAG_GLOBAL_WA")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "999888777")
    monkeypatch.setenv("TEAMS_TENANT_ID", "global-tenant")
    monkeypatch.setenv("TEAMS_CLIENT_ID", "global-client")
    monkeypatch.setenv("TEAMS_CLIENT_SECRET", "global-secret")

    with app.app_context():
        app.mongo_db["organizations"].docs.append(
            {"organization_id": "org-empty", "name": "Empty Org", "status": "ACTIVE"}
        )
        for prov, chan in (
            ("sendgrid", "email"),
            ("ses", "email"),
            ("smtp", "email"),
            ("twilio", "sms"),
            ("whatsapp", "whatsapp"),
            ("teams", "teams"),
        ):
            with pytest.raises(ProviderResolutionError) as exc:
                AdapterRegistry.get_adapter(prov, channel=chan, organization_id="org-empty")
            assert exc.value.code == ProviderResolutionError.PROVIDER_NOT_CONFIGURED

        # Explicit platform-level call (`organization_id=None`, e.g., OTPService) still works
        plat_adapter = AdapterRegistry.get_adapter("sendgrid", channel="email", organization_id=None)
        assert isinstance(plat_adapter, SendGridAdapter)
        assert plat_adapter._api_key == "SG.global_platform_env_secret"


def test_platform_credentials_require_explicit_authorization():
    app = _build_isolated_app()
    with app.app_context():
        app.mongo_db["organizations"].docs.extend([
            {"organization_id": "org-denied", "name": "Denied Org", "status": "ACTIVE"},
            {
                "organization_id": "org-allowed",
                "name": "Allowed Org",
                "status": "ACTIVE",
                "authorized_platform_providers": ["sendgrid"],
            },
        ])
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "SG.platform_key", "from_email": "platform@senderx.test"},
            organization_id=None,
        )

        # Without explicit allow_platform_fallback flag: fails closed as NOT_CONFIGURED
        with pytest.raises(ProviderResolutionError) as exc:
            AdapterRegistry.get_adapter("sendgrid", channel="email", organization_id="org-denied")
        assert exc.value.code == ProviderResolutionError.PROVIDER_NOT_CONFIGURED

        # With allow_platform_fallback=True but no PlatformProviderPolicy authorization: PROVIDER_NOT_AUTHORIZED
        with pytest.raises(ProviderResolutionError) as exc_unauth:
            AdapterRegistry.get_adapter(
                "sendgrid",
                channel="email",
                organization_id="org-denied",
                allow_platform_fallback=True,
            )
        assert exc_unauth.value.code == ProviderResolutionError.PROVIDER_NOT_AUTHORIZED

        # Status lookup for org-denied must NOT claim platform provider is configured
        assert ProviderConfigService.get_configuration_status("sendgrid", organization_id="org-denied") is None

        # Explicitly authorized organization succeeds with platform config
        assert PlatformProviderPolicy.is_authorized("org-allowed", provider="sendgrid", channel="email") is True
        authorized_adapter = AdapterRegistry.get_adapter(
            "sendgrid",
            channel="email",
            organization_id="org-allowed",
            allow_platform_fallback=True,
        )
        assert isinstance(authorized_adapter, SendGridAdapter)
        assert authorized_adapter._api_key == "SG.platform_key"


def test_inactive_provider_configuration_fails_closed():
    app = _build_isolated_app()
    with app.app_context():
        app.mongo_db["organizations"].docs.append(
            {"organization_id": "org-inactive-prov", "name": "Org Inactive", "status": "ACTIVE"}
        )
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "SG.org_key", "from_email": "noreply@org.test"},
            organization_id="org-inactive-prov",
        )
        ProviderConfigService.set_configuration_active_state(
            "sendgrid",
            is_active=False,
            organization_id="org-inactive-prov",
        )

        with pytest.raises(ProviderResolutionError) as exc:
            AdapterRegistry.get_adapter("sendgrid", channel="email", organization_id="org-inactive-prov")
        assert exc.value.code == ProviderResolutionError.PROVIDER_INACTIVE

        # Re-activating restores dispatch cleanly with existing credentials preserved
        ProviderConfigService.set_configuration_active_state(
            "sendgrid",
            is_active=True,
            organization_id="org-inactive-prov",
        )
        restored = AdapterRegistry.get_adapter("sendgrid", channel="email", organization_id="org-inactive-prov")
        assert isinstance(restored, SendGridAdapter)
        assert restored._api_key == "SG.org_key"


def test_ambiguous_provider_and_channel_mismatch_fail_closed():
    app = _build_isolated_app()
    with app.app_context():
        app.mongo_db["organizations"].docs.append(
            {"organization_id": "org-multi-email", "name": "Multi Email", "status": "ACTIVE"}
        )
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "SG.key1", "from_email": "a@org.test"},
            organization_id="org-multi-email",
        )
        ProviderConfigService.save_configuration(
            "smtp",
            {"smtp_host": "smtp.org.test", "from_email": "b@org.test"},
            organization_id="org-multi-email",
        )

        # Omitted provider with >1 active email provider -> AMBIGUOUS_PROVIDER_CONFIGURATION
        with pytest.raises(ProviderResolutionError) as exc:
            AdapterRegistry.get_adapter(provider=None, channel="email", organization_id="org-multi-email")
        assert exc.value.code == ProviderResolutionError.AMBIGUOUS_PROVIDER_CONFIGURATION

        # Channel/provider mismatch -> CHANNEL_PROVIDER_MISMATCH
        with pytest.raises(ProviderResolutionError) as exc_mismatch:
            AdapterRegistry.get_adapter(provider="sendgrid", channel="sms", organization_id="org-multi-email")
        assert exc_mismatch.value.code == ProviderResolutionError.CHANNEL_PROVIDER_MISMATCH


def test_whatsapp_integration_selection_and_isolation():
    app = _build_isolated_app()
    with app.app_context():
        app.mongo_db["organizations"].docs.extend([
            {"organization_id": "org-wa-1", "name": "WA 1", "status": "ACTIVE"},
            {"organization_id": "org-wa-2", "name": "WA 2", "status": "ACTIVE"},
        ])
        meta_secret_enc, _ = WhatsAppEncryption.encrypt_secret("meta_app_secret_123456")
        app.mongo_db["platform_settings"].docs.append({
            "setting_key": "meta_whatsapp",
            "meta_app_id": "1234567890",
            "encrypted_app_secret": meta_secret_enc,
            "graph_api_version": "v21.0",
        })
        tok_1, kv = WhatsAppEncryption.encrypt_token("EAAG_TOKEN_WA_1_ABCDE")
        tok_2, _ = WhatsAppEncryption.encrypt_token("EAAG_TOKEN_WA_2_VWXYZ")
        tok_3, _ = WhatsAppEncryption.encrypt_token("EAAG_TOKEN_WA_3_OTHER")

        app.mongo_db["whatsapp_integrations"].docs.extend([
            {
                "integration_id": "wa-int-1",
                "organization_id": "org-wa-1",
                "waba_id": "waba-1",
                "phone_number_id": "phone-1",
                "display_phone_number": "+15550001",
                "encrypted_access_token": tok_1,
                "key_version": kv,
                "status": "CONNECTED",
                "deleted_at": None,
            },
            {
                "integration_id": "wa-int-2",
                "organization_id": "org-wa-1",
                "waba_id": "waba-1",
                "phone_number_id": "phone-2",
                "display_phone_number": "+15550002",
                "encrypted_access_token": tok_2,
                "key_version": kv,
                "status": "CONNECTED",
                "deleted_at": None,
            },
            {
                "integration_id": "wa-int-other",
                "organization_id": "org-wa-2",
                "waba_id": "waba-2",
                "phone_number_id": "phone-other",
                "display_phone_number": "+15559999",
                "encrypted_access_token": tok_3,
                "key_version": kv,
                "status": "CONNECTED",
                "deleted_at": None,
            },
        ])

        # Ambiguous when multiple active WhatsApp integrations exist and no sender specified
        with pytest.raises(ProviderResolutionError) as exc_ambig:
            AdapterRegistry.get_adapter(provider="whatsapp", channel="whatsapp", organization_id="org-wa-1")
        assert exc_ambig.value.code == ProviderResolutionError.AMBIGUOUS_PROVIDER_CONFIGURATION

        # Explicit integration_id resolves exact sender cleanly
        adapter_2 = AdapterRegistry.get_adapter(
            provider="whatsapp",
            channel="whatsapp",
            organization_id="org-wa-1",
            integration_id="wa-int-2",
        )
        assert isinstance(adapter_2, WhatsAppCloudAdapter)
        assert adapter_2.phone_number_id == "phone-2"

        # Single active integration auto-resolves even if provider omitted
        adapter_other = AdapterRegistry.get_adapter(
            provider=None,
            channel="whatsapp",
            organization_id="org-wa-2",
        )
        assert isinstance(adapter_other, WhatsAppCloudAdapter)
        assert adapter_other.phone_number_id == "phone-other"

        # Cross-tenant integration ID blocked with PROVIDER_NOT_AUTHORIZED
        with pytest.raises(ProviderResolutionError) as exc_cross:
            WhatsAppIntegrationService.resolve_credentials_for_dispatch(
                organization_id="org-wa-1",
                integration_id="wa-int-other",
            )
        assert exc_cross.value.code == ProviderResolutionError.PROVIDER_NOT_AUTHORIZED


def test_multifernet_rotation_backward_compatibility_and_failure():
    old_key = Fernet.generate_key().decode("ascii")
    new_key = Fernet.generate_key().decode("ascii")

    # Save legacy record with old_key
    old_app = _build_isolated_app(primary_key=old_key)
    with old_app.app_context():
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "SG.legacy_secret_value", "from_email": "legacy@org.test"},
            organization_id="org-rotate",
        )
        legacy_doc = copy.deepcopy(old_app.mongo_db["provider_configs"].docs[0])

    # Read with new primary key + old key in CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS
    rotated_app = _build_isolated_app(primary_key=new_key, previous_keys=old_key)
    rotated_app.mongo_db["provider_configs"].docs.append(copy.deepcopy(legacy_doc))

    with rotated_app.app_context():
        decrypted = ProviderConfigService.get_decrypted_configuration("sendgrid", organization_id="org-rotate")
        assert decrypted == {"api_key": "SG.legacy_secret_value", "from_email": "legacy@org.test"}

        # Saving/updating must re-encrypt using the CURRENT primary key (new_key)
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"from_email": "updated@org.test"},
            organization_id="org-rotate",
        )
        new_ciphertext = rotated_app.mongo_db["provider_configs"].docs[0]["credentials"]
        assert "SG.legacy_secret_value" not in new_ciphertext
        assert rotated_app.mongo_db["provider_configs"].docs[0]["key_version"] == "v1"

        # Old key alone can no longer decrypt the newly encrypted ciphertext, proving primary key was used
        decrypted_with_new_only = json.loads(Fernet(new_key.encode("utf-8")).decrypt(new_ciphertext.encode("utf-8")).decode("utf-8"))
        assert decrypted_with_new_only["api_key"] == "SG.legacy_secret_value"
        assert decrypted_with_new_only["from_email"] == "updated@org.test"

    # Without previous key, corrupt/wrong-key ciphertext fails closed with CREDENTIAL_DECRYPTION_FAILED
    wrong_key_app = _build_isolated_app(primary_key=Fernet.generate_key().decode("ascii"))
    wrong_key_app.mongo_db["provider_configs"].docs.append(copy.deepcopy(legacy_doc))
    with wrong_key_app.app_context():
        with pytest.raises(ProviderResolutionError) as exc_dec:
            AdapterRegistry.get_adapter("sendgrid", channel="email", organization_id="org-rotate")
        assert exc_dec.value.code == ProviderResolutionError.CREDENTIAL_DECRYPTION_FAILED
        assert "SG.legacy_secret_value" not in str(exc_dec.value)
        assert old_key not in str(exc_dec.value)


def test_unauthorized_user_cannot_access_other_org_configuration(monkeypatch):
    app = _build_isolated_app()

    with app.app_context():
        app.mongo_db["organizations"].docs.extend([
            {"organization_id": "org-1", "name": "Org 1", "status": "ACTIVE"},
            {"organization_id": "org-2", "name": "Org 2", "status": "ACTIVE"},
        ])
        app.mongo_db["roles"].docs.append({
            "role_id": "r1",
            "organization_id": "org-1",
            "name": "Provider Manager",
            "scope": "ORGANIZATION",
            "permissions": ["organization:providers:read", "organization:providers:manage"],
        })
        app.mongo_db["users"].docs.append({
            "user_id": "user-org-1",
            "organization_id": "org-1",
            "email": "u1@org1.test",
            "is_active": True,
            "status": "ACTIVE",
            "token_version": 1,
            "role_ids": ["r1"],
        })
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "SG.org2_secret_never_leak", "from_email": "u@org2.test"},
            organization_id="org-2",
        )
        token = create_access_token(
            identity="user-org-1",
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": "org-1", "token_version": 1},
        )

    from app.modules.organizations.repository import OrganizationRepository
    from app.modules.organizations.role_repository import RoleRepository
    from app.modules.users.repository import UserRepository

    monkeypatch.setattr(UserRepository, "find_by_id", classmethod(lambda cls, uid, **kw: app.mongo_db["users"].find_one({"user_id": uid})))
    monkeypatch.setattr(OrganizationRepository, "find_by_id", classmethod(lambda cls, oid, **kw: app.mongo_db["organizations"].find_one({"organization_id": oid})))
    monkeypatch.setattr(RoleRepository, "find_by_id", classmethod(lambda cls, rid, **kw: app.mongo_db["roles"].find_one({"role_id": rid})))

    client = app.test_client()
    # User from org-1 querying sendgrid sees 404 (cannot see org-2's config)
    res = client.get("/api/v1/provider-config/organization?provider=sendgrid", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404
    assert "SG.org2_secret_never_leak" not in str(res.get_json())

    # User from org-1 calling list sees empty (no org-2 leakage)
    res_list = client.get("/api/v1/provider-config/organization", headers={"Authorization": f"Bearer {token}"})
    assert res_list.status_code == 200
    assert res_list.get_json()["data"] == []

    # User from org-1 cannot access SUPER_ADMIN platform configs
    res_plat = client.get("/api/v1/provider-config/", headers={"Authorization": f"Bearer {token}"})
    assert res_plat.status_code == 403


def test_celery_process_message_fails_closed_without_org_credentials():
    app = _build_isolated_app()
    with app.app_context():
        app.mongo_db["organizations"].docs.append(
            {"organization_id": "org-worker", "name": "Worker Org", "status": "ACTIVE"}
        )
        app.mongo_db["messages"].docs.append({
            "message_id": "msg-isolated-1",
            "organization_id": "org-worker",
            "channel": "email",
            "provider": "sendgrid",
            "recipient": "user@example.test",
            "data": {"subject": "Test", "message": "Hello"},
            "status": "QUEUED",
            "retry_count": 0,
            "status_history": [],
        })

        result = process_message("msg-isolated-1")
        assert result["success"] is False
        assert result["status"] == "FAILED"
        assert result.get("error_code") == ProviderResolutionError.PROVIDER_NOT_CONFIGURED
        updated = app.mongo_db["messages"].find_one({"message_id": "msg-isolated-1"})
        assert updated["status"] == "FAILED"
        assert "[PROVIDER_NOT_CONFIGURED]" in updated["last_error"]


def test_blank_organization_id_cannot_escalate_to_platform_scope():
    app = _build_isolated_app()
    with app.app_context():
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "SG.plat_secret", "from_email": "plat@senderx.test"},
            organization_id=None,
        )
        for bad_org in ("", "   ", 123):
            with pytest.raises(ProviderResolutionError) as exc:
                AdapterRegistry.get_adapter("sendgrid", channel="email", organization_id=bad_org)
            assert exc.value.code == ProviderResolutionError.PROVIDER_NOT_AUTHORIZED
