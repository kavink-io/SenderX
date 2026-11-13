"""
SenderX CLI Tool: Migrate Payload Encryption and Rotate Cryptographic Keys
Usage:
    python backend/scripts/migrate_payload_encryption.py [--batch-size 100] [--dry-run] [--rotate-keys]
"""

import argparse
import json
import os
import sys

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import create_app
from app.modules.payloads.migration import PayloadMigrationService


def main():
    parser = argparse.ArgumentParser(description="SenderX Payload Encryption Migration and Key Rotation CLI")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of records to process per batch")
    parser.add_argument("--dry-run", action="store_true", help="Perform verification without writing changes to DB")
    parser.add_argument("--rotate-keys", action="store_true", help="Rotate encryption keys for already encrypted payloads")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("SenderX Payload Cryptographic Operations Tool")
        print("=" * 60)
        print(f"Batch Size: {args.batch_size}")
        print(f"Dry Run:    {args.dry_run}")
        print(f"Operation:  {'Key Rotation' if args.rotate_keys else 'Legacy Encryption Migration'}")
        print("-" * 60)

        if args.rotate_keys:
            results = PayloadMigrationService.rotate_payload_keys(
                batch_size=args.batch_size,
                dry_run=args.dry_run
            )
        else:
            results = PayloadMigrationService.migrate_legacy_payloads(
                batch_size=args.batch_size,
                dry_run=args.dry_run
            )

        print("\nResults:")
        print(json.dumps(results, indent=2))
        print("=" * 60)

        if results.get("failed", 0) > 0:
            print(f"WARNING: Encountered {results['failed']} failure(s). Review logs.")
            sys.exit(1)
        else:
            print("Operation completed successfully.")
            sys.exit(0)


if __name__ == "__main__":
    main()
