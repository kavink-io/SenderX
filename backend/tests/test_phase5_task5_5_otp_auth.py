import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from flask_jwt_extended import create_access_token

from app.adapters.adapter_registry import AdapterRegistry
from app.modules.api_credentials.rate_limiter import DistributedRateLimiter
from app.modules.auth.otp_service import OTPService, OTPServiceError
from app.modules.auth.repository import AuthRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.users.audit_repository import SecurityAuditRepository
from app.modules.users.repository import UserRepository
from app.queue.tasks import send_auth_otp_email


@pytest.fixture
def otp_context(app, client, monkeypatch):
    app.config["OTP_HMAC_SECRET"] = "test-only-otp-hmac-secret"
    app.config["APP_ENV"] = "test"
    app.config["TESTING"] = True
    app.config["AUTH_OTP_EMAIL_PROVIDER"] = None

    suffix = uuid.uuid4().hex[:10]
    organization_id = f"otp-org-{suffix}"
    role_id = f"otp-role-{suffix}"
    admin_id = f"otp-admin-{suffix}"
    admin_email = f"admin-{suffix}@example.test"
    admin_password = "AdminPassword123!"
    db = app.mongo_db

    OrganizationRepository.create({
        "organization_id": organization_id,
        "name": f"OTP Test {suffix}",
        "slug": f"otp-test-{suffix}",
        "status": "ACTIVE"
    })
    db["roles"].insert_one({
        "role_id": role_id,
        "organization_id": organization_id,
        "name": "ORG_ADMIN",
        "scope": "ORGANIZATION",
        "is_system_role": True,
        "permissions": ["organization:users:manage", "organization:users:delete"]
    })
    admin_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
    UserRepository.create({
        "user_id": admin_id,
        "organization_id": organization_id,
        "name": "OTP Test Admin",
        "email": admin_email,
        "password_hash": admin_hash,
        "role_ids": [role_id],
        "role_assignments": [{"role_id": role_id, "application_id": None}],
        "status": "ACTIVE",
        "is_active": True,
        "token_version": 1
    })
    with app.app_context():
        admin_token = create_access_token(
            identity=admin_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": organization_id,
                "role_ids": [role_id],
                "email": admin_email,
                "token_version": 1
            }
        )

    queued_emails = []
    def capture_email_task(*, args=None, **kwargs):
        queued_emails.append(args)
        return {"id": f"task-{len(queued_emails)}"}

    monkeypatch.setattr(send_auth_otp_email, "apply_async", capture_email_task)

    limiter = {"blocked_dimension": None, "calls": []}
    def fake_rate_limit(dimension, identifier, limit=None, window_seconds=60):
        limiter["calls"].append({
            "dimension": dimension,
            "identifier": identifier,
            "limit": limit,
            "window_seconds": window_seconds
        })
        if limiter["blocked_dimension"] == dimension:
            return False, 37
        return True, 0

    monkeypatch.setattr(
        DistributedRateLimiter,
        "check_rate_limit",
        staticmethod(fake_rate_limit)
    )

    return {
        "app": app,
        "client": client,
        "db": db,
        "organization_id": organization_id,
        "role_id": role_id,
        "admin_id": admin_id,
        "admin_token": admin_token,
        "admin_email": admin_email,
        "queued": queued_emails,
        "limiter": limiter
    }


def create_employee(context, email=None, name="Pending Employee"):
    suffix = uuid.uuid4().hex[:8]
    email = email or f"employee-{suffix}@example.test"
    response = context["client"].post(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {context['admin_token']}"},
        json={
            "name": name,
            "email": email,
            "employee_code": f"EMP-{suffix.upper()}",
            "role_ids": [context["role_id"]],
            "role_assignments": [{
                "role_id": context["role_id"],
                "application_id": None
            }]
        }
    )
    return response, email


def create_active_user(context, email=None, password="ExistingPassword123!"):
    suffix = uuid.uuid4().hex[:8]
    email = email or f"active-{suffix}@example.test"
    user_id = f"user-{suffix}"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    UserRepository.create({
        "user_id": user_id,
        "organization_id": context["organization_id"],
        "name": "Existing Employee",
        "email": email,
        "password_hash": password_hash,
        "status": "ACTIVE",
        "is_active": True,
        "role_ids": [context["role_id"]],
        "role_assignments": [{
            "role_id": context["role_id"],
            "application_id": None
        }],
        "token_version": 1
    })
    return user_id, email, password


def get_queued_code(context, index=-1):
    encrypted_payload, _provider = context["queued"][index]
    with context["app"].app_context():
        return OTPService.decrypt_email_payload(encrypted_payload)["code"]


def post_json(context, path, body, headers=None):
    return context["client"].post(path, json=body, headers=headers or {})


def request_activation_code(context, email):
    return post_json(
        context,
        "/api/v1/auth/activation/request-otp",
        {"email": email}
    )


def request_reset_code(context, email):
    return post_json(
        context,
        "/api/v1/auth/password/forgot",
        {"email": email}
    )


def verify_code(context, email, purpose, code):
    return post_json(context, "/api/v1/auth/otp/verify", {
        "email": email,
        "purpose": purpose,
        "code": code
    })


def set_password(context, purpose, reset_token, password="StrongPass123!"):
    return post_json(context, "/api/v1/auth/otp/set-password", {
        "purpose": purpose,
        "reset_token": reset_token,
        "password": password
    })


def wrong_code(valid_code, attempt):
    candidate = f"{attempt:06d}"
    if candidate == valid_code:
        candidate = f"{(attempt + 1) % 1_000_000:06d}"
    return candidate


def test_pending_employee_cannot_login_and_create_rejects_password(otp_context):
    response, email = create_employee(otp_context)
    assert response.status_code == 201
    user = UserRepository.find_by_email(email)
    assert user["status"] == "PENDING_ACTIVATION"
    assert user["is_active"] is False
    assert "password_hash" not in user
    assert "temporary_password" not in response.json["data"]

    login = post_json(otp_context, "/api/v1/auth/login", {
        "email": email,
        "password": "Anything123!"
    })
    assert login.status_code == 401
    assert "activate" in login.json["message"].lower()

    rejected = otp_context["client"].post(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {otp_context['admin_token']}"},
        json={
            "name": "No Password",
            "email": f"no-password-{uuid.uuid4().hex[:8]}@example.test",
            "employee_code": f"EMP-{uuid.uuid4().hex[:8].upper()}",
            "password": None,
            "role_ids": [otp_context["role_id"]]
        }
    )
    assert rejected.status_code == 400
    assert "activation" in rejected.json["message"].lower()


def test_activation_full_flow(otp_context):
    response, email = create_employee(otp_context)
    assert response.status_code == 201

    requested = request_activation_code(otp_context, email)
    assert requested.status_code == 200
    assert "sent" in requested.json["message"].lower()
    assert len(otp_context["queued"]) == 1
    code = get_queued_code(otp_context)
    assert code.isdigit() and len(code) == 6
    requested_audit = otp_context["db"]["security_audit_logs"].find_one({
        "event_type": "ACTIVATION_OTP_REQUESTED",
        "target_name": "Pending Employee"
    })
    assert requested_audit["action_label"] == "Activation Code Requested"

    verified = verify_code(otp_context, email, "ACTIVATION", code)
    assert verified.status_code == 200
    assert "reset_token" in verified.json["data"]
    assert code not in str(verified.json)

    activated = set_password(
        otp_context,
        "ACTIVATION",
        verified.json["data"]["reset_token"]
    )
    assert activated.status_code == 200
    user = UserRepository.find_by_email(email)
    assert user["status"] == "ACTIVE"
    assert user["is_active"] is True
    assert user.get("password_hash")
    assert user["token_version"] == 2
    activated_audit = otp_context["db"]["security_audit_logs"].find_one({
        "event_type": "ACCOUNT_ACTIVATED",
        "target_id": user["user_id"]
    })
    assert activated_audit["target_name"] == "Pending Employee"

    login = post_json(otp_context, "/api/v1/auth/login", {
        "email": email,
        "password": "StrongPass123!"
    })
    assert login.status_code == 200
    assert login.json["success"] is True


def test_wrong_otp_is_rejected(otp_context):
    _user_id, email, _password = create_active_user(otp_context)
    assert request_reset_code(otp_context, email).status_code == 200
    code = get_queued_code(otp_context)

    result = verify_code(
        otp_context,
        email,
        "PASSWORD_RESET",
        wrong_code(code, 0)
    )
    assert result.status_code == 400
    assert "incorrect" in result.json["message"].lower()
    record = otp_context["db"]["auth_otps"].find_one({"email": email})
    assert record["attempts"] == 1


def test_expired_otp_is_rejected(otp_context):
    _user_id, email, _password = create_active_user(otp_context)
    request_reset_code(otp_context, email)
    otp_context["db"]["auth_otps"].update_one(
        {"email": email},
        {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}}
    )

    result = verify_code(otp_context, email, "PASSWORD_RESET", get_queued_code(otp_context))
    assert result.status_code == 410
    assert "expired" in result.json["message"].lower()


def test_otp_reuse_is_rejected(otp_context):
    _user_id, email, _password = create_active_user(otp_context)
    request_reset_code(otp_context, email)
    code = get_queued_code(otp_context)

    assert verify_code(otp_context, email, "PASSWORD_RESET", code).status_code == 200
    reused = verify_code(otp_context, email, "PASSWORD_RESET", code)
    assert reused.status_code == 400
    assert "already been used" in reused.json["message"].lower()


def test_fifth_wrong_attempt_locks_otp_and_audits_without_code(otp_context):
    user_id, email, _password = create_active_user(otp_context)
    request_reset_code(otp_context, email)
    code = get_queued_code(otp_context)

    for attempt in range(4):
        result = verify_code(
            otp_context,
            email,
            "PASSWORD_RESET",
            wrong_code(code, attempt)
        )
        assert result.status_code == 400
    locked = verify_code(
        otp_context,
        email,
        "PASSWORD_RESET",
        wrong_code(code, 999999)
    )
    assert locked.status_code == 429
    assert "too many" in locked.json["message"].lower()

    record = otp_context["db"]["auth_otps"].find_one({"email": email})
    assert record["status"] == "LOCKED"
    assert record["attempts"] == 5
    audit = otp_context["db"]["security_audit_logs"].find_one({
        "event_type": "OTP_LOCKED",
        "target_id": user_id
    })
    assert audit["target_name"] == "Existing Employee"
    assert audit["action_label"] == "Verification Code Locked"
    assert code not in str(audit)


def test_resend_cooldown_returns_429(otp_context):
    _response, email = create_employee(otp_context)
    assert request_activation_code(otp_context, email).status_code == 200
    otp_context["limiter"]["blocked_dimension"] = "auth_otp_cooldown"

    result = request_activation_code(otp_context, email)
    assert result.status_code == 429
    assert "wait" in result.json["message"].lower()
    assert result.headers["Retry-After"] == "37"
    cooldown = next(
        call for call in otp_context["limiter"]["calls"]
        if call["dimension"] == "auth_otp_cooldown"
    )
    assert cooldown["limit"] == 1
    assert cooldown["window_seconds"] == 60


@pytest.mark.parametrize("dimension", ["auth_otp_email", "auth_otp_ip"])
def test_per_email_and_per_ip_limits_return_429(otp_context, dimension):
    otp_context["limiter"]["blocked_dimension"] = dimension
    result = request_reset_code(otp_context, f"unknown-{uuid.uuid4().hex[:8]}@example.test")

    assert result.status_code == 429
    assert "too many" in result.json["message"].lower()
    assert result.json["retry_after"] == 37
    assert any(call["dimension"] == dimension for call in otp_context["limiter"]["calls"])
    expected_limit = 5 if dimension == "auth_otp_email" else 20
    expected_window = 3600
    assert any(
        call["dimension"] == dimension
        and call["limit"] == expected_limit
        and call["window_seconds"] == expected_window
        for call in otp_context["limiter"]["calls"]
    )
    assert all(
        "example.test" not in call["identifier"]
        for call in otp_context["limiter"]["calls"]
    )


def test_purpose_separation_rejects_cross_purpose_code(otp_context):
    _response, email = create_employee(otp_context)
    request_activation_code(otp_context, email)
    code = get_queued_code(otp_context)

    wrong_purpose = verify_code(otp_context, email, "PASSWORD_RESET", code)
    assert wrong_purpose.status_code == 400
    assert verify_code(otp_context, email, "ACTIVATION", code).status_code == 200


def test_new_code_invalidates_previous_code(otp_context, monkeypatch):
    _response, email = create_employee(otp_context)
    codes = iter([123456, 654321])
    monkeypatch.setattr(
        "app.modules.auth.otp_service.secrets.randbelow",
        lambda _limit: next(codes)
    )
    request_activation_code(otp_context, email)
    first_code = get_queued_code(otp_context, 0)
    request_activation_code(otp_context, email)
    second_code = get_queued_code(otp_context, 1)

    records = list(otp_context["db"]["auth_otps"].find({"email": email}))
    assert len(records) == 2
    assert next(record for record in records if record["otp_hash"] == OTPService._digest(
        "ACTIVATION", email, first_code
    ))["status"] == "INVALIDATED"
    assert verify_code(otp_context, email, "ACTIVATION", first_code).status_code == 400
    assert verify_code(otp_context, email, "ACTIVATION", second_code).status_code == 200


def test_reset_token_is_single_use_and_expires(otp_context):
    _user_id, email, _password = create_active_user(otp_context)
    request_reset_code(otp_context, email)
    code = get_queued_code(otp_context)
    token = verify_code(otp_context, email, "PASSWORD_RESET", code).json["data"]["reset_token"]

    assert set_password(otp_context, "PASSWORD_RESET", token).status_code == 200
    second_use = set_password(otp_context, "PASSWORD_RESET", token)
    assert second_use.status_code == 410
    assert "already used" in second_use.json["message"].lower()

    another_email = f"expiry-{uuid.uuid4().hex[:8]}@example.test"
    create_active_user(otp_context, email=another_email)
    request_reset_code(otp_context, another_email)
    token2 = verify_code(
        otp_context,
        another_email,
        "PASSWORD_RESET",
        get_queued_code(otp_context)
    ).json["data"]["reset_token"]
    otp_context["db"]["auth_otps"].update_one(
        {"email": another_email, "status": "VERIFIED"},
        {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}}
    )
    expired = set_password(otp_context, "PASSWORD_RESET", token2)
    assert expired.status_code == 410


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("Ab1!xyz", "8 characters"),
        ("alllowercase1!", "uppercase"),
        ("ALLUPPERCASE1!", "lowercase"),
        ("NoDigit!!", "number"),
        ("NoSpecial123", "special character")
    ]
)
def test_password_policy_is_enforced(otp_context, password, message):
    _user_id, email, _old_password = create_active_user(otp_context)
    request_reset_code(otp_context, email)
    code = get_queued_code(otp_context)
    reset_token = verify_code(
        otp_context,
        email,
        "PASSWORD_RESET",
        code
    ).json["data"]["reset_token"]

    result = set_password(
        otp_context,
        "PASSWORD_RESET",
        reset_token,
        password=password
    )
    assert result.status_code == 400
    assert message in result.json["message"].lower()


def test_forgot_password_response_is_generic_for_unknown_inactive_and_deleted(otp_context):
    _active_id, active_email, _password = create_active_user(otp_context)
    inactive_email = f"inactive-{uuid.uuid4().hex[:8]}@example.test"
    UserRepository.create({
        "user_id": f"inactive-{uuid.uuid4().hex[:8]}",
        "organization_id": otp_context["organization_id"],
        "name": "Inactive Employee",
        "email": inactive_email,
        "password_hash": "unused",
        "status": "INACTIVE",
        "is_active": False
    })
    deleted_email = f"deleted-{uuid.uuid4().hex[:8]}@example.test"
    UserRepository.create({
        "user_id": f"deleted-{uuid.uuid4().hex[:8]}",
        "organization_id": otp_context["organization_id"],
        "name": "Deleted Employee",
        "email": deleted_email,
        "password_hash": "unused",
        "status": "DELETED",
        "is_active": False,
        "is_deleted": True,
        "deleted_at": datetime.now(timezone.utc).isoformat()
    })
    unknown_email = f"unknown-{uuid.uuid4().hex[:8]}@example.test"

    responses = [
        request_reset_code(otp_context, email)
        for email in (unknown_email, inactive_email, deleted_email)
    ]
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json == responses[1].json == responses[2].json
    assert len(otp_context["queued"]) == 0
    assert otp_context["db"]["auth_otps"].count_documents({"email": {"$in": [
        unknown_email, inactive_email, deleted_email
    ]}}) == 0

    # Eligible active users receive the same public response shape and message.
    eligible = request_reset_code(otp_context, active_email)
    assert eligible.status_code == 200
    assert eligible.json == responses[0].json
    assert len(otp_context["queued"]) == 1


def test_inactive_organization_blocks_password_reset(otp_context):
    organization_id = f"inactive-org-{uuid.uuid4().hex[:8]}"
    OrganizationRepository.create({
        "organization_id": organization_id,
        "name": "Inactive OTP Org",
        "slug": f"inactive-otp-{uuid.uuid4().hex[:8]}",
        "status": "INACTIVE"
    })
    email = f"inactive-org-user-{uuid.uuid4().hex[:8]}@example.test"
    UserRepository.create({
        "user_id": f"inactive-org-user-{uuid.uuid4().hex[:8]}",
        "organization_id": organization_id,
        "name": "Inactive Organization User",
        "email": email,
        "password_hash": "unused",
        "status": "ACTIVE",
        "is_active": True
    })

    result = request_reset_code(otp_context, email)
    assert result.status_code == 200
    assert len(otp_context["queued"]) == 0
    assert otp_context["db"]["auth_otps"].count_documents({"email": email}) == 0


def test_old_tokens_and_password_are_invalid_after_reset(otp_context):
    user_id, email, old_password = create_active_user(otp_context)
    with otp_context["app"].app_context():
        legacy_token = create_access_token(
            identity=user_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": otp_context["organization_id"],
                "role_ids": [otp_context["role_id"]],
                "email": email
            }
        )
    assert request_reset_code(otp_context, email).status_code == 200
    code = get_queued_code(otp_context)
    token = verify_code(otp_context, email, "PASSWORD_RESET", code).json["data"]["reset_token"]
    assert set_password(otp_context, "PASSWORD_RESET", token).status_code == 200

    old_session = otp_context["client"].get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {legacy_token}"}
    )
    assert old_session.status_code == 401
    assert post_json(otp_context, "/api/v1/auth/login", {
        "email": email,
        "password": old_password
    }).status_code == 401
    new_login = post_json(otp_context, "/api/v1/auth/login", {
        "email": email,
        "password": "StrongPass123!"
    })
    assert new_login.status_code == 200
    assert UserRepository.find_by_id(user_id)["token_version"] == 2
    assert otp_context["db"]["security_audit_logs"].count_documents({
        "event_type": "PASSWORD_RESET_REQUESTED",
        "target_id": user_id
    }) == 1
    assert otp_context["db"]["security_audit_logs"].count_documents({
        "event_type": "PASSWORD_RESET_COMPLETED",
        "target_id": user_id
    }) == 1


@pytest.mark.parametrize("role", ["ORG_ADMIN", "SUPER_ADMIN"])
def test_password_reset_supports_admin_account_types(otp_context, role):
    if role == "ORG_ADMIN":
        _user_id, email, old_password = create_active_user(
            otp_context,
            email=f"org-admin-{uuid.uuid4().hex[:8]}@example.test"
        )
        account_id = _user_id
    else:
        suffix = uuid.uuid4().hex[:8]
        email = f"super-admin-{suffix}@example.test"
        old_password = "PlatformPassword123!"
        password_hash = bcrypt.hashpw(old_password.encode(), bcrypt.gensalt()).decode()
        account_id = f"platform-admin-{suffix}"
        AuthRepository.create_admin({
            "admin_id": account_id,
            "email": email,
            "name": "OTP Platform Admin",
            "role": "SUPER_ADMIN",
            "password_hash": password_hash,
            "is_active": True,
            "token_version": 1
        })

    assert request_reset_code(otp_context, email).status_code == 200
    code = get_queued_code(otp_context)
    token = verify_code(otp_context, email, "PASSWORD_RESET", code).json["data"]["reset_token"]
    assert set_password(otp_context, "PASSWORD_RESET", token).status_code == 200
    assert post_json(otp_context, "/api/v1/auth/login", {
        "email": email,
        "password": old_password
    }).status_code == 401
    assert post_json(otp_context, "/api/v1/auth/login", {
        "email": email,
        "password": "StrongPass123!"
    }).status_code == 200

    collection = otp_context["db"]["admins"] if role == "SUPER_ADMIN" else otp_context["db"]["users"]
    identity_key = "admin_id" if role == "SUPER_ADMIN" else "user_id"
    assert collection.find_one({identity_key: account_id})["token_version"] == 2


def test_existing_active_user_remains_active_and_can_login(otp_context):
    user_id, email, password = create_active_user(otp_context)
    login = post_json(otp_context, "/api/v1/auth/login", {
        "email": email,
        "password": password
    })
    assert login.status_code == 200
    user = UserRepository.find_by_id(user_id)
    assert user["status"] == "ACTIVE"
    assert user["is_active"] is True
    assert user["token_version"] == 1
    assert len(otp_context["queued"]) == 0


def test_otp_is_hashed_and_never_returned_or_logged(otp_context, caplog):
    _user_id, email, _password = create_active_user(otp_context)
    response = request_reset_code(otp_context, email)
    code = get_queued_code(otp_context)
    record = otp_context["db"]["auth_otps"].find_one({"email": email})
    wrong_response = verify_code(
        otp_context,
        email,
        "PASSWORD_RESET",
        wrong_code(code, 0)
    )
    verified_response = verify_code(otp_context, email, "PASSWORD_RESET", code)
    reset_response = set_password(
        otp_context,
        "PASSWORD_RESET",
        verified_response.json["data"]["reset_token"]
    )

    assert code not in str(response.json)
    assert code not in wrong_response.get_data(as_text=True)
    assert code not in verified_response.get_data(as_text=True)
    assert code not in reset_response.get_data(as_text=True)
    assert record["otp_hash"] == OTPService._digest("PASSWORD_RESET", email, code)
    assert record["otp_hash"] != code
    assert "code" not in record
    assert "otp" not in record
    assert code not in caplog.text
    expiry = record["expires_at"]
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    remaining = expiry - datetime.now(timezone.utc)
    assert timedelta(minutes=9) < remaining <= timedelta(minutes=10)
    ttl_index = next(
        index for index in otp_context["db"]["auth_otps"].list_indexes()
        if index["key"] == {"expires_at": 1}
    )
    assert ttl_index["expireAfterSeconds"] == 0


def test_activation_resend_is_audited_with_actor_and_target_names(otp_context, monkeypatch):
    _response, email = create_employee(otp_context, name="New Hire")
    user = UserRepository.find_by_email(email)
    codes = iter([123456, 654321])
    monkeypatch.setattr(
        "app.modules.auth.otp_service.secrets.randbelow",
        lambda _limit: next(codes)
    )
    first = request_activation_code(otp_context, email)
    assert first.status_code == 200
    previous_code = get_queued_code(otp_context, 0)

    resent = otp_context["client"].post(
        f"/api/v1/users/{user['user_id']}/activation/resend",
        headers={"Authorization": f"Bearer {otp_context['admin_token']}"}
    )
    assert resent.status_code == 202
    current_code = get_queued_code(otp_context, 1)

    audit = otp_context["db"]["security_audit_logs"].find_one({
        "event_type": "ACTIVATION_OTP_RESENT",
        "target_id": user["user_id"]
    })
    assert audit["actor_name"] == "OTP Test Admin"
    assert audit["actor_role_label"] == "Organization Admin"
    assert audit["target_name"] == "New Hire"
    assert current_code not in str(audit)
    assert verify_code(otp_context, email, "ACTIVATION", previous_code).status_code == 400
    assert verify_code(otp_context, email, "ACTIVATION", current_code).status_code == 200


def test_production_requires_configured_platform_email_provider(otp_context, monkeypatch):
    otp_context["app"].config["APP_ENV"] = "production"
    otp_context["app"].config["TESTING"] = False
    for name in (
        "SENDGRID_API_KEY",
        "SENDGRID_FROM_EMAIL",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SES_FROM_EMAIL",
        "SMTP_HOST",
        "SMTP_FROM_EMAIL"
    ):
        monkeypatch.delenv(name, raising=False)
        otp_context["app"].config[name] = None
    monkeypatch.setattr(
        "app.modules.auth.otp_service.ProviderConfigService.get_all_configuration_statuses",
        lambda: []
    )

    result = request_reset_code(otp_context, "missing@example.test")
    assert result.status_code == 503
    assert "provider" in result.json["message"].lower()


def test_production_selects_configured_sendgrid_environment_provider(otp_context, monkeypatch):
    app = otp_context["app"]
    app.config.update({
        "APP_ENV": "production",
        "TESTING": False,
        "AUTH_OTP_EMAIL_PROVIDER": "sendgrid",
        "SENDGRID_API_KEY": "configured-for-test-only",
        "SENDGRID_FROM_EMAIL": "no-reply@example.test",
        "OTP_HMAC_SECRET": "p" * 40
    })
    monkeypatch.setattr(
        "app.modules.auth.otp_service.ProviderConfigService.get_all_configuration_statuses",
        lambda: []
    )

    with app.app_context():
        assert OTPService.configured_email_provider() == "sendgrid"
        assert len(OTPService._secret()) >= 32


def test_production_requires_explicit_choice_when_multiple_providers_exist(otp_context, monkeypatch):
    app = otp_context["app"]
    app.config.update({
        "APP_ENV": "production",
        "TESTING": False,
        "AUTH_OTP_EMAIL_PROVIDER": None,
        "SENDGRID_API_KEY": None,
        "SENDGRID_FROM_EMAIL": None
    })
    monkeypatch.setattr(
        "app.modules.auth.otp_service.ProviderConfigService.get_all_configuration_statuses",
        lambda: [
            {"provider": "sendgrid", "configured": True, "organization_id": None},
            {"provider": "smtp", "configured": True, "organization_id": None}
        ]
    )

    with app.app_context(), pytest.raises(OTPServiceError, match="Multiple platform email providers"):
        OTPService.configured_email_provider()


def test_production_never_allows_mock_even_when_testing_flag_is_set(otp_context, monkeypatch):
    app = otp_context["app"]
    app.config.update({
        "APP_ENV": "production",
        "TESTING": True,
        "AUTH_OTP_EMAIL_PROVIDER": "mock"
    })
    monkeypatch.setattr(
        "app.modules.auth.otp_service.ProviderConfigService.get_all_configuration_statuses",
        lambda: []
    )

    with app.app_context(), pytest.raises(OTPServiceError, match="Mock authentication email"):
        OTPService.configured_email_provider()


def test_production_requires_dedicated_otp_secret(otp_context):
    app = otp_context["app"]
    app.config.update({
        "APP_ENV": "production",
        "OTP_HMAC_SECRET": None,
        "JWT_SECRET_KEY": "fallback-secret-that-must-not-be-used"
    })

    with app.app_context(), pytest.raises(OTPServiceError, match="OTP_HMAC_SECRET"):
        OTPService._secret()


def test_adapter_registry_disables_mock_providers_in_production(otp_context):
    otp_context["app"].config.update({
        "APP_ENV": "production",
        "TESTING": True
    })

    with otp_context["app"].app_context(), pytest.raises(ValueError, match="disabled in production"):
        AdapterRegistry.get_adapter("mock", channel="email")


def test_otp_email_contains_code_expiry_and_ignore_notice(otp_context, monkeypatch):
    delivered = {}

    class CapturingAdapter:
        def send(self, message):
            delivered.update(message)
            return {"success": True}

    monkeypatch.setattr(
        AdapterRegistry,
        "get_adapter",
        classmethod(lambda cls, provider, channel, organization_id=None: CapturingAdapter())
    )
    code = "123456"
    with otp_context["app"].app_context():
        encrypted = OTPService.encrypt_email_payload(
            "recipient@example.test",
            "PASSWORD_RESET",
            code
        )
        OTPService.send_email(encrypted, "mock")

    email = delivered["data"]
    assert email["subject"] == "Reset your SenderX password"
    assert code in email["message"]
    assert code in email["html"]
    assert "expires in 10 minutes" in email["message"]
    assert "If you did not request this, ignore this email." in email["html"]
    assert "StrongPass123!" not in email["html"]
    assert "password_hash" not in email["html"]
    assert "reset_token" not in email["html"]
