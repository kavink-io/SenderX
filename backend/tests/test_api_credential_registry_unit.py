from copy import deepcopy
from unittest.mock import patch
import uuid

from cryptography.fernet import Fernet
from flask import Flask

from app.modules.api_credentials.models import hash_api_key
from app.modules.api_credentials.service import ApiCredentialService
from app.modules.payloads.encryption import PayloadEncryption


def _test_app():
    app = Flask(__name__)
    app.config["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
    return app


def test_registration_encrypts_secret_and_returns_only_safe_metadata():
    app = _test_app()
    supplied_key = f"external-{uuid.uuid4().hex}"
    stored = {}

    def store_credential(data):
        stored.update(data)
        stored.update({
            "credential_id": "credential-1",
            "status": "ACTIVE",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        })
        return deepcopy(stored)

    with patch(
        "app.modules.api_credentials.service.OrganizationRepository.find_by_id",
        return_value={"organization_id": "org-1", "status": "ACTIVE"},
    ), patch(
        "app.modules.api_credentials.service.ApplicationRepository.find_by_id",
        return_value={"application_id": "app-1", "status": "ACTIVE", "environment": "all"},
    ), patch(
        "app.modules.api_credentials.service.ApiCredentialRepository.find_by_hash",
        return_value=None,
    ), patch(
        "app.modules.api_credentials.service.ApiCredentialRepository.create",
        side_effect=store_credential,
    ), patch(
        "app.modules.api_credentials.service.SecurityAuditRepository.log_event",
    ) as audit_log:
        with app.app_context():
            result = ApiCredentialService.create_credential(
                organization_id="org-1",
                application_id="app-1",
                name="External client",
                api_key=supplied_key,
                created_by="user-1",
            )
            envelope = stored["key_encrypted"]
            assert PayloadEncryption.decrypt_dict(envelope) == {"api_key": supplied_key}

    assert stored["key_hash"] == hash_api_key(supplied_key)
    assert supplied_key not in str(envelope)
    assert supplied_key not in str(result)
    assert "key_hash" not in result["data"]
    assert "key_encrypted" not in result["data"]
    assert supplied_key not in str(audit_log.call_args)


def test_metadata_edits_preserve_encrypted_key_and_replacement_changes_hash():
    app = _test_app()
    original_key = f"external-original-{uuid.uuid4().hex}"
    replacement_key = f"external-replacement-{uuid.uuid4().hex}"
    with app.app_context():
        original_envelope = PayloadEncryption.encrypt_dict({"api_key": original_key})
    credential = {
        "credential_id": "credential-2",
        "organization_id": "org-1",
        "application_id": "app-1",
        "name": "Original",
        "description": "",
        "notes": "",
        "status": "ACTIVE",
        "environment": "live",
        "key_hash": hash_api_key(original_key),
        "key_encrypted": original_envelope,
        "key_prefix": "••••••••",
    }

    def find_by_hash(key_hash):
        return deepcopy(credential) if credential["key_hash"] == key_hash else None

    def update_credential(_credential_id, _organization_id, fields):
        credential.update(fields)
        return True

    with patch(
        "app.modules.api_credentials.service.ApiCredentialRepository.find_by_id",
        side_effect=lambda *_args, **_kwargs: deepcopy(credential),
    ), patch(
        "app.modules.api_credentials.service.ApiCredentialRepository.find_by_hash",
        side_effect=find_by_hash,
    ), patch(
        "app.modules.api_credentials.service.ApiCredentialRepository.update",
        side_effect=update_credential,
    ), patch(
        "app.modules.api_credentials.service.ApplicationRepository.find_by_id",
        return_value={"application_id": "app-1", "status": "ACTIVE", "environment": "all"},
    ), patch(
        "app.modules.api_credentials.service.SecurityAuditRepository.log_event",
    ) as audit_log:
        with app.app_context():
            original_hash = credential["key_hash"]
            original_envelope = deepcopy(credential["key_encrypted"])
            metadata_result = ApiCredentialService.update_credential(
                "credential-2",
                "org-1",
                "user-1",
                {"name": "Metadata only"},
            )
            assert metadata_result["success"] is True
            assert credential["key_hash"] == original_hash
            assert credential["key_encrypted"] == original_envelope

            replacement_result = ApiCredentialService.update_credential(
                "credential-2",
                "org-1",
                "user-1",
                {"api_key": replacement_key},
            )
            assert replacement_result["success"] is True
            assert PayloadEncryption.decrypt_dict(credential["key_encrypted"]) == {
                "api_key": replacement_key
            }

    assert credential["key_hash"] == hash_api_key(replacement_key)
    assert credential["key_hash"] != original_hash
    assert "key_hash" not in replacement_result["data"]
    assert "key_encrypted" not in replacement_result["data"]
    assert original_key not in str(audit_log.call_args_list)
    assert replacement_key not in str(audit_log.call_args_list)
