"""
SenderX API Credentials Service
Business logic for external API key generation, verification, revocation, and rotation.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.modules.api_credentials.models import generate_api_key, hash_api_key
from app.modules.api_credentials.repository import ApiCredentialRepository
from app.modules.applications.models import ApplicationStatus
from app.modules.applications.repository import ApplicationRepository
from app.modules.organizations.repository import OrganizationRepository


class ApiCredentialService:
    """Service managing cryptographically secure external API keys."""

    ALLOWED_SCOPES = {"payloads:ingest", "messages:create", "messages:read"}
    SCOPE_ALIASES = {"payloads:write": "payloads:ingest", "messages:write": "messages:create"}

    @classmethod
    def create_credential(
        cls,
        organization_id: str,
        application_id: str,
        name: str,
        created_by: str,
        environment: str = "live",
        scopes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a new external application API key.
        Returns the full raw_key ONCE in the response.
        The database stores only the SHA-256 hash.
        """
        if not organization_id or not application_id or not name:
            raise ValueError("organization_id, application_id, and name are required")

        org = OrganizationRepository.find_by_id(organization_id)
        if not org or org.get("status") != "ACTIVE":
            raise ValueError("Organization is inactive or not found")

        # Verify connected application exists and is ACTIVE
        app_id_clean = str(application_id).strip()
        app = ApplicationRepository.find_by_id(app_id_clean, organization_id=organization_id)
        if not app or app.get("status") != ApplicationStatus.ACTIVE:
            raise ValueError(f"Application '{app_id_clean}' is not registered or is inactive/deactivated")

        app_env = app.get("environment", "all").lower()
        requested_env = environment.lower()
        if app_env != "all" and app_env != requested_env:
            raise ValueError(f"Application '{app_id_clean}' is configured for '{app_env}' environment, cannot issue '{requested_env}' credential")

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

        raw_key, key_prefix, key_hash = generate_api_key(environment=environment)

        credential_data = {
            "organization_id": organization_id,
            "application_id": app_id_clean,
            "name": str(name).strip(),
            "key_prefix": key_prefix,
            "key_hash": key_hash,
            "environment": requested_env,
            "created_by": created_by,
            "scopes": effective_scopes
        }

        created = ApiCredentialRepository.create(credential_data)
        created_safe = {k: v for k, v in created.items() if k != "key_hash"}

        return {
            "success": True,
            "message": "API key generated successfully. Save this key now; it cannot be shown again.",
            "raw_key": raw_key,
            "credential": created_safe
        }

    @classmethod
    def verify_api_key(cls, raw_key: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Verify incoming raw API key against stored SHA-256 hash.
        Returns (credential_doc, organization_doc) if valid and active, else (None, None).
        """
        if not raw_key or not isinstance(raw_key, str):
            return None, None

        key_hash = hash_api_key(raw_key)
        cred = ApiCredentialRepository.find_by_hash(key_hash)
        if not cred or cred.get("status") != "ACTIVE":
            return None, None

        org_id = cred.get("organization_id")
        org = OrganizationRepository.find_by_id(org_id)
        if not org or org.get("status") != "ACTIVE":
            return None, None

        # Verify connected application exists and is ACTIVE
        app_id = cred.get("application_id")
        if not app_id:
            return None, None

        app = ApplicationRepository.find_by_id(app_id, organization_id=org_id)
        if not app or app.get("status") != ApplicationStatus.ACTIVE:
            return None, None

        # Update last used timestamps
        ApiCredentialRepository.update_last_used(cred["credential_id"], org_id, app_id)
        ApplicationRepository.record_activity(app_id, organization_id=org_id)

        cred_safe = {k: v for k, v in cred.items() if k != "key_hash"}
        return cred_safe, org

    @classmethod
    def list_credentials(
        cls,
        organization_id: str,
        application_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List active and historical credentials for an organization."""
        return ApiCredentialRepository.find_all(
            organization_id=organization_id,
            application_id=application_id
        )

    @classmethod
    def get_credential(cls, credential_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
        """Fetch metadata for a specific credential."""
        cred = ApiCredentialRepository.find_by_id(credential_id, organization_id=organization_id)
        if not cred:
            return None
        return {k: v for k, v in cred.items() if k != "key_hash"}

    @classmethod
    def revoke_credential(cls, credential_id: str, organization_id: str, user_id: str) -> bool:
        """Revoke an API credential immediately."""
        return ApiCredentialRepository.revoke(
            credential_id=credential_id,
            organization_id=organization_id,
            revoked_by=user_id
        )

    @classmethod
    def rotate_credential(
        cls,
        credential_id: str,
        organization_id: str,
        user_id: str,
        environment: str = "live"
    ) -> Dict[str, Any]:
        """Rotate an existing API key, returning the new raw key once."""
        cred = ApiCredentialRepository.find_by_id(credential_id, organization_id=organization_id)
        if not cred or cred.get("status") != "ACTIVE":
            return {"success": False, "message": "Credential not found or not active"}

        raw_key, key_prefix, key_hash = generate_api_key(environment=environment)

        rotated = ApiCredentialRepository.rotate(
            credential_id=credential_id,
            organization_id=organization_id,
            new_key_hash=key_hash,
            new_key_prefix=key_prefix,
            rotated_by=user_id
        )

        if not rotated:
            return {"success": False, "message": "Failed to rotate credential"}

        updated = ApiCredentialRepository.find_by_id(credential_id, organization_id=organization_id)
        updated_safe = {k: v for k, v in updated.items() if k != "key_hash"}

        return {
            "success": True,
            "message": "API key rotated successfully. Save this new key now; it cannot be shown again.",
            "raw_key": raw_key,
            "credential": updated_safe
        }
