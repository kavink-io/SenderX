
import uuid
from unittest.mock import patch

from app import create_app
from app.modules.messages.repository import MessageRepository
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.dead_letters.service import DeadLetterService


app = create_app()

message_id = f"recovery-resolution-test-{uuid.uuid4()}"
task_id = str(uuid.uuid4())

with app.app_context():

    message = {
        "message_id": message_id,
        "channel": "email",
        "recipient": "test@example.com",
        "provider": "mock",
        "status": "SENT",
        "retry_count": 0,
        "manual_retry_count": 1
    }

    MessageRepository.save(message)

    now = DeadLetterRepository._now()

    DeadLetterRepository._collection().insert_one({
        "message_id": message_id,
        "dead_letter_status": "RETRY_REQUESTED",
        "manual_retry_count": 1,
        "manual_retry_dispatch_state": "RECOVERY_REQUIRED",
        "manual_retry_task_id": task_id,
        "dead_lettered_at": now,
        "created_in_dlq_at": now
    })

    class FakeTaskResult:
        state = "SUCCESS"

        def ready(self):
            return True

        def successful(self):
            return True

        def failed(self):
            return False

    class FakeCelery:
        def AsyncResult(self, requested_task_id):
            assert requested_task_id == task_id
            return FakeTaskResult()

    app.celery = FakeCelery()

    try:
        result = DeadLetterService.resolve_recovery(
            message_id=message_id,
            resolved_by="test-admin",
            notes="Automated recovery resolution test"
        )

        assert result.get("success") is True, result

        record = DeadLetterRepository.find_by_message_id(message_id)

        assert record["dead_letter_status"] == "RESOLVED"
        assert record["manual_retry_dispatch_state"] == "RESOLVED"

        print("PASS: Recovery resolution succeeded.")
        print("PASS: DLQ status changed to RESOLVED.")
        print("PASS: Dispatch state changed to RESOLVED.")
        print(result)

    finally:
        DeadLetterRepository._collection().delete_one({
            "message_id": message_id
        })

        MessageRepository._collection().delete_one({
            "message_id": message_id
        })

        print("Temporary test records cleaned up.")
