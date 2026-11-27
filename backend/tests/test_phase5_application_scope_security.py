"""
Phase 5 Security Test Suite: Application-Scoped Authorization & Tenant Isolation.

Verifies fail-closed application ownership across:
- Messages (create, list, retrieve, status/history, queue, patch status, retry, search, pagination)
- Payloads (ingest, list, retrieve, versions, audit, edit, validate, retry, anti-tampering)
- Dead Letter Queue (list, retrieve, history, statistics, analytics, edit, validate, retry, delete, orphaned/ambiguous)
- Analytics & validation endpoints
- Celery task dispatch, automatic retry -> DLQ preservation, and manual replay ownership guarantees
- Organization Admin, Application-Scoped User, Multi-App Partial User, Read-Only/Scoped API Keys, and Platform Admin
"""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch
import uuid

import bcrypt
from flask_jwt_extended import create_access_token
import pytest

from app import create_app
from app.modules.api_credentials.repository import ApiCredentialRepository
from app.modules.applications.repository import ApplicationRepository
from app.modules.auth.repository import AuthRepository
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.dead_letters.service import DeadLetterService
from app.modules.messages.repository import MessageRepository
from app.modules.messages.service import MessageService
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.organizations.service import OrganizationService
from app.modules.payloads.repository import PayloadRepository
from app.modules.payloads.service import PayloadService
from app.modules.users.repository import UserRepository
from app.queue.tasks import process_message


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def phase5_env(app):
    """Seed two isolated organizations with applications, users, roles, API keys, and platform admin."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        pw_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(4)).decode("utf-8")

        org_a = f"p5-org-a-{suffix}"
        org_b = f"p5-org-b-{suffix}"
        for oid, name, slug in [
            (org_a, f"Phase5 Org A {suffix}", f"p5-org-a-{suffix}"),
            (org_b, f"Phase5 Org B {suffix}", f"p5-org-b-{suffix}"),
        ]:
            OrganizationRepository.create({
                "organization_id": oid,
                "name": name,
                "slug": slug,
                "status": "ACTIVE",
            })

        app_a = ApplicationRepository.create({
            "organization_id": org_a,
            "name": f"App Alpha {suffix}",
            "environment": "all",
            "status": "ACTIVE",
        })["application_id"]
        app_b = ApplicationRepository.create({
            "organization_id": org_a,
            "name": f"App Beta {suffix}",
            "environment": "all",
            "status": "ACTIVE",
        })["application_id"]
        app_c_org_b = ApplicationRepository.create({
            "organization_id": org_b,
            "name": f"OrgB App {suffix}",
            "environment": "all",
            "status": "ACTIVE",
        })["application_id"]

        # Roles
        role_org_admin_a = str(uuid.uuid4())
        RoleRepository.create({
            "role_id": role_org_admin_a,
            "organization_id": org_a,
            "name": f"ORG_ADMIN_{suffix}",
            "scope": "ORGANIZATION",
            "permissions": list(OrganizationService.ORG_ADMIN_PERMISSIONS),
            "is_system_role": True,
        })

        role_app_full = str(uuid.uuid4())
        RoleRepository.create({
            "role_id": role_app_full,
            "organization_id": org_a,
            "name": f"App Operator {suffix}",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage",
                "organization:payloads:read",
                "organization:payloads:edit",
                "organization:payloads:validate",
                "organization:dead_letters:read",
                "organization:dead_letters:manage",
                "organization:dlq:read",
                "organization:dlq:retry",
                "organization:analytics:read",
            ],
        })

        role_app_read = str(uuid.uuid4())
        RoleRepository.create({
            "role_id": role_app_read,
            "organization_id": org_a,
            "name": f"App Viewer {suffix}",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:messages:read",
                "organization:payloads:read",
                "organization:dead_letters:read",
                "organization:analytics:read",
            ],
        })

        # Users
        user_admin_a = str(uuid.uuid4())
        UserRepository.create({
            "user_id": user_admin_a,
            "organization_id": org_a,
            "name": "Org Admin A",
            "email": f"admin-a-{suffix}@p5.test",
            "password_hash": pw_hash,
            "role_ids": [role_org_admin_a],
            "role_assignments": [{"role_id": role_org_admin_a, "application_id": None}],
            "is_active": True,
        })

        user_app_a = str(uuid.uuid4())
        UserRepository.create({
            "user_id": user_app_a,
            "organization_id": org_a,
            "name": "User App A",
            "email": f"user-appa-{suffix}@p5.test",
            "password_hash": pw_hash,
            "role_ids": [role_app_full],
            "role_assignments": [{"role_id": role_app_full, "application_id": app_a}],
            "is_active": True,
        })

        user_app_b = str(uuid.uuid4())
        UserRepository.create({
            "user_id": user_app_b,
            "organization_id": org_a,
            "name": "User App B",
            "email": f"user-appb-{suffix}@p5.test",
            "password_hash": pw_hash,
            "role_ids": [role_app_full],
            "role_assignments": [{"role_id": role_app_full, "application_id": app_b}],
            "is_active": True,
        })

        # User with read on App A, and full manage on App B
        user_partial = str(uuid.uuid4())
        UserRepository.create({
            "user_id": user_partial,
            "organization_id": org_a,
            "name": "Partial Multi-App User",
            "email": f"partial-{suffix}@p5.test",
            "password_hash": pw_hash,
            "role_ids": [role_app_read, role_app_full],
            "role_assignments": [
                {"role_id": role_app_read, "application_id": app_a},
                {"role_id": role_app_full, "application_id": app_b},
            ],
            "is_active": True,
        })

        # Platform Admin
        plat_admin_id = f"plat-admin-{suffix}"
        AuthRepository.create_admin({
            "admin_id": plat_admin_id,
            "email": f"super-{suffix}@senderx.io",
            "password_hash": pw_hash,
            "role": "SUPER_ADMIN",
            "is_active": True,
        })

        def _jwt_org(uid):
            tok = create_access_token(
                identity=uid,
                additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a},
            )
            return {"Authorization": f"Bearer {tok}"}

        plat_tok = create_access_token(
            identity=plat_admin_id,
            additional_claims={"account_type": "PLATFORM_ADMIN", "role": "SUPER_ADMIN"},
        )

        # External API Keys via admin HTTP route
        admin_headers = _jwt_org(user_admin_a)

        test_client = app.test_client()
        key_a_full = f"sx_live_appa_full_{suffix}"
        key_a_ro = f"sx_live_appa_ro_{suffix}"
        key_b_full = f"sx_live_appb_full_{suffix}"

        for aid, kname, kval, scopes in [
            (app_a, "AppA Full", key_a_full, ["payloads:ingest", "messages:create", "messages:read", "messages:manage"]),
            (app_a, "AppA ReadOnly", key_a_ro, ["messages:read"]),
            (app_b, "AppB Full", key_b_full, ["payloads:ingest", "messages:create", "messages:read", "messages:manage"]),
        ]:
            r = test_client.post(
                "/api/v1/api-credentials/",
                json={"application_id": aid, "name": kname, "environment": "live", "api_key": kval, "scopes": scopes},
                headers=admin_headers,
            )
            assert r.status_code == 201, r.get_json()

        role_org_admin_b = str(uuid.uuid4())
        RoleRepository.create({
            "role_id": role_org_admin_b,
            "organization_id": org_b,
            "name": f"ORG_ADMIN_B_{suffix}",
            "scope": "ORGANIZATION",
            "permissions": list(OrganizationService.ORG_ADMIN_PERMISSIONS),
            "is_system_role": True,
        })
        user_admin_b = str(uuid.uuid4())
        UserRepository.create({
            "user_id": user_admin_b,
            "organization_id": org_b,
            "name": "Org Admin B",
            "email": f"admin-b-{suffix}@p5.test",
            "password_hash": pw_hash,
            "role_ids": [role_org_admin_b],
            "role_assignments": [{"role_id": role_org_admin_b, "application_id": None}],
            "is_active": True,
        })
        key_orgb = f"sx_live_orgb_{suffix}"
        admin_b_tok = create_access_token(
            identity=user_admin_b,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b},
        )
        r_b = test_client.post(
            "/api/v1/api-credentials/",
            json={"application_id": app_c_org_b, "name": "OrgB Full", "environment": "live", "api_key": key_orgb, "scopes": ["payloads:ingest", "messages:create", "messages:read", "messages:manage"]},
            headers={"Authorization": f"Bearer {admin_b_tok}"},
        )
        assert r_b.status_code == 201

        ctx = {
            "org_a": org_a,
            "org_b": org_b,
            "app_a": app_a,
            "app_b": app_b,
            "app_c_org_b": app_c_org_b,
            "user_admin_a": user_admin_a,
            "user_admin_b": user_admin_b,
            "user_app_a": user_app_a,
            "user_app_b": user_app_b,
            "user_partial": user_partial,
            "headers_admin_a": admin_headers,
            "headers_admin_b": {"Authorization": f"Bearer {admin_b_tok}"},
            "headers_user_a": _jwt_org(user_app_a),
            "headers_user_b": _jwt_org(user_app_b),
            "headers_partial": _jwt_org(user_partial),
            "headers_plat": {"Authorization": f"Bearer {plat_tok}"},
            "key_a_full": {"X-API-Key": key_a_full},
            "key_a_ro": {"X-API-Key": key_a_ro},
            "key_b_full": {"X-API-Key": key_b_full},
            "key_orgb": {"X-API-Key": key_orgb},
        }
    yield ctx

    with app.app_context():
        # Clean up isolated synthetic test records
        for oid in (org_a, org_b):
            MessageRepository._collection().delete_many({"organization_id": oid})
            PayloadRepository._payloads_col().delete_many({"organization_id": oid})
            PayloadRepository._audit_col().delete_many({"organization_id": oid})
            DeadLetterRepository._collection().delete_many({"organization_id": oid})
            ApiCredentialRepository._collection().delete_many({"organization_id": oid})
            ApplicationRepository._collection().delete_many({"organization_id": oid})
            UserRepository._collection().delete_many({"organization_id": oid})
            RoleRepository._collection().delete_many({"organization_id": oid})
            OrganizationRepository._collection().delete_many({"organization_id": oid})
        AuthRepository._collection().delete_one({"admin_id": plat_admin_id})


def _seed_app_resources(app, org_id, app_id, marker):
    """Create message, FAILED/DEAD DLQ message, and IN_DLQ/edited payload for one app."""
    with app.app_context():
        msg_ok = MessageService.create_message({
            "channel": "email",
            "provider": "mock",
            "recipient": f"secret-{marker}@victim.example",
            "data": {"subject": f"Confidential {marker}", "body": f"SecretBody-{marker}"},
            "application_id": app_id,
        }, organization_id=org_id, application_id=app_id)["message"]

        msg_failed = MessageService.create_message({
            "channel": "email",
            "provider": "mock",
            "recipient": f"fail-{marker}@victim.example",
            "data": {"subject": f"RetryMe {marker}", "body": f"RetryBody-{marker}"},
            "application_id": app_id,
        }, organization_id=org_id, application_id=app_id)["message"]
        MessageRepository.update_status(msg_failed["message_id"], "QUEUED", "CREATED", organization_id=org_id)
        MessageRepository.update_status(msg_failed["message_id"], "PROCESSING", "QUEUED", organization_id=org_id)
        MessageRepository.mark_failed(msg_failed["message_id"], retry_count=1, error=f"SecretErr-{marker}", organization_id=org_id)

        msg_dead = MessageService.create_message({
            "channel": "email",
            "provider": "mock",
            "recipient": f"dead-{marker}@victim.example",
            "data": {"subject": f"DeadSubject {marker}", "body": f"DeadSecret-{marker}", "api_key": f"sk-{marker}"},
            "application_id": app_id,
        }, organization_id=org_id, application_id=app_id)["message"]
        MessageRepository.update_status(msg_dead["message_id"], "QUEUED", "CREATED", organization_id=org_id)
        MessageRepository.update_status(msg_dead["message_id"], "PROCESSING", "QUEUED", organization_id=org_id)
        MessageRepository.update_retry_info(msg_dead["message_id"], 3, "PROCESSING", "DEAD", error=f"DeadErr-{marker}", organization_id=org_id)
        dead_snapshot = MessageRepository.find_by_id(msg_dead["message_id"], organization_id=org_id)
        DeadLetterRepository.save_from_message(dead_snapshot, f"DeadErr-{marker}", organization_id=org_id, application_id=app_id)

        ing_bad = PayloadService.ingest_payload(
            raw_json={"channel": "unknown_ch", "recipient": f"pay-{marker}@victim.example", "data": {"body": f"PaySecret-{marker}", "secret": f"ps-{marker}"}},
            organization_id=org_id,
            application_id=app_id,
            user_id="seed",
        )
        payload_id = ing_bad["payload_id"]
        PayloadService.edit_payload(
            payload_id=payload_id,
            organization_id=org_id,
            edited_json={"channel": "email", "recipient": f"pay-{marker}@victim.example", "data": {"subject": f"Fixed {marker}", "body": f"FixedSecret-{marker}"}},
            user_id="seed",
            reason=f"Fix {marker}",
        )

        return {
            "msg_created": msg_ok["message_id"],
            "msg_failed": msg_failed["message_id"],
            "msg_dead": msg_dead["message_id"],
            "payload_id": payload_id,
        }


# 1–9 & 19. Cross-application isolation across Messages, Payloads, Versions, Retries, DLQ, Search, Analytics & no content leak
def test_cross_application_isolation_all_endpoints(app, client, phase5_env):
    res_a = _seed_app_resources(app, phase5_env["org_a"], phase5_env["app_a"], "ALPHA1")
    res_b = _seed_app_resources(app, phase5_env["org_a"], phase5_env["app_b"], "BETA2")

    app_a_callers = [phase5_env["key_a_full"], phase5_env["headers_user_a"]]

    for caller in app_a_callers:
        # 1. App A cannot retrieve App B's message
        r_msg = client.get(f"/api/v1/messages/{res_b['msg_created']}", headers=caller)
        assert r_msg.status_code in (403, 404)
        assert "SecretBody-BETA2" not in r_msg.get_data(as_text=True)
        assert "BETA2" not in r_msg.get_data(as_text=True)

        # 2. App A cannot retrieve App B's payload
        r_pay = client.get(f"/api/v1/payloads/{res_b['payload_id']}", headers=caller)
        assert r_pay.status_code == 404
        assert "PaySecret-BETA2" not in r_pay.get_data(as_text=True)

        # 3. App A cannot retrieve App B's payload versions or audit trail
        r_ver = client.get(f"/api/v1/payloads/{res_b['payload_id']}/versions", headers=caller)
        assert r_ver.status_code == 404
        assert "FixedSecret-BETA2" not in r_ver.get_data(as_text=True)
        r_aud = client.get(f"/api/v1/payloads/{res_b['payload_id']}/audit", headers=caller)
        assert r_aud.status_code == 404

        # 4. App A cannot retry, queue, or patch status on App B's messages
        r_retry = client.post(f"/api/v1/messages/{res_b['msg_failed']}/retry", headers=caller)
        assert r_retry.status_code == 404
        r_queue = client.post(f"/api/v1/messages/{res_b['msg_created']}/queue", headers=caller)
        assert r_queue.status_code == 404
        r_patch = client.patch(f"/api/v1/messages/{res_b['msg_created']}/status", json={"status": "VALIDATED"}, headers=caller)
        assert r_patch.status_code == 404

        # 5 & 6. App A cannot inspect, view history, edit, validate, replay, or delete App B's DLQ record
        r_dlq_get = client.get(f"/api/v1/dead-letters/organization/{res_b['msg_dead']}", headers=caller)
        assert r_dlq_get.status_code == 404
        assert "DeadErr-BETA2" not in r_dlq_get.get_data(as_text=True)

        r_dlq_hist = client.get(f"/api/v1/dead-letters/organization/{res_b['msg_dead']}/history", headers=caller)
        assert r_dlq_hist.status_code == 404

        r_dlq_retry = client.post(f"/api/v1/dead-letters/organization/{res_b['msg_dead']}/retry", headers=caller)
        assert r_dlq_retry.status_code == 404

        r_dlq_del = client.delete(
            f"/api/v1/dead-letters/organization/{res_b['msg_dead']}",
            json={"confirm": True},
            headers=caller,
        )
        assert r_dlq_del.status_code == 404

        r_dlq_edit = client.put(
            f"/api/v1/dead-letters/organization/{res_b['payload_id']}/payload",
            json={"payload": {"channel": "email", "recipient": "x@x.test", "data": {"body": "hijack"}}},
            headers=caller,
        )
        assert r_dlq_edit.status_code in (403, 404)
        if caller is phase5_env["headers_user_a"]:
            assert r_dlq_edit.status_code == 404

        r_dlq_val = client.post(f"/api/v1/dead-letters/organization/{res_b['payload_id']}/validate", headers=caller)
        assert r_dlq_val.status_code == 404

        # 9. App A cannot modify/validate/retry App B's payloads directly
        r_pay_edit = client.put(
            f"/api/v1/payloads/{res_b['payload_id']}",
            json={"payload": {"channel": "email", "recipient": "hijack@x.test", "data": {"body": "hijack"}}},
            headers=caller,
        )
        assert r_pay_edit.status_code in (403, 404)
        if caller is phase5_env["headers_user_a"]:
            assert r_pay_edit.status_code == 404
        r_pay_val = client.post(f"/api/v1/payloads/{res_b['payload_id']}/validate", headers=caller)
        assert r_pay_val.status_code == 404
        r_pay_ret = client.post(f"/api/v1/payloads/{res_b['payload_id']}/retry", headers=caller)
        assert r_pay_ret.status_code == 404

        # 7. App A cannot search App B's messages
        r_search = client.get("/api/v1/messages/?search=BETA2", headers=caller)
        assert r_search.status_code == 200
        assert r_search.get_json()["data"] == []
        assert r_search.get_json()["total_count"] == 0

        r_list_forged = client.get(f"/api/v1/messages/?application_id={phase5_env['app_b']}", headers=caller)
        assert r_list_forged.status_code == 403

        # 8. App A cannot query App B's analytics or DLQ stats
        r_ana = client.get(f"/api/v1/analytics/organization?application_id={phase5_env['app_b']}", headers=caller)
        assert r_ana.status_code == 403

        r_dlq_stats = client.get(f"/api/v1/dead-letters/organization/statistics?application_id={phase5_env['app_b']}", headers=caller)
        assert r_dlq_stats.status_code == 403


# 10. Request JSON / Header / Query application_id spoofing & conflict rejection
def test_application_id_forgery_and_conflicts_rejected(app, client, phase5_env):
    res_a = _seed_app_resources(app, phase5_env["org_a"], phase5_env["app_a"], "FORGE_A")
    res_b = _seed_app_resources(app, phase5_env["org_a"], phase5_env["app_b"], "FORGE_B")

    # API key forging app_b in body, header, or query
    assert client.post(
        "/api/v1/messages/",
        json={"channel": "email", "application_id": phase5_env["app_b"], "recipient": "a@b.test", "data": {"body": "x"}},
        headers=phase5_env["key_a_full"],
    ).status_code == 403

    assert client.post(
        "/api/v1/payloads/ingest",
        json={"channel": "email", "application_id": phase5_env["app_b"], "recipient": "a@b.test", "data": {"body": "x"}},
        headers=phase5_env["key_a_full"],
    ).status_code == 403

    assert client.post(
        "/api/v1/validation/analyze",
        json={"channel": "email", "application_id": phase5_env["app_b"], "recipient": "a@b.test", "data": {"body": "x"}},
        headers=phase5_env["key_a_full"],
    ).status_code == 403

    # Matching header + forged JSON body must NOT slip past decorator
    assert client.post(
        "/api/v1/messages/",
        json={"channel": "email", "application_id": phase5_env["app_b"], "recipient": "a@b.test", "data": {"body": "x"}},
        headers={**phase5_env["key_a_full"], "X-Application-ID": phase5_env["app_a"]},
    ).status_code == 403

    # JWT user with App A scope passing conflicting header vs body
    assert client.post(
        "/api/v1/messages/",
        json={"channel": "email", "application_id": phase5_env["app_b"], "recipient": "a@b.test", "data": {"body": "x"}},
        headers={**phase5_env["headers_user_a"], "X-Application-ID": phase5_env["app_a"]},
    ).status_code == 403

    # Editing own payload to switch its application_id to app_b is strictly rejected
    r_tamper_edit = client.put(
        f"/api/v1/payloads/{res_a['payload_id']}",
        json={"payload": {"channel": "email", "application_id": phase5_env["app_b"], "recipient": "a@b.test", "data": {"body": "x"}}},
        headers=phase5_env["headers_user_a"],
    )
    assert r_tamper_edit.status_code == 403
    assert "application_id" in r_tamper_edit.get_json()["message"]

    # Non-string / NoSQL operator injection in application_id rejected cleanly
    assert client.post(
        "/api/v1/messages/",
        json={"channel": "email", "application_id": {"$ne": None}, "recipient": "a@b.test", "data": {"body": "x"}},
        headers=phase5_env["headers_user_a"],
    ).status_code == 400


# 11 & 12. Org Admin vs Platform Admin explicit boundaries
def test_org_admin_and_platform_admin_boundaries(app, client, phase5_env):
    res_a = _seed_app_resources(app, phase5_env["org_a"], phase5_env["app_a"], "ADMIN_A")
    res_b = _seed_app_resources(app, phase5_env["org_a"], phase5_env["app_b"], "ADMIN_B")
    res_orgb = _seed_app_resources(app, phase5_env["org_b"], phase5_env["app_c_org_b"], "ADMIN_ORGB")

    # Org A admin sees both App A and App B, and can filter each explicitly
    r_list_all = client.get("/api/v1/messages/?limit=100", headers=phase5_env["headers_admin_a"])
    assert r_list_all.status_code == 200
    all_ids = {m["message_id"] for m in r_list_all.get_json()["data"]}
    assert res_a["msg_created"] in all_ids
    assert res_b["msg_created"] in all_ids
    assert res_orgb["msg_created"] not in all_ids

    r_only_b = client.get(f"/api/v1/messages/?application_id={phase5_env['app_b']}", headers=phase5_env["headers_admin_a"])
    assert r_only_b.status_code == 200
    assert all(m["application_id"] == phase5_env["app_b"] for m in r_only_b.get_json()["data"])

    # Org B admin cannot reach Org A messages/payloads/dlq even via X-Application-ID
    assert client.get(f"/api/v1/messages/{res_a['msg_created']}", headers=phase5_env["headers_admin_b"]).status_code == 404
    assert client.get(f"/api/v1/payloads/{res_a['payload_id']}", headers=phase5_env["headers_admin_b"]).status_code == 404
    assert client.get(
        f"/api/v1/messages/?application_id={phase5_env['app_a']}",
        headers=phase5_env["headers_admin_b"],
    ).status_code == 404

    # Platform Admin cannot access organization-user endpoints without an org-user policy
    assert client.get("/api/v1/messages/", headers=phase5_env["headers_plat"]).status_code == 403
    assert client.get("/api/v1/analytics/platform", headers=phase5_env["headers_plat"]).status_code == 200

    # Platform Admin DLQ replay preserves original organization_id & application_id
    fake_task = MagicMock()
    with app.app_context():
        def mock_send(name, args=None, kwargs=None, task_id=None, **_kw):
            fake_task.id = task_id
            fake_task.kwargs = kwargs
            return fake_task

        orig_send = app.celery.send_task
        app.celery.send_task = MagicMock(side_effect=mock_send)
        try:
            plat_retry = client.post(f"/api/v1/dead-letters/{res_a['msg_dead']}/retry", headers=phase5_env["headers_plat"])
            assert plat_retry.status_code == 202
            assert fake_task.kwargs["expected_organization_id"] == phase5_env["org_a"]
            assert fake_task.kwargs["expected_application_id"] == phase5_env["app_a"]
        finally:
            app.celery.send_task = orig_send


# 13 & 14. Cross-organization API keys & Read-only API key restrictions
def test_api_key_cross_org_and_readonly_scope_enforcement(app, client, phase5_env):
    res_a = _seed_app_resources(app, phase5_env["org_a"], phase5_env["app_a"], "RO_A")
    res_orgb = _seed_app_resources(app, phase5_env["org_b"], phase5_env["app_c_org_b"], "RO_ORGB")

    # API key from Org B cannot retrieve Org A message or payload
    assert client.get(f"/api/v1/messages/{res_a['msg_created']}", headers=phase5_env["key_orgb"]).status_code == 404
    assert client.get(f"/api/v1/payloads/{res_a['payload_id']}", headers=phase5_env["key_orgb"]).status_code == 404
    assert client.get(f"/api/v1/dead-letters/organization/{res_a['msg_dead']}", headers=phase5_env["key_orgb"]).status_code == 404

    # Read-only API key CAN read its own app's resources
    ro_headers = phase5_env["key_a_ro"]
    assert client.get(f"/api/v1/messages/{res_a['msg_created']}", headers=ro_headers).status_code == 200
    assert client.get("/api/v1/messages/", headers=ro_headers).status_code == 200
    assert client.get(f"/api/v1/payloads/{res_a['payload_id']}", headers=ro_headers).status_code == 200
    assert client.get(f"/api/v1/payloads/{res_a['payload_id']}/versions", headers=ro_headers).status_code == 200
    assert client.get("/api/v1/analytics/organization", headers=ro_headers).status_code == 200
    assert client.get("/api/v1/dead-letters/organization", headers=ro_headers).status_code == 200

    # Read-only API key CANNOT write, validate, queue, status-update, edit, retry, or delete
    for method, url, body in [
        ("POST", "/api/v1/messages/", {"channel": "email", "recipient": "a@b.test", "data": {"body": "hi"}}),
        ("POST", "/api/v1/payloads/ingest", {"channel": "email", "recipient": "a@b.test", "data": {"body": "hi"}}),
        ("POST", "/api/v1/validation/analyze", {"channel": "email", "recipient": "a@b.test", "data": {"body": "hi"}}),
        ("POST", f"/api/v1/messages/{res_a['msg_created']}/queue", None),
        ("PATCH", f"/api/v1/messages/{res_a['msg_created']}/status", {"status": "VALIDATED"}),
        ("POST", f"/api/v1/messages/{res_a['msg_failed']}/retry", None),
        ("PUT", f"/api/v1/payloads/{res_a['payload_id']}", {"payload": {"channel": "email", "recipient": "x@x.test", "data": {"body": "y"}}}),
        ("POST", f"/api/v1/payloads/{res_a['payload_id']}/retry", None),
        ("POST", f"/api/v1/dead-letters/organization/{res_a['msg_dead']}/retry", None),
        ("DELETE", f"/api/v1/dead-letters/organization/{res_a['msg_dead']}", {"confirm": True}),
    ]:
        r = client.open(url, method=method, json=body, headers=ro_headers)
        assert r.status_code == 403, f"Expected 403 for read-only key on {method} {url}, got {r.status_code}"
        assert r.get_json().get("missing_scopes")


# 15 & 16. Celery process_message ownership & Payload retry ownership preservation
def test_celery_and_payload_retry_preserve_application_ownership(app, client, phase5_env):
    org_id = phase5_env["org_a"]
    app_a = phase5_env["app_a"]
    app_b = phase5_env["app_b"]

    with app.app_context():
        # A. Exhausted automatic retry -> DLQ record MUST retain application_id
        msg_auto = MessageService.create_message({
            "channel": "email",
            "provider": "mock",
            "recipient": "celery-auto@p5.test",
            "data": {"subject": "Auto DLQ", "body": "fail", "mock_scenario": "temporary_failure"},
            "application_id": app_a,
        }, organization_id=org_id, application_id=app_a)["message"]
        MessageRepository.update_status(msg_auto["message_id"], "QUEUED", "CREATED", organization_id=org_id, application_ids=app_a)
        MessageRepository._collection().update_one({"message_id": msg_auto["message_id"]}, {"$set": {"retry_count": 3}})

        # Mismatched expected_application_id fails closed BEFORE touching message
        mismatch_res = process_message.apply(
            args=[msg_auto["message_id"]],
            kwargs={"expected_organization_id": org_id, "expected_application_id": app_b},
        ).result
        assert mismatch_res["success"] is False
        assert "mismatch" in mismatch_res["message"].lower()
        assert MessageRepository.find_by_id(msg_auto["message_id"], organization_id=org_id)["status"] == "QUEUED"

        # Correct owner runs until MAX_RETRIES -> writes DEAD message and DLQ entry with application_id=app_a
        auto_res = process_message.apply(
            args=[msg_auto["message_id"]],
            kwargs={"expected_organization_id": org_id, "expected_application_id": app_a},
            retries=3,
        ).result
        assert auto_res["status"] == "DEAD"
        assert auto_res["dlq_saved"] is True
        dlq_saved = DeadLetterRepository.find_by_message_id(msg_auto["message_id"], organization_id=org_id, application_ids=app_a)
        assert dlq_saved is not None
        assert dlq_saved["application_id"] == app_a

        # App B cannot see or retry this DLQ entry
        assert DeadLetterRepository.find_by_message_id(msg_auto["message_id"], organization_id=org_id, application_ids=[app_b]) is None

        # B. Payload retry rejects tampered current_payload.application_id and preserves persisted ownership
        seeded = _seed_app_resources(app, org_id, app_a, "PAYLOAD_OWN")
        # Simulate historical or tampered inner payload claiming app_b
        tampered_enc = PayloadRepository._payloads_col().find_one({"payload_id": seeded["payload_id"]})
        from app.modules.payloads.encryption import PayloadEncryption
        tampered_curr = PayloadEncryption.decrypt_dict(tampered_enc["current_payload"])
        tampered_curr["application_id"] = app_b
        PayloadRepository._payloads_col().update_one(
            {"payload_id": seeded["payload_id"]},
            {"$set": {"current_payload": PayloadEncryption.encrypt_dict(tampered_curr)}},
        )
        tamper_retry = PayloadService.retry_payload(seeded["payload_id"], org_id, user_id="u1", user_application_ids=[app_a])
        assert tamper_retry["success"] is False
        assert tamper_retry["status_code"] == 409

        # Legitimate payload retry creates message pinned to app_a and queues with expected_application_id=app_a
        clean_seeded = _seed_app_resources(app, org_id, app_a, "PAYLOAD_CLEAN")
        sent_calls = []

        def capture_send(name, args=None, kwargs=None, task_id=None, **_kw):
            sent_calls.append({"args": args, "kwargs": kwargs})
            t = MagicMock()
            t.id = task_id or "t-clean"
            return t

        orig_send = app.celery.send_task
        app.celery.send_task = MagicMock(side_effect=capture_send)
        try:
            r_retry = client.post(f"/api/v1/payloads/{clean_seeded['payload_id']}/retry", headers=phase5_env["key_a_full"])
            assert r_retry.status_code == 200
            r_json = r_retry.get_json()
            assert r_json["application_id"] == app_a
            created_msg = MessageRepository.find_by_id(r_json["message_id"], organization_id=org_id, application_ids=app_a)
            assert created_msg is not None
            assert sent_calls[-1]["kwargs"] == {"expected_organization_id": org_id, "expected_application_id": app_a}
        finally:
            app.celery.send_task = orig_send


# 17. Ambiguous or orphaned DLQ records and empty scopes fail safely
def test_ambiguous_orphaned_dlq_and_empty_scope_fail_closed(app, phase5_env):
    org_id = phase5_env["org_a"]
    app_a = phase5_env["app_a"]
    app_b = phase5_env["app_b"]

    with app.app_context():
        # Empty user_application_ids=[] MUST return 0 items and reject gets (never falsy-bypass)
        listed = MessageService.get_all_messages(organization_id=org_id, user_application_ids=[])
        assert listed["items"] == []
        assert listed["pagination"]["total"] == 0
        assert MessageService.get_message("any-id", org_id, user_application_ids=[]) is None
        assert PayloadService.list_payloads(organization_id=org_id, user_application_ids=[])["data"]["items"] == []
        assert DeadLetterService.get_all_dead_letters(organization_id=org_id, user_application_ids=[])["data"] == []

        # Ambiguous DLQ (dlq claims app_b, original message belongs to app_a) -> rejected on replay
        seeded = _seed_app_resources(app, org_id, app_a, "AMBIG")
        DeadLetterRepository._collection().update_one(
            {"message_id": seeded["msg_dead"], "organization_id": org_id},
            {"$set": {"application_id": app_b}},
        )
        res_ambig = DeadLetterService.retry_dead_letter(seeded["msg_dead"], organization_id=org_id)
        assert res_ambig["success"] is False
        assert "mismatch" in res_ambig["message"].lower()

        # Orphaned DLQ (message_id missing from messages) -> fails safely
        orphan_id = f"orphan-{uuid.uuid4().hex[:8]}"
        DeadLetterRepository._collection().insert_one({
            "message_id": orphan_id,
            "organization_id": org_id,
            "application_id": app_a,
            "dead_letter_status": "PENDING_REVIEW",
            "status": "DEAD",
        })
        res_orphan = DeadLetterService.retry_dead_letter(orphan_id, organization_id=org_id, user_application_ids=[app_a])
        assert res_orphan["success"] is False
        assert "not found" in res_orphan["message"].lower()


# 18 & 20. Scoped pagination totals, analytics counts, and legitimate multi-app partial permissions workflow
def test_scoped_pagination_analytics_and_legitimate_multi_app_workflow(app, client, phase5_env):
    org_id = phase5_env["org_a"]
    app_a = phase5_env["app_a"]
    app_b = phase5_env["app_b"]

    with app.app_context():
        MessageRepository._collection().delete_many({"organization_id": org_id})
        PayloadRepository._payloads_col().delete_many({"organization_id": org_id})
        DeadLetterRepository._collection().delete_many({"organization_id": org_id})

    res_a = _seed_app_resources(app, org_id, app_a, "PAG_A")
    res_b1 = _seed_app_resources(app, org_id, app_b, "PAG_B1")
    res_b2 = _seed_app_resources(app, org_id, app_b, "PAG_B2")

    # App A has 3 messages, App B has 6 messages (3 per seed), total org has 9 messages
    m_a = client.get("/api/v1/messages/?limit=50", headers=phase5_env["key_a_full"]).get_json()
    m_b = client.get("/api/v1/messages/?limit=50", headers=phase5_env["key_b_full"]).get_json()
    m_org = client.get("/api/v1/messages/?limit=50", headers=phase5_env["headers_admin_a"]).get_json()
    assert m_a["total_count"] == 3
    assert m_b["total_count"] == 6
    assert m_org["total_count"] == 9
    assert all(m["application_id"] == app_a for m in m_a["data"])
    assert all(m["application_id"] == app_b for m in m_b["data"])

    # Scoped payload & DLQ pagination counts match App A only
    p_a = client.get("/api/v1/payloads/", headers=phase5_env["key_a_full"]).get_json()["data"]
    p_org = client.get("/api/v1/payloads/", headers=phase5_env["headers_admin_a"]).get_json()["data"]
    assert p_a["pagination"]["total"] == 1
    assert p_org["pagination"]["total"] == 3

    d_a = client.get("/api/v1/dead-letters/organization", headers=phase5_env["key_a_full"]).get_json()
    d_org = client.get("/api/v1/dead-letters/organization", headers=phase5_env["headers_admin_a"]).get_json()
    assert d_a["total_count"] == 2  # 1 failed/dead message + 1 invalid ingested payload
    assert d_org["total_count"] == 6

    # Analytics counts isolated strictly per app
    ana_a = client.get("/api/v1/analytics/organization", headers=phase5_env["key_a_full"]).get_json()
    ana_b = client.get("/api/v1/analytics/organization", headers=phase5_env["key_b_full"]).get_json()
    ana_org = client.get("/api/v1/analytics/organization", headers=phase5_env["headers_admin_a"]).get_json()
    assert ana_a["overview"]["total_messages"] == 3
    assert ana_a["dead_letter_queue"]["total_records"] == 2
    assert ana_b["overview"]["total_messages"] == 6
    assert ana_b["dead_letter_queue"]["total_records"] == 4
    assert ana_org["overview"]["total_messages"] == 9

    # Multi-app user (read on App A, manage on App B):
    # - Can list and read messages from BOTH App A & App B
    # - Can retry App B's failed message
    # - CANNOT retry App A's failed message (manage permission only granted on App B!)
    partial_list = client.get("/api/v1/messages/?limit=50", headers=phase5_env["headers_partial"]).get_json()
    assert partial_list["total_count"] == 9
    assert client.post(
        f"/api/v1/messages/{res_a['msg_failed']}/retry",
        headers=phase5_env["headers_partial"],
    ).status_code == 404

    with app.app_context():
        orig_send = app.celery.send_task
        t_mock = MagicMock()
        t_mock.id = "t-partial"
        app.celery.send_task = MagicMock(return_value=t_mock)
        try:
            r_retry_b = client.post(
                f"/api/v1/messages/{res_b1['msg_failed']}/retry",
                headers=phase5_env["headers_partial"],
            )
            assert r_retry_b.status_code == 200
            assert r_retry_b.get_json()["application_id"] == app_b
        finally:
            app.celery.send_task = orig_send
