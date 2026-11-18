"""
Migration Script: Employee Business Identity Management Backfill
Phase 5 Task 4 Scope Correction - Employee IDs Only

Provides safe, idempotent migration and backfilling for:
1. Organization employee ID prefix configuration (defaults to 'EMP').
2. Employee business ID sequences and missing employee_code backfilling.
3. Database index verification (users organization_id + employee_code unique partial index).

Usage:
    python -m app.migrations.migrate_business_identities [--dry-run] [--batch-size 50] [--org-id <uuid>]
"""

import os
import sys
import argparse
import logging

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app import create_app
from app.config.database_indexes import ensure_database_indexes
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.sequence_repository import SequenceRepository
from app.modules.users.repository import UserRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("employee_identity_migration")


def run_migration(dry_run=False, batch_size=50, target_org_id=None, ensure_indexes=True):
    logger.info("=" * 60)
    logger.info(f"Starting Employee Identity Migration (dry_run={dry_run}, batch_size={batch_size}, target_org_id={target_org_id})")
    logger.info("=" * 60)

    # 1. Ensure database indexes
    if not dry_run and ensure_indexes:
        try:
            logger.info("Applying and verifying sparse unique database indexes...")
            ensure_database_indexes()
        except Exception as e:
            logger.warning(f"Index verification skipped or encountered transient issue: {e}")
    else:
        logger.info("[DRY RUN or SKIP] Skipping index creation step.")

    # 2. Inspect organizations
    org_query = {}
    if target_org_id:
        org_query["organization_id"] = target_org_id

    orgs = list(OrganizationRepository._collection().find(org_query))
    logger.info(f"Found {len(orgs)} organizations to evaluate.")

    org_summary = {
        "total": len(orgs),
        "custom_prefix": 0,
        "default_prefix": 0
    }

    org_prefixes = {}  # org_id -> prefix

    for org in orgs:
        org_id = org.get("organization_id")
        prefix = org.get("employee_id_prefix")

        if prefix:
            org_summary["custom_prefix"] += 1
            org_prefixes[org_id] = prefix
        else:
            org_summary["default_prefix"] += 1
            org_prefixes[org_id] = "EMP"
            if not dry_run:
                OrganizationRepository.update(org_id, {"employee_id_prefix": "EMP"})

    # 3. Inspect employees and backfill missing employee_code
    user_query = {}
    if target_org_id:
        user_query["organization_id"] = target_org_id

    total_users = UserRepository._collection().count_documents(user_query)
    missing_code_query = dict(user_query)
    missing_code_query["$or"] = [
        {"employee_code": {"$exists": False}},
        {"employee_code": None},
        {"employee_code": ""}
    ]

    users_missing_code = list(UserRepository._collection().find(missing_code_query))
    logger.info(f"Found {len(users_missing_code)} / {total_users} employees without an assigned employee_code.")

    user_summary = {
        "total": total_users,
        "already_had_code": total_users - len(users_missing_code),
        "backfilled": 0,
        "errors": 0
    }

    # Process in batches
    dry_run_counters = {}

    for i in range(0, len(users_missing_code), batch_size):
        batch = users_missing_code[i:i + batch_size]
        for user in batch:
            u_id = user.get("user_id")
            u_email = user.get("email")
            u_org_id = user.get("organization_id")
            default_prefix = org_prefixes.get(u_org_id, "EMP")

            if dry_run:
                if u_org_id not in dry_run_counters:
                    preview = SequenceRepository.preview_next_sequence(
                        organization_id=u_org_id,
                        sequence_type="employee",
                        default_prefix=default_prefix
                    )
                    dry_run_counters[u_org_id] = preview["next_value"]
                simulated_val = dry_run_counters[u_org_id]
                dry_run_counters[u_org_id] += 1
                simulated_code = f"{default_prefix}-{simulated_val:03d}"
                logger.info(f"[DRY RUN] Would assign employee_code '{simulated_code}' to user {u_email} ({u_id}) in org {u_org_id}")
                user_summary["backfilled"] += 1
            else:
                try:
                    seq = SequenceRepository.allocate_next_sequence(
                        organization_id=u_org_id,
                        sequence_type="employee",
                        default_prefix=default_prefix
                    )
                    assigned_code = seq["code"]
                    UserRepository.update_user(u_id, u_org_id, {"employee_code": assigned_code})
                    logger.info(f"Assigned employee_code '{assigned_code}' to user {u_email} ({u_id}) in org {u_org_id}")
                    user_summary["backfilled"] += 1
                except Exception as ex:
                    logger.error(f"Error backfilling user {u_email} ({u_id}): {ex}")
                    user_summary["errors"] += 1

    # 4. Final Report
    logger.info("=" * 60)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Organizations: Total={org_summary['total']} | Custom Prefix={org_summary['custom_prefix']} | Default Prefix={org_summary['default_prefix']}")
    logger.info(f"Employees:     Total={user_summary['total']} | Already Had Code={user_summary['already_had_code']} | Backfilled={user_summary['backfilled']} | Errors={user_summary['errors']}")
    logger.info("=" * 60)
    logger.info("Migration complete.")
    return {"organizations": org_summary, "users": user_summary}


def main():
    parser = argparse.ArgumentParser(description="SenderX Employee Identity Migration")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without modifying database records")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for user processing")
    parser.add_argument("--org-id", type=str, default=None, help="Target specific organization ID")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        run_migration(dry_run=args.dry_run, batch_size=args.batch_size, target_org_id=args.org_id)


if __name__ == "__main__":
    main()
