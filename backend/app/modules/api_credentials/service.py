"""
SenderX API Credentials Service
Business logic for registering and managing externally supplied API keys.
"""

from typing import Any, Dict, List, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from app.modules.api_credentials.models import hash_api_key
from app.modules.api_credentials.repository import ApiCredentialRepository
from app.modules.applications.models import ApplicationStatus
from app.modules.applications.repository import ApplicationRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.users.audit_repository import SecurityAuditRepository


class DuplicateApiKeyError(ValueError):
    """Raised when a supplied API key is already registered."""


class ApiCredentialService:
    """Service managing encrypted, externally supplied API keys."""

    ALLOWED_SCOPES = {
        "payloads:ingest",
        "messages:create",
        "messages:read",
        "messages:manage",
        "media:upload",
        "media:read",
        "media:delete",
    }
    SCOPE_ALIASES = {"payloads:write": "payloads:ingest", "messages:write": "messages:create"}
    ALLOWED_ENVIRONMENTS = {"live", "test"}
    ALLOWED_STATUSES = {"ACTIVE", "INACTIVE"}
    MASKED_KEY = "••••••••"

    @staticmethod
    def _validate_api_key(api_key: Any) -> str:
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("API key value is required")
        if len(api_key) > 4096:
            raise ValueError("API key value is too long")
        if any(character.isspace() for character in api_key):
            raise ValueError("API key value cannot contain whitespace")
        return api_key

    @staticmethod
    def _validate_text(value: Any, label: str, maximum: int, required: bool = False) -> str:
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"{label} must be a string")
        cleaned = value.strip()
        if required and not cleaned:
            raise ValueError(f"{label} is required")
        if len(cleaned) > maximum:
            raise ValueError(f"{label} cannot exceed {maximum} characters")
        return cleaned

    @staticmethod
    def _safe_credential(credential: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not credential:
            return None
        excluded_fields = {
            "_id",
            "key_hash",
            "key_encrypted",
            "api_key",
            "raw_key",
            "secret_key",
            "encrypted_api_key",
        }
        return {key: value for key, value in credential.items() if key not in excluded_fields}

    @staticmethod
    def _encrypt_api_key(api_key: str) -> Dict[str, Any]:
        from app.modules.payloads.encryption import PayloadEncryption

        return PayloadEncryption.encrypt_dict({"api_key": api_key})

    @classmethod
    def _validate_application(
        cls,
        organization_id: str,
        application_id: str,
        environment: str,
        allow_inactive: bool = False
    ) -> Dict[str, Any]:
        application = ApplicationRepository.find_by_id(
            application_id,
            organization_id=organization_id
        )
        if not application or application.get("deleted_at"):
            raise ValueError("Connected application is not registered in this organization")
        if not allow_inactive and application.get("status") != ApplicationStatus.ACTIVE:
            raise ValueError("Connected application is inactive")

        application_environment = str(application.get("environment", "all")).lower()
        if application_environment != "all" and application_environment != environment:
            raise ValueError(
                f"Connected application is configured for '{application_environment}' "
                f"environment, not '{environment}'"
            )
        return application

    @classmethod
    def create_credential(
        cls,
        organization_id: str,
        application_id: str,
        name: str,
        api_key: str,
        created_by: str,
        environment: str = "live",
        status: str = "ACTIVE",
        description: Optional[str] = None,
        notes: Optional[str] = None,
        scopes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Register a key supplied by the selected external application."""
        if not organization_id:
            raise ValueError("organization_id is required")

        supplied_key = cls._validate_api_key(api_key)
        clean_name = cls._validate_text(name, "API key name", 100, required=True)
        clean_description = cls._validate_text(description, "Description", 500)
        clean_notes = cls._validate_text(notes, "Notes", 2000)

        org = OrganizationRepository.find_by_id(organization_id)
        if not org or org.get("status") != "ACTIVE":
            raise ValueError("Organization is inactive or not found")

        if not isinstance(application_id, str) or not application_id.strip():
            raise ValueError("Connected application is required")
        app_id_clean = application_id.strip()

        requested_env = environment.strip().lower() if isinstance(environment, str) else ""
        if requested_env not in cls.ALLOWED_ENVIRONMENTS:
            raise ValueError("Environment must be 'live' or 'test'")
        cls._validate_application(organization_id, app_id_clean, requested_env)

        requested_status = status.strip().upper() if isinstance(status, str) else ""
        if requested_status not in cls.ALLOWED_STATUSES:
            raise ValueError("Status must be ACTIVE or INACTIVE")

        effective_scopes = scopes or ["payloads:ingest", "messages:create", "messages:read"]
        if not isinstance(effective_scopes, list) or any(not isinstance(scope, str) for scope in effective_scopes):
            raise ValueError("scopes must be a list of supported scope names")
        effective_scopes = sorted(set(
            cls.SCOPE_ALIASES.get(scope.strip(), scope.strip())
            for scope in effective_scopes if scope.strip()
        ))
        unsupported_scopes = set(effective_scopes) - cls.ALLOWED_SCOPES
        if unsupported_scopes:
            raise ValueError(f"Unsupported API credential scope(s): {', '.join(sorted(unsupported_scopes))}")

        key_hash = hash_api_key(supplied_key)
        if ApiCredentialRepository.find_by_hash(key_hash):
            raise DuplicateApiKeyError("This API key is already registered")

        credential_data = {
            "organization_id": organization_id,
            "application_id": app_id_clean,
            "name": clean_name,
            "description": clean_description,
            "notes": clean_notes,
            "key_prefix": cls.MASKED_KEY,
            "key_hash": key_hash,
            "key_encrypted": cls._encrypt_api_key(supplied_key),
            "environment": requested_env,
            "status": requested_status,
            "created_by": created_by,
            "scopes": effective_scopes,
        }

        try:
            created = ApiCredentialRepository.create(credential_data)
        except DuplicateKeyError as exc:
            raise DuplicateApiKeyError("This API key is already registered") from exc

        if not created:
            raise RuntimeError("API credential could not be loaded after registration")
        safe_credential = cls._safe_credential(created)
        if not safe_credential or not safe_credential.get("credential_id"):
            raise RuntimeError("Registered API credential is missing its identifier")
        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="API_CREDENTIAL_REGISTERED",
            actor_id=created_by,
            target_id=safe_credential["credential_id"],
            target_type="API_CREDENTIAL",
            target_name=clean_name,
            details={
                "application_id": app_id_clean,
                "environment": requested_env,
                "status": requested_status,
            }
        )
        return {
            "success": True,
            "message": "External API key registered successfully.",
            "data": safe_credential,
        }

    @classmethod
    def verify_api_key(cls, raw_key: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Verify an incoming external API key and resolve its organization/application.
        Returns (credential_doc, organization_doc) only for active, valid records.
        """
        if not raw_key or not isinstance(raw_key, str):
            return None, None

        key_hash = hash_api_key(raw_key)
        credential = ApiCredentialRepository.find_by_hash(key_hash)
        if not credential or credential.get("status") != "ACTIVE":
            return None, None

        organization_id = credential.get("organization_id")
        organization = OrganizationRepository.find_by_id(organization_id)
        if not organization or organization.get("status") != "ACTIVE":
            return None, None

        application_id = credential.get("application_id")
        if not application_id:
            return None, None

        application = ApplicationRepository.find_by_id(
            application_id,
            organization_id=organization_id
        )
        if not application or application.get("status") != ApplicationStatus.ACTIVE:
            return None, None

        ApiCredentialRepository.update_last_used(
            credential["credential_id"],
            organization_id,
            application_id
        )
        ApplicationRepository.record_activity(application_id, organization_id=organization_id)
        return cls._safe_credential(credential), organization

    @classmethod
    def list_credentials(
        cls,
        organization_id: str,
        application_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List organization credentials without hash or encrypted secret material."""
        return [
            cls._safe_credential(credential)
            for credential in ApiCredentialRepository.find_all(
                organization_id=organization_id,
                application_id=application_id
            )
        ]

    @classmethod
    def get_credential(cls, credential_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
        """Fetch credential metadata strictly within its organization."""
        credential = ApiCredentialRepository.find_by_id(
            credential_id,
            organization_id=organization_id
        )
        return cls._safe_credential(credential)

    @classmethod
    def update_credential(
        cls,
        credential_id: str,
        organization_id: str,
        user_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update metadata or replace a stored key with a supplied value."""
        credential = ApiCredentialRepository.find_by_id(
            credential_id,
            organization_id=organization_id
        )
        if not credential:
            return {"success": False, "status_code": 404, "message": "API credential not found"}
        if not isinstance(data, dict):
            raise ValueError("Request body must be an object")

        updates: Dict[str, Any] = {}
        current_application_id = credential.get("application_id")
        application_id = data.get("application_id", current_application_id)
        if not isinstance(application_id, str) or not application_id.strip():
            raise ValueError("Connected application is required")
        application_id = application_id.strip()
        if "application_id" in data:
            updates["application_id"] = application_id

        environment_value = data.get("environment", credential.get("environment", "live"))
        environment = environment_value.strip().lower() if isinstance(environment_value, str) else ""
        if environment not in cls.ALLOWED_ENVIRONMENTS:
            raise ValueError("Environment must be 'live' or 'test'")
        if "environment" in data:
            updates["environment"] = environment

        application_changed = application_id != current_application_id
        cls._validate_application(
            organization_id,
            application_id,
            environment,
            allow_inactive=not application_changed
        )

        if "name" in data:
            updates["name"] = cls._validate_text(data["name"], "API key name", 100, required=True)
        if "description" in data:
            updates["description"] = cls._validate_text(data["description"], "Description", 500)
        if "notes" in data:
            updates["notes"] = cls._validate_text(data["notes"], "Notes", 2000)

        if "status" in data:
            status = data["status"].strip().upper() if isinstance(data["status"], str) else ""
            current_status = str(credential.get("status", "ACTIVE")).upper()
            if status not in cls.ALLOWED_STATUSES | {"REVOKED"}:
                raise ValueError("Status must be ACTIVE or INACTIVE")
            if current_status == "REVOKED" and status != "REVOKED":
                raise ValueError("A revoked API key cannot be reactivated")
            updates["status"] = status

        replacement_key = data.get("api_key")
        key_replaced = replacement_key not in (None, "")
        if key_replaced:
            supplied_key = cls._validate_api_key(replacement_key)
            key_hash = hash_api_key(supplied_key)
            duplicate = ApiCredentialRepository.find_by_hash(key_hash)
            if duplicate and duplicate.get("credential_id") != credential_id:
                raise DuplicateApiKeyError("This API key is already registered")
            updates.update({
                "key_hash": key_hash,
                "key_encrypted": cls._encrypt_api_key(supplied_key),
                "key_prefix": cls.MASKED_KEY,
                "replaced_by": user_id,
            })

        if not updates:
            raise ValueError("No API key changes were provided")
        try:
            updated_successfully = ApiCredentialRepository.update(
                credential_id,
                organization_id,
                updates
            )
        except DuplicateKeyError as exc:
            raise DuplicateApiKeyError("This API key is already registered") from exc
        if not updated_successfully:
            return {"success": False, "status_code": 404, "message": "API credential not found"}

        updated = ApiCredentialRepository.find_by_id(
            credential_id,
            organization_id=organization_id
        )
        event_type = "API_CREDENTIAL_REPLACED" if key_replaced else "API_CREDENTIAL_UPDATED"
        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type=event_type,
            actor_id=user_id,
            target_id=credential_id,
            target_type="API_CREDENTIAL",
            target_name=updates.get("name", credential.get("name")),
            details={
                "application_id": application_id,
                "environment": environment,
                "changed_fields": [
                    field for field in updates
                    if field not in {"key_hash", "key_encrypted", "key_prefix", "replaced_by"}
                ],
                "credential_replaced": key_replaced,
            }
        )
        return {
            "success": True,
            "message": "API key updated successfully.",
            "data": cls._safe_credential(updated),
        }

    @classmethod
    def revoke_credential(cls, credential_id: str, organization_id: str, user_id: str) -> bool:
        """Retain the internal revocation mechanism for compatibility and safety."""
        return ApiCredentialRepository.revoke(
            credential_id=credential_id,
            organization_id=organization_id,
            revoked_by=user_id
        )

    @classmethod
    def delete_credential(cls, credential_id: str, organization_id: str, user_id: str) -> bool:
        """Delete a credential and record an audit entry containing only metadata."""
        credential = ApiCredentialRepository.find_by_id(
            credential_id,
            organization_id=organization_id
        )
        if not credential or not ApiCredentialRepository.delete(credential_id, organization_id):
            return False

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="API_CREDENTIAL_DELETED",
            actor_id=user_id,
            target_id=credential_id,
            target_type="API_CREDENTIAL",
            target_name=credential.get("name"),
            details={
                "application_id": credential.get("application_id"),
                "environment": credential.get("environment"),
            }
        )
        return True
