
from run import app
from app.modules.dead_letters.repository import DeadLetterRepository

TEST_MESSAGE_ID = "senderx-idempotency-test-001"

with app.app_context():

    collection = DeadLetterRepository._collection()

    # Clean up any previous test record
    collection.delete_one({
        "message_id": TEST_MESSAGE_ID
    })

    message = {
        "message_id": TEST_MESSAGE_ID,
        "channel": "email",
        "provider": "mock",
        "recipient": "idempotency-test@example.com",
        "status": "DEAD",
        "retry_count": 3,
        "manual_retry_count": 0
    }

    try:
        # Test 1: First automatic exhaustion
        DeadLetterRepository.save_from_message(
            message,
            "Simulated automatic failure"
        )

        record = DeadLetterRepository.find_by_message_id(
            TEST_MESSAGE_ID
        )

        print("Test 1: First automatic failure")
        print("Failure cycles:", len(record.get("failure_cycles", [])))

        # Test 2: Duplicate automatic execution
        DeadLetterRepository.save_from_message(
            message,
            "Simulated automatic failure"
        )

        record = DeadLetterRepository.find_by_message_id(
            TEST_MESSAGE_ID
        )

        print("\nTest 2: Duplicate automatic execution")
        print("Failure cycles:", len(record.get("failure_cycles", [])))

        # Test 3: New manual retry failure
        manual_message = {
            **message,
            "manual_retry_count": 1
        }

        DeadLetterRepository.save_from_message(
            manual_message,
            "Simulated manual retry failure"
        )

        record = DeadLetterRepository.find_by_message_id(
            TEST_MESSAGE_ID
        )

        print("\nTest 3: Manual retry failure")
        print("Failure cycles:", len(record.get("failure_cycles", [])))

        print("\nFailure cycle details:")

        for cycle in record.get("failure_cycles", []):
            print({
                "failure_cycle_id": cycle.get("failure_cycle_id"),
                "cycle_type": cycle.get("cycle_type"),
                "retry_count": cycle.get("retry_count"),
                "manual_retry_cycle": cycle.get("manual_retry_cycle")
            })

        cycles = record.get("failure_cycles", [])

        assert len(cycles) == 2, (
            "Expected exactly two failure cycles"
        )

        assert cycles[0]["cycle_type"] == "AUTOMATIC"
        assert cycles[1]["cycle_type"] == "MANUAL"

        assert (
            cycles[0]["failure_cycle_id"]
            != cycles[1]["failure_cycle_id"]
        )

        print("\nALL IDEMPOTENCY TESTS PASSED")

    finally:
        # Remove only our temporary test record
        collection.delete_one({
            "message_id": TEST_MESSAGE_ID
        })

        print("\nTemporary test record cleaned up.")
