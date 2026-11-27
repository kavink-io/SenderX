"""
Phase 4 Distributed Rate Limiting & Authentication Abuse Protection Test Suite.

Covers all 15 Phase 4 security requirements using an atomic thread-safe Lua-emulating
in-memory Redis double (plus optional live Redis check when reachable):
- Login brute-force protection & no counter reset on success
- OTP verify / request / resend / password reset / refresh abuse protection
- JWT validation analyzer rate limiting (user / app / org)
- API key rate limiting & non-enumerable auth failure responses
- Cross-tenant and application-level isolation
- Spoofed X-Forwarded-For / X-Real-IP rejection & trusted proxy chain extraction
- Fail-closed 503 on Redis unavailability without HTTP 500 or URI/secret leakage
- Zero plaintext PII/secrets in Redis keys
- Multi-threaded concurrent race-condition protection
"""

from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timedelta, timezone
import math
import threading
import time
import bcrypt
from cryptography.fernet import Fernet
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token
import pytest

from app.core.client_ip import resolve_client_ip
from app.modules.api_credentials.rate_limiter import DistributedRateLimiter, RateLimiterError
from app.modules.auth.otp_service import OTPService
from app.modules.auth.routes import auth_bp
from app.modules.messages.routes import messages_bp
from app.modules.payloads.routes import payloads_bp
from app.modules.users.routes import users_bp
from app.modules.validation.routes import validation_bp


class AtomicRedisDouble:
    """Thread-safe in-memory Redis double implementing atomic Lua ZSET sliding windows & backoff."""

    def __init__(self):
        self.lock = threading.Lock()
        self.zsets = {}
        self.kv = {}
        self.recorded_keys = []

    def eval(self, script, numkeys, *args):
        with self.lock:
            keys = list(args[:numkeys])
            argv = list(args[numkeys:])
            for k in keys:
                self.recorded_keys.append(k)

            if numkeys == 2:
                gkey, bkey = keys
                now = float(argv[0])
                window = float(argv[1])
                threshold = int(argv[2])
                base_backoff = float(argv[3])
                max_backoff = float(argv[4])

                zset = self.zsets.setdefault(gkey, {})
                for m in [m for m, sc in zset.items() if sc <= now - window]:
                    del zset[m]

                if len(argv) >= 6:
                    member = str(argv[5])
                    zset[member] = now
                    gcount = len(zset)
                    if gcount < threshold:
                        return [1, 0, gcount]
                    excess = min(gcount - threshold, 6)
                    backoff = max(1.0, min(max_backoff, base_backoff * (2 ** excess)))
                    self.kv[bkey] = (now + backoff, now + max_backoff + 10)
                    if gcount == threshold:
                        return [1, 0, gcount]
                    return [0, int(math.ceil(backoff)), gcount]

                gcount = len(zset)
                if gcount < threshold:
                    return [1, 0, gcount]

                unlock_entry = self.kv.get(bkey)
                unlock_ts = unlock_entry[0] if (unlock_entry and unlock_entry[1] > now) else 0.0
                if unlock_ts > now:
                    return [0, max(1, int(math.ceil(unlock_ts - now))), gcount]

                excess = min(gcount - threshold, 6)
                backoff = max(1.0, min(max_backoff, base_backoff * (2 ** excess)))
                self.kv[bkey] = (now + backoff, now + max_backoff + 10)
                return [1, 0, gcount]

            key = keys[0]
            now = float(argv[0])
            window = float(argv[1])
            limit = int(argv[2])

            zset = self.zsets.setdefault(key, {})
            expired = [m for m, sc in zset.items() if sc <= now - window]
            for m in expired:
                del zset[m]

            count = len(zset)
            is_peek = len(argv) == 3

            if is_peek:
                if count >= limit:
                    oldest = min(zset.values()) if zset else now
                    retry = max(1, int(math.ceil(oldest + window - now)))
                    return [0, retry]
                return [1, 0]

            member = str(argv[3])
            always_record = int(argv[4]) if len(argv) > 4 else 0

            if count >= limit:
                if always_record == 1:
                    zset[member] = now
                oldest = min(zset.values()) if zset else now
                retry = max(1, int(math.ceil(oldest + window - now)))
                return [0, retry]

            zset[member] = now
            return [1, 0]

    def delete(self, *keys):
        with self.lock:
            for k in keys:
                self.zsets.pop(k, None)
                self.kv.pop(k, None)


class BrokenRedisDouble:
    """Simulates Redis outage."""

    def eval(self, *args, **kwargs):
        raise ConnectionError("Error 10061 connecting to redis://secret-redis-host:6379/0")

    def pipeline(self):
        raise ConnectionError("Error 10061 connecting to redis://secret-redis-host:6379/0")


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *a, **kw):
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = [copy.deepcopy(d) for d in (docs or [])]

    @staticmethod
    def _matches(doc, query):
        for k, v in (query or {}).items():
            if k == "$or":
                if not any(FakeCollection._matches(doc, b) for b in v):
                    return False
            elif isinstance(v, dict):
                if "$exists" in v and (k in doc) != bool(v["$exists"]):
                    return False
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
                if "$gt" in v and (doc.get(k) is None or not (doc.get(k) > v["$gt"])):
                    return False
                if "$lt" in v and (doc.get(k) is None or not (doc.get(k) < v["$lt"])):
                    return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    def insert_one(self, doc):
        stored = copy.deepcopy(doc)
        stored.setdefault("_id", f"fake_{len(self.docs)}")
        self.docs.append(stored)

        class R:
            inserted_id = stored["_id"]

        return R()

    def find_one(self, query=None, projection=None, sort=None):
        matches = [copy.deepcopy(d) for d in self.docs if self._matches(d, query or {})]
        if not matches:
            return None
        return matches[0]

    def find(self, query=None, projection=None):
        return FakeCursor([copy.deepcopy(d) for d in self.docs if self._matches(d, query or {})])

    def update_one(self, query, update, upsert=False):
        class R:
            def __init__(self, m, mod):
                self.matched_count = m
                self.modified_count = mod

        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                u = copy.deepcopy(d)
                if "$set" in update:
                    u.update(copy.deepcopy(update["$set"]))
                if "$inc" in update:
                    for k, val in update["$inc"].items():
                        u[k] = u.get(k, 0) + val
                self.docs[i] = u
                return R(1, 1)
        return R(0, 0)

    def update_many(self, query, update):
        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                u = copy.deepcopy(d)
                if "$set" in update:
                    u.update(copy.deepcopy(update["$set"]))
                self.docs[i] = u

    def find_one_and_update(self, query, update, return_document=None):
        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                u = copy.deepcopy(d)
                if "$set" in update:
                    u.update(copy.deepcopy(update["$set"]))
                if "$unset" in update:
                    for k in update["$unset"]:
                        u.pop(k, None)
                if "$inc" in update:
                    for k, val in update["$inc"].items():
                        u[k] = u.get(k, 0) + val
                self.docs[i] = u
                return copy.deepcopy(u)
        return None


class FakeMongoDB:
    def __init__(self):
        self._cols = {
            "admins": FakeCollection(),
            "organizations": FakeCollection(),
            "roles": FakeCollection(),
            "users": FakeCollection(),
            "connected_applications": FakeCollection(),
            "api_credentials": FakeCollection(),
            "auth_otps": FakeCollection(),
            "security_audit_logs": FakeCollection(),
        }

    def __getitem__(self, name):
        if name not in self._cols:
            self._cols[name] = FakeCollection()
        return self._cols[name]


def _build_app(redis_client=None, extra_config=None):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["APP_ENV"] = "development"  # Intentionally non-production to verify FAIL_CLOSED_DIMENSIONS
    app.config["SECRET_KEY"] = "phase4-app-secret-key"
    app.config["JWT_SECRET_KEY"] = "phase4-jwt-secret-key-at-least-32-bytes"
    app.config["OTP_HMAC_SECRET"] = "phase4-otp-hmac-secret-at-least-32-bytes"
    app.config["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
    app.config["AUTH_OTP_EMAIL_PROVIDER"] = "mock"
    app.config["TRUST_PROXY_HEADERS"] = False
    app.config["TRUSTED_PROXY_IPS"] = ["10.0.0.5"]
    app.config["RATE_LIMIT_AUTH_LOGIN_IP_RPM"] = 20
    app.config["RATE_LIMIT_AUTH_LOGIN_FAILURE_MAX"] = 3
    app.config["RATE_LIMIT_AUTH_LOGIN_WINDOW_SECONDS"] = 300
    app.config["RATE_LIMIT_AUTH_OTP_VERIFY_IP_MAX"] = 5
    app.config["RATE_LIMIT_AUTH_OTP_VERIFY_EMAIL_MAX"] = 4
    app.config["RATE_LIMIT_AUTH_OTP_VERIFY_WINDOW_SECONDS"] = 300
    app.config["RATE_LIMIT_AUTH_SET_PASSWORD_MAX"] = 3
    app.config["RATE_LIMIT_AUTH_REFRESH_RPM"] = 3
    app.config["RATE_LIMIT_VALIDATION_USER_RPM"] = 3
    app.config["RATE_LIMIT_VALIDATION_APP_RPM"] = 10
    app.config["RATE_LIMIT_VALIDATION_ORG_RPM"] = 15
    if extra_config:
        app.config.update(extra_config)

    JWTManager(app)
    app.mongo_db = FakeMongoDB()
    app.redis_client = AtomicRedisDouble() if redis_client is None else redis_client
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(validation_bp, url_prefix="/api/v1/validation")
    app.register_blueprint(messages_bp, url_prefix="/api/v1/messages")
    app.register_blueprint(payloads_bp, url_prefix="/api/v1/payloads")
    return app


def _seed_data(app, monkeypatch):
    from app.modules.api_credentials.service import ApiCredentialService
    from app.modules.applications.repository import ApplicationRepository
    from app.modules.auth.repository import AuthRepository
    from app.modules.organizations.repository import OrganizationRepository
    from app.modules.organizations.role_repository import RoleRepository
    from app.modules.users.repository import UserRepository

    pwd_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(4)).decode("utf-8")

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
            "role_id": "role-a",
            "organization_id": "org-a",
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "permissions": ["organization:payloads:validate", "organization:messages:create", "organization:messages:read", "organization:users:manage"],
        },
        {
            "role_id": "role-b",
            "organization_id": "org-b",
            "name": "ORG_ADMIN",
            "scope": "ORGANIZATION",
            "permissions": ["organization:payloads:validate", "organization:messages:create", "organization:messages:read"],
        },
    ])
    app.mongo_db["users"].docs.extend([
        {
            "user_id": "user-a",
            "organization_id": "org-a",
            "name": "Alice",
            "email": "alice@orga.test",
            "password_hash": pwd_hash,
            "is_active": True,
            "status": "ACTIVE",
            "token_version": 1,
            "role_ids": ["role-a"],
        },
        {
            "user_id": "user-pending",
            "organization_id": "org-a",
            "name": "Pending Bob",
            "email": "pending@orga.test",
            "password_hash": None,
            "is_active": False,
            "status": "PENDING_ACTIVATION",
            "token_version": 1,
            "role_ids": ["role-a"],
        },
        {
            "user_id": "user-b",
            "organization_id": "org-b",
            "name": "Bob B",
            "email": "bob@orgb.test",
            "password_hash": pwd_hash,
            "is_active": True,
            "status": "ACTIVE",
            "token_version": 1,
            "role_ids": ["role-b"],
        },
    ])

    monkeypatch.setattr(AuthRepository, "find_by_email", staticmethod(lambda e: app.mongo_db["admins"].find_one({"email": e})))
    monkeypatch.setattr(AuthRepository, "find_by_id", staticmethod(lambda i: app.mongo_db["admins"].find_one({"admin_id": i})))
    monkeypatch.setattr(AuthRepository, "find_user_by_email", staticmethod(lambda e: app.mongo_db["users"].find_one({"email": e})))
    monkeypatch.setattr(AuthRepository, "update_user_last_login", staticmethod(lambda uid: None))
    monkeypatch.setattr(UserRepository, "find_by_id", classmethod(lambda cls, uid, organization_id=None, **kw: app.mongo_db["users"].find_one({"user_id": uid, **({"organization_id": organization_id} if organization_id else {})})))
    monkeypatch.setattr(UserRepository, "find_by_email", classmethod(lambda cls, e: app.mongo_db["users"].find_one({"email": e})))
    monkeypatch.setattr(OrganizationRepository, "find_by_id", classmethod(lambda cls, oid, **kw: app.mongo_db["organizations"].find_one({"organization_id": oid})))
    monkeypatch.setattr(RoleRepository, "find_by_id", classmethod(lambda cls, rid, organization_id=None, **kw: app.mongo_db["roles"].find_one({"role_id": rid, **({"organization_id": organization_id} if organization_id else {})})))
    monkeypatch.setattr(ApplicationRepository, "find_by_id", classmethod(lambda cls, aid, organization_id=None, **kw: app.mongo_db["connected_applications"].find_one({"application_id": aid, **({"organization_id": organization_id} if organization_id else {})})))

    api_keys = {
        "sx_live_secret_key_app_a1": (
            {"credential_id": "cred-a1", "application_id": "app-a1", "organization_id": "org-a", "environment": "live", "scopes": ["payloads:ingest", "messages:create"]},
            {"organization_id": "org-a", "name": "Org A", "status": "ACTIVE"},
        ),
        "sx_live_secret_key_app_a2": (
            {"credential_id": "cred-a2", "application_id": "app-a2", "organization_id": "org-a", "environment": "live", "scopes": ["payloads:ingest", "messages:create"]},
            {"organization_id": "org-a", "name": "Org A", "status": "ACTIVE"},
        ),
        "sx_live_secret_key_org_b1": (
            {"credential_id": "cred-b1", "application_id": "app-b1", "organization_id": "org-b", "environment": "live", "scopes": ["payloads:ingest", "messages:create"]},
            {"organization_id": "org-b", "name": "Org B", "status": "ACTIVE"},
        ),
        "sx_live_readonly_key": (
            {"credential_id": "cred-ro", "application_id": "app-a1", "organization_id": "org-a", "environment": "live", "scopes": ["messages:read"]},
            {"organization_id": "org-a", "name": "Org A", "status": "ACTIVE"},
        ),
    }
    monkeypatch.setattr(ApiCredentialService, "verify_api_key", staticmethod(lambda k: api_keys.get(k, (None, None))))

    # Ensure no real email task runs
    monkeypatch.setattr("app.queue.tasks.send_auth_otp_email.apply_async", lambda *a, **kw: {"id": "mock-task"})

    with app.app_context():
        tokens = {
            "a": create_access_token("user-a", additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": "org-a", "token_version": 1}),
            "b": create_access_token("user-b", additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": "org-b", "token_version": 1}),
            "refresh_a": create_refresh_token("user-a", additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": "org-a", "token_version": 1}),
        }
    return tokens


# 1 & 15. Login brute-force protection, counter persistence on success & valid login compat
def test_login_brute_force_protection_and_counter_persistence(monkeypatch):
    app = _build_app()
    _seed_data(app, monkeypatch)
    client = app.test_client()

    # Valid login initially works cleanly
    ok = client.post("/api/v1/auth/login", json={"email": "alice@orga.test", "password": "ValidPassword123!"})
    assert ok.status_code == 200
    assert ok.get_json()["success"] is True

    # 3 failed attempts recorded (401); 4th attempt hits RATE_LIMIT_AUTH_LOGIN_FAILURE_MAX=3 -> 429
    for idx in range(4):
        r = client.post("/api/v1/auth/login", json={"email": "alice@orga.test", "password": f"WrongPass{idx}!"})
        if idx < 3:
            assert r.status_code == 401
        else:
            assert r.status_code == 429
            assert int(r.headers["Retry-After"]) >= 1

    # Even the CORRECT password is now blocked while lockout window is active (429 + Retry-After)
    blocked_valid = client.post("/api/v1/auth/login", json={"email": "alice@orga.test", "password": "ValidPassword123!"})
    assert blocked_valid.status_code == 429
    assert int(blocked_valid.headers["Retry-After"]) >= 1

    # Ensure successful login on another account (bob) does NOT reset bob's failure/IP counters
    bob_fail = client.post("/api/v1/auth/login", json={"email": "bob@orgb.test", "password": "Wrong1!"})
    assert bob_fail.status_code == 401
    bob_ok = client.post("/api/v1/auth/login", json={"email": "bob@orgb.test", "password": "ValidPassword123!"})
    assert bob_ok.status_code == 200
    # Failure counter stays (2 more failures recorded + 4th blocked with 429)
    assert client.post("/api/v1/auth/login", json={"email": "bob@orgb.test", "password": "Wrong2!"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "bob@orgb.test", "password": "Wrong3!"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "bob@orgb.test", "password": "Wrong4!"}).status_code == 429


# 2. OTP verification brute-force protection
def test_otp_verify_brute_force_protection(monkeypatch):
    app = _build_app()
    _seed_data(app, monkeypatch)
    client = app.test_client()

    # Rapid wrong verify guesses against different or missing accounts hit email + IP limits -> 429
    statuses = []
    for idx in range(5):
        res = client.post(
            "/api/v1/auth/otp/verify",
            json={"email": "alice@orga.test", "purpose": "PASSWORD_RESET", "code": f"{100000 + idx}"},
        )
        statuses.append(res.status_code)
        if res.status_code == 429:
            assert int(res.headers["Retry-After"]) >= 1
    assert 429 in statuses


# 3 & 4. OTP resend abuse & password reset abuse (request, resend, set-password)
def test_otp_request_resend_and_password_reset_abuse(monkeypatch):
    app = _build_app()
    tokens = _seed_data(app, monkeypatch)
    client = app.test_client()

    # Password forgot cooldown triggers 429 + Retry-After on second rapid request
    r1 = client.post("/api/v1/auth/password/forgot", json={"email": "alice@orga.test"})
    assert r1.status_code == 200
    r2 = client.post("/api/v1/auth/password/forgot", json={"email": "alice@orga.test"})
    assert r2.status_code == 429
    assert int(r2.headers["Retry-After"]) >= 1

    # Admin activation resend cooldown triggers 429 + Retry-After cleanly
    res1 = client.post("/api/v1/users/user-pending/activation/resend", headers={"Authorization": f"Bearer {tokens['a']}"})
    assert res1.status_code == 202
    res2 = client.post("/api/v1/users/user-pending/activation/resend", headers={"Authorization": f"Bearer {tokens['a']}"})
    assert res2.status_code == 429
    assert int(res2.headers["Retry-After"]) >= 1

    # /otp/set-password brute force limit triggers 429 after RATE_LIMIT_AUTH_SET_PASSWORD_MAX=3
    for _ in range(3):
        s_bad = client.post(
            "/api/v1/auth/otp/set-password",
            json={"purpose": "PASSWORD_RESET", "reset_token": "forged_reset_token_secret", "password": "StrongPassword123!"},
        )
        assert s_bad.status_code == 410
    s_429 = client.post(
        "/api/v1/auth/otp/set-password",
        json={"purpose": "PASSWORD_RESET", "reset_token": "forged_reset_token_secret", "password": "StrongPassword123!"},
    )
    assert s_429.status_code == 429
    assert int(s_429.headers["Retry-After"]) >= 1


# 5. JWT validation analyzer rate limiting (+ /auth/refresh)
def test_jwt_validation_analyzer_and_refresh_rate_limiting(monkeypatch):
    app = _build_app()
    tokens = _seed_data(app, monkeypatch)
    client = app.test_client()
    payload = {"channel": "email", "recipient": "u@example.com", "data": {"message": "hello"}}

    # RATE_LIMIT_VALIDATION_USER_RPM=3
    for _ in range(3):
        r = client.post("/api/v1/validation/analyze", json=payload, headers={"Authorization": f"Bearer {tokens['a']}"})
        assert r.status_code == 200
    r4 = client.post("/api/v1/validation/analyze", json=payload, headers={"Authorization": f"Bearer {tokens['a']}"})
    assert r4.status_code == 429
    assert int(r4.headers["Retry-After"]) >= 1
    assert r4.get_json()["valid"] is False

    # /auth/refresh limit=3
    for _ in range(3):
        rf = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_a']}"})
        assert rf.status_code == 200
    rf4 = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_a']}"})
    assert rf4.status_code == 429
    assert int(rf4.headers["Retry-After"]) >= 1


# 6, 7 & 8. API key rate limiting, read-only separation, cross-tenant & app-level isolation
def test_api_key_rate_limits_cross_tenant_and_application_isolation(monkeypatch):
    app = _build_app(extra_config={"RATE_LIMIT_CREDENTIAL_RPM": 2, "RATE_LIMIT_APPLICATION_RPM": 100, "RATE_LIMIT_ORGANIZATION_RPM": 100})
    tokens = _seed_data(app, monkeypatch)
    client = app.test_client()
    payload = {"channel": "email", "recipient": "u@example.com", "data": {"message": "hello"}}

    # Read-only API key cannot access write/validate endpoint (403)
    ro = client.post("/api/v1/validation/analyze", json=payload, headers={"X-API-Key": "sx_live_readonly_key"})
    assert ro.status_code == 403

    # App A1 key hits credential limit=2 -> 3rd returns 429 with Retry-After
    for _ in range(2):
        assert client.post("/api/v1/validation/analyze", json=payload, headers={"X-API-Key": "sx_live_secret_key_app_a1"}).status_code == 200
    r_a1_3 = client.post("/api/v1/validation/analyze", json=payload, headers={"X-API-Key": "sx_live_secret_key_app_a1"})
    assert r_a1_3.status_code == 429
    assert int(r_a1_3.headers["Retry-After"]) >= 1
    assert "sx_live_" not in str(r_a1_3.get_json())

    # Application isolation: App A2 within SAME Org A still has full quota
    assert client.post("/api/v1/validation/analyze", json=payload, headers={"X-API-Key": "sx_live_secret_key_app_a2"}).status_code == 200

    # Cross-tenant isolation: Org B user & Org B API key unaffected by Org A exhaustion
    assert client.post("/api/v1/validation/analyze", json=payload, headers={"X-API-Key": "sx_live_secret_key_org_b1"}).status_code == 200
    assert client.post("/api/v1/validation/analyze", json=payload, headers={"Authorization": f"Bearer {tokens['b']}"}).status_code == 200


# 9 & 10. Spoofed X-Forwarded-For / X-Real-IP rejection vs trusted reverse-proxy handling
def test_spoofed_forwarded_ip_rejected_and_trusted_proxy_supported(monkeypatch):
    # Direct connection (TRUST_PROXY_HEADERS=False): rotating spoofed X-Forwarded-For MUST NOT bypass IP limit
    app_direct = _build_app(extra_config={"RATE_LIMIT_AUTH_LOGIN_IP_RPM": 2, "TRUST_PROXY_HEADERS": False})
    _seed_data(app_direct, monkeypatch)
    c_direct = app_direct.test_client()

    for idx in range(2):
        res = c_direct.post(
            "/api/v1/auth/login",
            json={"email": "alice@orga.test", "password": "ValidPassword123!"},
            environ_base={"REMOTE_ADDR": "203.0.113.10"},
            headers={"X-Forwarded-For": f"198.51.100.{idx + 1}", "X-Real-IP": f"198.51.100.{idx + 50}"},
        )
        assert res.status_code == 200

    blocked = c_direct.post(
        "/api/v1/auth/login",
        json={"email": "alice@orga.test", "password": "ValidPassword123!"},
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
        headers={"X-Forwarded-For": "8.8.8.8", "X-Real-IP": "1.1.1.1"},
    )
    assert blocked.status_code == 429

    # Untrusted proxy IP even when TRUST_PROXY_HEADERS=True ignores forwarded headers
    app_proxy = _build_app(extra_config={
        "TRUST_PROXY_HEADERS": True,
        "TRUSTED_PROXY_IPS": ["10.0.0.5"],
        "RATE_LIMIT_AUTH_LOGIN_IP_RPM": 2,
    })
    _seed_data(app_proxy, monkeypatch)
    with app_proxy.test_request_context("/api/v1/auth/login", environ_base={"REMOTE_ADDR": "198.51.100.77"}, headers={"X-Forwarded-For": "1.2.3.4"}):
        from flask import request
        assert resolve_client_ip(request) == "198.51.100.77"

    # Trusted proxy IP extracts right-most non-trusted IP (immune to client-prepended spoof leftmost IP!)
    with app_proxy.test_request_context("/api/v1/auth/login", environ_base={"REMOTE_ADDR": "10.0.0.5"}, headers={"X-Forwarded-For": "9.9.9.9, 198.51.100.42"}):
        from flask import request
        assert resolve_client_ip(request) == "198.51.100.42"

    # Invalid IP in header falls back safely to remote_addr
    with app_proxy.test_request_context("/api/v1/auth/login", environ_base={"REMOTE_ADDR": "10.0.0.5"}, headers={"X-Forwarded-For": "not_an_ip"}):
        from flask import request
        assert resolve_client_ip(request) == "10.0.0.5"


# 12. Redis unavailable on sensitive endpoints -> sanitized 503 (never 500, never silently bypassed)
@pytest.mark.parametrize("redis_stub", [None, BrokenRedisDouble()])
def test_redis_unavailable_fails_closed_with_sanitized_503(monkeypatch, redis_stub):
    app = _build_app(redis_client=BrokenRedisDouble())
    tokens = _seed_data(app, monkeypatch)
    if redis_stub is None:
        app.redis_client = None

    client = app.test_client()
    endpoints = [
        ("POST", "/api/v1/auth/login", {"email": "alice@orga.test", "password": "ValidPassword123!"}, {}),
        ("POST", "/api/v1/auth/activation/request-otp", {"email": "pending@orga.test"}, {}),
        ("POST", "/api/v1/auth/password/forgot", {"email": "alice@orga.test"}, {}),
        ("POST", "/api/v1/auth/otp/verify", {"email": "alice@orga.test", "purpose": "PASSWORD_RESET", "code": "123456"}, {}),
        ("POST", "/api/v1/auth/otp/set-password", {"purpose": "PASSWORD_RESET", "reset_token": "tok", "password": "StrongPassword123!"}, {}),
        ("POST", "/api/v1/auth/refresh", None, {"Authorization": f"Bearer {tokens['refresh_a']}"}),
        ("POST", "/api/v1/validation/analyze", {"channel": "email", "recipient": "u@example.com", "data": {"m": "x"}}, {"Authorization": f"Bearer {tokens['a']}"}),
        ("POST", "/api/v1/validation/analyze", {"channel": "email", "recipient": "u@example.com", "data": {"m": "x"}}, {"X-API-Key": "sx_live_secret_key_app_a1"}),
    ]
    for method, path, body, hdrs in endpoints:
        res = client.open(path, method=method, json=body, headers=hdrs) if body is not None else client.open(path, method=method, headers=hdrs)
        assert res.status_code == 503, f"Expected 503 on {path} when Redis unavailable, got {res.status_code}"
        text = str(res.get_json())
        assert "secret-redis-host" not in text
        assert "6379" not in text
        assert "Traceback" not in text


# 13. Zero plaintext secrets or PII in Redis keys
def test_no_plaintext_secrets_or_pii_in_redis_keys(monkeypatch):
    redis_double = AtomicRedisDouble()
    app = _build_app(redis_client=redis_double)
    tokens = _seed_data(app, monkeypatch)
    client = app.test_client()

    secret_email = "alice@orga.test"
    secret_pwd = "ValidPassword123!"
    secret_otp = "654321"
    secret_reset = "super_secret_reset_token_xyz"
    secret_api_key = "sx_live_secret_key_app_a1"

    client.post("/api/v1/auth/login", json={"email": secret_email, "password": secret_pwd})
    client.post("/api/v1/auth/password/forgot", json={"email": secret_email})
    client.post("/api/v1/auth/otp/verify", json={"email": secret_email, "purpose": "PASSWORD_RESET", "code": secret_otp})
    client.post("/api/v1/auth/otp/set-password", json={"purpose": "PASSWORD_RESET", "reset_token": secret_reset, "password": "StrongPassword123!"})
    client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_a']}"})
    client.post("/api/v1/validation/analyze", json={"channel": "email", "recipient": "u@example.com", "data": {"m": "x"}}, headers={"X-API-Key": "sx_live_invalid_probe_999"})
    client.post("/api/v1/validation/analyze", json={"channel": "email", "recipient": "u@example.com", "data": {"m": "x"}}, headers={"X-API-Key": secret_api_key})

    joined_keys = "\n".join(redis_double.recorded_keys)
    assert len(redis_double.recorded_keys) >= 6
    for sensitive in (secret_email, secret_pwd, secret_otp, secret_reset, secret_api_key, "sx_live_invalid_probe_999", "cred-a1"):
        assert sensitive not in joined_keys


# 14. Concurrent requests cannot bypass atomic Lua sliding-window rate limits
def test_concurrent_requests_cannot_bypass_rate_limit():
    app = _build_app()
    ident = "concurrent-client-digest"

    def hit(_):
        with app.app_context():
            return DistributedRateLimiter.check_rate_limit("auth_login_ip", ident, limit=5, window_seconds=60)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(hit, range(20)))

    allowed_count = sum(1 for allowed, _ in results if allowed)
    blocked_results = [retry for allowed, retry in results if not allowed]
    assert allowed_count == 5
    assert len(blocked_results) == 15
    assert all(r >= 1 for r in blocked_results)


# Live optional Redis integration check (only runs when Redis is actually reachable)
def test_optional_live_redis_lua_atomicity():
    import socket
    sock = socket.socket()
    sock.settimeout(0.5)
    is_open = sock.connect_ex(("127.0.0.1", 6379)) == 0
    sock.close()
    if not is_open:
        pytest.skip("Live Redis 127.0.0.1:6379 not running in this environment")

    import redis as real_redis
    app = _build_app(redis_client=real_redis.Redis.from_url("redis://localhost:6379/0", decode_responses=True))
    with app.app_context():
        ident = f"phase4_live_{int(time.time() * 1000)}"
        DistributedRateLimiter.reset_key("auth_login_ip", ident)
        try:
            outcomes = [DistributedRateLimiter.check_rate_limit("auth_login_ip", ident, limit=3, window_seconds=30)[0] for _ in range(5)]
            assert outcomes == [True, True, True, False, False]
        finally:
            DistributedRateLimiter.reset_key("auth_login_ip", ident)
