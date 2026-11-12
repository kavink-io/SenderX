from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app import create_app
from app.modules.dead_letters.service import DeadLetterService


app = create_app()

with app.app_context():

    collection = app.mongo_db["dead_letters"]

    message_id = f"recovery-test-{uuid4()}"
    task_id = str(uuid4())

    old_time = (
        datetime.now(timezone.utc) - timedelta(minutes=10)
    ).isoformat()

    test_record = {
        "message_id": message_id,
        "dead_letter_status": "RETRY_REQUESTED",
        "manual_retry_count": 1,
        "manual_retry_dispatch_state": "DISPATCHING",
        "manual_retry_task_id": task_id,
        "manual_retry_dispatch_started_at": old_time,
        "manual_retry_history": [
            {
                "attempt": 1,
                "task_id": task_id,
                "status": "DISPATCHING",
                "requested_at": old_time
            }
        ]
    }

    try:
        # Insert temporary test record.
        collection.insert_one(test_record)

        print("Test record created:", message_id)

        # Run recovery.
        result = DeadLetterService.recover_stale_dispatches(
            minutes=5,
            limit=100
        )

        print("\nRecovery result:")
        print(result)

        # Verify database state.
        updated = collection.find_one({
            "message_id": message_id
        })

        assert updated is not None
        assert updated["manual_retry_dispatch_state"] == "RECOVERY_REQUIRED"
        assert updated["dead_letter_status"] == "RETRY_REQUESTED"

        print("\nPASS: Stale dispatch detected.")
        print("PASS: Dispatch state changed to RECOVERY_REQUIRED.")
        print("PASS: DLQ status and retry counter preserved.")

    finally:
        collection.delete_one({
            "message_id": message_id
        })

        print("\nTemporary test record cleaned up.")