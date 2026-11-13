"""
SenderX Payload Encryption Migration & Key Rotation Service
Idempotent migration service for encrypting legacy plaintext payloads
and rotating cryptographic keys across MongoDB collections.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from flask import current_app

from app.modules.payloads.encryption import PayloadEncryption, PayloadEncryptionError


class PayloadMigrationService:
    """Service handling bounded-batch encryption migration and key rotation."""

    TARGET_COLLECTIONS = ["ingested_payloads", "dead_letters"]

    @classmethod
    def migrate_legacy_payloads(
        cls,
        batch_size: int = 100,
        dry_run: bool = False,
        collections: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Migrate legacy unencrypted payload documents to authenticated encrypted envelopes.
        Safe, idempotent, bounded, with in-memory roundtrip verification.
        """
        db = current_app.mongo_db
        target_cols = collections or cls.TARGET_COLLECTIONS

        overall_stats = {
            "dry_run": dry_run,
            "total_scanned": 0,
            "migrated": 0,
            "skipped": 0,
            "failed": 0,
            "collections": {}
        }

        for col_name in target_cols:
            col = db[col_name]
            col_stats = {"scanned": 0, "migrated": 0, "skipped": 0, "failed": 0}
            overall_stats["collections"][col_name] = col_stats

            # Find unencrypted documents
            query = {
                "$or": [
                    {"original_payload._encrypted": {"$ne": True}},
                    {"current_payload._encrypted": {"$ne": True}}
                ]
            }

            cursor = col.find(query).limit(batch_size)
            for doc in cursor:
                col_stats["scanned"] += 1
                overall_stats["total_scanned"] += 1

                doc_id = doc.get("payload_id") or doc.get("message_id")
                id_field = "payload_id" if "payload_id" in doc else "message_id"

                orig_payload = doc.get("original_payload")
                curr_payload = doc.get("current_payload")

                orig_is_enc = isinstance(orig_payload, dict) and orig_payload.get("_encrypted") is True
                curr_is_enc = isinstance(curr_payload, dict) and curr_payload.get("_encrypted") is True

                if orig_is_enc and (curr_payload is None or curr_is_enc):
                    col_stats["skipped"] += 1
                    overall_stats["skipped"] += 1
                    continue

                update_fields = {}
                try:
                    # 1. Encrypt original_payload if needed
                    if orig_payload is not None and not orig_is_enc:
                        enc_orig = PayloadEncryption.encrypt_dict(orig_payload)
                        # In-memory verification
                        verified_orig = PayloadEncryption.decrypt_dict(enc_orig)
                        if verified_orig != orig_payload:
                            raise PayloadEncryptionError(f"Verification mismatch for original_payload in {doc_id}")
                        update_fields["original_payload"] = enc_orig

                    # 2. Encrypt current_payload if needed
                    if curr_payload is not None and not curr_is_enc:
                        enc_curr = PayloadEncryption.encrypt_dict(curr_payload)
                        verified_curr = PayloadEncryption.decrypt_dict(enc_curr)
                        if verified_curr != curr_payload:
                            raise PayloadEncryptionError(f"Verification mismatch for current_payload in {doc_id}")
                        update_fields["current_payload"] = enc_curr

                    if not update_fields:
                        col_stats["skipped"] += 1
                        overall_stats["skipped"] += 1
                        continue

                    # 3. Persist update if not dry-run
                    if not dry_run:
                        now = datetime.now(timezone.utc).isoformat()
                        update_fields["migrated_at"] = now
                        res = col.update_one(
                            {id_field: doc_id},
                            {"$set": update_fields}
                        )
                        if res.modified_count == 0:
                            col_stats["skipped"] += 1
                            overall_stats["skipped"] += 1
                            continue

                    col_stats["migrated"] += 1
                    overall_stats["migrated"] += 1

                except Exception as exc:
                    current_app.logger.error(f"Migration error for {col_name} doc {doc_id}: {exc}")
                    col_stats["failed"] += 1
                    overall_stats["failed"] += 1

        return overall_stats

    @classmethod
    def rotate_payload_keys(
        cls,
        batch_size: int = 100,
        dry_run: bool = False,
        collections: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Re-encrypt records encrypted with older keys under the current primary key.
        """
        db = current_app.mongo_db
        target_cols = collections or cls.TARGET_COLLECTIONS
        _, _, current_version = PayloadEncryption._get_fernet_instances()

        overall_stats = {
            "dry_run": dry_run,
            "target_key_version": current_version,
            "total_scanned": 0,
            "rotated": 0,
            "skipped": 0,
            "failed": 0,
            "collections": {}
        }

        for col_name in target_cols:
            col = db[col_name]
            col_stats = {"scanned": 0, "rotated": 0, "skipped": 0, "failed": 0}
            overall_stats["collections"][col_name] = col_stats

            # Find encrypted records with key_version != current_version or missing key_version
            query = {
                "original_payload._encrypted": True,
                "original_payload.key_version": {"$ne": current_version}
            }

            cursor = col.find(query).limit(batch_size)
            for doc in cursor:
                col_stats["scanned"] += 1
                overall_stats["total_scanned"] += 1

                doc_id = doc.get("payload_id") or doc.get("message_id")
                id_field = "payload_id" if "payload_id" in doc else "message_id"

                orig_envelope = doc.get("original_payload")
                curr_envelope = doc.get("current_payload")

                update_fields = {}
                try:
                    new_orig, rotated_orig = PayloadEncryption.reencrypt_envelope(orig_envelope)
                    if rotated_orig:
                        update_fields["original_payload"] = new_orig

                    if curr_envelope and curr_envelope.get("_encrypted"):
                        new_curr, rotated_curr = PayloadEncryption.reencrypt_envelope(curr_envelope)
                        if rotated_curr:
                            update_fields["current_payload"] = new_curr

                    if not update_fields:
                        col_stats["skipped"] += 1
                        overall_stats["skipped"] += 1
                        continue

                    if not dry_run:
                        now = datetime.now(timezone.utc).isoformat()
                        update_fields["keys_rotated_at"] = now
                        col.update_one({id_field: doc_id}, {"$set": update_fields})

                    col_stats["rotated"] += 1
                    overall_stats["rotated"] += 1

                except Exception as exc:
                    current_app.logger.error(f"Rotation error for {col_name} doc {doc_id}: {exc}")
                    col_stats["failed"] += 1
                    overall_stats["failed"] += 1

        return overall_stats
