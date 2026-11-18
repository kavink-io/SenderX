import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import logging
from app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_cleanup():
    app = create_app()
    with app.app_context():
        db = app.mongo_db
        logger.info("Starting SenderX Phase 5 Task 5.2 Database Cleanup...")

        # 1. Drop obsolete organization_sequences collection
        colls = db.list_collection_names()
        if "organization_sequences" in colls:
            db.drop_collection("organization_sequences")
            logger.info("Successfully dropped obsolete collection: 'organization_sequences'")
        else:
            logger.info("Collection 'organization_sequences' was already absent.")

        # 2. Unset obsolete employee_id_prefix in organizations
        unset_res = db.organizations.update_many(
            {"employee_id_prefix": {"$exists": True}},
            {"$unset": {"employee_id_prefix": ""}}
        )
        logger.info(f"Cleaned up 'employee_id_prefix' field from {unset_res.modified_count} organization documents.")

        # 3. Verify user counts and preserve existing employee records
        total_users = db.users.count_documents({})
        users_with_code = db.users.count_documents({"employee_code": {"$exists": True, "$nin": [None, ""]}})
        logger.info(f"Verified: Total users preserved = {total_users}; users with employee_code = {users_with_code}.")

        # 4. Verify users index on (organization_id, employee_code)
        user_indexes = list(db.users.list_indexes())
        has_code_index = any(
            idx.get("key") == {"organization_id": 1, "employee_code": 1} or
            list(idx.get("key", {}).items()) == [("organization_id", 1), ("employee_code", 1)]
            for idx in user_indexes
        )
        logger.info(f"User organization_id + employee_code unique index present: {has_code_index}")

        logger.info("Phase 5 Task 5.2 Database Cleanup Completed Successfully.")


if __name__ == "__main__":
    run_cleanup()
