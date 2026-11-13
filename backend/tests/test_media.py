"""
SenderX Phase 4, Task 1: Centralized Media & Attachment Management Test Suite
Comprehensive testing for:
1. Single upload and secure download
2. Multiple / bulk upload
3. Invalid MIME types and unsupported formats
4. File signature magic byte mismatch (spoofing detection)
5. File size and request size limits
6. Filename sanitization
7. Path traversal prevention (local storage & S3)
8. Multi-tenant organization isolation (cross-tenant access denial)
9. Unauthorized downloads (unauthenticated & RBAC permission checks)
10. File deletion (physical and logical)
11. Storage backend failures (no silent fallback from S3 to local)
12. Signed URL generation and verification
13. SHA-256 cryptographic checksum verification
14. Orphan file cleanup
15. Expired file cleanup
16. Provider-specific media validation (Email, WhatsApp, SMS/MMS, Microsoft Teams)
17. Message service integration (media_ids attachment resolution and cross-tenant blocking)
"""

import io
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import bcrypt
import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.modules.media.repository import MediaRepository
from app.modules.media.service import MediaService
from app.modules.media.storage.base_storage import (
    StorageConfigurationError,
    StorageNotFoundError,
    StorageOperationError,
    StorageSecurityError,
)
from app.modules.media.storage.local_storage import LocalStorage
from app.modules.media.storage.s3_storage import S3Storage
from app.modules.media.storage import get_storage_backend
from app.modules.media.validators import (
    check_channel_compatibility,
    detect_file_signature,
    sanitize_filename,
    validate_media_for_channel,
    verify_file_signature,
    NoOpMalwareScanner,
    ClamAVMalwareScanner,
)
from app.modules.messages.service import MessageService
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository


# ---------------------------------------------------------------------------
# TEST FIXTURES & VALID BYTE SEQUENCES
# ---------------------------------------------------------------------------

# Sample genuine magic byte payloads
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00" + b"\x00" * 100
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x00" * 100
VALID_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 50
VALID_PDF_BYTES = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
VALID_MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 100
VALID_MP3_BYTES = b"ID3\x03\x00\x00\x00\x00\x00#" + b"\xff\xfb\x90\x44" + b"\x00" * 100
VALID_TXT_BYTES = b"SenderX Centralized Media Management sample plain text document.\n"
VALID_CSV_BYTES = b"id,name,role\n1,Alice,Engineer\n2,Bob,Manager\n"


@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    temp_dir = tempfile.mkdtemp(prefix="senderx_media_test_")
    flask_app.config["MEDIA_LOCAL_STORAGE_DIR"] = temp_dir
    flask_app.config["STORAGE_BACKEND"] = "local"
    flask_app.config["MEDIA_STORAGE_BACKEND"] = "local"
    yield flask_app
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def test_setup(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())

        role_admin_a = str(uuid.uuid4())
        role_readonly_a = str(uuid.uuid4())
        role_admin_b = str(uuid.uuid4())

        user_admin_a = str(uuid.uuid4())
        user_readonly_a = str(uuid.uuid4())
        user_admin_b = str(uuid.uuid4())

        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(12)).decode("utf-8")

        # Org A
        OrganizationRepository.create({
            "organization_id": org_a,
            "name": f"Media Org A {suffix}",
            "slug": f"media-org-a-{suffix}",
            "status": "ACTIVE"
        })

        # Org A Admin Role (Full media permissions)
        RoleRepository.create({
            "role_id": role_admin_a,
            "organization_id": org_a,
            "name": "Media Admin A",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:media:upload",
                "organization:media:read",
                "organization:media:delete",
                "organization:media:manage",
                "organization:messages:create",
                "organization:messages:read"
            ]
        })

        # Org A Read-Only Role
        RoleRepository.create({
            "role_id": role_readonly_a,
            "organization_id": org_a,
            "name": "Media Readonly A",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:media:read"
            ]
        })

        # Org B
        OrganizationRepository.create({
            "organization_id": org_b,
            "name": f"Media Org B {suffix}",
            "slug": f"media-org-b-{suffix}",
            "status": "ACTIVE"
        })

        # Org B Admin Role
        RoleRepository.create({
            "role_id": role_admin_b,
            "organization_id": org_b,
            "name": "Media Admin B",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:media:upload",
                "organization:media:read",
                "organization:media:delete",
                "organization:media:manage",
                "organization:messages:create",
                "organization:messages:read"
            ]
        })

        # Users
        UserRepository.create({
            "user_id": user_admin_a,
            "organization_id": org_a,
            "email": f"admin-a-{suffix}@example.com",
            "name": "Admin Org A",
            "password_hash": password_hash,
            "role_ids": [role_admin_a],
            "is_active": True
        })

        UserRepository.create({
            "user_id": user_readonly_a,
            "organization_id": org_a,
            "email": f"readonly-a-{suffix}@example.com",
            "name": "Readonly Org A",
            "password_hash": password_hash,
            "role_ids": [role_readonly_a],
            "is_active": True
        })

        UserRepository.create({
            "user_id": user_admin_b,
            "organization_id": org_b,
            "email": f"admin-b-{suffix}@example.com",
            "name": "Admin Org B",
            "password_hash": password_hash,
            "role_ids": [role_admin_b],
            "is_active": True
        })

        token_a_admin = create_access_token(
            identity=user_admin_a,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a}
        )
        token_a_readonly = create_access_token(
            identity=user_readonly_a,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_a}
        )
        token_b_admin = create_access_token(
            identity=user_admin_b,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_b}
        )

        return {
            "org_a": org_a,
            "org_b": org_b,
            "user_admin_a": user_admin_a,
            "user_readonly_a": user_readonly_a,
            "user_admin_b": user_admin_b,
            "token_a_admin": token_a_admin,
            "token_a_readonly": token_a_readonly,
            "token_b_admin": token_b_admin
        }


# ---------------------------------------------------------------------------
# 1. SINGLE UPLOAD & SECURE DOWNLOAD
# ---------------------------------------------------------------------------

def test_media_single_upload_and_download(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_a_admin']}"}
    data = {
        "file": (io.BytesIO(VALID_PDF_BYTES), "sample_report.pdf"),
        "purpose": "monthly_statement"
    }

    # Upload
    resp = client.post("/api/v1/media/upload", headers=headers, data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    media = body["media"]
    assert media["organization_id"] == test_setup["org_a"]
    assert media["filename"] == "sample_report.pdf"
    assert media["mime_type"] == "application/pdf"
    assert media["status"] == "ACTIVE"
    assert media["scan_status"] == "NOT_CONFIGURED"  # No real scanner configured
    assert media["size_bytes"] == len(VALID_PDF_BYTES)
    media_id = media["media_id"]

    # Get Metadata
    get_resp = client.get(f"/api/v1/media/{media_id}", headers=headers)
    assert get_resp.status_code == 200
    meta = get_resp.get_json()["data"]
    assert meta["media_id"] == media_id
    assert meta["checksum_sha256"] is not None

    # Download
    dl_resp = client.get(f"/api/v1/media/{media_id}/download", headers=headers)
    assert dl_resp.status_code == 200
    assert dl_resp.data == VALID_PDF_BYTES
    assert "attachment" in dl_resp.headers.get("Content-Disposition", "")
    assert dl_resp.headers.get("X-Content-Type-Options") == "nosniff"


# ---------------------------------------------------------------------------
# 2. BULK / MULTIPLE UPLOADS
# ---------------------------------------------------------------------------

def test_media_bulk_upload(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_a_admin']}"}
    data = {
        "files": [
            (io.BytesIO(VALID_PNG_BYTES), "image_1.png"),
            (io.BytesIO(VALID_TXT_BYTES), "notes.txt"),
            (io.BytesIO(VALID_CSV_BYTES), "data.csv")
        ],
        "purpose": "bulk_batch"
    }

    resp = client.post("/api/v1/media/bulk-upload", headers=headers, data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    assert body["total_count"] == 3
    assert body["success_count"] == 3
    assert body["failure_count"] == 0
    assert len(body["uploaded"]) == 3

    # Check listing includes these files
    list_resp = client.get("/api/v1/media?limit=10", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.get_json()["data"]
    filenames = [i["filename"] for i in items]
    assert "image_1.png" in filenames
    assert "notes.txt" in filenames
    assert "data.csv" in filenames


# ---------------------------------------------------------------------------
# 3. INVALID MIME TYPE & EXECUTABLE DETECTION
# ---------------------------------------------------------------------------

def test_media_invalid_mime_type_rejected(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_a_admin']}"}

    # Upload Windows Executable (MZ) disguised as document
    evil_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 50
    data = {
        "file": (io.BytesIO(evil_exe), "program.exe")
    }

    resp = client.post("/api/v1/media/upload", headers=headers, data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "Dangerous executable" in body["message"] or "unsupported" in body["message"].lower()


# ---------------------------------------------------------------------------
# 4. FILE SIGNATURE MISMATCH (SPOOFING PREVENTION)
# ---------------------------------------------------------------------------

def test_media_file_signature_mismatch(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_a_admin']}"}

    # Declared as .png, but actual content is PDF magic bytes
    spoofed_data = {
        "file": (io.BytesIO(VALID_PDF_BYTES), "fake_photo.png")
    }

    resp = client.post("/api/v1/media/upload", headers=headers, data=spoofed_data, content_type="multipart/form-data")
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert "extension" in body["message"].lower() or "signature mismatch" in body["message"].lower()


# ---------------------------------------------------------------------------
# 5. FILE SIZE LIMITS
# ---------------------------------------------------------------------------

def test_media_file_size_limits(client, test_setup, app):
    headers = {"Authorization": f"Bearer {test_setup['token_a_admin']}"}

    # Temporarily set max file size to 500 bytes
    orig_limit = app.config.get("MEDIA_MAX_FILE_SIZE_BYTES")
    app.config["MEDIA_MAX_FILE_SIZE_BYTES"] = 500

    try:
        large_bytes = VALID_JPEG_BYTES + b"\x00" * 1000  # > 1000 bytes
        data = {
            "file": (io.BytesIO(large_bytes), "large_image.jpg")
        }

        resp = client.post("/api/v1/media/upload", headers=headers, data=data, content_type="multipart/form-data")
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["success"] is False
        assert "exceeds maximum limit" in body["message"]
    finally:
        app.config["MEDIA_MAX_FILE_SIZE_BYTES"] = orig_limit


# ---------------------------------------------------------------------------
# 6. FILENAME SANITIZATION
# ---------------------------------------------------------------------------

def test_media_filename_sanitization(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_a_admin']}"}

    # Dirty filename with path characters, spaces, and special symbols
    dirty_name = "../../../my secret $photo! #1.jpg"
    data = {
        "file": (io.BytesIO(VALID_JPEG_BYTES), dirty_name)
    }

    resp = client.post("/api/v1/media/upload", headers=headers, data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    media = resp.get_json()["media"]
    sanitized = media["filename"]

    # Verify no path traversal components and only clean characters
    assert ".." not in sanitized
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert "$" not in sanitized
    assert "!" not in sanitized
    assert sanitized.endswith(".jpg")


# ---------------------------------------------------------------------------
# 7. PATH TRAVERSAL PREVENTION IN STORAGE BACKEND
# ---------------------------------------------------------------------------

def test_media_path_traversal_storage_backend(app):
    base_dir = app.config["MEDIA_LOCAL_STORAGE_DIR"]
    storage = LocalStorage(base_dir=base_dir)

    # Traversal using ..
    with pytest.raises(StorageSecurityError):
        storage._resolve_safe_path("../../../etc/passwd")

    with pytest.raises(StorageSecurityError):
        storage._resolve_safe_path("..\\..\\windows\\system32")

    # Traversal using null bytes
    with pytest.raises(StorageSecurityError):
        storage._resolve_safe_path("orgs/org-123/\x00secret.txt")


# ---------------------------------------------------------------------------
# 8. MULTI-TENANT ORGANIZATION ISOLATION
# ---------------------------------------------------------------------------

def test_media_organization_isolation(client, test_setup):
    headers_a = {"Authorization": f"Bearer {test_setup['token_a_admin']}"}
    headers_b = {"Authorization": f"Bearer {test_setup['token_b_admin']}"}

    # Org A uploads file
    data = {"file": (io.BytesIO(VALID_PDF_BYTES), "org_a_confidential.pdf")}
    resp_a = client.post("/api/v1/media/upload", headers=headers_a, data=data, content_type="multipart/form-data")
    assert resp_a.status_code == 201
    media_id_a = resp_a.get_json()["media"]["media_id"]

    # Org B tries to retrieve metadata -> 404
    resp_get_b = client.get(f"/api/v1/media/{media_id_a}", headers=headers_b)
    assert resp_get_b.status_code == 404

    # Org B tries to download Org A file -> 404
    resp_dl_b = client.get(f"/api/v1/media/{media_id_a}/download", headers=headers_b)
    assert resp_dl_b.status_code == 404

    # Org B tries to delete Org A file -> 404
    resp_del_b = client.delete(f"/api/v1/media/{media_id_a}", headers=headers_b)
    assert resp_del_b.status_code == 404

    # Org B listing does not contain Org A file
    list_b = client.get("/api/v1/media", headers=headers_b).get_json()["data"]
    assert all(item["media_id"] != media_id_a for item in list_b)


# ---------------------------------------------------------------------------
# 9. UNAUTHORIZED ACCESS & RBAC CHECKS
# ---------------------------------------------------------------------------

def test_media_unauthorized_access(client, test_setup):
    # 1. Unauthenticated request -> 401
    resp = client.get("/api/v1/media")
    assert resp.status_code == 401

    # 2. Read-only user trying to upload -> 403
    headers_readonly = {"Authorization": f"Bearer {test_setup['token_a_readonly']}"}
    data = {"file": (io.BytesIO(VALID_PNG_BYTES), "test.png")}
    resp_upload = client.post("/api/v1/media/upload", headers=headers_readonly, data=data, content_type="multipart/form-data")
    assert resp_upload.status_code == 403

    # 3. Read-only user trying to delete -> 403
    resp_del = client.delete("/api/v1/media/some-id", headers=headers_readonly)
    assert resp_del.status_code == 403


# ---------------------------------------------------------------------------
# 10. FILE DELETION (LOGICAL & PHYSICAL)
# ---------------------------------------------------------------------------

def test_media_file_deletion(client, test_setup, app):
    headers = {"Authorization": f"Bearer {test_setup['token_a_admin']}"}

    # Upload
    data = {"file": (io.BytesIO(VALID_JPEG_BYTES), "to_delete.jpg")}
    resp = client.post("/api/v1/media/upload", headers=headers, data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    media = resp.get_json()["media"]
    media_id = media["media_id"]
    storage_key = media["storage_key"]

    storage = get_storage_backend(app.config)
    assert storage.exists(storage_key) is True

    # Delete
    del_resp = client.delete(f"/api/v1/media/{media_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.get_json()["success"] is True

    # Verify physical file removed
    assert storage.exists(storage_key) is False

    # Verify retrieval returns 404
    get_resp = client.get(f"/api/v1/media/{media_id}", headers=headers)
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# 11. STORAGE BACKEND FAILURES & NO SILENT FALLBACK
# ---------------------------------------------------------------------------

def test_storage_backend_no_silent_fallback():
    # If S3 configured but AWS_S3_BUCKET is missing, MUST raise StorageConfigurationError
    bad_config = {
        "STORAGE_BACKEND": "s3",
        "AWS_S3_BUCKET": ""
    }
    with pytest.raises(StorageConfigurationError) as exc_info:
        get_storage_backend(bad_config)
    assert "forbidden" in str(exc_info.value).lower() or "missing" in str(exc_info.value).lower()


def test_storage_operation_failure_handling(app, monkeypatch):
    with app.app_context():
        # Mock storage.save to simulate disk write failure
        mock_storage = MagicMock()
        mock_storage.save.side_effect = StorageOperationError("Disk I/O failure")
        mock_storage.backend_name = "mock"

        monkeypatch.setattr(MediaService, "_get_storage", classmethod(lambda cls: mock_storage))

        res = MediaService.upload_file(
            file_obj=VALID_PDF_BYTES,
            organization_id=str(uuid.uuid4()),
            custom_filename="fail.pdf"
        )
        assert res["success"] is False
        assert "Storage engine failed" in res["message"]


# ---------------------------------------------------------------------------
# 12. SIGNED URL GENERATION & VERIFICATION
# ---------------------------------------------------------------------------

def test_signed_url_generation_and_verification(app):
    base_dir = app.config["MEDIA_LOCAL_STORAGE_DIR"]
    storage = LocalStorage(base_dir=base_dir, signing_secret="secret-key-123")

    key = "orgs/org-123/2026/11/doc.pdf"
    signed_url = storage.generate_signed_url(key, expires_in=10, filename="doc.pdf")
    assert "/api/v1/media/download-signed" in signed_url
    assert "key=" in signed_url
    assert "sig=" in signed_url

    # Verify valid signature
    import urllib.parse
    parsed = urllib.parse.urlparse(signed_url)
    params = urllib.parse.parse_qs(parsed.query)
    exp = int(params["exp"][0])
    sig = params["sig"][0]

    assert storage.verify_signed_url(key, exp=exp, sig=sig, filename="doc.pdf") is True

    # Tampered key should fail
    assert storage.verify_signed_url("orgs/other/doc.pdf", exp=exp, sig=sig, filename="doc.pdf") is False

    # Expired token should fail
    past_exp = int(time.time()) - 100
    assert storage.verify_signed_url(key, exp=past_exp, sig=sig, filename="doc.pdf") is False


# ---------------------------------------------------------------------------
# 13. SHA-256 CHECKSUM VERIFICATION
# ---------------------------------------------------------------------------

def test_checksum_sha256_verification(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['token_a_admin']}"}
    import hashlib
    expected_hash = hashlib.sha256(VALID_PDF_BYTES).hexdigest()

    data = {"file": (io.BytesIO(VALID_PDF_BYTES), "checksum_test.pdf")}
    resp = client.post("/api/v1/media/upload", headers=headers, data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    media = resp.get_json()["media"]
    assert media["checksum_sha256"] == expected_hash


# ---------------------------------------------------------------------------
# 14. ORPHAN FILE CLEANUP
# ---------------------------------------------------------------------------

def test_orphan_file_cleanup(app, test_setup):
    with app.app_context():
        storage = get_storage_backend(app.config)
        org_id = test_setup["org_a"]

        # Create an orphan file on disk with no MongoDB record
        orphan_key = f"orgs/{org_id}/2026/11/orphan_{uuid.uuid4().hex}.pdf"
        storage.save(VALID_PDF_BYTES, orphan_key)
        assert storage.exists(orphan_key) is True

        # Run orphan cleanup
        res = MediaService.cleanup_orphaned_files(organization_id=org_id)
        assert res["success"] is True
        assert res["orphaned_count"] >= 1
        assert orphan_key in res["cleaned_keys"]
        assert storage.exists(orphan_key) is False


# ---------------------------------------------------------------------------
# 15. EXPIRED FILE CLEANUP
# ---------------------------------------------------------------------------

def test_expired_file_cleanup(app, test_setup):
    with app.app_context():
        # Upload file with expires_in_seconds=1
        res = MediaService.upload_file(
            file_obj=VALID_PDF_BYTES,
            organization_id=test_setup["org_a"],
            custom_filename="expiring.pdf",
            expires_in_seconds=1
        )
        assert res["success"] is True
        media_id = res["media"]["media_id"]
        storage_key = res["media"]["storage_key"]
        storage = get_storage_backend(app.config)
        assert storage.exists(storage_key) is True

        # Wait 1.1s for expiration
        time.sleep(1.1)

        # Run cleanup
        cleanup_res = MediaService.cleanup_expired_files()
        assert cleanup_res["success"] is True
        assert media_id in cleanup_res["cleaned_ids"]

        # Storage file deleted and status set to EXPIRED
        assert storage.exists(storage_key) is False
        rec = MediaRepository.find_by_id(media_id, organization_id=test_setup["org_a"])
        assert rec["status"] == "EXPIRED"


# ---------------------------------------------------------------------------
# 16. PROVIDER-SPECIFIC MEDIA VALIDATION
# ---------------------------------------------------------------------------

def test_provider_specific_media_validation():
    # Email size limits: single max 10MB
    valid_email_media = {"mime_type": "image/jpeg", "size_bytes": 8 * 1024 * 1024, "filename": "photo.jpg"}
    is_v, _ = validate_media_for_channel(valid_email_media, "email")
    assert is_v is True

    oversized_email_media = {"mime_type": "image/jpeg", "size_bytes": 12 * 1024 * 1024, "filename": "big.jpg"}
    is_v, err = validate_media_for_channel(oversized_email_media, "email")
    assert is_v is False
    assert "exceeds Email single file limit" in err

    # WhatsApp image limit: 5MB
    valid_wa_img = {"mime_type": "image/jpeg", "size_bytes": 4 * 1024 * 1024, "filename": "wa.jpg"}
    is_v, _ = validate_media_for_channel(valid_wa_img, "whatsapp")
    assert is_v is True

    oversized_wa_img = {"mime_type": "image/jpeg", "size_bytes": 6 * 1024 * 1024, "filename": "wa.jpg"}
    is_v, err = validate_media_for_channel(oversized_wa_img, "whatsapp")
    assert is_v is False
    assert "WhatsApp image" in err

    # SMS/MMS limit: 5MB
    valid_sms_mms = {"mime_type": "image/png", "size_bytes": 2 * 1024 * 1024, "filename": "mms.png"}
    is_v, _ = validate_media_for_channel(valid_sms_mms, "sms")
    assert is_v is True

    oversized_sms_mms = {"mime_type": "image/png", "size_bytes": 6 * 1024 * 1024, "filename": "big.png"}
    is_v, err = validate_media_for_channel(oversized_sms_mms, "sms")
    assert is_v is False
    assert "exceeds MMS limit" in err

    # Teams: 250MB limit
    valid_teams = {"mime_type": "application/pdf", "size_bytes": 50 * 1024 * 1024, "filename": "teams.pdf"}
    is_v, _ = validate_media_for_channel(valid_teams, "microsoft_teams")
    assert is_v is True

    oversized_teams = {"mime_type": "application/pdf", "size_bytes": 260 * 1024 * 1024, "filename": "teams.pdf"}
    is_v, err = validate_media_for_channel(oversized_teams, "microsoft_teams")
    assert is_v is False
    assert "exceeds 250 MB" in err


# ---------------------------------------------------------------------------
# 17. MESSAGE ENGINE INTEGRATION WITH CENTRALIZED MEDIA
# ---------------------------------------------------------------------------

def test_message_service_media_resolution_and_cross_tenant_block(app, test_setup):
    with app.app_context():
        # Org A uploads invoice
        res = MediaService.upload_file(
            file_obj=VALID_PDF_BYTES,
            organization_id=test_setup["org_a"],
            custom_filename="invoice_101.pdf"
        )
        assert res["success"] is True
        media_id_a = res["media"]["media_id"]

        # Org A sends email referencing media_id
        email_payload = {
            "channel": "email",
            "recipient": "customer@example.com",
            "provider": "mock",
            "data": {
                "subject": "Your Invoice",
                "body": "Please find attached your invoice.",
                "media_ids": [media_id_a]
            }
        }

        msg_res = MessageService.create_message(email_payload, organization_id=test_setup["org_a"])
        assert msg_res["success"] is True
        message = msg_res["message"]
        attachments = message["data"].get("attachments", [])
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "invoice_101.pdf"
        assert attachments[0]["mime_type"] == "application/pdf"
        assert attachments[0]["media_id"] == media_id_a
        assert "content" in attachments[0]  # Base64 hydrated

        # Org B attempts to hijack Org A's media_id in a message dispatch -> BLOCKED
        hijack_payload = {
            "channel": "email",
            "recipient": "other@example.com",
            "provider": "mock",
            "data": {
                "subject": "Phishing Attempt",
                "body": "Stealing Org A document.",
                "media_ids": [media_id_a]
            }
        }

        hijack_res = MessageService.create_message(hijack_payload, organization_id=test_setup["org_b"])
        assert hijack_res["success"] is False
        assert "not found in organization" in hijack_res["message"]


# ---------------------------------------------------------------------------
# 18. WHATSAPP META MEDIA UPLOAD & RETURNED MEDIA ID
# ---------------------------------------------------------------------------

def test_whatsapp_meta_media_upload_and_returned_id():
    from app.adapters.whatsapp.cloud_adapter import WhatsAppCloudAdapter
    from unittest.mock import MagicMock
    import requests

    mock_session = MagicMock(spec=requests.Session)

    # 1. Media upload response
    upload_resp = MagicMock()
    upload_resp.status_code = 200
    upload_resp.json.return_value = {"id": "meta_wa_media_987654"}
    upload_resp.text = '{"id": "meta_wa_media_987654"}'

    # 2. Message send response
    msg_resp = MagicMock()
    msg_resp.status_code = 200
    msg_resp.json.return_value = {"messages": [{"id": "wamid.HBgL12345"}]}
    msg_resp.text = '{"messages": [{"id": "wamid.HBgL12345"}]}'

    # Route POST calls: upload vs message dispatch
    def mock_post(url, **kwargs):
        if url.endswith("/media"):
            return upload_resp
        return msg_resp

    mock_session.post.side_effect = mock_post

    adapter = WhatsAppCloudAdapter(
        access_token="EAABtesttoken",
        phone_number_id="10987654321",
        session=mock_session
    )

    message = {
        "channel": "whatsapp",
        "recipient": "+14155552671",
        "data": {
            "type": "image",
            "caption": "Photo from SenderX",
            "resolved_media": [
                {
                    "media_id": str(uuid.uuid4()),  # SenderX UUID
                    "filename": "photo.jpg",
                    "mime_type": "image/jpeg",
                    "raw_bytes": VALID_JPEG_BYTES
                }
            ]
        }
    }

    res = adapter.send(message)
    assert res["success"] is True
    assert res["provider_message_id"] == "wamid.HBgL12345"

    # Verify upload was called with file bytes
    assert mock_session.post.call_count == 2
    upload_call = mock_session.post.call_args_list[0]
    assert upload_call[0][0] == "https://graph.facebook.com/v21.0/10987654321/media"

    # Verify message payload sent to Meta has Meta media ID, not SenderX UUID
    msg_call = mock_session.post.call_args_list[1]
    msg_payload = msg_call[1]["json"]
    assert msg_payload["image"]["id"] == "meta_wa_media_987654"
    assert msg_payload["image"]["caption"] == "Photo from SenderX"


# ---------------------------------------------------------------------------
# 19. TEAMS SHAREPOINT/ONEDRIVE UPLOAD & REFERENCE ATTACHMENT
# ---------------------------------------------------------------------------

def test_teams_sharepoint_onedrive_upload_and_reference_workflow():
    from app.adapters.teams.teams_adapter import MicrosoftTeamsAdapter
    from unittest.mock import MagicMock
    import requests

    mock_session = MagicMock(spec=requests.Session)
    mock_auth = MagicMock()
    mock_auth.get_access_token.return_value = "eyJvalidGraphToken"

    # 1. Drive PUT upload response
    drive_resp = MagicMock()
    drive_resp.status_code = 201
    drive_resp.json.return_value = {
        "id": "drive_item_abc123",
        "name": "statement.pdf",
        "webUrl": "https://senderx.sharepoint.com/sites/team/statement.pdf"
    }

    # 2. Teams message post response
    msg_resp = MagicMock()
    msg_resp.status_code = 201
    msg_resp.json.return_value = {"id": "1731500000000"}

    def mock_put_or_post(url, **kwargs):
        if "/drive/root:" in url:
            return drive_resp
        return msg_resp

    mock_session.put.side_effect = mock_put_or_post
    mock_session.post.side_effect = mock_put_or_post

    adapter = MicrosoftTeamsAdapter(
        tenant_id=str(uuid.uuid4()),
        client_id=str(uuid.uuid4()),
        client_secret="teamsSecret",
        auth_client=mock_auth,
        session=mock_session
    )

    message = {
        "channel": "microsoft_teams",
        "recipient": "chat:19:meeting_xyz@thread.v2",
        "data": {
            "text": "Monthly Financial Report",
            "media_references": [
                {
                    "media_id": str(uuid.uuid4()),
                    "filename": "statement.pdf",
                    "mime_type": "application/pdf",
                    "raw_bytes": VALID_PDF_BYTES
                }
            ]
        }
    }

    res = adapter.send(message)
    assert res["success"] is True
    assert res["provider_message_id"] == "1731500000000"

    # Verify drive upload was called
    assert mock_session.put.call_count == 1
    put_call = mock_session.put.call_args_list[0]
    assert "/me/drive/root:/statement.pdf:/content" in put_call[0][0]

    # Verify Teams message received completed reference attachment
    assert mock_session.post.call_count == 1
    post_payload = mock_session.post.call_args[1]["json"]
    attachments = post_payload.get("attachments", [])
    assert len(attachments) == 1
    assert attachments[0]["contentType"] == "reference"
    assert attachments[0]["contentUrl"] == "https://senderx.sharepoint.com/sites/team/statement.pdf"
    assert attachments[0]["name"] == "statement.pdf"


# ---------------------------------------------------------------------------
# 20. TWILIO MMS DESTINATION & MEDIA URL VALIDATION
# ---------------------------------------------------------------------------

def test_twilio_mms_us_ca_validation_and_url_checks():
    from app.adapters.sms.twilio_adapter import TwilioSMSAdapter
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.sid = "SM1234567890abcdef"
    mock_msg.status = "queued"
    mock_msg.num_segments = "1"
    mock_client.messages.create.return_value = mock_msg

    adapter = TwilioSMSAdapter(
        account_sid="AC" + "1" * 32,
        auth_token="token" * 6,
        from_number="+15005550006",
        client=mock_client
    )

    # 1. Valid US/Canada destination with valid HTTPS media URL -> SUCCESS
    valid_mms = {
        "channel": "sms",
        "recipient": "+14155552671",
        "data": {
            "text": "Check out this image",
            "media_urls": ["https://senderx.io/public/flyer.png"]
        }
    }
    res = adapter.send(valid_mms)
    assert res["success"] is True
    assert res["provider_message_id"] == "SM1234567890abcdef"
    mock_client.messages.create.assert_called_with(
        to="+14155552671",
        body="Check out this image",
        from_="+15005550006",
        media_url=["https://senderx.io/public/flyer.png"]
    )

    # 2. Non-US/Canada destination (+44 UK) with media -> REJECTED
    invalid_dest_mms = {
        "channel": "sms",
        "recipient": "+447911123456",
        "data": {
            "text": "MMS to UK",
            "media_urls": ["https://senderx.io/public/flyer.png"]
        }
    }
    with pytest.raises(ValueError) as exc:
        adapter.send(invalid_dest_mms)
    assert "only supported for US and Canada" in str(exc.value)

    # 3. Invalid non-HTTP media URL -> REJECTED
    bad_url_mms = {
        "channel": "sms",
        "recipient": "+14155552671",
        "data": {
            "text": "Bad URL",
            "media_urls": ["ftp://invalid-server/file.png"]
        }
    }
    with pytest.raises(ValueError) as exc:
        adapter.send(bad_url_mms)
    assert "publicly accessible HTTP/HTTPS" in str(exc.value)


# ---------------------------------------------------------------------------
# 21. MALWARE SCANNING CLAMAV STATES & PRODUCTION BLOCKING
# ---------------------------------------------------------------------------

def test_malware_scanning_clamav_states_and_production_block(app, test_setup):
    import socket

    # 1. ClamAV CLEAN state
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.side_effect = [b"stream: OK\n", b""]

        scanner = ClamAVMalwareScanner(host="localhost", port=3310)
        res_clean = scanner.scan(VALID_PDF_BYTES, "doc.pdf")
        assert res_clean.is_clean is True
        assert res_clean.scan_status == "CLEAN"

    # 2. ClamAV INFECTED state
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.side_effect = [b"stream: Eicar-Signature FOUND\n", b""]

        scanner = ClamAVMalwareScanner(host="localhost", port=3310)
        res_infected = scanner.scan(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*", "eicar.com")
        assert res_infected.is_clean is False
        assert res_infected.scan_status == "INFECTED"
        assert res_infected.threat_name == "Eicar-Signature"

    # 3. ClamAV TIMEOUT state
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        mock_sock.recv.side_effect = socket.timeout("Timed out waiting for clamd")

        scanner = ClamAVMalwareScanner(host="localhost", port=3310)
        res_timeout = scanner.scan(VALID_PDF_BYTES, "slow.pdf")
        assert res_timeout.is_clean is False
        assert res_timeout.scan_status == "FAILED"
        assert "timed out" in res_timeout.details.lower()

    # 4. ClamAV SCANNER UNAVAILABLE state
    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value.__enter__.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError("Connection refused")

        scanner = ClamAVMalwareScanner(host="localhost", port=3310)
        res_unavail = scanner.scan(VALID_PDF_BYTES, "doc.pdf")
        assert res_unavail.is_clean is False
        assert res_unavail.scan_status == "FAILED"
        assert "unavailable" in res_unavail.details.lower()

    # 5. Production dispatch block for non-CLEAN files
    with app.app_context():
        # Inject an infected file into database
        org_id = test_setup["org_a"]
        media_id = str(uuid.uuid4())
        MediaRepository.create({
            "media_id": media_id,
            "organization_id": org_id,
            "filename": "infected.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "storage_key": f"orgs/{org_id}/2026/11/{media_id}_infected.pdf",
            "status": "ACTIVE",
            "scan_status": "INFECTED"
        })

        # Must reject dispatch for INFECTED file
        with pytest.raises(ValueError) as exc:
            MediaService.resolve_media_for_channel([media_id], "email", org_id)
        assert "INFECTED with malware" in str(exc.value)

        # Download of INFECTED file must return 403 Forbidden
        dl_res = MediaService.download_media(media_id, org_id)
        assert dl_res["success"] is False
        assert dl_res["status_code"] == 403
        assert "infected" in dl_res["message"].lower()

        # In production, unscanned file cannot be dispatched unless explicitly allowed
        media_unscanned = str(uuid.uuid4())
        MediaRepository.create({
            "media_id": media_unscanned,
            "organization_id": org_id,
            "filename": "unscanned.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "storage_key": f"orgs/{org_id}/2026/11/{media_unscanned}_unscanned.pdf",
            "status": "ACTIVE",
            "scan_status": "NOT_CONFIGURED"
        })

        orig_env = app.config.get("APP_ENV")
        orig_allow = app.config.get("MEDIA_ALLOW_UNSCANNED_DISPATCH")
        app.config["APP_ENV"] = "production"
        app.config["MEDIA_ALLOW_UNSCANNED_DISPATCH"] = False

        try:
            with pytest.raises(ValueError) as exc_prod:
                MediaService.resolve_media_for_channel([media_unscanned], "email", org_id)
            assert "not verified clean" in str(exc_prod.value)
        finally:
            app.config["APP_ENV"] = orig_env
            app.config["MEDIA_ALLOW_UNSCANNED_DISPATCH"] = orig_allow


# ---------------------------------------------------------------------------
# 22. S3 PRODUCTION SECURITY & IAM WORKLOAD IDENTITY
# ---------------------------------------------------------------------------

def test_s3_production_security_fail_closed_and_iam_workload_identity():
    # 1. Production must fail closed if local storage requested
    with pytest.raises(StorageConfigurationError) as exc:
        get_storage_backend({
            "APP_ENV": "production",
            "STORAGE_BACKEND": "local"
        })
    assert "forbidden in production" in str(exc.value)

    # 2. Production must fail closed if S3 bucket missing
    with pytest.raises(StorageConfigurationError) as exc:
        get_storage_backend({
            "APP_ENV": "production",
            "STORAGE_BACKEND": "s3",
            "AWS_S3_BUCKET": ""
        })
    assert "missing" in str(exc.value).lower()

    # 3. IAM Role / Workload Identity: initializes without explicit keys
    with patch("boto3.client") as mock_boto:
        mock_boto.return_value = MagicMock()
        storage = S3Storage(
            bucket_name="production-corp-bucket",
            region_name="us-east-1",
            aws_access_key_id=None,
            aws_secret_access_key=None
        )
        assert storage.backend_name == "s3"
        # Boto3 client was initialized without static credentials
        client_kwargs = mock_boto.call_args[1]
        assert "aws_access_key_id" not in client_kwargs
        assert "aws_secret_access_key" not in client_kwargs

    # 4. Enforces private ACL and AES256 encryption in S3 save
    mock_s3 = MagicMock()
    storage = S3Storage(bucket_name="secure-bucket", s3_client=mock_s3)
    storage.save(VALID_PDF_BYTES, "orgs/org-123/2026/11/doc.pdf", content_type="application/pdf")

    assert mock_s3.upload_fileobj.call_count == 1
    extra_args = mock_s3.upload_fileobj.call_args[1]["ExtraArgs"]
    assert extra_args["ACL"] == "private"
    assert extra_args["ServerSideEncryption"] == "AES256"

    # 5. Pre-signed URL expiration capped at 3600 seconds
    storage.generate_signed_url("orgs/org-123/2026/11/doc.pdf", expires_in=7200)
    presigned_call = mock_s3.generate_presigned_url.call_args[1]
    assert presigned_call["ExpiresIn"] == 3600


# ---------------------------------------------------------------------------
# 23. COMPENSATION LOGIC ON DATABASE FAILURE
# ---------------------------------------------------------------------------

def test_compensation_logic_on_database_failure(app, test_setup):
    with app.app_context():
        org_id = test_setup["org_a"]
        storage = get_storage_backend(app.config)

        # Mock MediaRepository.create to raise an unexpected database exception
        with patch.object(MediaRepository, "create", side_effect=Exception("MongoDB write timeout")):
            res = MediaService.upload_file(
                file_obj=VALID_PDF_BYTES,
                organization_id=org_id,
                custom_filename="compensate.pdf"
            )
            assert res["success"] is False
            assert "Database recording error" in res["message"]

        # Verify no orphaned file left in storage
        orphan_candidates = [k for k in storage.list_keys(f"orgs/{org_id}/") if "compensate.pdf" in k]
        assert len(orphan_candidates) == 0


# ---------------------------------------------------------------------------
# 24. EXPIRED MEDIA DISPATCH REJECTION
# ---------------------------------------------------------------------------

def test_expired_media_dispatch_rejection(app, test_setup):
    with app.app_context():
        org_id = test_setup["org_a"]
        media_id = str(uuid.uuid4())

        # Expired 2 hours ago
        past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        MediaRepository.create({
            "media_id": media_id,
            "organization_id": org_id,
            "filename": "old_contract.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "storage_key": f"orgs/{org_id}/2026/11/{media_id}_old_contract.pdf",
            "status": "ACTIVE",
            "scan_status": "CLEAN",
            "expires_at": past_iso
        })

        with pytest.raises(ValueError) as exc:
            MediaService.resolve_media_for_channel([media_id], "email", org_id)
        assert "has expired and cannot be dispatched" in str(exc.value)


# ---------------------------------------------------------------------------
# 25. CROSS-TENANT STORAGE KEY ISOLATION
# ---------------------------------------------------------------------------

def test_cross_tenant_storage_key_isolation(app):
    base_dir = app.config["MEDIA_LOCAL_STORAGE_DIR"]
    storage = LocalStorage(base_dir=base_dir)

    # Org A tries to access Org B file via storage key
    key_org_b = "orgs/org-b/2026/11/secret.pdf"

    with pytest.raises(StorageSecurityError) as exc:
        storage._resolve_safe_path(key_org_b, organization_id="org-a")
    assert "Cross-tenant storage access violation" in str(exc.value)

    with pytest.raises(StorageSecurityError) as exc_del:
        storage.delete(key_org_b, organization_id="org-a")
    assert "Cross-tenant storage access violation" in str(exc_del.value)


# ---------------------------------------------------------------------------
# 26. PROVIDER-SPECIFIC SIZE RESTRICTIONS
# ---------------------------------------------------------------------------

def test_provider_specific_size_restrictions():
    from app.modules.media.validators import validate_provider_media_limits

    # 1. Amazon SES: max 10MB
    ses_oversized = {"filename": "big.pdf", "mime_type": "application/pdf", "size_bytes": 15 * 1024 * 1024}
    is_v, err = validate_provider_media_limits("email", "ses", ses_oversized)
    assert is_v is False
    assert "Amazon SES" in err and "10 MB" in err

    # 2. SendGrid: allows up to 25MB total
    sendgrid_valid = {"filename": "big.pdf", "mime_type": "application/pdf", "size_bytes": 15 * 1024 * 1024}
    is_v, _ = validate_provider_media_limits("email", "sendgrid", sendgrid_valid)
    assert is_v is True

    # 3. Twilio MMS: requires US/Canada number and <= 5MB
    twilio_valid = {"filename": "pic.jpg", "mime_type": "image/jpeg", "size_bytes": 3 * 1024 * 1024}
    is_v, _ = validate_provider_media_limits("sms", "twilio", twilio_valid, recipient="+14155552671")
    assert is_v is True

    # Twilio MMS: rejects overseas recipient
    is_v, err = validate_provider_media_limits("sms", "twilio", twilio_valid, recipient="+447911123456")
    assert is_v is False
    assert "only supported for US and Canada" in err

