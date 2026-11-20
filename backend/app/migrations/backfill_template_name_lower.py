"""
MongoDB Migration: Backfill name_lower for email templates.

Idempotent migration script that normalizes and backfills the `name_lower` field
in the `templates` collection.

Safety Guards:
- Defaults to --dry-run mode. Writes require explicit --apply.
- Refuses to write to production database (SenderX_db) by default.
- Processes documents in bounded batches using bulk_write.
- Detects intra-organization lowercase name collisions before writing.
"""

import argparse
import logging
import os
import sys
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

load_dotenv(os.path.join(backend_dir, ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration.backfill_template_name_lower")


def run_migration(
    apply: bool = False,
    batch_size: int = 100,
    prod_safety_phrase: str = "",
    allow_prod_write: bool = False,
    **kwargs,
):
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB", "SenderX_test")

    logger.info(f"Target Database: {db_name}")
    logger.info(f"Mode: {'APPLY (WRITE)' if apply else 'DRY RUN (READ ONLY)'}")

    # Production safety guard: strictly refuse writes to SenderX_db unless two independent gates pass
    if apply and db_name == "SenderX_db":
        env_gate = os.getenv("ALLOW_PRODUCTION_TEMPLATE_MIGRATION", "").strip() == "YES_PROCEED"
        phrase_gate = prod_safety_phrase.strip() == "CONFIRM_SENDERX_DB_PRODUCTION_BACKFILL"

        if not (env_gate and phrase_gate):
            logger.error(
                "SAFETY VIOLATION: Refusing to perform writes against production database 'SenderX_db'. "
                "Production writes require BOTH ALLOW_PRODUCTION_TEMPLATE_MIGRATION='YES_PROCEED' env var "
                "and --prod-safety-phrase 'CONFIRM_SENDERX_DB_PRODUCTION_BACKFILL'."
            )
            return {
                "status": "BLOCKED",
                "reason": "Production write guard enforced (multi-step gate required)",
                "db_name": db_name,
            }

    client = MongoClient(mongo_uri)
    try:
        db = client[db_name]
        collection = db["templates"]

        total_templates = collection.count_documents({})
        logger.info(f"Total documents in '{collection.name}': {total_templates}")

        # Query documents needing backfill
        missing_query = {
            "$or": [
                {"name_lower": {"$exists": False}},
                {"name_lower": None},
                {"name_lower": {"$not": {"$type": "string"}}},
            ]
        }
        docs_to_backfill = list(collection.find(missing_query))
        logger.info(f"Documents requiring 'name_lower' backfill: {len(docs_to_backfill)}")

        if not docs_to_backfill:
            logger.info("All templates already possess valid 'name_lower'. Nothing to do.")
            return {
                "status": "COMPLETE",
                "total_templates": total_templates,
                "needed_backfill": 0,
                "updated": 0,
                "conflicts": [],
            }

        # Analyze for potential collision against partialFilterExpression: {"status": {"$in": ["ACTIVE", "DRAFT"]}}
        # Unique constraint only applies to active and draft templates.
        ACTIVE_INDEX_STATUSES = {"ACTIVE", "DRAFT"}

        existing_lookup = {}
        for doc in collection.find(
            {"name_lower": {"$type": "string"}, "status": {"$in": list(ACTIVE_INDEX_STATUSES)}},
            {"organization_id": 1, "name_lower": 1, "status": 1}
        ):
            key = (doc.get("organization_id"), doc.get("name_lower"))
            existing_lookup[key] = str(doc["_id"])

        conflicts = []
        updates = []
        seen_in_batch = {}

        for doc in docs_to_backfill:
            doc_id = doc["_id"]
            org_id = doc.get("organization_id")
            raw_name = doc.get("name", "")
            doc_status = (doc.get("status") or "ACTIVE").upper()
            norm_name = raw_name.strip().lower() if raw_name else ""

            if not norm_name:
                logger.warning(f"Document {doc_id} has empty name; skipping backfill.")
                continue

            pair = (org_id, norm_name)
            is_active_indexed = doc_status in ACTIVE_INDEX_STATUSES

            # Check unique index collision only for ACTIVE and DRAFT records
            if is_active_indexed:
                if pair in existing_lookup and existing_lookup[pair] != str(doc_id):
                    conflicts.append({
                        "doc_id": str(doc_id),
                        "conflicting_id": existing_lookup[pair],
                        "organization_id": org_id,
                        "normalized_name": norm_name,
                        "status": doc_status,
                    })
                    logger.error(
                        f"Conflict detected for org {org_id}: active/draft '{norm_name}' "
                        f"already used by {existing_lookup[pair]}"
                    )
                    continue

                if pair in seen_in_batch:
                    conflicts.append({
                        "doc_id": str(doc_id),
                        "conflicting_id": seen_in_batch[pair],
                        "organization_id": org_id,
                        "normalized_name": norm_name,
                        "status": doc_status,
                    })
                    logger.error(
                        f"Duplicate active/draft detected within migration batch for org {org_id}: '{norm_name}'"
                    )
                    continue

                seen_in_batch[pair] = str(doc_id)

            updates.append((doc_id, norm_name))

        logger.info(f"Validation complete: {len(updates)} valid updates, {len(conflicts)} conflicts detected.")

        if not apply:
            logger.info(f"[DRY-RUN] Would backfill {len(updates)} documents in batches of {batch_size}.")
            return {
                "status": "DRY_RUN_COMPLETE",
                "total_templates": total_templates,
                "needed_backfill": len(docs_to_backfill),
                "would_update": len(updates),
                "conflicts": conflicts,
            }

        # Execute bounded batches
        updated_count = 0
        for i in range(0, len(updates), batch_size):
            chunk = updates[i:i + batch_size]
            operations = [
                UpdateOne({"_id": doc_id}, {"$set": {"name_lower": norm_name}})
                for doc_id, norm_name in chunk
            ]
            res = collection.bulk_write(operations, ordered=False)
            updated_count += res.modified_count
            logger.info(f"Processed batch {i // batch_size + 1}: modified {res.modified_count} documents.")

        logger.info(f"[APPLY] Successfully updated {updated_count} documents.")
        return {
            "status": "APPLY_COMPLETE",
            "total_templates": total_templates,
            "needed_backfill": len(docs_to_backfill),
            "updated": updated_count,
            "conflicts": conflicts,
        }

    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill name_lower in templates collection")
    parser.add_argument("--apply", action="store_true", default=False, help="Execute writes (default: dry run)")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for bulk updates (default: 100)")
    parser.add_argument("--prod-safety-phrase", type=str, default="", help="Safety phrase required for SenderX_db")

    args = parser.parse_args()
    result = run_migration(
        apply=args.apply,
        batch_size=args.batch_size,
        prod_safety_phrase=args.prod_safety_phrase,
    )
    print("Migration Result:", result)


if __name__ == "__main__":
    main()
