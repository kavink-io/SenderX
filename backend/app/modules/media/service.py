"""
SenderX Centralized Media Service
Implements:
- File ingestion, validation, and storage routing
- SHA-256 cryptographic digest calculation
- File signature magic byte verification
- Filename sanitization & path traversal prevention
- Single and bulk multipart upload handling
- Secure download dispatch (streaming or S3 pre-signed URL)
- Tenant ownership & organization validation
- Channel-specific media resolution & constraint validation (Email, WhatsApp, SMS/MMS, Teams)
- Audit logging
- Safe cleanup of expired and orphaned files
"""

import base64
from datetime import datetime, timezone, timedelta
import hashlib
import io
import os
from typing import Any, BinaryIO, Dict, List, Optional, Union
import uuid

from flask import current_app, has_app_context

from app.modules.media.models import MediaMetadataModel
from app.modules.media.repository import MediaRepository
from app.modules.media.storage import (
    BaseStorage,
    get_storage_backend,
    StorageError,
    StorageNotFoundError,
    StorageSecurityError,
)
from app.modules.media.validators import (
    check_channel_compatibility,
    detect_file_signature,
    get_malware_scanner,
    sanitize_filename,
    validate_file_size,
    validate_media_for_channel,
    validate_request_size,
    verify_file_signature,
    SUPPORTED_MEDIA_TYPES,
)


class MediaService:

    @classmethod
    def _get_storage(cls) -> BaseStorage:
        return get_storage_backend()

    @classmethod
    def upload_file(
        cls,
        file_obj: Any,
        organization_id: str,
        user_id: Optional[str] = None,
        purpose: Optional[str] = None,
        channel: Optional[str] = None,
        expires_in_seconds: Optional[int] = None,
        expires_in_days: Optional[int] = None,
        custom_filename: Optional[str] = None,
        application_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest, validate, store, and record metadata for a single uploaded media file.
        Strictly enforces tenant isolation, magic bytes validation, and size constraints.
        """
        if not organization_id or not isinstance(organization_id, str):
            return {"success": False, "message": "organization_id is required", "status_code": 400}

        # 1. Extract raw filename and binary content
        original_filename = ""
        declared_mime = None

        if hasattr(file_obj, "filename"):
            original_filename = file_obj.filename or ""
            declared_mime = getattr(file_obj, "content_type", None)
            raw_bytes = file_obj.read()
        elif hasattr(file_obj, "read"):
            raw_bytes = file_obj.read()
            original_filename = custom_filename or "uploaded_file"
        elif isinstance(file_obj, bytes):
            raw_bytes = file_obj
            original_filename = custom_filename or "uploaded_file"
        else:
            return {"success": False, "message": "Invalid file payload. Must be a file stream or bytes.", "status_code": 400}

        if not original_filename:
            original_filename = custom_filename or "uploaded_file"

        size_bytes = len(raw_bytes)

        # 2. Enforce file size limit
        max_file_size = (
            current_app.config.get("MEDIA_MAX_FILE_SIZE_BYTES")
            if has_app_context() else 50 * 1024 * 1024
        )
        is_valid_size, size_err = validate_file_size(size_bytes, max_file_size)
        if not is_valid_size:
            return {"success": False, "message": size_err, "status_code": 400}

        # 3. Sanitize filename
        safe_filename = sanitize_filename(custom_filename or original_filename)
        _, ext = os.path.splitext(safe_filename)
        if not ext and original_filename:
            _, orig_ext = os.path.splitext(original_filename)
            ext = orig_ext.lower()
            safe_filename = f"{safe_filename}{ext}"

        # 4. Verify magic byte file signature
        header = raw_bytes[:4096]
        is_sig_valid, sig_msg, detected_mime = verify_file_signature(
            header_bytes=header,
            declared_mime=declared_mime,
            filename=safe_filename
        )
        if not is_sig_valid:
            if has_app_context():
                current_app.logger.warning(
                    "File signature validation failed for '%s' (org: %s): %s",
                    original_filename, organization_id, sig_msg
                )
            return {
                "success": False,
                "message": sig_msg,
                "status_code": 400,
                "detected_mime": detected_mime
            }

        canonical_mime = detected_mime or declared_mime or "application/octet-stream"

        # 5. Compute SHA-256 cryptographic checksum
        checksum_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # 6. Malware scanning interface
        scanner = get_malware_scanner(current_app.config if has_app_context() else None)
        scan_result = scanner.scan(raw_bytes, filename=safe_filename)
        if not scan_result.is_clean:
            if has_app_context():
                current_app.logger.error(
                    "Malware detected in uploaded file '%s' (org: %s): %s",
                    safe_filename, organization_id, scan_result.details
                )
            return {
                "success": False,
                "message": f"Malware scan failed: {scan_result.details}",
                "status_code": 400,
                "scan_status": scan_result.scan_status
            }

        # 7. Check channel compatibility
        channel_compat = check_channel_compatibility(canonical_mime, size_bytes)
        if channel:
            chan_key = channel.lower().strip()
            temp_record = {"mime_type": canonical_mime, "size_bytes": size_bytes, "filename": safe_filename}
            chan_valid, chan_err = validate_media_for_channel(temp_record, chan_key)
            if not chan_valid:
                return {
                    "success": False,
                    "message": f"Media violates channel restrictions for '{channel}': {chan_err}",
                    "status_code": 400
                }

        # 8. Compute expiration timestamp if specified
        now = datetime.now(timezone.utc)
        expires_at = None
        if expires_in_seconds is not None and expires_in_seconds > 0:
            expires_at = (now + timedelta(seconds=expires_in_seconds)).isoformat()
        elif expires_in_days is not None and expires_in_days > 0:
            expires_at = (now + timedelta(days=expires_in_days)).isoformat()

        # 9. Generate isolated randomized storage key
        media_id = str(uuid.uuid4())
        year = now.year
        month = f"{now.month:02d}"
        storage_key = f"orgs/{organization_id}/{year}/{month}/{media_id}_{safe_filename}"

        clean_app_id = application_id.strip() if isinstance(application_id, str) and application_id.strip() else None

        # 10. Persist binary to storage backend
        try:
            storage = cls._get_storage()
            storage_metadata = {
                "organization_id": organization_id,
                "media_id": media_id,
                "original_filename": original_filename
            }
            if clean_app_id:
                storage_metadata["application_id"] = clean_app_id
            storage_res = storage.save(
                data=raw_bytes,
                storage_key=storage_key,
                content_type=canonical_mime,
                metadata=storage_metadata,
                organization_id=organization_id,
            )
        except StorageError as exc:
            if has_app_context():
                current_app.logger.exception("Storage backend failed during save: %s", exc)
            return {
                "success": False,
                "message": f"Storage engine failed to save media: {exc.message}",
                "status_code": exc.status_code
            }
        except Exception as exc:
            if has_app_context():
                current_app.logger.exception("Unexpected storage error: %s", exc)
            return {
                "success": False,
                "message": f"Failed to persist file in storage: {str(exc)}",
                "status_code": 500
            }

        # 11. Create metadata document in MongoDB
        media_document = {
            "media_id": media_id,
            "organization_id": organization_id,
            "application_id": clean_app_id,
            "filename": safe_filename,
            "original_filename": original_filename,
            "mime_type": canonical_mime,
            "file_extension": ext.lower(),
            "size_bytes": size_bytes,
            "checksum_sha256": checksum_sha256,
            "storage_backend": storage.backend_name,
            "storage_key": storage_key,
            "status": "ACTIVE",
            "scan_status": scan_result.scan_status,
            "scan_details": scan_result.details,
            "purpose": purpose,
            "channel_compatibility": channel_compat,
            "created_at": now.isoformat(),
            "created_by": user_id,
            "expires_at": expires_at,
            "usage_count": 0
        }

        # 11. Create metadata document in MongoDB with safe compensation logic
        try:
            created = MediaRepository.create(media_document)
        except Exception as exc:
            # Safe compensation: remove uploaded physical file to prevent orphaned blob
            try:
                storage.delete(storage_key, organization_id=organization_id)
            except Exception:
                pass
            if has_app_context():
                current_app.logger.exception("Database recording failed; rolled back stored file %s: %s", storage_key, exc)
            return {
                "success": False,
                "message": f"Database recording error: {str(exc)}",
                "status_code": 500
            }

        # 12. Audit log
        if has_app_context():
            current_app.logger.info(
                "Media uploaded: %s (%s, %d bytes, mime: %s) for org: %s by user: %s",
                media_id, safe_filename, size_bytes, canonical_mime, organization_id, user_id
            )

        download_url = f"/api/v1/media/{media_id}/download"

        return {
            "success": True,
            "status_code": 201,
            "message": "Media uploaded successfully",
            "media": created,
            "download_url": download_url
        }

    @classmethod
    def bulk_upload(
        cls,
        files_list: List[Any],
        organization_id: str,
        user_id: Optional[str] = None,
        purpose: Optional[str] = None,
        expires_in_seconds: Optional[int] = None,
        expires_in_days: Optional[int] = None,
        application_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process multiple file uploads with total request size validation and individual error handling.
        """
        if not files_list:
            return {"success": False, "message": "No files provided for upload", "status_code": 400}

        max_req_size = (
            current_app.config.get("MEDIA_MAX_REQUEST_SIZE_BYTES")
            if has_app_context() else 100 * 1024 * 1024
        )

        uploaded = []
        failed = []
        total_bytes = 0

        for file_item in files_list:
            # Check individual size without consuming generator completely
            try:
                if hasattr(file_item, "seek") and hasattr(file_item, "tell"):
                    file_item.seek(0, io.SEEK_END)
                    file_size = file_item.tell()
                    file_item.seek(0, io.SEEK_SET)
                elif hasattr(file_item, "content_length") and file_item.content_length:
                    file_size = file_item.content_length
                elif isinstance(file_item, bytes):
                    file_size = len(file_item)
                else:
                    file_size = 0
                total_bytes += file_size
            except Exception:
                pass

        is_valid_req, req_err = validate_request_size(total_bytes, max_req_size)
        if not is_valid_req:
            return {"success": False, "message": req_err, "status_code": 400}

        for idx, file_item in enumerate(files_list):
            res = cls.upload_file(
                file_obj=file_item,
                organization_id=organization_id,
                user_id=user_id,
                purpose=purpose,
                expires_in_seconds=expires_in_seconds,
                expires_in_days=expires_in_days,
                application_id=application_id
            )
            if res.get("success"):
                uploaded.append(res["media"])
            else:
                fname = getattr(file_item, "filename", f"file_{idx}")
                failed.append({
                    "filename": fname,
                    "error": res.get("message", "Upload failed")
                })

        overall_success = len(uploaded) > 0 or len(failed) == 0

        return {
            "success": overall_success,
            "status_code": 201 if len(failed) == 0 else 207,
            "uploaded": uploaded,
            "failed": failed,
            "total_count": len(files_list),
            "success_count": len(uploaded),
            "failure_count": len(failed)
        }

    @classmethod
    def get_media(
        cls,
        media_id: str,
        organization_id: str,
        allowed_application_ids: Optional[List[str]] = None,
        include_org_shared: bool = False
    ) -> Dict[str, Any]:
        """Retrieve media metadata, enforcing tenant and application isolation."""
        record = MediaRepository.find_by_id(
            media_id,
            organization_id=organization_id,
            allowed_application_ids=allowed_application_ids,
            include_org_shared=include_org_shared
        )
        if not record or record.get("status") == "DELETED":
            return {"success": False, "message": "Media not found", "status_code": 404}
        return {"success": True, "status_code": 200, "data": record}

    @classmethod
    def list_media(
        cls,
        organization_id: str,
        page: int = 1,
        limit: int = 50,
        mime_type: Optional[str] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        search: Optional[str] = None,
        allowed_application_ids: Optional[List[str]] = None,
        include_org_shared: bool = False
    ) -> Dict[str, Any]:
        """List media with pagination, filters, and multi-tenant scoping."""
        return MediaRepository.find_all(
            organization_id=organization_id,
            page=page,
            limit=limit,
            mime_type=mime_type,
            status=status,
            channel=channel,
            search=search,
            allowed_application_ids=allowed_application_ids,
            include_org_shared=include_org_shared
        )

    @classmethod
    def download_media(
        cls,
        media_id: str,
        organization_id: str,
        prefer_signed_url: bool = False,
        allowed_application_ids: Optional[List[str]] = None,
        include_org_shared: bool = False
    ) -> Dict[str, Any]:
        """
        Validate download authorization and prepare binary stream or pre-signed URL.
        """
        record = MediaRepository.find_by_id(
            media_id,
            organization_id=organization_id,
            allowed_application_ids=allowed_application_ids,
            include_org_shared=include_org_shared
        )
        if not record or record.get("status") == "DELETED":
            return {"success": False, "message": "Media not found", "status_code": 404}

        # Security policy: infected files cannot be downloaded
        if record.get("scan_status") == "INFECTED":
            return {
                "success": False,
                "message": "Infected media cannot be downloaded: file failed malware security scan",
                "status_code": 403
            }

        storage_key = record.get("storage_key")
        if not storage_key:
            return {"success": False, "message": "Media storage record is missing", "status_code": 404}

        storage = cls._get_storage()

        # If S3 or client requested signed URL, generate pre-signed link
        if prefer_signed_url or storage.backend_name == "s3":
            try:
                url = storage.generate_signed_url(
                    storage_key=storage_key,
                    expires_in=3600,
                    filename=record.get("filename"),
                    organization_id=organization_id
                )
                if url:
                    return {
                        "success": True,
                        "status_code": 200,
                        "download_mode": "redirect",
                        "url": url,
                        "media": record
                    }
            except Exception as exc:
                if has_app_context():
                    current_app.logger.warning("Could not generate signed URL: %s", exc)

        # Fallback to direct stream (for local storage or direct download)
        try:
            stream = storage.get_stream(storage_key, organization_id=organization_id)
            return {
                "success": True,
                "status_code": 200,
                "download_mode": "stream",
                "stream": stream,
                "filename": record.get("filename", "download"),
                "mime_type": record.get("mime_type", "application/octet-stream"),
                "size_bytes": record.get("size_bytes", 0),
                "media": record
            }
        except StorageNotFoundError:
            return {"success": False, "message": "Storage file not found on disk", "status_code": 404}
        except Exception as exc:
            return {"success": False, "message": f"Storage retrieval error: {str(exc)}", "status_code": 500}

    @classmethod
    def delete_media(
        cls,
        media_id: str,
        organization_id: str,
        allowed_application_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Delete physical file from storage and mark metadata as DELETED.
        """
        record = MediaRepository.find_by_id(
            media_id,
            organization_id=organization_id,
            allowed_application_ids=allowed_application_ids
        )
        if not record or record.get("status") == "DELETED":
            return {"success": False, "message": "Media not found", "status_code": 404}

        storage_key = record.get("storage_key")
        if storage_key:
            try:
                storage = cls._get_storage()
                storage.delete(storage_key, organization_id=organization_id)
            except Exception as exc:
                if has_app_context():
                    current_app.logger.warning("Could not delete physical storage key %s: %s", storage_key, exc)

        MediaRepository.soft_delete(
            media_id,
            organization_id=organization_id,
            allowed_application_ids=allowed_application_ids
        )

        if has_app_context():
            current_app.logger.info("Media deleted: %s for org: %s", media_id, organization_id)

        return {
            "success": True,
            "status_code": 200,
            "message": "Media deleted successfully",
            "media_id": media_id
        }

    @classmethod
    def resolve_media_for_channel(
        cls,
        media_ids: List[str],
        channel: str,
        organization_id: str,
        provider: Optional[str] = None,
        recipient: Optional[str] = None,
        include_bytes: bool = False,
        allowed_application_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Validate, verify channel and provider compatibility, enforce malware policy and expiration,
        and resolve centralized media records for message dispatch.
        """
        if not media_ids:
            return []

        records = MediaRepository.find_by_ids(
            media_ids,
            organization_id=organization_id,
            allowed_application_ids=allowed_application_ids
        )
        found_ids = {r["media_id"] for r in records}
        missing = set(media_ids) - found_ids
        if missing:
            raise ValueError(f"Referenced media IDs not found in organization: {list(missing)}")

        storage = None
        resolved: List[Dict[str, Any]] = []
        total_bytes = 0

        for r in records:
            if r.get("status") != "ACTIVE":
                raise ValueError(f"Media '{r.get('filename')}' ({r['media_id']}) is not active ({r.get('status')})")

            # 1. Enforce file expiration
            exp_iso = r.get("expires_at")
            if exp_iso:
                try:
                    exp_dt = datetime.fromisoformat(exp_iso)
                    if exp_dt <= datetime.now(timezone.utc):
                        raise ValueError(
                            f"Media '{r.get('filename')}' ({r['media_id']}) has expired and cannot be dispatched"
                        )
                except (ValueError, TypeError) as exc:
                    if "has expired" in str(exc):
                        raise

            # 2. Enforce malware scanning policy
            scan_status = r.get("scan_status", "NOT_CONFIGURED")
            if scan_status == "INFECTED":
                raise ValueError(f"Media '{r.get('filename')}' is INFECTED with malware and cannot be dispatched")

            allow_unscanned = (
                current_app.config.get("MEDIA_ALLOW_UNSCANNED_DISPATCH", False)
                if has_app_context() else False
            )
            app_env = (
                current_app.config.get("APP_ENV", "development")
                if has_app_context() else "development"
            )
            if app_env == "production" and scan_status != "CLEAN" and not allow_unscanned:
                raise ValueError(
                    f"Media '{r.get('filename')}' cannot be dispatched in production: file is not verified clean (status: {scan_status})"
                )

            # 3. Validate against channel and provider constraints
            from app.modules.media.validators import validate_provider_media_limits
            is_valid, err_msg = validate_provider_media_limits(
                channel=channel,
                provider=provider,
                media_record=r,
                recipient=recipient
            )
            if not is_valid:
                raise ValueError(f"Media validation error for channel '{channel}': {err_msg}")

            size = int(r.get("size_bytes", 0))
            total_bytes += size

            item: Dict[str, Any] = {
                "media_id": r["media_id"],
                "filename": r.get("filename"),
                "mime_type": r.get("mime_type"),
                "size_bytes": size,
                "storage_key": r.get("storage_key"),
                "checksum_sha256": r.get("checksum_sha256"),
                "scan_status": scan_status
            }

            if include_bytes and r.get("storage_key"):
                if storage is None:
                    storage = cls._get_storage()
                raw_bytes = storage.get_bytes(r["storage_key"], organization_id=organization_id)
                item["raw_bytes"] = raw_bytes
                item["base64_content"] = base64.b64encode(raw_bytes).decode("ascii")

            resolved.append(item)
            # Increment reuse counter
            MediaRepository.increment_usage(r["media_id"], organization_id=organization_id)

        # Enforce Email total attachments size limits
        if channel == "email":
            prov = (provider or "").lower().strip()
            if prov in ("ses", "amazon_ses") and total_bytes > 10 * 1024 * 1024:
                raise ValueError(
                    f"Total email attachments size ({total_bytes} bytes) exceeds Amazon SES maximum limit of 10 MB"
                )
            if total_bytes > 25 * 1024 * 1024:
                raise ValueError(
                    f"Total email attachments size ({total_bytes} bytes) exceeds maximum limit of 25 MB"
                )

        return resolved

    @classmethod
    def cleanup_expired_files(cls, cutoff_iso: Optional[str] = None) -> Dict[str, Any]:
        """
        Purge expired files from storage and mark their status as EXPIRED.
        """
        if not cutoff_iso:
            cutoff_iso = datetime.now(timezone.utc).isoformat()

        expired = MediaRepository.find_expired(cutoff_iso=cutoff_iso)
        storage = cls._get_storage()
        cleaned_ids = []

        for item in expired:
            m_id = item["media_id"]
            s_key = item.get("storage_key")
            org_id = item.get("organization_id")
            if s_key:
                try:
                    storage.delete(s_key, organization_id=org_id)
                except Exception as exc:
                    if has_app_context():
                        current_app.logger.warning("Failed to delete expired storage file %s: %s", s_key, exc)

            MediaRepository.update(
                m_id,
                {
                    "status": "EXPIRED",
                    "storage_key": None,
                    "cleaned_at": datetime.now(timezone.utc).isoformat()
                }
            )
            cleaned_ids.append(m_id)

        return {
            "success": True,
            "expired_count": len(cleaned_ids),
            "cleaned_ids": cleaned_ids
        }

    @classmethod
    def cleanup_orphaned_files(cls, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Reconcile physical storage keys against active database records and delete orphans.
        Strictly limits cleanup to the organization prefix when specified.
        """
        storage = cls._get_storage()
        prefix = f"orgs/{organization_id}/" if organization_id else "orgs/"
        physical_keys = set(storage.list_keys(prefix=prefix))
        scoped_physical_keys = {k for k in physical_keys if k.startswith(prefix)}
        db_keys = MediaRepository.find_all_storage_keys(organization_id=organization_id)

        orphaned = scoped_physical_keys - db_keys
        cleaned_keys = []

        for key in orphaned:
            if not key.startswith(prefix):
                continue
            try:
                storage.delete(key, organization_id=organization_id)
                cleaned_keys.append(key)
            except Exception as exc:
                if has_app_context():
                    current_app.logger.warning("Failed to delete orphan file %s: %s", key, exc)

        return {
            "success": True,
            "orphaned_count": len(cleaned_keys),
            "cleaned_keys": cleaned_keys
        }

        return {
            "success": True,
            "orphaned_count": len(cleaned_keys),
            "cleaned_keys": cleaned_keys
        }
