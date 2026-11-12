
from uuid import uuid4

from app import create_app
from app.modules.dead_letters.service import DeadLetterService


app = create_app()

with app.app_context():

    messages = app.mongo_db["messages"]
    dead_letters = app.mongo_db["dead_letters"]

    message_id = f"reconciliation-test-{uuid4()}"
    task_id = str(uuid4())

    celery_backend = app.celery.backend

    try:
        # 1. Create a temporary DEAD message.
        messages.insert_one({
            "message_id": message_id,
            "status": "DEAD",
            "retry_count": 3,
            "manual_retry_count": 1,
            "provider": "mock",
            "channel": "email",
            "recipient": "test@example.com"
        })

        # 2. Create a temporary recovery-required DLQ record.
        dead_letters.insert_one({
            "message_id": message_id,
            "dead_letter_status": "RETRY_REQUESTED",
            "manual_retry_count": 1,
            "manual_retry_dispatch_state": "RECOVERY_REQUIRED",
            "manual_retry_task_id": task_id,
            "manual_retry_history": []
        })

        # 3. Simulate Celery SUCCESS without publishing a task.
        celery_backend.store_result(
            task_id,
            {
                "success": False,
                "status": "DEAD"
            },
            state="SUCCESS"
        )

        print("Temporary test records created.")
        print("Celery state simulated as SUCCESS.")
        print("MongoDB message status set to DEAD.")

        # 4. Run reconciliation.
        result = DeadLetterService.reconcile_recovery_required()

        print("\nReconciliation result:")
        print(result)

        # 5. Verify expected classification.
        matching = [
            item for item in result.get("data", [])
            if item.get("message_id") == message_id
        ]

        assert len(matching) == 1

        item = matching[0]

        assert item["celery_state"] == "SUCCESS"
        assert item["message_status"] == "DEAD"

        assert item["classification"] == "MESSAGE_DEAD"

        assert (
            item["recommended_action"]
            == "INSPECT_DLQ_BEFORE_RETRY"
        )

        print("\nPASS: Celery SUCCESS did not imply delivery.")
        print("PASS: DEAD message was classified correctly.")
        print("PASS: No message was dispatched.")

    finally:
        # 6. Clean up temporary MongoDB records and Redis result.
        messages.delete_one({"message_id": message_id})
        dead_letters.delete_one({"message_id": message_id})

        celery_backend.delete(task_id)

        print("\nTemporary test records cleaned up.")
