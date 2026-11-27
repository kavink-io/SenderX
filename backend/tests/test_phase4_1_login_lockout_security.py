"""
Phase 4.1 Security Test Suite: Login Account Lockout DoS Remediation.

Verifies layered progressive login throttling across:
- Per-IP request rate limit (password spraying protection)
- Per-(IP + normalized email) failed-login limit (single-source brute force without locking other IPs)
- Higher-threshold account-global distributed failure tracking with bounded progressive backoff
- Email normalization consistency, Redis key privacy, trusted IP resolution,
  concurrency atomicity, and Redis outage fail-closed behavior (HTTP 503).
"""

from concurrent.futures import ThreadPoolExecutor
import copy
import math
import socket
import threading
import time
import bcrypt
from flask import Flask
from flask_jwt_extended import JWTManager
import pytest

from app.modules.api_credentials.rate_limiter import DistributedRateLimiter
from app.modules.auth.routes import auth_bp


class AtomicLoginRedisDouble:
    """Thread-safe Redis double implementing Phase 4 & 4.1 Lua ZSET + backoff semantics."""

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

            # Global backoff Lua scripts use 2 keys
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

                is_record = len(argv) >= 6
                if is_record:
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

                # Check script
                gcount = len(zset)
                if gcount < threshold:
                    return [1, 0, gcount]

                unlock_entry = self.kv.get(bkey)
                unlock_ts = unlock_entry[0] if (unlock_entry and unlock_entry[1] > now) else 0.0
                if unlock_ts > now:
                    retry = max(1, int(math.ceil(unlock_ts - now)))
                    return [0, retry, gcount]

                excess = min(gcount - threshold, 6)
                backoff = max(1.0, min(max_backoff, base_backoff * (2 ** excess)))
                self.kv[bkey] = (now + backoff, now + max_backoff + 10)
                return [1, 0, gcount]

            # Single-key sliding window scripts
            key = keys[0]
            now = float(argv[0])
            window = float(argv[1])
            limit = int(argv[2])

            zset = self.zsets.setdefault(key, {})
            for m in [m for m, sc in zset.items() if sc <= now - window]:
                del zset[m]

            count = len(zset)
            if len(argv) == 3:
                if count >= limit:
                    oldest = min(zset.values()) if zset else now
                    return [0, max(1, int(math.ceil(oldest + window - now)))]
                return [1, 0]

            member = str(argv[3])
            always_record = int(argv[4]) if len(argv) > 4 else 0
            if count >= limit:
                if always_record == 1:
                    zset[member] = now
                oldest = min(zset.values()) if zset else now
                return [0, max(1, int(math.ceil(oldest + window - now)))]

            zset[member] = now
            return [1, 0]

    def delete(self, *keys):
        with self.lock:
            for k in keys:
                self.zsets.pop(k, None)
                self.kv.pop(k, None)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = [copy.deepcopy(d) for d in (docs or [])]

    def find_one(self, query=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in (query or {}).items()):
                return copy.deepcopy(d)
        return None


class FakeMongoDB:
    def __init__(self):
        self._cols = {
            "admins": FakeCollection(),
            "users": FakeCollection(),
            "organizations": FakeCollection(),
        }

    def __getitem__(self, name):
        return self._cols.setdefault(name, FakeCollection())


def _build_app(redis_client=None, extra_config=None):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["APP_ENV"] = "development"
    app.config["SECRET_KEY"] = "phase41-secret-key"
    app.config["JWT_SECRET_KEY"] = "phase41-jwt-secret-key-at-least-32-bytes"
    app.config["OTP_HMAC_SECRET"] = "phase41-otp-secret-at-least-32-bytes"
    app.config["TRUST_PROXY_HEADERS"] = False
    app.config["TRUSTED_PROXY_IPS"] = ["10.0.0.5"]
    app.config["RATE_LIMIT_AUTH_LOGIN_IP_RPM"] = 20
    app.config["RATE_LIMIT_AUTH_LOGIN_PAIR_FAILURE_MAX"] = 5
    app.config["RATE_LIMIT_AUTH_LOGIN_WINDOW_SECONDS"] = 300
    app.config["RATE_LIMIT_AUTH_LOGIN_GLOBAL_FAILURE_MAX"] = 15
    app.config["RATE_LIMIT_AUTH_LOGIN_GLOBAL_WINDOW_SECONDS"] = 900
    app.config["RATE_LIMIT_AUTH_LOGIN_GLOBAL_BASE_BACKOFF_SECONDS"] = 2
    app.config["RATE_LIMIT_AUTH_LOGIN_GLOBAL_MAX_BACKOFF_SECONDS"] = 30
    if extra_config:
        app.config.update(extra_config)

    JWTManager(app)
    app.mongo_db = FakeMongoDB()
    app.redis_client = AtomicLoginRedisDouble() if redis_client is None else redis_client
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    return app


def _seed_users(app, monkeypatch):
    from app.modules.auth.repository import AuthRepository
    from app.modules.organizations.repository import OrganizationRepository

    pwd_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(4)).decode("utf-8")
    app.mongo_db["organizations"].docs.append({"organization_id": "org-a", "name": "Org A", "status": "ACTIVE"})
    app.mongo_db["users"].docs.append({
        "user_id": "user-alice",
        "organization_id": "org-a",
        "name": "Alice",
        "email": "alice@orga.test",
        "password_hash": pwd_hash,
        "is_active": True,
        "status": "ACTIVE",
        "token_version": 1,
        "role_ids": [],
    })

    monkeypatch.setattr(AuthRepository, "find_by_email", staticmethod(lambda e: app.mongo_db["admins"].find_one({"email": e})))
    monkeypatch.setattr(AuthRepository, "find_user_by_email", staticmethod(lambda e: app.mongo_db["users"].find_one({"email": e})))
    monkeypatch.setattr(AuthRepository, "update_user_last_login", staticmethod(lambda uid: None))
    monkeypatch.setattr(OrganizationRepository, "find_by_id", classmethod(lambda cls, oid, **kw: app.mongo_db["organizations"].find_one({"organization_id": oid})))


# 1 & 2. Five failures from one IP throttle that (IP, email) pair WITHOUT blocking a different IP
def test_pair_throttling_does_not_lock_out_legitimate_different_ip(monkeypatch):
    app = _build_app()
    _seed_users(app, monkeypatch)
    client = app.test_client()

    # Attacker at IP_A sends 5 wrong passwords for Alice -> 401 each; 6th from IP_A is throttled (429)
    for i in range(5):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@orga.test", "password": f"WrongPass{i}!"},
            environ_base={"REMOTE_ADDR": "198.51.100.10"},
        )
        assert r.status_code == 401

    r_pair_blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@orga.test", "password": "WrongPassFinal!"},
        environ_base={"REMOTE_ADDR": "198.51.100.10"},
    )
    assert r_pair_blocked.status_code == 429
    assert int(r_pair_blocked.headers["Retry-After"]) >= 1

    # Legitimate Alice logging in from her own IP_B is NOT locked out!
    r_legit = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@orga.test", "password": "ValidPassword123!"},
        environ_base={"REMOTE_ADDR": "203.0.113.55"},
    )
    assert r_legit.status_code == 200
    assert r_legit.get_json()["success"] is True


# 3 & 5. Distributed attempts across multiple IPs trigger bounded progressive global backoff,
#        and legitimate user can still log in cleanly once short backoff expires (no permanent lockout)
def test_distributed_attack_triggers_bounded_global_backoff_without_permanent_lockout(monkeypatch):
    app = _build_app(extra_config={
        "RATE_LIMIT_AUTH_LOGIN_GLOBAL_FAILURE_MAX": 15,
        "RATE_LIMIT_AUTH_LOGIN_GLOBAL_BASE_BACKOFF_SECONDS": 2,
        "RATE_LIMIT_AUTH_LOGIN_GLOBAL_MAX_BACKOFF_SECONDS": 16,
    })
    _seed_users(app, monkeypatch)
    client = app.test_client()

    # 3 distinct attacker IPs fail 5 times each = 15 failures total across IPs
    for ip_idx in range(3):
        attacker_ip = f"198.51.100.{ip_idx + 1}"
        for attempt in range(5):
            r = client.post(
                "/api/v1/auth/login",
                json={"email": "alice@orga.test", "password": f"Bad{ip_idx}-{attempt}!"},
                environ_base={"REMOTE_ADDR": attacker_ip},
            )
            assert r.status_code == 401

    # Attempt 16 from a brand-new IP_4 hits account-global progressive backoff (429 Retry-After=2)
    r_global_block = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@orga.test", "password": "ValidPassword123!"},
        environ_base={"REMOTE_ADDR": "203.0.113.77"},
    )
    assert r_global_block.status_code == 429
    retry_after = int(r_global_block.headers["Retry-After"])
    assert 1 <= retry_after <= 16

    # After bounded backoff expires, legitimate Alice on clean IP logs in with valid password (200)
    with app.app_context():
        bkey = DistributedRateLimiter._build_key(
            "auth_login_global_backoff",
            DistributedRateLimiter.hash_identifier("auth_login_acct", "alice@orga.test"),
        )
    app.redis_client.kv[bkey] = (time.time() - 1.0, time.time() + 10.0)

    r_after_backoff = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@orga.test", "password": "ValidPassword123!"},
        environ_base={"REMOTE_ADDR": "203.0.113.77"},
    )
    assert r_after_backoff.status_code == 200
    assert r_after_backoff.get_json()["success"] is True

    # Abuse counters were NOT cleared by the successful login: once cooldown gate expires,
    # a fresh wrong guess immediately escalates backoff from 2s to 4s
    app.redis_client.kv[bkey] = (time.time() - 1.0, time.time() + 10.0)
    r_next_fail = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@orga.test", "password": "WrongAfterSuccess!"},
        environ_base={"REMOTE_ADDR": "203.0.113.78"},
    )
    assert r_next_fail.status_code == 429
    assert int(r_next_fail.headers["Retry-After"]) >= 4


# 4. IP-based password spraying across many different emails is restricted
def test_ip_based_password_spraying_blocked(monkeypatch):
    app = _build_app(extra_config={"RATE_LIMIT_AUTH_LOGIN_IP_RPM": 6})
    _seed_users(app, monkeypatch)
    client = app.test_client()

    for idx in range(6):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": f"victim{idx}@orga.test", "password": "Spring2026!"},
            environ_base={"REMOTE_ADDR": "198.51.100.200"},
        )
        assert r.status_code == 401

    r_spray_blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "victim99@orga.test", "password": "Spring2026!"},
        environ_base={"REMOTE_ADDR": "198.51.100.200"},
    )
    assert r_spray_blocked.status_code == 429
    assert int(r_spray_blocked.headers["Retry-After"]) >= 1


# 6 & 7. Email normalization consistency & zero plaintext email/secrets in Redis keys
def test_email_normalization_and_no_plaintext_secrets_in_redis_keys(monkeypatch):
    redis_double = AtomicLoginRedisDouble()
    app = _build_app(redis_client=redis_double)
    _seed_users(app, monkeypatch)
    client = app.test_client()

    secret_pwd = "MyWrongSecretPass123!"
    variants = [
        "Alice@OrgA.test",
        " alice@orga.test ",
        "ALICE@ORGA.TEST",
        "aLiCe@orga.test",
        "alice@orga.test",
    ]
    for v in variants:
        r = client.post(
            "/api/v1/auth/login",
            json={"email": v, "password": secret_pwd},
            environ_base={"REMOTE_ADDR": "203.0.113.11"},
        )
        assert r.status_code == 401

    # 6th attempt using yet another case variant hits the shared pair failure limit=5!
    r6 = client.post(
        "/api/v1/auth/login",
        json={"email": "  ALICE@orgA.TEST ", "password": secret_pwd},
        environ_base={"REMOTE_ADDR": "203.0.113.11"},
    )
    assert r6.status_code == 429

    joined = "\n".join(redis_double.recorded_keys)
    assert len(redis_double.recorded_keys) >= 10
    for forbidden in ("alice@orga.test", "Alice", "orga.test", secret_pwd, "203.0.113.11"):
        assert forbidden.lower() not in joined.lower()


# 8. Spoofed X-Forwarded-For cannot bypass pair or IP restrictions
def test_spoofed_xff_cannot_bypass_login_throttling(monkeypatch):
    app = _build_app(extra_config={"TRUST_PROXY_HEADERS": False})
    _seed_users(app, monkeypatch)
    client = app.test_client()

    for idx in range(5):
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@orga.test", "password": f"Bad{idx}!"},
            environ_base={"REMOTE_ADDR": "198.51.100.88"},
            headers={"X-Forwarded-For": f"10.10.10.{idx + 1}", "X-Real-IP": f"10.10.20.{idx + 1}"},
        )
        assert r.status_code == 401

    # Rotating X-Forwarded-For still resolves to direct 198.51.100.88 -> blocked with 429
    r_blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@orga.test", "password": "BadNext!"},
        environ_base={"REMOTE_ADDR": "198.51.100.88"},
        headers={"X-Forwarded-For": "8.8.4.4", "X-Real-IP": "1.1.1.1"},
    )
    assert r_blocked.status_code == 429


# 9. Concurrent requests cannot bypass pair or global backoff limits
def test_concurrent_login_requests_cannot_bypass_limits():
    app = _build_app()
    pair_ident = "concurrent-pair-digest"
    acct_ident = "concurrent-acct-digest"

    def hit_pair(_):
        with app.app_context():
            return DistributedRateLimiter.check_rate_limit(
                "auth_login_failure_pair", pair_ident, limit=5, window_seconds=300
            )

    with ThreadPoolExecutor(max_workers=12) as pool:
        pair_results = list(pool.map(hit_pair, range(18)))

    assert sum(1 for ok, _ in pair_results if ok) == 5
    assert sum(1 for ok, _ in pair_results if not ok) == 13

    # Also test concurrent backoff check after global threshold=15 is armed
    with app.app_context():
        for _ in range(15):
            DistributedRateLimiter.record_global_login_failure(
                acct_ident, threshold=15, window_seconds=900, base_backoff_seconds=5, max_backoff_seconds=30
            )

    def hit_global(_):
        with app.app_context():
            return DistributedRateLimiter.check_global_login_backoff(
                acct_ident, threshold=15, window_seconds=900, base_backoff_seconds=5, max_backoff_seconds=30
            )

    with ThreadPoolExecutor(max_workers=10) as pool:
        global_results = list(pool.map(hit_global, range(15)))

    assert all(not ok and ra >= 1 for ok, ra in global_results)


# 10. Redis outage retains fail-closed 503 behavior (never silently bypassed)
def test_redis_outage_fails_closed_with_503(monkeypatch):
    class DownRedis:
        def eval(self, *a, **kw):
            raise ConnectionError("redis://internal-prod-redis:6379 refused")

    for broken_client in (None, DownRedis()):
        app = _build_app(redis_client=DownRedis())
        _seed_users(app, monkeypatch)
        if broken_client is None:
            app.redis_client = None
        res = app.test_client().post(
            "/api/v1/auth/login",
            json={"email": "alice@orga.test", "password": "ValidPassword123!"},
        )
        assert res.status_code == 503
        body_text = str(res.get_json())
        assert "internal-prod-redis" not in body_text
        assert "6379" not in body_text


# Live Redis multi-IP / backoff / concurrency check when localhost:6379 is running
def test_live_redis_phase4_1_layered_lockout_and_concurrency():
    s = socket.socket()
    s.settimeout(0.5)
    is_open = s.connect_ex(("127.0.0.1", 6379)) == 0
    s.close()
    if not is_open:
        pytest.skip("Live Redis 127.0.0.1:6379 unavailable")

    import redis as real_redis
    app = _build_app(redis_client=real_redis.Redis.from_url("redis://localhost:6379/0", decode_responses=True))
    acct_id = f"live_p41_{int(time.time() * 1000)}"
    gkey = DistributedRateLimiter._build_key("auth_login_failure_global", acct_id)
    bkey = DistributedRateLimiter._build_key("auth_login_global_backoff", acct_id)
    app.redis_client.delete(gkey, bkey)

    try:
        with app.app_context():
            # First 15 failures succeed in recording; 15th arms 2s backoff
            for i in range(15):
                ok, retry = DistributedRateLimiter.record_global_login_failure(
                    acct_id, threshold=15, window_seconds=900, base_backoff_seconds=2, max_backoff_seconds=16
                )
                assert ok is True and retry == 0

            # Immediate concurrent checks while 2s backoff is active all return False with retry >= 1
            def check_one(_):
                with app.app_context():
                    return DistributedRateLimiter.check_global_login_backoff(
                        acct_id, threshold=15, window_seconds=900, base_backoff_seconds=2, max_backoff_seconds=16
                    )

            with ThreadPoolExecutor(max_workers=8) as pool:
                live_checks = list(pool.map(check_one, range(12)))
            assert all((not ok) and retry >= 1 for ok, retry in live_checks)
    finally:
        app.redis_client.delete(gkey, bkey)
