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

        # Fast-expire file in DB directly instead of real-time sleep
        from datetime import datetime, timezone, timedelta
        db = app.mongo_db
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        db.media.update_one({"media_id": media_id}, {"$set": {"expires_at": past_time}})

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

    # 4. Enforces no object ACL (BucketOwnerEnforced compatible) and AES256 encryption in S3 save
    mock_s3 = MagicMock()
    storage = S3Storage(bucket_name="secure-bucket", s3_client=mock_s3)
    storage.save(
        VALID_PDF_BYTES,
        "orgs/org-123/2026/11/doc.pdf",
        content_type="application/pdf",
        organization_id="org-123",
    )

    assert mock_s3.upload_fileobj.call_count == 1
    extra_args = mock_s3.upload_fileobj.call_args[1]["ExtraArgs"]
    assert "ACL" not in extra_args
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


# ---------------------------------------------------------------------------
# 27. S3 BUCKET OWNER ENFORCED, ORG ISOLATION & ADAPTER OPERATIONS
# ---------------------------------------------------------------------------

def test_s3_upload_bucket_owner_enforced_no_acl():
    mock_s3 = MagicMock()
    storage = S3Storage(bucket_name="senderx-prod-media-test", region_name="ap-south-1", s3_client=mock_s3)

    res = storage.save(
        data=VALID_PDF_BYTES,
        storage_key="orgs/org-1/2026/11/file.pdf",
        content_type="application/pdf",
        metadata={"organization_id": "org-1", "media_id": "m-1"},
        organization_id="org-1",
    )

    assert res["storage_backend"] == "s3"
    assert res["bucket"] == "senderx-prod-media-test"
    assert res["storage_key"] == "orgs/org-1/2026/11/file.pdf"
    assert res["encryption"] == "AES256"
    call_kwargs = mock_s3.upload_fileobj.call_args[1]
    assert "ACL" not in call_kwargs["ExtraArgs"]
    assert call_kwargs["ExtraArgs"]["ContentType"] == "application/pdf"
    assert call_kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"
    assert call_kwargs["ExtraArgs"]["Metadata"] == {"organization_id": "org-1", "media_id": "m-1"}


def test_media_service_upload_passes_organization_id_to_storage(app, monkeypatch):
    with app.app_context():
        mock_storage = MagicMock()
        mock_storage.backend_name = "s3"
        mock_storage.save.return_value = {
            "storage_key": "orgs/org-x/2026/11/id_test.pdf",
            "storage_backend": "s3",
            "bucket": "test-bucket",
            "size_bytes": len(VALID_PDF_BYTES),
            "content_type": "application/pdf",
            "encryption": "AES256",
        }
        monkeypatch.setattr(MediaService, "_get_storage", classmethod(lambda cls: mock_storage))
        monkeypatch.setattr(MediaRepository, "create", classmethod(lambda cls, doc: "media-id-1"))

        org_id = str(uuid.uuid4())
        res = MediaService.upload_file(
            file_obj=VALID_PDF_BYTES,
            organization_id=org_id,
            custom_filename="test.pdf",
        )

        assert res["success"] is True
        save_kwargs = mock_storage.save.call_args[1]
        assert save_kwargs["organization_id"] == org_id
        assert save_kwargs["storage_key"].startswith(f"orgs/{org_id}/")


def test_s3_organization_prefix_validation():
    mock_s3 = MagicMock()
    storage = S3Storage(bucket_name="senderx-prod-media-test", s3_client=mock_s3)

    with pytest.raises(StorageSecurityError):
        storage.save(
            VALID_PDF_BYTES,
            "orgs/org-other/2026/11/doc.pdf",
            organization_id="org-owner",
        )

    with pytest.raises(StorageSecurityError):
        storage.generate_signed_url(
            "orgs/org-other/2026/11/doc.pdf",
            organization_id="org-owner",
        )

    with pytest.raises(StorageSecurityError):
        storage.delete(
            "orgs/org-other/2026/11/doc.pdf",
            organization_id="org-owner",
        )

    with pytest.raises(StorageSecurityError):
        storage.get_stream(
            "../orgs/org-owner/2026/11/doc.pdf",
            organization_id="org-owner",
        )

    assert storage.exists("../orgs/org-owner/2026/11/doc.pdf", organization_id="org-owner") is False
    mock_s3.head_object.assert_not_called()


def test_s3_presigned_download_url_generation():
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://senderx-prod-media-test.s3.ap-south-1.amazonaws.com/signed"
    storage = S3Storage(bucket_name="senderx-prod-media-test", region_name="ap-south-1", s3_client=mock_s3)

    url = storage.generate_signed_url(
        storage_key="orgs/org-1/2026/11/doc.pdf",
        expires_in=600,
        filename="report.pdf",
        organization_id="org-1",
    )

    assert url == "https://senderx-prod-media-test.s3.ap-south-1.amazonaws.com/signed"
    call_kwargs = mock_s3.generate_presigned_url.call_args[1]
    assert call_kwargs["ClientMethod"] == "get_object"
    assert call_kwargs["ExpiresIn"] == 600
    assert call_kwargs["Params"]["Bucket"] == "senderx-prod-media-test"
    assert call_kwargs["Params"]["Key"] == "orgs/org-1/2026/11/doc.pdf"
    assert call_kwargs["Params"]["ResponseContentDisposition"] == 'attachment; filename="report.pdf"'


def test_s3_object_existence_and_deletion():
    from botocore.exceptions import ClientError

    mock_s3 = MagicMock()
    storage = S3Storage(bucket_name="senderx-prod-media-test", s3_client=mock_s3)
    key = "orgs/org-1/2026/11/doc.pdf"

    assert storage.exists(key, organization_id="org-1") is True
    mock_s3.head_object.assert_called_once_with(Bucket="senderx-prod-media-test", Key=key)

    mock_s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}},
        "HeadObject",
    )
    assert storage.exists(key, organization_id="org-1") is False

    assert storage.delete(key, organization_id="org-1") is True
    mock_s3.delete_object.assert_called_once_with(Bucket="senderx-prod-media-test", Key=key)


def test_s3_upload_error_handling():
    from botocore.exceptions import ClientError

    mock_s3 = MagicMock()
    mock_s3.upload_fileobj.side_effect = ClientError(
        {"Error": {"Code": "AccessControlListNotSupported", "Message": "The bucket does not allow ACLs"}},
        "PutObject",
    )
    storage = S3Storage(bucket_name="senderx-prod-media-test", s3_client=mock_s3)

    with pytest.raises(StorageOperationError) as exc:
        storage.save(
            VALID_PDF_BYTES,
            "orgs/org-1/2026/11/doc.pdf",
            organization_id="org-1",
        )
    assert "AccessControlListNotSupported" in str(exc.value)


# ---------------------------------------------------------------------------
# 28. PHASE 8 DUAL AUTHENTICATION & APPLICATION-SCOPED MEDIA ISOLATION
# ---------------------------------------------------------------------------

def _setup_dual_auth_media_env(monkeypatch, app):
    """Build isolated in-memory Mongo-backed state for Phase 8 dual-auth media tests."""
    from app.modules.api_credentials.models import hash_api_key
    from app.modules.api_credentials.rate_limiter import DistributedRateLimiter
    from app.modules.api_credentials.repository import ApiCredentialRepository
    from app.modules.applications.repository import ApplicationRepository

    org_id = f"org-{uuid.uuid4().hex[:8]}"
    app_a_id = f"app-a-{uuid.uuid4().hex[:6]}"
    app_b_id = f"app-b-{uuid.uuid4().hex[:6]}"
    key_a_full = f"sx_test_{uuid.uuid4().hex}"
    key_a_read_only = f"sx_test_{uuid.uuid4().hex}"
    key_b = f"sx_test_{uuid.uuid4().hex}"
    key_revoked = f"sx_test_{uuid.uuid4().hex}"
    key_inactive_app = f"sx_test_{uuid.uuid4().hex}"

    org_doc = {"organization_id": org_id, "name": "Phase8 Org", "status": "ACTIVE"}
    apps_db = {
        app_a_id: {"application_id": app_a_id, "organization_id": org_id, "status": "ACTIVE"},
        app_b_id: {"application_id": app_b_id, "organization_id": org_id, "status": "ACTIVE"},
        "app-inactive": {"application_id": "app-inactive", "organization_id": org_id, "status": "INACTIVE"},
    }
    creds_by_hash = {
        hash_api_key(key_a_full): {
            "credential_id": "cred-a-full",
            "organization_id": org_id,
            "application_id": app_a_id,
            "status": "ACTIVE",
            "environment": "test",
            "scopes": ["media:upload", "media:read", "media:delete"],
        },
        hash_api_key(key_a_read_only): {
            "credential_id": "cred-a-ro",
            "organization_id": org_id,
            "application_id": app_a_id,
            "status": "ACTIVE",
            "environment": "test",
            "scopes": ["media:read"],
        },
        hash_api_key(key_b): {
            "credential_id": "cred-b",
            "organization_id": org_id,
            "application_id": app_b_id,
            "status": "ACTIVE",
            "environment": "test",
            "scopes": ["media:upload", "media:read", "media:delete"],
        },
        hash_api_key(key_revoked): {
            "credential_id": "cred-revoked",
            "organization_id": org_id,
            "application_id": app_a_id,
            "status": "INACTIVE",
            "environment": "test",
            "scopes": ["media:upload", "media:read", "media:delete"],
        },
        hash_api_key(key_inactive_app): {
            "credential_id": "cred-inactive-app",
            "organization_id": org_id,
            "application_id": "app-inactive",
            "status": "ACTIVE",
            "environment": "test",
            "scopes": ["media:upload", "media:read", "media:delete"],
        },
    }

    monkeypatch.setattr(DistributedRateLimiter, "peek_auth_failure", classmethod(lambda cls, ip: (True, 0)))
    monkeypatch.setattr(DistributedRateLimiter, "record_auth_failure", classmethod(lambda cls, ip: (True, 0)))
    monkeypatch.setattr(DistributedRateLimiter, "check_rate_limit", classmethod(lambda cls, **kw: (True, 0)))
    monkeypatch.setattr(ApiCredentialRepository, "find_by_hash", classmethod(lambda cls, h: creds_by_hash.get(h)))
    monkeypatch.setattr(ApiCredentialRepository, "update_last_used", classmethod(lambda cls, *a, **kw: None))
    monkeypatch.setattr(OrganizationRepository, "find_by_id", classmethod(lambda cls, oid: org_doc if oid == org_id else None))
    monkeypatch.setattr(ApplicationRepository, "find_by_id", classmethod(lambda cls, aid, organization_id=None: apps_db.get(aid)))
    monkeypatch.setattr(ApplicationRepository, "record_activity", classmethod(lambda cls, *a, **kw: None))

    # In-memory media store
    media_store = {}
    legacy_id = str(uuid.uuid4())
    media_store[legacy_id] = {
        "media_id": legacy_id,
        "organization_id": org_id,
        "filename": "legacy.txt",
        "original_filename": "legacy.txt",
        "mime_type": "text/plain",
        "file_extension": ".txt",
        "size_bytes": 12,
        "checksum_sha256": "abc",
        "storage_backend": "local",
        "storage_key": f"orgs/{org_id}/2026/11/{legacy_id}_legacy.txt",
        "status": "ACTIVE",
        "scan_status": "CLEAN",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    def _match(doc, organization_id=None, allowed_application_ids=None, include_org_shared=False):
        if organization_id is not None and doc.get("organization_id") != organization_id:
            return False
        if allowed_application_ids is not None:
            app_val = doc.get("application_id")
            if app_val not in allowed_application_ids and not (include_org_shared and app_val is None):
                return False
        return True

    def _create(cls, doc):
        media_store[doc["media_id"]] = dict(doc)
        return dict(doc)

    def _find_by_id(cls, media_id, organization_id=None, allowed_application_ids=None, include_org_shared=False):
        doc = media_store.get(media_id)
        if doc and _match(doc, organization_id, allowed_application_ids, include_org_shared):
            return dict(doc)
        return None

    def _find_all(cls, organization_id, page=1, limit=50, allowed_application_ids=None, include_org_shared=False, **kw):
        items = [
            dict(d) for d in media_store.values()
            if d.get("status") != "DELETED" and _match(d, organization_id, allowed_application_ids, include_org_shared)
        ]
        return {"data": items, "pagination": {"total": len(items), "page": page, "limit": limit, "pages": 1}}

    def _soft_delete(cls, media_id, organization_id=None, allowed_application_ids=None):
        doc = media_store.get(media_id)
        if doc and _match(doc, organization_id, allowed_application_ids):
            doc["status"] = "DELETED"
            return True
        return False

    monkeypatch.setattr(MediaRepository, "create", classmethod(_create))
    monkeypatch.setattr(MediaRepository, "find_by_id", classmethod(_find_by_id))
    monkeypatch.setattr(MediaRepository, "find_all", classmethod(_find_all))
    monkeypatch.setattr(MediaRepository, "soft_delete", classmethod(_soft_delete))

    mock_storage = MagicMock()
    mock_storage.backend_name = "s3"
    mock_storage.save.side_effect = lambda **kw: {
        "storage_key": kw["storage_key"],
        "storage_backend": "s3",
        "bucket": "test-bucket",
        "size_bytes": len(kw["data"]),
        "content_type": kw["content_type"],
        "encryption": "AES256",
    }
    mock_storage.generate_signed_url.return_value = "https://s3.ap-south-1.amazonaws.com/test-bucket/signed"
    mock_storage.delete.return_value = True
    monkeypatch.setattr(MediaService, "_get_storage", classmethod(lambda cls: mock_storage))

    return {
        "org_id": org_id,
        "app_a_id": app_a_id,
        "app_b_id": app_b_id,
        "key_a_full": key_a_full,
        "key_a_read_only": key_a_read_only,
        "key_b": key_b,
        "key_revoked": key_revoked,
        "key_inactive_app": key_inactive_app,
        "legacy_id": legacy_id,
        "media_store": media_store,
    }


def test_phase8_media_dual_auth_authentication_and_mixed_credentials(app, monkeypatch):
    ctx = _setup_dual_auth_media_env(monkeypatch, app)
    client = app.test_client()

    # 1. Missing credentials -> 401
    assert client.get("/api/v1/media/").status_code == 401

    # 2. Invalid API key -> 401
    assert client.get("/api/v1/media/", headers={"X-API-Key": "sx_test_invalid"}).status_code == 401

    # 3. Revoked API key -> 401
    assert client.get("/api/v1/media/", headers={"X-API-Key": ctx["key_revoked"]}).status_code == 401

    # 4. Inactive application -> 401
    assert client.get("/api/v1/media/", headers={"X-API-Key": ctx["key_inactive_app"]}).status_code == 401

    # 5. Insufficient API key scope (read-only key attempting upload/delete) -> 403
    resp_scope = client.post(
        "/api/v1/media/upload",
        headers={"X-API-Key": ctx["key_a_read_only"]},
        data={"file": (io.BytesIO(VALID_TXT_BYTES), "hello.txt")},
        content_type="multipart/form-data",
    )
    assert resp_scope.status_code == 403

    # 6. Conflicting X-API-Key + Authorization Bearer JWT -> 401
    with app.app_context():
        jwt_token = create_access_token(
            identity="user-1",
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": ctx["org_id"]},
        )
    resp_conflict = client.get(
        "/api/v1/media/",
        headers={"X-API-Key": ctx["key_a_full"], "Authorization": f"Bearer {jwt_token}"},
    )
    assert resp_conflict.status_code == 401
    assert "Conflicting authentication credentials" in resp_conflict.get_json()["message"]

    # 7. Expired JWT -> 401
    with app.app_context():
        expired_jwt = create_access_token(
            identity="user-1",
            expires_delta=timedelta(seconds=-10),
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": ctx["org_id"]},
        )
    assert client.get("/api/v1/media/", headers={"Authorization": f"Bearer {expired_jwt}"}).status_code == 401


def test_phase8_media_api_key_crud_and_cross_application_isolation(app, monkeypatch):
    ctx = _setup_dual_auth_media_env(monkeypatch, app)
    client = app.test_client()

    # 1. App A single upload -> 201 and stores server-derived application_id
    up_resp = client.post(
        "/api/v1/media/upload",
        headers={"X-API-Key": ctx["key_a_full"]},
        data={"file": (io.BytesIO(VALID_TXT_BYTES), "app_a.txt")},
        content_type="multipart/form-data",
    )
    assert up_resp.status_code == 201
    media_a = up_resp.get_json()["media"]
    media_a_id = media_a["media_id"]
    assert media_a["application_id"] == ctx["app_a_id"]
    assert media_a["organization_id"] == ctx["org_id"]

    # 2. App A bulk upload -> 201
    bulk_resp = client.post(
        "/api/v1/media/bulk-upload",
        headers={"X-API-Key": ctx["key_a_full"]},
        data={"files": [(io.BytesIO(VALID_TXT_BYTES), "b1.txt"), (io.BytesIO(VALID_TXT_BYTES), "b2.txt")]},
        content_type="multipart/form-data",
    )
    assert bulk_resp.status_code == 201
    assert bulk_resp.get_json()["success_count"] == 2

    # 3. App A lists only its own 3 files (legacy record without application_id is hidden!)
    list_a = client.get("/api/v1/media/", headers={"X-API-Key": ctx["key_a_full"]}).get_json()
    listed_ids_a = {item["media_id"] for item in list_a["data"]}
    assert media_a_id in listed_ids_a
    assert ctx["legacy_id"] not in listed_ids_a

    # 4. App A gets metadata and downloads (S3 presigned 302 redirect)
    assert client.get(f"/api/v1/media/{media_a_id}", headers={"X-API-Key": ctx["key_a_full"]}).status_code == 200
    dl_a = client.get(f"/api/v1/media/{media_a_id}/download", headers={"X-API-Key": ctx["key_a_full"]})
    assert dl_a.status_code == 302
    assert "s3.ap-south-1.amazonaws.com" in dl_a.headers["Location"]

    # 5. App B cannot list, get, download, or delete App A's media or legacy media
    list_b = client.get("/api/v1/media/", headers={"X-API-Key": ctx["key_b"]}).get_json()
    assert list_b["data"] == []
    assert client.get(f"/api/v1/media/{media_a_id}", headers={"X-API-Key": ctx["key_b"]}).status_code == 404
    assert client.get(f"/api/v1/media/{media_a_id}/download", headers={"X-API-Key": ctx["key_b"]}).status_code == 404
    assert client.delete(f"/api/v1/media/{media_a_id}", headers={"X-API-Key": ctx["key_b"]}).status_code == 404
    assert client.get(f"/api/v1/media/{ctx['legacy_id']}", headers={"X-API-Key": ctx["key_b"]}).status_code == 404

    # 6. App A deletes its own media -> 200, then 404
    assert client.delete(f"/api/v1/media/{media_a_id}", headers={"X-API-Key": ctx["key_a_full"]}).status_code == 200
    assert client.get(f"/api/v1/media/{media_a_id}", headers={"X-API-Key": ctx["key_a_full"]}).status_code == 404


def test_phase8_media_jwt_backward_compatibility_and_org_wide_scope(app, monkeypatch):
    ctx = _setup_dual_auth_media_env(monkeypatch, app)
    client = app.test_client()

    user_org_wide = {
        "user_id": "u-org",
        "email": "org@example.com",
        "organization_id": ctx["org_id"],
        "is_active": True,
        "status": "ACTIVE",
        "token_version": 1,
        "role_assignments": [{"role_id": "r-org", "application_id": None}],
    }
    user_app_scoped = {
        "user_id": "u-app",
        "email": "app@example.com",
        "organization_id": ctx["org_id"],
        "is_active": True,
        "status": "ACTIVE",
        "token_version": 1,
        "role_assignments": [{"role_id": "r-app", "application_id": ctx["app_a_id"]}],
    }
    roles_db = {
        "r-org": {
            "role_id": "r-org",
            "scope": "ORGANIZATION",
            "permissions": ["organization:media:upload", "organization:media:read", "organization:media:delete"],
        },
        "r-app": {
            "role_id": "r-app",
            "scope": "ORGANIZATION",
            "permissions": ["organization:media:upload", "organization:media:read", "organization:media:delete"],
        },
    }
    monkeypatch.setattr(
        UserRepository,
        "find_by_id",
        classmethod(lambda cls, uid: user_org_wide if uid == "u-org" else (user_app_scoped if uid == "u-app" else None)),
    )
    monkeypatch.setattr(RoleRepository, "find_by_id", classmethod(lambda cls, rid, organization_id=None: roles_db.get(rid)))

    with app.app_context():
        jwt_org = create_access_token(
            identity="u-org",
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": ctx["org_id"], "token_version": 1},
        )
        jwt_app = create_access_token(
            identity="u-app",
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": ctx["org_id"], "token_version": 1},
        )

    # 1. Org-wide JWT can still see legacy media (application_id=None) and upload org-shared media
    list_org = client.get("/api/v1/media/", headers={"Authorization": f"Bearer {jwt_org}"})
    assert list_org.status_code == 200
    assert any(item["media_id"] == ctx["legacy_id"] for item in list_org.get_json()["data"])

    up_org = client.post(
        "/api/v1/media/upload",
        headers={"Authorization": f"Bearer {jwt_org}"},
        data={"file": (io.BytesIO(VALID_TXT_BYTES), "org_shared.txt")},
        content_type="multipart/form-data",
    )
    assert up_org.status_code == 201
    assert up_org.get_json()["media"]["application_id"] is None

    # 2. App-scoped JWT is still blocked by require_organization_wide_scope() on upload/delete -> 403
    up_app_jwt = client.post(
        "/api/v1/media/upload",
        headers={"Authorization": f"Bearer {jwt_app}"},
        data={"file": (io.BytesIO(VALID_TXT_BYTES), "blocked.txt")},
        content_type="multipart/form-data",
    )
    assert up_app_jwt.status_code == 403
    del_app_jwt = client.delete(f"/api/v1/media/{ctx['legacy_id']}", headers={"Authorization": f"Bearer {jwt_app}"})
    assert del_app_jwt.status_code == 403


def test_phase8_5_1_media_repository_find_all_preserves_scope_with_search(monkeypatch):
    """Ensure search $or never overwrites application-ownership $or in MediaRepository.find_all."""
    captured_queries = []

    class _FakeCursor:
        def sort(self, *a, **kw):
            return self

        def skip(self, *a, **kw):
            return self

        def limit(self, *a, **kw):
            return []

    class _FakeCollection:
        def count_documents(self, q):
            captured_queries.append(dict(q))
            return 0

        def find(self, q, proj):
            return _FakeCursor()

    monkeypatch.setattr(MediaRepository, "_collection", classmethod(lambda cls: _FakeCollection()))

    # 1. App-scoped JWT (include_org_shared=True) + search -> must combine both $or clauses via $and
    MediaRepository.find_all(
        organization_id="org-1",
        search="report",
        allowed_application_ids=["app-a"],
        include_org_shared=True,
    )
    q_jwt_search = captured_queries[-1]
    assert "$and" in q_jwt_search
    assert "$or" not in q_jwt_search
    assert len(q_jwt_search["$and"]) == 2
    assert q_jwt_search["$and"][0]["$or"] == [
        {"application_id": {"$in": ["app-a"]}},
        {"application_id": None},
        {"application_id": {"$exists": False}},
    ]
    assert any("filename" in cond for cond in q_jwt_search["$and"][1]["$or"])

    # 2. API_KEY (include_org_shared=False) + search -> keeps strict application_id filter and search $or
    MediaRepository.find_all(
        organization_id="org-1",
        search="report",
        allowed_application_ids=["app-a"],
        include_org_shared=False,
    )
    q_api_search = captured_queries[-1]
    assert q_api_search["application_id"] == {"$in": ["app-a"]}
    assert "$or" in q_api_search

    # 3. Empty/whitespace search -> leaves ownership $or untouched
    MediaRepository.find_all(
        organization_id="org-1",
        search="   ",
        allowed_application_ids=["app-a"],
        include_org_shared=True,
    )
    q_jwt_empty = captured_queries[-1]
    assert "$and" not in q_jwt_empty
    assert q_jwt_empty["$or"] == [
        {"application_id": {"$in": ["app-a"]}},
        {"application_id": None},
        {"application_id": {"$exists": False}},
    ]

