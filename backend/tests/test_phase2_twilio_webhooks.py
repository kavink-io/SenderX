"""
Phase 2 Security & Delivery Safety Test Suite:
Twilio Webhook Signature Verification, Reverse Proxy Hardening, Tenant-Safe
Message Resolution, Status Lifecycle Protection & Audit Sanitization.
Runs cleanly offline against in-memory doubles (no real network/SMS/DB required).
"""

import copy
import logging
import os
import pytest
from cryptography.fernet import Fernet
from flask import Flask
from twilio.request_validator import RequestValidator

from app.modules.messages.repository import MessageRepository
from app.modules.messages.routes import messages_bp
from app.modules.messages.twilio_webhook import account_sid_digest
from app.modules.provider_config.service import ProviderConfigService


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key_or_list, direction=None):
        return self

    def limit(self, count):
        self._docs = self._docs[:count]
        return self

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = [copy.deepcopy(d) for d in (docs or [])]

    @staticmethod
    def _matches(doc, query):
        for key, val in (query or {}).items():
            if key == "$or":
                if not any(FakeCollection._matches(doc, branch) for branch in val):
                    return False
            elif isinstance(val, dict):
                if "$exists" in val:
                    exists = key in doc
                    if exists != bool(val["$exists"]):
                        return False
                if "$ne" in val:
                    if doc.get(key) == val["$ne"]:
                        return False
                if "$in" in val:
                    if doc.get(key) not in val["$in"]:
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

    def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

        class Result:
            inserted_id = "fake"

        return Result()

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
        self._cols = {
            "organizations": FakeCollection(),
            "provider_configs": FakeCollection(),
            "messages": FakeCollection(),
            "security_audit_logs": FakeCollection(),
        }

    def list_collection_names(self):
        return list(self._cols.keys())

    def __getitem__(self, name):
        if name not in self._cols:
            self._cols[name] = FakeCollection()
        return self._cols[name]


def _build_app(key=None, extra_config=None):
    enc_key = key or Fernet.generate_key().decode("ascii")
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["APP_ENV"] = "production"
    app.config["SECRET_KEY"] = "phase2-test-secret"
    app.config["CREDENTIAL_ENCRYPTION_KEY"] = enc_key
    app.config["CREDENTIAL_ENCRYPTION_PREVIOUS_KEYS"] = ""
    app.config["CREDENTIAL_ENCRYPTION_KEY_VERSION"] = "v1"
    app.config["PUBLIC_BASE_URL"] = None
    app.config["WEBHOOK_PUBLIC_BASE_URL"] = None
    app.config["TRUST_PROXY_HEADERS"] = False
    app.config["TRUSTED_PROXY_IPS"] = ["127.0.0.1", "::1"]
    app.config["TRUSTED_FORWARDED_HOSTS"] = []
    if extra_config:
        app.config.update(extra_config)

    app.mongo_db = FakeMongoDB()
    app.register_blueprint(messages_bp, url_prefix="/api/v1/messages")
    return app


def _seed_org_with_twilio(app, org_id, account_sid, auth_token, active=True, from_number="+14155550001"):
    app.mongo_db["organizations"].docs.append({
        "organization_id": org_id,
        "name": f"Org {org_id}",
        "status": "ACTIVE",
    })
    ProviderConfigService.save_configuration(
        "twilio",
        {
            "account_sid": account_sid,
            "auth_token": auth_token,
            "from_number": from_number,
        },
        organization_id=org_id,
        active=active,
    )
    return ProviderConfigService.get_configuration_status("twilio", organization_id=org_id)


def _seed_sent_sms(app, org_id, message_id, provider_msg_id, recipient="+14155552671", config_id=None, sid=None, status="SENT"):
    doc = {
        "message_id": message_id,
        "organization_id": org_id,
        "channel": "sms",
        "provider": "twilio",
        "provider_message_id": provider_msg_id,
        "recipient": recipient,
        "data": {"message": "Hello phase 2"},
        "status": status,
        "status_history": [
            {"from": "PROCESSING", "to": status, "timestamp": "2026-11-27T00:00:00+00:00"}
        ],
    }
    if config_id:
        doc["provider_config_id"] = config_id
    if sid:
        doc["provider_account_sid_digest"] = account_sid_digest(sid)
    app.mongo_db["messages"].insert_one(doc)


def _sign_twilio_form(url, params, auth_token):
    return RequestValidator(auth_token).compute_signature(url, params)


# 1. Valid Twilio signature (both /webhook/twilio and /callbacks/twilio)
@pytest.mark.parametrize("path", ["/api/v1/messages/webhook/twilio", "/api/v1/messages/callbacks/twilio"])
def test_valid_twilio_signature_updates_message(path):
    app = _build_app()
    sid_a = "AC" + "a" * 32
    tok_a = "auth_token_secret_org_a_123456"

    with app.app_context():
        cfg = _seed_org_with_twilio(app, "org-a", sid_a, tok_a)
        _seed_sent_sms(app, "org-a", "msg-1", "SM1001", config_id=cfg["config_id"], sid=sid_a)

    form = {
        "AccountSid": sid_a,
        "MessageSid": "SM1001",
        "MessageStatus": "delivered",
        "To": "+14155552671",
        "From": "+14155550001",
    }
    sig = _sign_twilio_form(f"http://localhost{path}", form, tok_a)

    client = app.test_client()
    res = client.post(path, data=form, headers={"X-Twilio-Signature": sig})
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["status"] == "DELIVERED"
    assert body["updated"] is True

    with app.app_context():
        stored = MessageRepository.find_by_id("msg-1", organization_id="org-a")
        assert stored["status"] == "DELIVERED"
        assert stored["provider_status"] == "delivered"


# 2. Missing signature
@pytest.mark.parametrize("path", ["/api/v1/messages/webhook/twilio", "/api/v1/messages/callbacks/twilio"])
def test_missing_twilio_signature_rejected(path):
    app = _build_app()
    sid_a = "AC" + "a" * 32
    tok_a = "auth_token_secret_org_a_123456"

    with app.app_context():
        cfg = _seed_org_with_twilio(app, "org-a", sid_a, tok_a)
        _seed_sent_sms(app, "org-a", "msg-1", "SM1001", config_id=cfg["config_id"], sid=sid_a)

    client = app.test_client()
    res = client.post(
        path,
        data={"AccountSid": sid_a, "MessageSid": "SM1001", "MessageStatus": "delivered"},
    )
    assert res.status_code == 401
    assert res.get_json()["error_code"] == "MISSING_SIGNATURE"

    with app.app_context():
        assert MessageRepository.find_by_id("msg-1", organization_id="org-a")["status"] == "SENT"


# 3. Invalid signature (bad value & parameter tampering)
def test_invalid_twilio_signature_and_tampered_params_rejected(caplog):
    app = _build_app()
    sid_a = "AC" + "a" * 32
    tok_a = "auth_token_secret_org_a_123456"

    with app.app_context():
        cfg = _seed_org_with_twilio(app, "org-a", sid_a, tok_a)
        _seed_sent_sms(app, "org-a", "msg-1", "SM1001", config_id=cfg["config_id"], sid=sid_a)

    orig_form = {
        "AccountSid": sid_a,
        "MessageSid": "SM1001",
        "MessageStatus": "delivered",
        "To": "+14155552671",
    }
    valid_sig = _sign_twilio_form("http://localhost/api/v1/messages/callbacks/twilio", orig_form, tok_a)
    tampered_form = dict(orig_form, MessageStatus="failed", ErrorCode="30008")

    client = app.test_client()
    with caplog.at_level(logging.WARNING):
        res_bad = client.post(
            "/api/v1/messages/callbacks/twilio",
            data=orig_form,
            headers={"X-Twilio-Signature": "forged_sig_value_should_never_log"},
        )
        res_tamper = client.post(
            "/api/v1/messages/callbacks/twilio",
            data=tampered_form,
            headers={"X-Twilio-Signature": valid_sig},
        )

    assert res_bad.status_code == 401
    assert res_bad.get_json()["error_code"] == "INVALID_SIGNATURE"
    assert res_tamper.status_code == 401
    assert res_tamper.get_json()["error_code"] == "INVALID_SIGNATURE"

    # Security rule: never leak auth_token, signature, or full payload in logs or audit table
    log_text = caplog.text + str(app.mongo_db["security_audit_logs"].docs)
    assert tok_a not in log_text
    assert "forged_sig_value_should_never_log" not in log_text
    assert valid_sig not in log_text


# 4. Incorrect Auth Token (including signing with Org B token or env TWILIO_AUTH_TOKEN)
def test_incorrect_auth_token_and_no_env_fallback(monkeypatch):
    app = _build_app()
    sid_a = "AC" + "a" * 32
    tok_a = "real_org_a_token_secret"
    sid_b = "AC" + "b" * 32
    tok_b = "real_org_b_token_secret"
    global_env_tok = "global_env_token_must_not_work"
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", global_env_tok)

    with app.app_context():
        _seed_org_with_twilio(app, "org-a", sid_a, tok_a)
        _seed_org_with_twilio(app, "org-b", sid_b, tok_b)
        _seed_sent_sms(app, "org-a", "msg-a", "SM_A_1", sid=sid_a)

    form = {"AccountSid": sid_a, "MessageSid": "SM_A_1", "MessageStatus": "delivered"}
    url = "http://localhost/api/v1/messages/callbacks/twilio"

    client = app.test_client()
    for bad_token in (tok_b, global_env_tok, "totally_wrong_token"):
        sig = _sign_twilio_form(url, form, bad_token)
        res = client.post(
            "/api/v1/messages/callbacks/twilio",
            data=form,
            headers={"X-Twilio-Signature": sig},
        )
        assert res.status_code == 401
        assert res.get_json()["error_code"] == "INVALID_SIGNATURE"

    with app.app_context():
        assert MessageRepository.find_by_id("msg-a", organization_id="org-a")["status"] == "SENT"


# 5. Incorrect callback URL (path mismatch / query mismatch)
def test_incorrect_callback_url_rejected():
    app = _build_app()
    sid_a = "AC" + "a" * 32
    tok_a = "auth_token_secret_org_a_123456"

    with app.app_context():
        _seed_org_with_twilio(app, "org-a", sid_a, tok_a)
        _seed_sent_sms(app, "org-a", "msg-1", "SM1001", sid=sid_a)

    form = {"AccountSid": sid_a, "MessageSid": "SM1001", "MessageStatus": "delivered"}
    # Signed for /webhook/twilio, replayed to /callbacks/twilio
    wrong_path_sig = _sign_twilio_form("http://localhost/api/v1/messages/webhook/twilio", form, tok_a)
    wrong_host_sig = _sign_twilio_form("https://other.domain.test/api/v1/messages/callbacks/twilio", form, tok_a)

    client = app.test_client()
    r1 = client.post("/api/v1/messages/callbacks/twilio", data=form, headers={"X-Twilio-Signature": wrong_path_sig})
    r2 = client.post("/api/v1/messages/callbacks/twilio", data=form, headers={"X-Twilio-Signature": wrong_host_sig})
    assert r1.status_code == 401
    assert r2.status_code == 401


# 6. Unknown Twilio account (even when env vars configured)
def test_unknown_twilio_account_rejected(monkeypatch):
    app = _build_app()
    unknown_sid = "AC" + "9" * 32
    env_token = "env_fallback_should_never_authenticate_unknown"
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", unknown_sid)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", env_token)

    form = {"AccountSid": unknown_sid, "MessageSid": "SM999", "MessageStatus": "delivered"}
    sig = _sign_twilio_form("http://localhost/api/v1/messages/callbacks/twilio", form, env_token)

    client = app.test_client()
    res = client.post("/api/v1/messages/callbacks/twilio", data=form, headers={"X-Twilio-Signature": sig})
    assert res.status_code == 401
    assert res.get_json()["error_code"] == "UNKNOWN_TWILIO_ACCOUNT"


# 7. Cross-tenant MessageSid attempts
def test_cross_tenant_messagesid_attempt_blocked():
    app = _build_app()
    sid_a = "AC" + "a" * 32
    tok_a = "token_org_a_secret"
    sid_b = "AC" + "b" * 32
    tok_b = "token_org_b_secret"

    with app.app_context():
        cfg_a = _seed_org_with_twilio(app, "org-a", sid_a, tok_a)
        _seed_org_with_twilio(app, "org-b", sid_b, tok_b)
        _seed_sent_sms(app, "org-a", "msg-secret-a", "SM_SHARED_OR_TARGET", config_id=cfg_a["config_id"], sid=sid_a)

    # Org B legitimately signs a callback referencing Org A's MessageSid
    form = {
        "AccountSid": sid_b,
        "MessageSid": "SM_SHARED_OR_TARGET",
        "MessageStatus": "failed",
        "ErrorCode": "30008",
    }
    sig_b = _sign_twilio_form("http://localhost/api/v1/messages/callbacks/twilio", form, tok_b)

    client = app.test_client()
    res = client.post("/api/v1/messages/callbacks/twilio", data=form, headers={"X-Twilio-Signature": sig_b})
    assert res.status_code == 404
    assert res.get_json()["error_code"] == "MESSAGE_NOT_FOUND"

    # Org A's message must remain untouched
    with app.app_context():
        doc_a = MessageRepository.find_by_id("msg-secret-a", organization_id="org-a")
        assert doc_a["status"] == "SENT"
        assert "delivery_error_code" not in doc_a


# 8. Duplicate callbacks handled idempotently without duplicating status_history
def test_duplicate_twilio_callbacks_are_idempotent():
    app = _build_app()
    sid_a = "AC" + "a" * 32
    tok_a = "token_org_a_secret"

    with app.app_context():
        cfg_a = _seed_org_with_twilio(app, "org-a", sid_a, tok_a)
        _seed_sent_sms(app, "org-a", "msg-dup", "SM_DUP_1", config_id=cfg_a["config_id"], sid=sid_a)

    form = {"AccountSid": sid_a, "MessageSid": "SM_DUP_1", "MessageStatus": "delivered", "To": "+14155552671"}
    sig = _sign_twilio_form("http://localhost/api/v1/messages/callbacks/twilio", form, tok_a)
    client = app.test_client()

    r1 = client.post("/api/v1/messages/callbacks/twilio", data=form, headers={"X-Twilio-Signature": sig})
    r2 = client.post("/api/v1/messages/callbacks/twilio", data=form, headers={"X-Twilio-Signature": sig})

    assert r1.status_code == 200
    assert r1.get_json()["updated"] is True
    assert r2.status_code == 200
    assert r2.get_json()["updated"] is False
    assert r2.get_json()["duplicate"] is True

    with app.app_context():
        doc = MessageRepository.find_by_id("msg-dup", organization_id="org-a")
        assert doc["status"] == "DELIVERED"
        assert len(doc["status_history"]) == 2  # initial SENT + single DELIVERED


# 9. Status regression & forged failure attempts rejected
def test_status_regression_and_forged_failure_rejected():
    app = _build_app()
    sid_a = "AC" + "a" * 32
    tok_a = "token_org_a_secret"

    with app.app_context():
        cfg_a = _seed_org_with_twilio(app, "org-a", sid_a, tok_a)
        _seed_sent_sms(app, "org-a", "msg-deliv", "SM_DELIV", config_id=cfg_a["config_id"], sid=sid_a, status="DELIVERED")
        _seed_sent_sms(app, "org-a", "msg-fail", "SM_FAIL", config_id=cfg_a["config_id"], sid=sid_a, status="FAILED")

    client = app.test_client()
    url = "http://localhost/api/v1/messages/callbacks/twilio"

    for sid_msg, bad_status in (
        ("SM_DELIV", "sent"),
        ("SM_DELIV", "queued"),
        ("SM_DELIV", "failed"),
        ("SM_DELIV", "undelivered"),
        ("SM_FAIL", "sent"),
        ("SM_FAIL", "delivered"),
    ):
        form = {"AccountSid": sid_a, "MessageSid": sid_msg, "MessageStatus": bad_status}
        sig = _sign_twilio_form(url, form, tok_a)
        res = client.post("/api/v1/messages/callbacks/twilio", data=form, headers={"X-Twilio-Signature": sig})
        assert res.status_code == 409
        assert res.get_json()["updated"] is False
        assert res.get_json()["error_code"] == "INVALID_STATUS_TRANSITION"

    # Arbitrary unsupported status string also rejected cleanly (400)
    bad_enum_form = {"AccountSid": sid_a, "MessageSid": "SM_DELIV", "MessageStatus": "spoofed_state"}
    bad_enum_sig = _sign_twilio_form(url, bad_enum_form, tok_a)
    res_bad_enum = client.post("/api/v1/messages/callbacks/twilio", data=bad_enum_form, headers={"X-Twilio-Signature": bad_enum_sig})
    assert res_bad_enum.status_code == 400
    assert res_bad_enum.get_json()["error_code"] == "INVALID_TWILIO_STATUS"

    with app.app_context():
        assert MessageRepository.find_by_id("msg-deliv", organization_id="org-a")["status"] == "DELIVERED"
        assert MessageRepository.find_by_id("msg-fail", organization_id="org-a")["status"] == "FAILED"


# 10. Valid delivery lifecycle, identity check & ambiguous MessageSid detection
def test_valid_delivery_lifecycle_and_ambiguous_or_identity_mismatch():
    app = _build_app()
    sid_a = "AC" + "a" * 32
    tok_a = "token_org_a_secret"

    with app.app_context():
        cfg_a = _seed_org_with_twilio(app, "org-a", sid_a, tok_a)
        _seed_sent_sms(app, "org-a", "msg-ok", "SM_LIFE_1", recipient="+14155552671", config_id=cfg_a["config_id"], sid=sid_a, status="PROCESSING")
        _seed_sent_sms(app, "org-a", "msg-dup-1", "SM_MULTI", config_id=cfg_a["config_id"], sid=sid_a)
        _seed_sent_sms(app, "org-a", "msg-dup-2", "SM_MULTI", config_id=cfg_a["config_id"], sid=sid_a)

    client = app.test_client()
    url = "http://localhost/api/v1/messages/callbacks/twilio"

    # Untrusted recipient mismatch blocked (cannot alter recipient identity)
    mismatch_form = {
        "AccountSid": sid_a,
        "MessageSid": "SM_LIFE_1",
        "MessageStatus": "sent",
        "To": "+19995550000",
    }
    res_mismatch = client.post(
        "/api/v1/messages/callbacks/twilio",
        data=mismatch_form,
        headers={"X-Twilio-Signature": _sign_twilio_form(url, mismatch_form, tok_a)},
    )
    assert res_mismatch.status_code == 409
    assert res_mismatch.get_json()["error_code"] == "IDENTITY_MISMATCH"

    # Valid PROCESSING -> SENT -> DELIVERED progression
    for raw_st, expected in (("sent", "SENT"), ("delivered", "DELIVERED")):
        f = {"AccountSid": sid_a, "MessageSid": "SM_LIFE_1", "MessageStatus": raw_st, "To": "+14155552671"}
        r = client.post(
            "/api/v1/messages/callbacks/twilio",
            data=f,
            headers={"X-Twilio-Signature": _sign_twilio_form(url, f, tok_a)},
        )
        assert r.status_code == 200
        assert r.get_json()["status"] == expected

    with app.app_context():
        assert MessageRepository.find_by_id("msg-ok", organization_id="org-a")["recipient"] == "+14155552671"

    # Multiple matching records inside same tenant rejected & audited
    multi_form = {"AccountSid": sid_a, "MessageSid": "SM_MULTI", "MessageStatus": "delivered"}
    res_multi = client.post(
        "/api/v1/messages/callbacks/twilio",
        data=multi_form,
        headers={"X-Twilio-Signature": _sign_twilio_form(url, multi_form, tok_a)},
    )
    assert res_multi.status_code == 409
    assert res_multi.get_json()["error_code"] == "AMBIGUOUS_MESSAGE_RECORD"


# 11. Reverse proxy URL handling & spoofed forwarded header rejection
def test_reverse_proxy_url_reconstruction_and_spoof_resistance():
    sid_a = "AC" + "a" * 32
    tok_a = "token_org_a_secret"
    form = {"AccountSid": sid_a, "MessageSid": "SM_PROXY_1", "MessageStatus": "delivered"}

    # Case A: Canonical WEBHOOK_PUBLIC_BASE_URL ignores spoofed X-Forwarded-* headers
    app_pub = _build_app(extra_config={"WEBHOOK_PUBLIC_BASE_URL": "https://api.senderx.io"})
    with app_pub.app_context():
        _seed_org_with_twilio(app_pub, "org-a", sid_a, tok_a)
        _seed_sent_sms(app_pub, "org-a", "msg-p1", "SM_PROXY_1", sid=sid_a)

    public_sig = _sign_twilio_form("https://api.senderx.io/api/v1/messages/callbacks/twilio", form, tok_a)
    client_pub = app_pub.test_client()
    res_pub = client_pub.post(
        "/api/v1/messages/callbacks/twilio",
        data=form,
        headers={
            "X-Twilio-Signature": public_sig,
            "X-Forwarded-Host": "evil.attacker.com",
            "X-Forwarded-Proto": "http",
            "X-Forwarded-For": "1.2.3.4",
        },
    )
    assert res_pub.status_code == 200
    assert res_pub.get_json()["status"] == "DELIVERED"

    # Case B: TRUST_PROXY_HEADERS=True accepts trusted proxy + allowed host, rejects untrusted IP / host
    app_proxy = _build_app(extra_config={
        "TRUST_PROXY_HEADERS": True,
        "TRUSTED_PROXY_IPS": ["10.0.0.5"],
        "TRUSTED_FORWARDED_HOSTS": ["webhooks.senderx.io"],
    })
    with app_proxy.app_context():
        _seed_org_with_twilio(app_proxy, "org-a", sid_a, tok_a)
        _seed_sent_sms(app_proxy, "org-a", "msg-p2", "SM_PROXY_1", sid=sid_a)

    proxy_sig = _sign_twilio_form("https://webhooks.senderx.io/api/v1/messages/callbacks/twilio", form, tok_a)
    client_proxy = app_proxy.test_client()

    # Spoofed client IP trying to impersonate X-Forwarded-Host / Proto is rejected (401)
    res_untrusted_ip = client_proxy.post(
        "/api/v1/messages/callbacks/twilio",
        data=form,
        environ_base={"REMOTE_ADDR": "203.0.113.50"},
        headers={
            "X-Twilio-Signature": proxy_sig,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "webhooks.senderx.io",
        },
    )
    assert res_untrusted_ip.status_code == 401

    # Trusted proxy IP + allowed forwarded host succeeds (200)
    res_trusted_proxy = client_proxy.post(
        "/api/v1/messages/callbacks/twilio",
        data=form,
        environ_base={"REMOTE_ADDR": "10.0.0.5"},
        headers={
            "X-Twilio-Signature": proxy_sig,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "webhooks.senderx.io",
        },
    )
    assert res_trusted_proxy.status_code == 200
    assert res_trusted_proxy.get_json()["status"] == "DELIVERED"


# 12. Unavailable integration credentials (inactive integration & unreadable encryption key)
def test_unavailable_and_corrupted_integration_credentials_rejected():
    key_1 = Fernet.generate_key().decode("ascii")
    key_2 = Fernet.generate_key().decode("ascii")
    sid_a = "AC" + "a" * 32
    tok_a = "token_org_a_secret"
    form = {"AccountSid": sid_a, "MessageSid": "SM_CRED_1", "MessageStatus": "delivered"}
    url = "http://localhost/api/v1/messages/callbacks/twilio"
    sig = _sign_twilio_form(url, form, tok_a)

    # Inactive / deactivated provider configuration
    app_inactive = _build_app(key=key_1)
    with app_inactive.app_context():
        _seed_org_with_twilio(app_inactive, "org-a", sid_a, tok_a, active=False)
        _seed_sent_sms(app_inactive, "org-a", "msg-c1", "SM_CRED_1", sid=sid_a)

    r_inact = app_inactive.test_client().post(
        "/api/v1/messages/callbacks/twilio",
        data=form,
        headers={"X-Twilio-Signature": sig},
    )
    assert r_inact.status_code == 403
    assert r_inact.get_json()["error_code"] == "INTEGRATION_INACTIVE"

    # Encrypted under key_1, verified after key mismatch -> 503 CREDENTIAL_UNAVAILABLE (no key/secret leakage)
    app_corrupt = _build_app(key=key_1)
    with app_corrupt.app_context():
        _seed_org_with_twilio(app_corrupt, "org-a", sid_a, tok_a, active=True)
        _seed_sent_sms(app_corrupt, "org-a", "msg-c2", "SM_CRED_1", sid=sid_a)
    app_corrupt.config["CREDENTIAL_ENCRYPTION_KEY"] = key_2

    r_corrupt = app_corrupt.test_client().post(
        "/api/v1/messages/callbacks/twilio",
        data=form,
        headers={"X-Twilio-Signature": sig},
    )
    assert r_corrupt.status_code == 503
    assert r_corrupt.get_json()["error_code"] == "CREDENTIAL_UNAVAILABLE"
    assert tok_a not in str(r_corrupt.get_json())
    assert key_1 not in str(r_corrupt.get_json())


# 13. Endpoint responsibility separation, ambiguous AccountSid & legacy record support
def test_endpoint_responsibilities_ambiguous_account_and_legacy_config():
    app = _build_app()
    shared_sid = "AC" + "c" * 32
    tok_1 = "token_shared_1_secret"
    tok_2 = "token_shared_2_secret"
    legacy_sid = "AC" + "d" * 32
    legacy_tok = "legacy_token_secret_123"

    with app.app_context():
        _seed_org_with_twilio(app, "org-1", shared_sid, tok_1)
        _seed_org_with_twilio(app, "org-2", shared_sid, tok_2)
        _seed_sent_sms(app, "org-1", "msg-shared", "SM_SHARED", sid=shared_sid)

        # Simulate legacy provider_configs record written prior to Phase 2 (no account_sid_digest / config_id)
        app.mongo_db["organizations"].docs.append({"organization_id": "org-legacy", "name": "Legacy", "status": "ACTIVE"})
        encrypted_legacy, _ = ProviderConfigService._encrypt_credentials({
            "account_sid": legacy_sid,
            "auth_token": legacy_tok,
            "from_number": "+14155550009",
        })
        app.mongo_db["provider_configs"].docs.append({
            "provider": "twilio",
            "organization_id": "org-legacy",
            "credentials": encrypted_legacy,
            "configured": True,
            "disconnected": False,
            "status": "ACTIVE",
        })
        _seed_sent_sms(app, "org-legacy", "msg-legacy", "SM_LEGACY_1")

    client = app.test_client()

    # Shared AccountSid across two active orgs fails closed (409)
    amb_form = {"AccountSid": shared_sid, "MessageSid": "SM_SHARED", "MessageStatus": "delivered"}
    amb_sig = _sign_twilio_form("http://localhost/api/v1/messages/callbacks/twilio", amb_form, tok_1)
    r_amb = client.post("/api/v1/messages/callbacks/twilio", data=amb_form, headers={"X-Twilio-Signature": amb_sig})
    assert r_amb.status_code == 409
    assert r_amb.get_json()["error_code"] == "AMBIGUOUS_TWILIO_ACCOUNT"

    # Legacy config (no account_sid_digest) still resolves & updates cleanly
    leg_form = {"AccountSid": legacy_sid, "MessageSid": "SM_LEGACY_1", "MessageStatus": "delivered"}
    leg_sig = _sign_twilio_form("http://localhost/api/v1/messages/callbacks/twilio", leg_form, legacy_tok)
    r_leg = client.post("/api/v1/messages/callbacks/twilio", data=leg_form, headers={"X-Twilio-Signature": leg_sig})
    assert r_leg.status_code == 200
    assert r_leg.get_json()["status"] == "DELIVERED"

    # Endpoint distinction: /callbacks/twilio requires status, /webhook/twilio acknowledges inbound SMS without mutating outbound state
    inbound_form = {"AccountSid": legacy_sid, "MessageSid": "SM_INBOUND_1", "From": "+14155551111", "To": "+14155550009", "Body": "STOP"}
    sig_cb = _sign_twilio_form("http://localhost/api/v1/messages/callbacks/twilio", inbound_form, legacy_tok)
    sig_wh = _sign_twilio_form("http://localhost/api/v1/messages/webhook/twilio", inbound_form, legacy_tok)
    r_cb_no_status = client.post("/api/v1/messages/callbacks/twilio", data=inbound_form, headers={"X-Twilio-Signature": sig_cb})
    r_wh_inbound = client.post("/api/v1/messages/webhook/twilio", data=inbound_form, headers={"X-Twilio-Signature": sig_wh})
    assert r_cb_no_status.status_code == 400
    assert r_cb_no_status.get_json()["error_code"] == "MISSING_MESSAGE_STATUS"
    assert r_wh_inbound.status_code == 200
    assert r_wh_inbound.get_json()["event_type"] == "twilio_webhook_acknowledged"
    assert r_wh_inbound.get_json()["updated"] is False

