"""
Phase 3 Security & Compatibility Test Suite:
Authenticated JSON Validation & Analyzer Endpoint, Threat Rejection (Never valid=True),
Iterative Resource-Exhaustion Guards, Tenant/RBAC Scoping & Ingestion Parity.
Runs cleanly offline against in-memory doubles (no real network/SMS/DB required).
"""

import copy
import json
import logging
import pytest
from cryptography.fernet import Fernet
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

from app.engine.message_engine import MessageEngine
from app.modules.messages.routes import messages_bp
from app.modules.payloads.models import validate_json_structure_and_limits
from app.modules.payloads.routes import payloads_bp
from app.modules.payloads.service import PayloadService
from app.modules.validation.routes import validation_bp
from app.validators.dynamic_json_validator import DynamicJSONValidator


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *args, **kwargs):
        return self

    def limit(self, count):
        self._docs = self._docs[:count]
        return self

    def skip(self, count):
        self._docs = self._docs[count:]
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
                if "$exists" in val and (key in doc) != bool(val["$exists"]):
                    return False
                if "$ne" in val and doc.get(key) == val["$ne"]:
                    return False
                if "$in" in val and doc.get(key) not in val["$in"]:
                    return False
            else:
                if doc.get(key) != val:
                    return False
        return True

    @staticmethod
    def _project(doc, projection):
        if doc is None or not projection:
            return copy.deepcopy(doc)
        include = {k for k, v in projection.items() if v}
        exclude = {k for k, v in projection.items() if v == 0}
        if include:
            out = {k: copy.deepcopy(doc[k]) for k in include if k in doc}
            if projection.get("_id", 1) != 0 and "_id" in doc:
                out["_id"] = doc["_id"]
            return out
        return {k: copy.deepcopy(v) for k, v in doc.items() if k not in exclude}

    def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

        class Res:
            inserted_id = "fake"

        return Res()

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
        class Res:
            def __init__(self, matched, modified):
                self.matched_count = matched
                self.modified_count = modified

        for idx, doc in enumerate(self.docs):
            if self._matches(doc, query):
                updated = copy.deepcopy(doc)
                if "$set" in update:
                    updated.update(copy.deepcopy(update["$set"]))
                if "$push" in update:
                    for k, v in update["$push"].items():
                        updated.setdefault(k, []).append(copy.deepcopy(v))
                self.docs[idx] = updated
                return Res(1, 1)

        if upsert:
            new_doc = {k: v for k, v in (query or {}).items() if not isinstance(v, dict)}
            if "$set" in update:
                new_doc.update(copy.deepcopy(update["$set"]))
            self.docs.append(new_doc)
            return Res(0, 1)

        return Res(0, 0)


class FakeMongoDB:
    def __init__(self):
        self._cols = {
            "organizations": FakeCollection(),
            "roles": FakeCollection(),
            "users": FakeCollection(),
            "connected_applications": FakeCollection(),
            "api_credentials": FakeCollection(),
            "messages": FakeCollection(),
            "ingested_payloads": FakeCollection(),
            "payload_audits": FakeCollection(),
            "dead_letters": FakeCollection(),
        }

    def list_collection_names(self):
        return list(self._cols.keys())

    def __getitem__(self, name):
        if name not in self._cols:
            self._cols[name] = FakeCollection()
        return self._cols[name]


class FakeRedis:
    def pipeline(self):
        class Pipe:
            def zremrangebyscore(self, *a, **kw):
                return self

            def zadd(self, *a, **kw):
                return self

            def zcard(self, *a, **kw):
                return self

            def expire(self, *a, **kw):
                return self

            def zrange(self, *a, **kw):
                return self

            def execute(self):
                return [0, 1, 1, True, [("member", 1.0)]]

        return Pipe()

    def zcard(self, *a, **kw):
        return 0

    def incr(self, *a, **kw):
        return 1

    def expire(self, *a, **kw):
        return True

    def get(self, *a, **kw):
        return None


def _build_app(extra_config=None):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["APP_ENV"] = "production"
    app.config["SECRET_KEY"] = "phase3-secret-key"
    app.config["JWT_SECRET_KEY"] = "phase3-jwt-secret-key-at-least-32-bytes"
    app.config["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
    app.config["VALIDATION_MAX_BODY_BYTES"] = 64 * 1024  # 64 KB for clean unit tests
    app.config["VALIDATION_MAX_DEPTH"] = 20
    app.config["VALIDATION_MAX_NODES"] = 250
    app.config["VALIDATION_MAX_ARRAY_LENGTH"] = 50
    app.config["VALIDATION_MAX_OBJECT_KEYS"] = 40
    app.config["VALIDATION_MAX_STRING_LENGTH"] = 4096
    app.config["PAYLOAD_INGEST_MAX_BYTES"] = 64 * 1024
    if extra_config:
        app.config.update(extra_config)

    JWTManager(app)
    app.mongo_db = FakeMongoDB()
    app.redis_client = FakeRedis()
    app.register_blueprint(validation_bp, url_prefix="/api/v1/validation")
    app.register_blueprint(messages_bp, url_prefix="/api/v1/messages")
    app.register_blueprint(payloads_bp, url_prefix="/api/v1/payloads")
    return app


def _setup_auth(app, monkeypatch):
    from app.modules.api_credentials.service import ApiCredentialService
    from app.modules.applications.repository import ApplicationRepository
    from app.modules.organizations.repository import OrganizationRepository
    from app.modules.organizations.role_repository import RoleRepository
    from app.modules.users.repository import UserRepository

    app.mongo_db["organizations"].docs.extend([
        {"organization_id": "org-a", "name": "Org A", "status": "ACTIVE"},
        {"organization_id": "org-b", "name": "Org B", "status": "ACTIVE"},
    ])
    app.mongo_db["connected_applications"].docs.extend([
        {"application_id": "app-a1", "organization_id": "org-a", "name": "App A1", "status": "ACTIVE"},
        {"application_id": "app-a2", "organization_id": "org-a", "name": "App A2", "status": "ACTIVE"},
        {"application_id": "app-b1", "organization_id": "org-b", "name": "App B1", "status": "ACTIVE"},
    ])
    app.mongo_db["roles"].docs.extend([
        {
            "role_id": "role-validator",
            "organization_id": "org-a",
            "name": "Validator",
            "scope": "ORGANIZATION",
            "permissions": ["organization:payloads:validate", "organization:messages:create"],
        },
        {
            "role_id": "role-viewer",
            "organization_id": "org-a",
            "name": "Viewer Only",
            "scope": "ORGANIZATION",
            "permissions": ["organization:messages:read", "organization:payloads:read"],
        },
        {
            "role_id": "role-app-scoped",
            "organization_id": "org-a",
            "name": "App1 Validator",
            "scope": "ORGANIZATION",
            "application_id": "app-a1",
            "permissions": ["organization:payloads:validate"],
        },
    ])
    app.mongo_db["users"].docs.extend([
        {
            "user_id": "u-validator",
            "organization_id": "org-a",
            "email": "val@orga.test",
            "is_active": True,
            "status": "ACTIVE",
            "token_version": 1,
            "role_ids": ["role-validator"],
        },
        {
            "user_id": "u-viewer",
            "organization_id": "org-a",
            "email": "view@orga.test",
            "is_active": True,
            "status": "ACTIVE",
            "token_version": 1,
            "role_ids": ["role-viewer"],
        },
        {
            "user_id": "u-app1",
            "organization_id": "org-a",
            "email": "app1@orga.test",
            "is_active": True,
            "status": "ACTIVE",
            "token_version": 1,
            "role_assignments": [{"role_id": "role-app-scoped", "application_id": "app-a1"}],
        },
    ])

    monkeypatch.setattr(UserRepository, "find_by_id", classmethod(lambda cls, uid, **kw: app.mongo_db["users"].find_one({"user_id": uid})))
    monkeypatch.setattr(OrganizationRepository, "find_by_id", classmethod(lambda cls, oid, **kw: app.mongo_db["organizations"].find_one({"organization_id": oid})))
    monkeypatch.setattr(RoleRepository, "find_by_id", classmethod(lambda cls, rid, organization_id=None, **kw: app.mongo_db["roles"].find_one({"role_id": rid, **({"organization_id": organization_id} if organization_id else {})})))
    monkeypatch.setattr(ApplicationRepository, "find_by_id", classmethod(lambda cls, aid, organization_id=None, **kw: app.mongo_db["connected_applications"].find_one({"application_id": aid, **({"organization_id": organization_id} if organization_id else {})})))

    api_keys = {
        "sx_live_valid_ingest_key_secret": (
            {"credential_id": "cred-1", "application_id": "app-a1", "organization_id": "org-a", "environment": "live", "scopes": ["payloads:ingest", "messages:create"]},
            {"organization_id": "org-a", "name": "Org A", "status": "ACTIVE"},
        ),
        "sx_live_readonly_key_secret": (
            {"credential_id": "cred-ro", "application_id": "app-a1", "organization_id": "org-a", "environment": "live", "scopes": ["messages:read"]},
            {"organization_id": "org-a", "name": "Org A", "status": "ACTIVE"},
        ),
    }
    monkeypatch.setattr(ApiCredentialService, "verify_api_key", staticmethod(lambda k: api_keys.get(k, (None, None))))

    with app.app_context():
        tokens = {
            "validator": create_access_token("u-validator", additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": "org-a", "token_version": 1}),
            "viewer": create_access_token("u-viewer", additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": "org-a", "token_version": 1}),
            "app1": create_access_token("u-app1", additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": "org-a", "token_version": 1}),
        }
    return tokens


# 1. Unauthenticated request rejection
def test_unauthenticated_request_rejected(monkeypatch):
    app = _build_app()
    _setup_auth(app, monkeypatch)
    res = app.test_client().post(
        "/api/v1/validation/analyze",
        json={"channel": "email", "recipient": "user@example.com", "data": {"message": "Hi"}},
    )
    assert res.status_code == 401


# 2. Authorized user & API key validation success
def test_authorized_user_and_api_key_validation_success(monkeypatch):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    client = app.test_client()
    payload = {"channel": "email", "recipient": "user@example.com", "data": {"subject": "Hi", "message": "Welcome"}}

    res_jwt = client.post("/api/v1/validation/analyze", json=payload, headers={"Authorization": f"Bearer {tokens['validator']}"})
    assert res_jwt.status_code == 200
    body_jwt = res_jwt.get_json()
    assert body_jwt["success"] is True
    assert body_jwt["valid"] is True
    assert body_jwt["status"] == "VALID"
    assert body_jwt["data"]["valid"] is True
    assert body_jwt["data"]["threats"] == []

    res_key = client.post("/api/v1/validation/analyze", json=payload, headers={"X-API-Key": "sx_live_valid_ingest_key_secret"})
    assert res_key.status_code == 200
    assert res_key.get_json()["valid"] is True


# 3. Unauthorized role & insufficient API key scope rejection
def test_unauthorized_role_and_scope_rejected(monkeypatch):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    client = app.test_client()
    payload = {"channel": "email", "recipient": "user@example.com", "data": {"message": "Hi"}}

    res_viewer = client.post("/api/v1/validation/analyze", json=payload, headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert res_viewer.status_code == 403

    res_ro_key = client.post("/api/v1/validation/analyze", json=payload, headers={"X-API-Key": "sx_live_readonly_key_secret"})
    assert res_ro_key.status_code == 403


# 4. Cross-tenant & out-of-scope application isolation
def test_cross_tenant_and_application_scope_rejected(monkeypatch):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    client = app.test_client()

    # Cross-org organization_id inside request payload
    r_org = client.post(
        "/api/v1/validation/analyze",
        json={"organization_id": "org-b", "channel": "email", "recipient": "u@example.com", "data": {"message": "Hi"}},
        headers={"Authorization": f"Bearer {tokens['validator']}"},
    )
    assert r_org.status_code == 403
    assert "org-b" not in str(r_org.get_json())
    assert "org-a" not in str(r_org.get_json())

    # Out-of-scope application via X-Application-ID / body
    r_app_jwt = client.post(
        "/api/v1/validation/analyze",
        json={"application_id": "app-a2", "channel": "email", "recipient": "u@example.com", "data": {"message": "Hi"}},
        headers={"Authorization": f"Bearer {tokens['app1']}"},
    )
    assert r_app_jwt.status_code == 403

    r_app_key = client.post(
        "/api/v1/validation/analyze",
        json={"channel": "email", "recipient": "u@example.com", "data": {"message": "Hi"}},
        headers={"X-API-Key": "sx_live_valid_ingest_key_secret", "X-Application-ID": "app-a2"},
    )
    assert r_app_key.status_code == 403


# 5 & 6. Valid JSON vs malformed JSON (syntax, NaN, bad UTF-8, non-object root)
def test_valid_vs_malformed_json(monkeypatch):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    client = app.test_client()
    hdrs = {"Authorization": f"Bearer {tokens['validator']}", "Content-Type": "application/json"}

    for bad_raw in (b"{bad json", b"", b"\xff\xfe", b'{"channel": "email", "val": NaN}', b'["not","an","object"]'):
        res = client.post("/api/v1/validation/analyze", data=bad_raw, headers=hdrs)
        assert res.status_code == 400
        body = res.get_json()
        assert body["success"] is False
        assert body["valid"] is False
        assert body["status"] == "INVALID_PAYLOAD"


# 7. Threat-containing JSON MUST return valid: false (never valid: true)
@pytest.mark.parametrize(
    "evil_payload",
    [
        {"channel": "email", "recipient": "u@example.com", "data": {"subject": "Hi", "html": "<p>x</p><script>alert(1)</script>"}},
        {"channel": "email", "recipient": "u@example.com", "data": {"body": "<img src=x onerror=alert(1)>"}},
        {"channel": "email", "recipient": "u@example.com", "data": {"link": "javascript:alert(1)"}},
        {"channel": "email", "recipient": "u@example.com", "data": {"subject": "Notice\r\nBcc: attacker@evil.test", "text": "x"}},
        {"channel": "email", "recipient": "u@example.com", "template_id": "t1", "variables": {"name": "<script>xss</script>"}},
        {"channel": "email", "recipient": "u@example.com", "data": {"msg": "{{ ''.__class__.__mro__ }}"}},
    ],
)
def test_threats_never_produce_valid_true(monkeypatch, evil_payload):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)

    with app.app_context():
        direct = DynamicJSONValidator.analyze(evil_payload)
        assert direct["valid"] is False
        assert direct["status"] == "SECURITY_THREAT_DETECTED"
        assert len(direct["threats"]) >= 1

    res = app.test_client().post(
        "/api/v1/validation/analyze",
        json=evil_payload,
        headers={"Authorization": f"Bearer {tokens['validator']}"},
    )
    assert res.status_code == 422
    body = res.get_json()
    assert body["success"] is False
    assert body["valid"] is False
    assert body["status"] == "SECURITY_THREAT_DETECTED"
    assert len(body["threats"]) >= 1


# 8. Deeply nested JSON (API + raw C recursion + huge iterative Python depth)
def test_deeply_nested_json_rejected_without_recursion_crash(monkeypatch):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    client = app.test_client()
    hdrs = {"Authorization": f"Bearer {tokens['validator']}", "Content-Type": "application/json"}

    # Depth 25 (> 20)
    deep = {"channel": "email", "recipient": "u@example.com", "data": {}}
    cur = deep["data"]
    for _ in range(25):
        cur["n"] = {}
        cur = cur["n"]

    res_deep = client.post("/api/v1/validation/analyze", json=deep, headers=hdrs)
    assert res_deep.status_code == 422
    assert res_deep.get_json()["valid"] is False
    assert res_deep.get_json()["status"] == "RESOURCE_LIMIT_EXCEEDED"

    # Very deep raw JSON string (> Python default recursion limit during json.loads) -> clean 422, no crash
    raw_huge_depth = ('{"a":' * 1500) + '1' + ('}' * 1500)
    res_raw = client.post("/api/v1/validation/analyze", data=raw_huge_depth.encode("utf-8"), headers=hdrs)
    assert res_raw.status_code == 422
    assert res_raw.get_json()["valid"] is False

    # Iterative validator directly handles depth 1500 Python object without RecursionError
    py_deep = {"channel": "email", "recipient": "u@example.com", "data": {}}
    c2 = py_deep["data"]
    for _ in range(1500):
        c2["x"] = {}
        c2 = c2["x"]
    with app.app_context():
        out = DynamicJSONValidator.analyze(py_deep)
        assert out["valid"] is False
        assert out["status"] == "RESOURCE_LIMIT_EXCEEDED"


# 9, 10, 11, 12. Oversized body, excessive arrays, excessive object properties, excessive string length
def test_resource_exhaustion_limits_enforced(monkeypatch):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    client = app.test_client()
    hdrs = {"Authorization": f"Bearer {tokens['validator']}"}

    # 9. Oversized request body (> 64 KB configured limit) rejected with 413
    oversized = {"channel": "email", "recipient": "u@example.com", "data": {"blob": "x" * (70 * 1024)}}
    r_big = client.post("/api/v1/validation/analyze", json=oversized, headers=hdrs)
    assert r_big.status_code == 413
    assert r_big.get_json()["valid"] is False
    assert r_big.get_json()["status"] == "RESOURCE_LIMIT_EXCEEDED"

    # 10. Excessive array length (> 50 elements)
    many_items = {"channel": "email", "recipient": "u@example.com", "data": {"items": list(range(60))}}
    r_arr = client.post("/api/v1/validation/analyze", json=many_items, headers=hdrs)
    assert r_arr.status_code == 422
    assert r_arr.get_json()["status"] == "RESOURCE_LIMIT_EXCEEDED"

    # 11. Excessive object keys (> 40 keys)
    many_keys = {"channel": "email", "recipient": "u@example.com", "data": {f"k{i}": i for i in range(45)}}
    r_obj = client.post("/api/v1/validation/analyze", json=many_keys, headers=hdrs)
    assert r_obj.status_code == 422
    assert r_obj.get_json()["status"] == "RESOURCE_LIMIT_EXCEEDED"

    # 12. Excessively long string (> 4096 chars, within 64 KB body limit)
    long_str = {"channel": "email", "recipient": "u@example.com", "data": {"text": "a" * 5000}}
    r_str = client.post("/api/v1/validation/analyze", json=long_str, headers=hdrs)
    assert r_str.status_code == 422
    assert r_str.get_json()["status"] == "RESOURCE_LIMIT_EXCEEDED"


# 13 & 14. Unsupported data types & missing/ambiguous channel
def test_unsupported_types_and_missing_or_ambiguous_channel(monkeypatch):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    client = app.test_client()
    hdrs = {"Authorization": f"Bearer {tokens['validator']}"}

    # 13. Unsupported Python types in direct validator calls
    with app.app_context():
        for bad_val in (float("nan"), float("inf"), b"rawbytes", {1, 2, 3}, object()):
            res = DynamicJSONValidator.analyze({
                "channel": "email",
                "recipient": "u@example.com",
                "data": {"bad": bad_val},
            })
            assert res["valid"] is False
            assert res["status"] == "INVALID_PAYLOAD"

    # 14. Missing, unsupported, non-string, or ambiguous channel
    for bad_chan_payload in (
        {"recipient": "u@example.com", "data": {"m": "x"}},
        {"channel": ["email"], "recipient": "u@example.com", "data": {"m": "x"}},
        {"channel": "schedule", "recipient": "u@example.com", "data": {"m": "x"}},
        {"channel": "email", "routing_channel": "sms", "recipient": "u@example.com", "data": {"m": "x"}},
        {"channel": "email", "recipient": "u@example.com", "data": {"channel": "whatsapp", "m": "x"}},
    ):
        r = client.post("/api/v1/validation/analyze", json=bad_chan_payload, headers=hdrs)
        assert r.status_code == 400
        assert r.get_json()["valid"] is False


# 15. MongoDB operator-like & prototype pollution keys
@pytest.mark.parametrize("bad_key", ["$where", "$ne", "$gt", "$expr", "$regex", "__proto__", "constructor"])
def test_mongodb_operator_and_prototype_keys_rejected(monkeypatch, bad_key):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    payload = {"channel": "email", "recipient": "u@example.com", "data": {bad_key: "1==1"}}

    res = app.test_client().post(
        "/api/v1/validation/analyze",
        json=payload,
        headers={"Authorization": f"Bearer {tokens['validator']}"},
    )
    assert res.status_code == 422
    body = res.get_json()
    assert body["valid"] is False
    assert body["status"] == "SECURITY_THREAT_DETECTED"
    assert len(body["threats"]) >= 1


# 16. Sanitized error responses & internal failures never leak secrets, payloads, or tracebacks
def test_sanitized_errors_and_internal_failure_handling(monkeypatch, caplog):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    client = app.test_client()

    secret_api_key = "sx_live_valid_ingest_key_secret"
    secret_payload = {
        "channel": "email",
        "recipient": "vip-secret-person@private.test",
        "data": {"subject": "Confidential", "secret_val": "<script>steal()</script>"},
    }

    with caplog.at_level(logging.WARNING):
        res_threat = client.post("/api/v1/validation/analyze", json=secret_payload, headers={"X-API-Key": secret_api_key})
    assert res_threat.status_code == 422
    assert secret_api_key not in str(res_threat.get_json())
    assert "vip-secret-person@private.test" not in str(res_threat.get_json())
    assert secret_api_key not in caplog.text
    assert "vip-secret-person@private.test" not in caplog.text

    # Internal failure returns 500 INTERNAL_ERROR without traceback/implementation details
    monkeypatch.setattr(DynamicJSONValidator, "analyze", classmethod(lambda cls, *a, **kw: (_ for _ in ()).throw(RuntimeError("db_internal_boom_secret_detail"))))
    res_err = client.post(
        "/api/v1/validation/analyze",
        json={"channel": "email", "recipient": "u@example.com", "data": {"m": "ok"}},
        headers={"Authorization": f"Bearer {tokens['validator']}"},
    )
    assert res_err.status_code == 500
    err_body = res_err.get_json()
    assert err_body["valid"] is False
    assert err_body["status"] == "INTERNAL_ERROR"
    assert "db_internal_boom_secret_detail" not in str(err_body)
    assert "Traceback" not in str(err_body)


# 17. Existing legitimate payload compatibility (Email, Safe HTML, SMS, WhatsApp, Teams, JsonAnalyzer default)
@pytest.mark.parametrize(
    "good_payload",
    [
        {"channel": "email", "recipient": "user@example.com", "data": {"subject": "Welcome", "html": "<p style='color:blue;'>Hello <b>Alice</b>!</p>"}},
        {"channel": "sms", "recipient": "+14155552671", "data": {"text": "Order #123 shipped on 2026-11-27"}},
        {"channel": "whatsapp", "recipient": "+14155552671", "data": {"type": "text", "text": {"body": "Hi from WhatsApp"}}},
        {"channel": "microsoft_teams", "recipient": "chat:19:abc@thread.v2", "data": {"text": "Deployment complete"}},
        {"channel": "email", "recipient": "customer@example.com", "template_id": "welcome_email", "variables": {"name": "Jane Doe", "activation_link": "https://senderx.io/verify"}},
    ],
)
def test_legitimate_payload_compatibility(monkeypatch, good_payload):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    res = app.test_client().post(
        "/api/v1/validation/analyze",
        json=good_payload,
        headers={"Authorization": f"Bearer {tokens['validator']}"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["valid"] is True
    assert body["status"] == "VALID"
    assert body["data"]["threats"] == []


# 18. Downstream ingestion rejects malicious payloads even if analyzer endpoint is bypassed
def test_ingestion_rejects_malicious_payloads_directly(monkeypatch):
    app = _build_app()
    tokens = _setup_auth(app, monkeypatch)
    client = app.test_client()
    hdrs = {"Authorization": f"Bearer {tokens['validator']}"}

    # Direct MessageEngine check fails closed on threat or operator key
    with app.app_context():
        prep_res = MessageEngine.prepare_message({
            "channel": "email",
            "recipient": "u@example.com",
            "data": {"$where": "sleep(1000)", "message": "<script>alert(1)</script>"},
        })
        assert prep_res["success"] is False
        assert prep_res["status"] == "SECURITY_THREAT_DETECTED"

        # validate_json_structure_and_limits rejects iterative complexity limits
        ok_big, code_big, _ = validate_json_structure_and_limits({"channel": "email", "recipient": "u@example.com", "data": {"arr": list(range(1200))}})
        assert ok_big is False
        assert code_big == "PAYLOAD_TOO_LARGE"

    # Direct /api/v1/messages/ creation bypass attempt rejects threat / operator payload (422)
    msg_res = client.post(
        "/api/v1/messages/",
        json={"channel": "email", "recipient": "u@example.com", "data": {"$where": "1==1", "message": "Hi"}},
        headers=hdrs,
    )
    assert msg_res.status_code == 422
    assert msg_res.get_json()["success"] is False

    # Direct /api/v1/payloads/ingest moves threat payload to DLQ and refuses to queue message
    ingest_res = client.post(
        "/api/v1/payloads/ingest",
        json={"channel": "email", "recipient": "u@example.com", "data": {"$ne": None, "message": "<script>evil()</script>"}},
        headers=hdrs,
    )
    assert ingest_res.status_code == 400
    ingest_body = ingest_res.get_json()
    assert ingest_body["success"] is False
    assert ingest_body["status"] == "IN_DLQ"
    assert len(app.mongo_db["messages"].docs) == 0

    # PayloadService.validate_payload rejects stored threat payload
    with app.app_context():
        p_id = ingest_body["payload_id"]
        val_res = PayloadService.validate_payload(p_id, organization_id="org-a")
        assert val_res["valid"] is False
        assert val_res["status"] == "SECURITY_THREAT_DETECTED"
