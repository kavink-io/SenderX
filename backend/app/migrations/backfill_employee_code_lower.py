"""
Migration: Backfill employee_code_lower for all users
Phase 5 Task 5.3 Step 0(b)
Populates normalized employee_code_lower while leaving employee_code display values completely intact.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

# Setup environment
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "SenderX_db")


def backfill_employee_code_lower(db_name=None):
    target_db = db_name or MONGO_DB
    mongo_kwargs = {"serverSelectionTimeoutMS": 5000}
    try:
        import certifi
        mongo_kwargs["tlsCAFile"] = certifi.where()
    except Exception:
        pass
    client = MongoClient(MONGO_URI, **mongo_kwargs)
    db = client[target_db]

    users_col = db["users"]
    cursor = users_col.find({
        "employee_code": {"$type": "string"}
    })

    updated_count = 0
    skipped_count = 0

    for user in cursor:
        user_id = user.get("user_id")
        emp_code = user.get("employee_code")
        existing_lower = user.get("employee_code_lower")

        if emp_code:
            expected_lower = str(emp_code).strip().lower()
            if existing_lower != expected_lower:
                users_col.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"employee_code_lower": expected_lower}}
                )
                updated_count += 1
            else:
                skipped_count += 1
        else:
            skipped_count += 1

    print(f"[{target_db}] Backfill complete: {updated_count} users updated, {skipped_count} users already normalized.")
    client.close()
    return updated_count


if __name__ == "__main__":
    backfill_employee_code_lower()
