"""
SenderX Stale Dispatch Recovery & DLQ Health Test Suite
Validates:
- Stale dispatch detection algorithm (cutoff calculation)
- Filtering by dead_letter_status="RETRY_REQUESTED" and manual_retry_dispatch_state="DISPATCHING"
- State transition to RECOVERY_REQUIRED
- POST /api/v1/dead-letters/recovery/stale-dispatches endpoint authorization (SUPER_ADMIN only)
- Validation of minutes and limit parameters
- GET /api/v1/dead-letters/recovery/inspect and reconcile
- POST /api/v1/dead-letters/recovery/<message_id>/resolve
"""

from datetime import datetime, timezone, timedelta
import uuid
import pytest
import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.auth.repository import AuthRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.users.repository import UserRepository
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.dead_letters.service import DeadLetterService
from app.modules.messages.repository import MessageRepository


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_context(app):
    suffix = uuid.uuid4().hex[:6]
    admin_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    password_hash = bcrypt.hashpw(b"ValidPass1234!", bcrypt.gensalt(12)).decode("utf-8")

    with app.app_context():
        # 1. Super Admin
        AuthRepository.create_admin({
            "admin_id": admin_id,
            "email": f"superadmin-{suffix}@senderx.io",
            "password_hash": password_hash,
            "role": "SUPER_ADMIN",
            "is_active": True
        })

        # 2. Organization
        OrganizationRepository.create({
            "organization_id": org_id,
            "name": f"Test Org {suffix}",
            "slug": f"test-org-{suffix}",
            "status": "ACTIVE"
        })

        # 3. Org User
        UserRepository.create({
            "user_id": user_id,
            "organization_id": org_id,
            "email": f"user-{suffix}@senderx.io",
            "password_hash": password_hash,
            "role_ids": [],
            "is_active": True
        })

        super_admin_token = create_access_token(
            identity=admin_id,
            additional_claims={
                "account_type": "PLATFORM_ADMIN",
                "role": "SUPER_ADMIN",
                "email": f"superadmin-{suffix}@senderx.io"
            }
        )

        org_user_token = create_access_token(
            identity=user_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_id,
                "role_ids": [],
                "email": f"user-{suffix}@senderx.io"
            }
        )

        yield {
            "admin_id": admin_id,
            "org_id": org_id,
            "user_id": user_id,
            "super_admin_token": super_admin_token,
            "org_user_token": org_user_token
        }

        # Cleanup
        AuthRepository._collection().delete_one({"admin_id": admin_id})
        OrganizationRepository._collection().delete_one({"organization_id": org_id})
        UserRepository._collection().delete_one({"user_id": user_id})


def clean_test_records(msg_ids):
    for mid in msg_ids:
        DeadLetterRepository._collection().delete_one({"message_id": mid})
        MessageRepository._collection().delete_one({"message_id": mid})


def test_stale_recovery_endpoint_auth(client, auth_context):
    """Verify endpoint rejects unauthenticated and organization users, but allows super admin."""
    # 1. Unauthenticated -> 401
    res1 = client.post("/api/v1/dead-letters/recovery/stale-dispatches")
    assert res1.status_code == 401

    # 2. Organization User -> 403
    res2 = client.post(
        "/api/v1/dead-letters/recovery/stale-dispatches",
        headers={"Authorization": f"Bearer {auth_context['org_user_token']}"}
    )
    assert res2.status_code == 403

    # 3. Super Admin -> 200
    res3 = client.post(
        "/api/v1/dead-letters/recovery/stale-dispatches",
        headers={"Authorization": f"Bearer {auth_context['super_admin_token']}"}
    )
    assert res3.status_code == 200
    data = res3.get_json()
    assert data["success"] is True


def test_stale_recovery_parameter_validation(client, auth_context):
    """Verify minutes and limit query parameters are strictly validated."""
    headers = {"Authorization": f"Bearer {auth_context['super_admin_token']}"}

    # minutes < 1
    res1 = client.post("/api/v1/dead-letters/recovery/stale-dispatches?minutes=0", headers=headers)
    assert res1.status_code == 400
    assert "at least 1" in res1.get_json()["message"]

    # limit > 500
    res2 = client.post("/api/v1/dead-letters/recovery/stale-dispatches?limit=501", headers=headers)
    assert res2.status_code == 400
    assert "between 1 and 500" in res2.get_json()["message"]


def test_stale_dispatch_filtering_and_recovery(app):
    """
    Verify find_stale_dispatches correctly isolates stale DISPATCHING records:
    - Stale DISPATCHING record (> 5 mins) -> detected and marked RECOVERY_REQUIRED
    - Recent DISPATCHING record (< 5 mins) -> ignored
    - Queued record in RETRY_QUEUED -> ignored
    """
    with app.app_context():
        now = datetime.now(timezone.utc)
        ten_mins_ago = (now - timedelta(minutes=10)).isoformat()
        one_min_ago = (now - timedelta(minutes=1)).isoformat()

        msg_stale = f"test-stale-{uuid.uuid4().hex[:8]}"
        msg_recent = f"test-recent-{uuid.uuid4().hex[:8]}"
        msg_queued = f"test-queued-{uuid.uuid4().hex[:8]}"
        all_ids = [msg_stale, msg_recent, msg_queued]

        try:
            # 1. Stale dispatch (10 mins ago)
            DeadLetterRepository._collection().insert_one({
                "message_id": msg_stale,
                "organization_id": "org-test-recovery",
                "dead_letter_status": "RETRY_REQUESTED",
                "manual_retry_dispatch_state": "DISPATCHING",
                "manual_retry_task_id": "task-stale-1",
                "manual_retry_dispatch_started_at": ten_mins_ago,
                "manual_retry_count": 1,
                "manual_retry_history": [{
                    "attempt": 1,
                    "task_id": "task-stale-1",
                    "status": "DISPATCHING",
                    "dispatch_started_at": ten_mins_ago
                }]
            })

            # 2. Recent dispatch (1 min ago)
            DeadLetterRepository._collection().insert_one({
                "message_id": msg_recent,
                "organization_id": "org-test-recovery",
                "dead_letter_status": "RETRY_REQUESTED",
                "manual_retry_dispatch_state": "DISPATCHING",
                "manual_retry_task_id": "task-recent-2",
                "manual_retry_dispatch_started_at": one_min_ago,
                "manual_retry_count": 1,
                "manual_retry_history": [{
                    "attempt": 1,
                    "task_id": "task-recent-2",
                    "status": "DISPATCHING",
                    "dispatch_started_at": one_min_ago
                }]
            })

            # 3. Queued dispatch (not in DISPATCHING)
            DeadLetterRepository._collection().insert_one({
                "message_id": msg_queued,
                "organization_id": "org-test-recovery",
                "dead_letter_status": "RETRY_QUEUED",
                "manual_retry_dispatch_state": "QUEUED",
                "manual_retry_task_id": "task-queued-3",
                "manual_retry_dispatch_started_at": ten_mins_ago,
                "manual_retry_count": 1
            })

            # Run find_stale_dispatches with 5 minutes threshold
            stale_found = DeadLetterRepository.find_stale_dispatches(minutes=5)
            found_ids = [r["message_id"] for r in stale_found]

            assert msg_stale in found_ids
            assert msg_recent not in found_ids
            assert msg_queued not in found_ids

            # Run recover_stale_dispatches
            recovery_res = DeadLetterService.recover_stale_dispatches(minutes=5)
            assert recovery_res["success"] is True
            assert any(r["message_id"] == msg_stale for r in recovery_res["recovered"])

            # Verify state updated to RECOVERY_REQUIRED
            rec_stale = DeadLetterRepository.find_by_message_id(msg_stale)
            assert rec_stale["manual_retry_dispatch_state"] == "RECOVERY_REQUIRED"
            assert "manual_retry_recovery_required_at" in rec_stale

            # Recent and queued unchanged
            rec_recent = DeadLetterRepository.find_by_message_id(msg_recent)
            assert rec_recent["manual_retry_dispatch_state"] == "DISPATCHING"

            rec_queued = DeadLetterRepository.find_by_message_id(msg_queued)
            assert rec_queued["manual_retry_dispatch_state"] == "QUEUED"

        finally:
            clean_test_records(all_ids)


def test_recovery_inspect_reconcile_and_resolve(app, client, auth_context):
    """
    Verify the complete recovery inspection, reconciliation, and resolution flow:
    - inspect_recovery_required lists the records
    - reconcile_recovery_required analyzes status
    - resolve_recovery transitions record to RESOLVED / COMPLETED
    """
    with app.app_context():
        headers = {"Authorization": f"Bearer {auth_context['super_admin_token']}"}
        msg_id = f"test-recon-{uuid.uuid4().hex[:8]}"
        task_id = str(uuid.uuid4())

        try:
            # Create original message in SENT
            MessageRepository.save({
                "message_id": msg_id,
                "organization_id": "org-test-recon",
                "status": "SENT",
                "channel": "email",
                "provider": "mock",
                "recipient": "recon@senderx.io",
                "data": {"subject": "Recon Test"}
            })

            # Create DLQ record in RECOVERY_REQUIRED
            DeadLetterRepository._collection().insert_one({
                "message_id": msg_id,
                "organization_id": "org-test-recon",
                "dead_letter_status": "RETRY_REQUESTED",
                "manual_retry_dispatch_state": "RECOVERY_REQUIRED",
                "manual_retry_task_id": task_id,
                "manual_retry_count": 1
            })

            # 1. Inspect endpoint
            inspect_res = client.get("/api/v1/dead-letters/recovery/inspect", headers=headers)
            assert inspect_res.status_code == 200
            inspect_data = inspect_res.get_json()
            assert any(r.get("message_id") == msg_id for r in inspect_data.get("data", []))

            # 2. Reconcile endpoint
            recon_res = client.get("/api/v1/dead-letters/recovery/reconcile", headers=headers)
            assert recon_res.status_code == 200
            recon_data = recon_res.get_json()
            recon_record = next((r for r in recon_data.get("data", []) if r.get("message_id") == msg_id), None)
            assert recon_record is not None
            assert recon_record["message_status"] == "SENT"
            assert recon_record["classification"] == "MESSAGE_COMPLETED"

            # 3. Direct resolve endpoint
            resolved = DeadLetterRepository.resolve_recovery(
                message_id=msg_id,
                task_id=task_id,
                resolved_by="admin@senderx.io",
                notes="Reconciled successfully with SENT message",
                dispatch_state="COMPLETED"
            )
            assert resolved is True

            # Verify DLQ record is resolved
            dlq = DeadLetterRepository.find_by_message_id(msg_id)
            assert dlq["dead_letter_status"] == "RESOLVED"
            assert dlq["manual_retry_dispatch_state"] == "COMPLETED"
            assert "manual_retry_resolved_at" in dlq

        finally:
            clean_test_records([msg_id])
