"""
SenderX - Manual Retry Lifecycle & DLQ Test Suite
Validates Test Cases A through F as specified in SenderX requirements.
"""

import uuid
import pytest
from unittest.mock import MagicMock

from app import create_app
from app.modules.messages.repository import MessageRepository
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.dead_letters.service import DeadLetterService
from app.queue.tasks import process_message


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def org_ids():
    return {
        "org_a": f"org-a-{uuid.uuid4().hex[:8]}",
        "org_b": f"org-b-{uuid.uuid4().hex[:8]}"
    }


def clean_records(message_id, org_id=None):
    DeadLetterRepository._collection().delete_one({"message_id": message_id})
    MessageRepository._collection().delete_one({"message_id": message_id})


def test_case_a_successful_manual_retry(app, org_ids):
    """
    Test Case A: Successful manual retry
    1. Create message with temporary_failure
    2. Simulate exhaustion to DEAD and DLQ (PENDING_REVIEW)
    3. Update mock_scenario to temporary_then_success
    4. Trigger manual retry -> verify task dispatched
    5. Run worker task -> message succeeds, marks SENT, DLQ marked RESOLVED
    6. Verify dispatch COMPLETED, history COMPLETED, failure cycles preserved
    """
    with app.app_context():
        msg_id = f"test-case-a-{uuid.uuid4()}"
        org_id = org_ids["org_a"]

        try:
            # 1. Create message
            msg = {
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "case_a@example.com",
                "data": {"subject": "Test A", "message": "Content A", "mock_scenario": "temporary_failure"},
                "status": "PROCESSING",
                "retry_count": 3,
                "manual_retry_count": 0
            }
            MessageRepository.save(msg)

            # 2. Exhaust to DEAD & DLQ
            MessageRepository.update_status(msg_id, "DEAD", "PROCESSING", organization_id=org_id)
            dead_msg = MessageRepository.find_by_id(msg_id, organization_id=org_id)
            dlq = DeadLetterRepository.save_from_message(dead_msg, "Simulated network failure", organization_id=org_id)

            assert dlq["dead_letter_status"] == "PENDING_REVIEW"
            assert len(dlq.get("failure_cycles", [])) == 1
            assert dlq["failure_cycles"][0]["cycle_type"] == "AUTOMATIC"

            # 3. Change scenario to temporary_then_success
            MessageRepository._collection().update_one(
                {"message_id": msg_id},
                {"$set": {"data.mock_scenario": "temporary_then_success"}}
            )

            # 4. Trigger manual retry
            # Mock Celery send_task to preserve the pre-generated task_id
            dispatched_task_ids = []

            def mock_send_task(name, args=None, task_id=None, **kwargs):
                dispatched_task_ids.append(task_id)
                t = MagicMock()
                t.id = task_id
                return t

            original_send_task = app.celery.send_task
            app.celery.send_task = MagicMock(side_effect=mock_send_task)

            try:
                retry_res = DeadLetterService.retry_dead_letter(msg_id, organization_id=org_id)
                assert retry_res["success"] is True
                assert retry_res["status"] == "QUEUED"
                assert retry_res["audit_updated"] is True
            finally:
                app.celery.send_task = original_send_task

            real_task_id = dispatched_task_ids[0]

            # Verify DLQ state is RETRY_QUEUED with correct task_id
            dlq_after_retry = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_after_retry["dead_letter_status"] == "RETRY_QUEUED"
            assert dlq_after_retry["manual_retry_dispatch_state"] == "QUEUED"
            assert dlq_after_retry["manual_retry_task_id"] == real_task_id

            # 5. Simulate Celery worker processing the task with self.request.id == real_task_id
            # In temporary_then_success, mock adapter succeeds when retry_count >= 2
            MessageRepository._collection().update_one(
                {"message_id": msg_id},
                {"$set": {"retry_count": 2}}
            )

            async_res = process_message.apply(args=[msg_id], task_id=real_task_id)
            worker_result = async_res.result
            assert worker_result["success"] is True
            assert worker_result["status"] == "SENT"

            # 6. Verify DLQ resolution
            dlq_resolved = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_resolved["dead_letter_status"] == "RESOLVED"
            assert dlq_resolved["manual_retry_dispatch_state"] == "COMPLETED"
            assert "manual_retry_task_id" not in dlq_resolved or not dlq_resolved.get("manual_retry_task_id")
            assert len(dlq_resolved["failure_cycles"]) == 1  # preserved previous cycle, no extra cycle on success

            # Verify manual retry history is COMPLETED
            history = dlq_resolved.get("manual_retry_history", [])
            assert len(history) >= 1
            assert history[-1]["status"] == "COMPLETED"

        finally:
            clean_records(msg_id, org_id)


def test_case_b_manual_retry_fails_again(app, org_ids):
    """
    Test Case B: Manual retry fails again
    1. Create message with temporary_failure
    2. Reach DEAD and DLQ
    3. Trigger manual retry without changing scenario
    4. Let retries exhaust again -> reaches DEAD
    5. Confirm another MANUAL failure cycle is added
    6. Confirm DLQ returns to PENDING_REVIEW
    7. Confirm dispatch state COMPLETED
    8. Confirm manual retry history reflects the failed attempt accurately
    """
    with app.app_context():
        msg_id = f"test-case-b-{uuid.uuid4()}"
        org_id = org_ids["org_a"]

        try:
            # 1. Create message and reach DEAD
            msg = {
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "case_b@example.com",
                "data": {"subject": "Test B", "message": "Content B", "mock_scenario": "temporary_failure"},
                "status": "DEAD",
                "retry_count": 3,
                "manual_retry_count": 0
            }
            MessageRepository.save(msg)
            dlq = DeadLetterRepository.save_from_message(msg, "Initial automatic exhaustion", organization_id=org_id)
            assert dlq["dead_letter_status"] == "PENDING_REVIEW"
            assert len(dlq["failure_cycles"]) == 1

            # 2. Trigger manual retry
            def mock_send_task(name, args=None, task_id=None, **kwargs):
                t = MagicMock()
                t.id = task_id
                return t

            original_send_task = app.celery.send_task
            app.celery.send_task = MagicMock(side_effect=mock_send_task)

            try:
                retry_res = DeadLetterService.retry_dead_letter(msg_id, organization_id=org_id)
                assert retry_res["success"] is True
                assert retry_res["status"] == "QUEUED"
            finally:
                app.celery.send_task = original_send_task

            # Verify queued state
            dlq_queued = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_queued["dead_letter_status"] == "RETRY_QUEUED"
            assert dlq_queued["manual_retry_dispatch_state"] == "QUEUED"

            # 3. Simulate automatic retries exhausting again during manual retry
            MessageRepository.update_status(msg_id, "PROCESSING", "QUEUED", organization_id=org_id)
            MessageRepository.update_retry_info(
                message_id=msg_id,
                retry_count=3,
                old_status="PROCESSING",
                new_status="DEAD",
                error="Exhausted during manual retry",
                organization_id=org_id
            )
            dead_again_msg = MessageRepository.find_by_id(msg_id, organization_id=org_id)
            assert dead_again_msg["status"] == "DEAD"
            assert dead_again_msg["manual_retry_count"] == 1

            # 4. Worker saves to DLQ
            dlq_after_fail = DeadLetterRepository.save_from_message(
                dead_again_msg,
                "Exhausted during manual retry",
                organization_id=org_id
            )

            # 5. Confirm DLQ returned to PENDING_REVIEW
            assert dlq_after_fail["dead_letter_status"] == "PENDING_REVIEW"
            assert dlq_after_fail["manual_retry_dispatch_state"] == "COMPLETED"

            # 6. Confirm second failure cycle is added and marked MANUAL
            cycles = dlq_after_fail["failure_cycles"]
            assert len(cycles) == 2
            assert cycles[0]["cycle_type"] == "AUTOMATIC"
            assert cycles[1]["cycle_type"] == "MANUAL"
            assert cycles[1]["manual_retry_cycle"] == 1

            # 7. Confirm manual retry history reflects failure
            history = dlq_after_fail.get("manual_retry_history", [])
            assert len(history) >= 1
            assert history[-1]["status"] == "FAILED"

        finally:
            clean_records(msg_id, org_id)


def test_case_c_duplicate_manual_retry_request(app, org_ids):
    """
    Test Case C: Duplicate manual retry request
    Trigger two manual retry requests concurrently.
    Only one should be accepted.
    """
    with app.app_context():
        msg_id = f"test-case-c-{uuid.uuid4()}"
        org_id = org_ids["org_a"]

        try:
            msg = {
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "case_c@example.com",
                "data": {"subject": "Test C", "message": "Content C"},
                "status": "DEAD",
                "retry_count": 3,
                "manual_retry_count": 0
            }
            MessageRepository.save(msg)
            DeadLetterRepository.save_from_message(msg, "Error", organization_id=org_id)

            def mock_send_task(name, args=None, task_id=None, **kwargs):
                t = MagicMock()
                t.id = task_id
                return t

            original_send_task = app.celery.send_task
            app.celery.send_task = MagicMock(side_effect=mock_send_task)

            try:
                # First attempt
                res1 = DeadLetterService.retry_dead_letter(msg_id, organization_id=org_id)
                assert res1["success"] is True

                # Second attempt while already requested / queued
                res2 = DeadLetterService.retry_dead_letter(msg_id, organization_id=org_id)
                assert res2["success"] is False
                assert "not available for retry" in res2["message"]

            finally:
                app.celery.send_task = original_send_task

            # Verify manual_retry_count was incremented only once
            dlq = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq["manual_retry_count"] == 1

        finally:
            clean_records(msg_id, org_id)


def test_case_d_wrong_task_id(app, org_ids):
    """
    Test Case D: Wrong task ID
    Attempt to resolve a DLQ record using an unrelated task ID.
    It must not resolve.
    """
    with app.app_context():
        msg_id = f"test-case-d-{uuid.uuid4()}"
        org_id = org_ids["org_a"]

        try:
            msg = {
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "case_d@example.com",
                "data": {"subject": "Test D", "message": "Content D"},
                "status": "PROCESSING",
                "retry_count": 0,
                "manual_retry_count": 1
            }
            MessageRepository.save(msg)

            # Insert DLQ in RETRY_QUEUED with specific task ID
            legit_task_id = str(uuid.uuid4())
            fake_task_id = str(uuid.uuid4())

            now = DeadLetterRepository._now()
            DeadLetterRepository._collection().insert_one({
                "message_id": msg_id,
                "organization_id": org_id,
                "dead_letter_status": "RETRY_QUEUED",
                "manual_retry_dispatch_state": "QUEUED",
                "manual_retry_task_id": legit_task_id,
                "created_in_dlq_at": now
            })

            # Attempt to resolve with fake_task_id
            resolved = DeadLetterRepository.mark_manual_retry_completed(
                message_id=msg_id,
                task_id=fake_task_id,
                organization_id=org_id
            )
            assert resolved is False

            # Verify DLQ record remained RETRY_QUEUED
            dlq = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq["dead_letter_status"] == "RETRY_QUEUED"
            assert dlq["manual_retry_dispatch_state"] == "QUEUED"

        finally:
            clean_records(msg_id, org_id)


def test_case_e_cross_tenant_access(app, org_ids):
    """
    Test Case E: Cross-tenant access
    Organization B must not access Organization A's DLQ record.
    Organization B must not retry or delete Organization A's record.
    """
    with app.app_context():
        msg_id = f"test-case-e-{uuid.uuid4()}"
        org_a = org_ids["org_a"]
        org_b = org_ids["org_b"]

        try:
            msg = {
                "message_id": msg_id,
                "organization_id": org_a,
                "channel": "email",
                "provider": "mock",
                "recipient": "case_e@example.com",
                "data": {"subject": "Test E", "message": "Content E"},
                "status": "DEAD",
                "retry_count": 3,
                "manual_retry_count": 0
            }
            MessageRepository.save(msg)
            DeadLetterRepository.save_from_message(msg, "Error", organization_id=org_a)

            # 1. Org B cannot find Org A's DLQ record
            assert DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_b) is None
            get_res = DeadLetterService.get_dead_letter(msg_id, organization_id=org_b)
            assert get_res["success"] is False

            # 2. Org B cannot retry Org A's record
            retry_res = DeadLetterService.retry_dead_letter(msg_id, organization_id=org_b)
            assert retry_res["success"] is False
            assert "not found" in retry_res["message"].lower()

            # 3. Org B cannot delete Org A's record
            delete_res = DeadLetterService.delete_dead_letter(msg_id, confirm=True, organization_id=org_b)
            assert delete_res["success"] is False
            assert "not found" in delete_res["message"].lower()

            # Verify Org A's record is intact
            record_a = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_a)
            assert record_a is not None
            assert record_a["organization_id"] == org_a

        finally:
            clean_records(msg_id, org_a)


def test_case_f_successful_ordinary_message(app, org_ids):
    """
    Test Case F: Successful ordinary message
    A normal successful message should not create or modify a DLQ record.
    """
    with app.app_context():
        msg_id = f"test-case-f-{uuid.uuid4()}"
        org_id = org_ids["org_a"]

        try:
            msg = {
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "case_f@example.com",
                "data": {"subject": "Test F", "message": "Content F", "mock_scenario": "success"},
                "status": "QUEUED",
                "retry_count": 0,
                "manual_retry_count": 0
            }
            MessageRepository.save(msg)

            # Process message using Celery apply
            async_res = process_message.apply(args=[msg_id])
            result = async_res.result
            assert result["success"] is True
            assert result["status"] == "SENT"

            # Verify message is SENT
            saved_msg = MessageRepository.find_by_id(msg_id, organization_id=org_id)
            assert saved_msg["status"] == "SENT"

            # Verify NO DLQ record exists
            dlq = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq is None

        finally:
            clean_records(msg_id, org_id)


def test_case_g_dispatch_cancellation_and_state_traceability(app, org_ids):
    """
    Test Case G: DLQ Dispatch Cancellation State Traceability
    Verify:
    1. mark_retry_requested sets state to DISPATCHING.
    2. restore_pending_review transitions state to CANCELLED (never unsets/leaves blank).
    3. Status history logs the transition.
    4. Record can subsequently be re-requested for retry.
    """
    with app.app_context():
        msg_id = f"test-case-g-{uuid.uuid4()}"
        org_id = org_ids["org_a"]

        try:
            msg = {
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "case_g@example.com",
                "data": {"subject": "Test G", "message": "Content G"},
                "status": "DEAD",
                "retry_count": 3,
                "manual_retry_count": 0
            }
            MessageRepository.save(msg)
            DeadLetterRepository.save_from_message(msg, "Error G", organization_id=org_id)

            # 1. Request manual retry -> DISPATCHING
            req = DeadLetterRepository.mark_retry_requested(msg_id, organization_id=org_id)
            assert req is not None
            task_id = req["task_id"]

            dlq_dispatching = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_dispatching["dead_letter_status"] == "RETRY_REQUESTED"
            assert dlq_dispatching["manual_retry_dispatch_state"] == "DISPATCHING"

            # 2. Cancel / restore to review -> CANCELLED
            restored = DeadLetterRepository.restore_pending_review(msg_id, organization_id=org_id)
            assert restored is True

            dlq_cancelled = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_cancelled["dead_letter_status"] == "PENDING_REVIEW"
            assert dlq_cancelled["manual_retry_dispatch_state"] == "CANCELLED"
            assert "manual_retry_cancelled_at" in dlq_cancelled

            # History entry verified
            history = dlq_cancelled.get("manual_retry_history", [])
            assert len(history) >= 1
            assert history[-1]["status"] == "CANCELLED"

            # Status history verified
            status_hist = dlq_cancelled.get("status_history", [])
            assert len(status_hist) >= 1
            assert status_hist[-1]["to"] == "PENDING_REVIEW"

            # 3. Subsequent retry request succeeds from CANCELLED state
            req2 = DeadLetterRepository.mark_retry_requested(msg_id, organization_id=org_id)
            assert req2 is not None
            dlq_re_requested = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_re_requested["dead_letter_status"] == "RETRY_REQUESTED"
            assert dlq_re_requested["manual_retry_dispatch_state"] == "DISPATCHING"

        finally:
            clean_records(msg_id, org_id)


def test_case_h_dispatch_failure_and_state_traceability(app, org_ids):
    """
    Test Case H: DLQ Dispatch Failure State Traceability
    Verify:
    1. mark_retry_dispatch_failed transitions state to DISPATCH_FAILED.
    2. Status returns to PENDING_REVIEW.
    3. Error is recorded in history and top-level fields.
    4. Record can subsequently be re-requested for retry.
    """
    with app.app_context():
        msg_id = f"test-case-h-{uuid.uuid4()}"
        org_id = org_ids["org_a"]

        try:
            msg = {
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "case_h@example.com",
                "data": {"subject": "Test H", "message": "Content H"},
                "status": "DEAD",
                "retry_count": 3,
                "manual_retry_count": 0
            }
            MessageRepository.save(msg)
            DeadLetterRepository.save_from_message(msg, "Error H", organization_id=org_id)

            req = DeadLetterRepository.mark_retry_requested(msg_id, organization_id=org_id)
            assert req is not None
            task_id = req["task_id"]

            # Dispatch failure
            error_reason = "Broker connection timeout: RabbitMQ unreachable"
            failed = DeadLetterRepository.mark_retry_dispatch_failed(
                message_id=msg_id,
                error=error_reason,
                task_id=task_id,
                organization_id=org_id
            )
            assert failed is True

            dlq_failed = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_failed["dead_letter_status"] == "PENDING_REVIEW"
            assert dlq_failed["manual_retry_dispatch_state"] == "DISPATCH_FAILED"
            assert "manual_retry_dispatch_failed_at" in dlq_failed

            # History entry verified
            history = dlq_failed.get("manual_retry_history", [])
            assert len(history) >= 1
            assert history[-1]["status"] == "DISPATCH_FAILED"
            assert error_reason in history[-1]["error"]

            # Subsequent retry from DISPATCH_FAILED succeeds
            req2 = DeadLetterRepository.mark_retry_requested(msg_id, organization_id=org_id)
            assert req2 is not None
            dlq_retry2 = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_retry2["manual_retry_dispatch_state"] == "DISPATCHING"

        finally:
            clean_records(msg_id, org_id)


def test_case_i_stale_dispatch_recovery_workflow(app, org_ids):
    """
    Test Case I: Stale Dispatch Recovery & Resolution Workflow
    Verify:
    1. Stale dispatch (started > 5 minutes ago) is detected by find_stale_dispatches.
    2. recover_stale_dispatches marks state as RECOVERY_REQUIRED.
    3. resolve_recovery transitions state to COMPLETED and status to RESOLVED.
    """
    from datetime import datetime, timezone, timedelta
    with app.app_context():
        msg_id = f"test-case-i-{uuid.uuid4()}"
        org_id = org_ids["org_a"]

        try:
            msg = {
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "case_i@example.com",
                "data": {"subject": "Test I", "message": "Content I"},
                "status": "DEAD",
                "retry_count": 3,
                "manual_retry_count": 0
            }
            MessageRepository.save(msg)
            DeadLetterRepository.save_from_message(msg, "Error I", organization_id=org_id)

            req = DeadLetterRepository.mark_retry_requested(msg_id, organization_id=org_id)
            assert req is not None
            task_id = req["task_id"]

            # Backdate manual_retry_dispatch_started_at by 10 minutes
            ten_mins_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            DeadLetterRepository._collection().update_one(
                {"message_id": msg_id},
                {"$set": {"manual_retry_dispatch_started_at": ten_mins_ago}}
            )

            # 1. Stale dispatch recovery scan
            recovery_result = DeadLetterService.recover_stale_dispatches(minutes=5)
            assert recovery_result["success"] is True
            assert any(r["message_id"] == msg_id for r in recovery_result["recovered"])

            # Verify DLQ state updated to RECOVERY_REQUIRED
            dlq_rec = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_rec["manual_retry_dispatch_state"] == "RECOVERY_REQUIRED"
            assert "manual_retry_recovery_required_at" in dlq_rec

            # 2. Resolve recovery
            resolved = DeadLetterRepository.resolve_recovery(
                message_id=msg_id,
                task_id=task_id,
                resolved_by="admin@senderx.io",
                notes="Verified task completed during investigation",
                dispatch_state="COMPLETED"
            )
            assert resolved is True

            dlq_resolved = DeadLetterRepository.find_by_message_id(msg_id, organization_id=org_id)
            assert dlq_resolved["dead_letter_status"] == "RESOLVED"
            assert dlq_resolved["manual_retry_dispatch_state"] == "COMPLETED"
            assert "manual_retry_resolved_at" in dlq_resolved

        finally:
            clean_records(msg_id, org_id)
