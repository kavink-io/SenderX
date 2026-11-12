
from app import create_app

from app.modules.messages.repository import MessageRepository
from app.modules.dead_letters.repository import DeadLetterRepository


MESSAGE_ID = "dd57f633-4541-4b24-bb2f-efd9727b77b4"

ORGANIZATION_ID = "ac3b6cae-f4b4-41fb-a57e-5a3f67247769"


app = create_app()

with app.app_context():

    print("\n--- SenderX DLQ Repair ---")

    # 1. Fetch the original tenant-owned message.
    message = MessageRepository.find_by_id(
        MESSAGE_ID,
        organization_id=ORGANIZATION_ID
    )

    if not message:
        print("ERROR: Original message not found.")
        raise SystemExit(1)

    print("Original message found.")
    print("Message ID:", message.get("message_id"))
    print("Organization ID:", message.get("organization_id"))
    print("Message status:", message.get("status"))

    # 2. Check that this is the expected organization.
    if message.get("organization_id") != ORGANIZATION_ID:
        print("ERROR: Organization ID mismatch.")
        raise SystemExit(1)

    # 3. Fetch existing DLQ record without tenant filter.
    existing = DeadLetterRepository.find_by_message_id(
        MESSAGE_ID
    )

    if not existing:
        print("ERROR: Existing DLQ record not found.")
        raise SystemExit(1)

    print("\nExisting DLQ record found.")
    print(
        "Existing organization ID:",
        existing.get("organization_id")
    )

    # 4. Repair only the missing tenant ownership field.
    # No retry cycle is created or modified.
    collection = DeadLetterRepository._collection()

    result = collection.update_one(
        {
            "message_id": MESSAGE_ID,
            "$or": [
                {"organization_id": {"$exists": False}},
                {"organization_id": None}
            ]
        },
        {
            "$set": {
                "organization_id": ORGANIZATION_ID
            }
        }
    )

    if result.modified_count == 1:
        print("\nSUCCESS: Organization ID added to existing DLQ record.")

    elif result.matched_count == 1:
        print("\nNo change required. Organization ID already matches.")

    else:
        print(
            "\nWARNING: Record was not modified. "
            "It may already belong to another organization."
        )
        raise SystemExit(1)

    # 5. Verify tenant-scoped retrieval.
    repaired = DeadLetterRepository.find_by_message_id(
        MESSAGE_ID,
        organization_id=ORGANIZATION_ID
    )

    if not repaired:
        print("ERROR: Tenant-scoped verification failed.")
        raise SystemExit(1)

    print("\n--- Verification Successful ---")
    print("Message ID:", repaired.get("message_id"))
    print("Organization ID:", repaired.get("organization_id"))
    print(
        "Failure cycles:",
        len(repaired.get("failure_cycles", []))
    )
    print(
        "DLQ status:",
        repaired.get("dead_letter_status")
    )

    print("\nRepair completed.")
