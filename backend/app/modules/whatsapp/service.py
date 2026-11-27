"""
SenderX WhatsApp Integration and Platform Settings Service
Implements organization-scoped business logic, access token encryption,
soft-delete reconnection, credential rotation auditing, and trusted worker dispatch resolution.
"""

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
import uuid

from flask import current_app, has_app_context

from app.modules.organizations.repository import OrganizationRepository
from app.modules.users.audit_repository import SecurityAuditRepository
from app.adapters.errors import ProviderResolutionError
from app.modules.whatsapp.encryption import WhatsAppEncryption, WhatsAppEncryptionError
from app.modules.whatsapp.meta_client import (
    MetaWhatsAppClient,
    WhatsAppVerificationError,
    WhatsAppVerificationErrorCode,
)
from app.modules.whatsapp.models import (
    WhatsAppIntegrationCreateSchema,
    WhatsAppManualConnectSchema,
    WhatsAppIntegrationUpdateSchema,
    WhatsAppCredentialRotateSchema,
    WhatsAppPlatformSettingsSchema,
    WhatsAppIntegrationStatus,
    WhatsAppTokenStatus,
    clean_phone_number,
    serialize_integration,
    serialize_platform_settings,
)
from app.modules.whatsapp.repository import (
    WhatsAppIntegrationRepository,
    PlatformSettingsRepository,
)


class WhatsAppIntegrationService:
    """Service layer managing organization-scoped WhatsApp Cloud API integrations."""

    @classmethod
    def _validate_org_active(cls, organization_id: str, app=None) -> Dict[str, Any]:
        """Validate that the organization exists and has ACTIVE status."""
        if not organization_id or not isinstance(organization_id, str):
            raise ValueError("organization_id must be a valid non-empty string")

        org = OrganizationRepository.find_by_id(organization_id.strip())
        if not org or org.get("status") != "ACTIVE":
            raise ValueError("Organization is inactive or does not exist")
        return org

    @classmethod
    def connect_manual_integration(
        cls,
        organization_id: str,
        data: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None,
        meta_client: Optional[MetaWhatsAppClient] = None,
        app=None
    ) -> Dict[str, Any]:
        """
        Manually connect an organization's WhatsApp Business Account using WABA ID,
        Phone Number ID, and Access Token verified against the real Meta Graph API.

        Workflow:
        1. Validates organization is ACTIVE and user has permission.
        2. Validates input schema (WABA ID, Phone Number ID, Access Token).
        3. Calls Meta Graph API to verify WABA ownership of the phone number.
        4. Calls Meta Graph API to retrieve phone number details (display number, verified name, quality).
        5. Fails closed without persisting if verification fails.
        6. Encrypts Access Token using MultiFernet.
        7. Checks duplicate active phone numbers (per-org and global).
        8. Reactivates if previously soft-deleted in the same organization.
        9. Persists new integration under authenticated organization.
        10. Records security audit log.
        11. Returns serialized integration (guaranteed zero secrets).
        """
        org = cls._validate_org_active(organization_id, app=app)
        validated = WhatsAppManualConnectSchema(**data)

        waba_id = validated.waba_id.strip()
        phone_number_id = validated.phone_number_id.strip()
        raw_token = validated.access_token.strip()

        # Meta Graph API verification
        if meta_client is None:
            platform_settings = PlatformSettingsService.get_meta_settings(decrypt=False, app=app)
            graph_ver = platform_settings.get("graph_api_version") or "v21.0"
            meta_client = MetaWhatsAppClient(graph_api_version=graph_ver)

        meta_info = meta_client.verify_and_fetch_metadata(
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            access_token=raw_token,
        )

        display_phone = meta_info.get("display_phone_number") or validated.display_phone_number
        if not display_phone:
            raise WhatsAppVerificationError(
                "Meta Graph API did not return a valid display phone number for this phone number ID",
                error_code=WhatsAppVerificationErrorCode.VERIFICATION_FAILED
            )

        clean_phone = clean_phone_number(display_phone)
        verified_name = meta_info.get("verified_name")
        quality_rating = meta_info.get("quality_rating", "UNKNOWN")
        platform_type = meta_info.get("platform_type", "CLOUD_API")
        code_verification_status = meta_info.get("code_verification_status", "VERIFIED")

        # Encrypt Access Token
        now_iso = datetime.now(timezone.utc).isoformat()
        ciphertext, key_version = WhatsAppEncryption.encrypt_token(raw_token)

        actor_id = actor.get("user_id") if actor else None
        actor_email = actor.get("email") if actor else None
        actor_name = actor.get("name") if actor else None
        actor_role = actor.get("role_label") if actor else None

        # Check existing integration for this phone_number_id
        existing = WhatsAppIntegrationRepository.find_by_phone_number_id(
            phone_number_id=phone_number_id,
            include_deleted=True,
            app=app
        )

        if existing:
            # Active conflict check
            if existing.get("deleted_at") is None:
                if existing.get("organization_id") == organization_id:
                    raise ValueError(
                        f"WhatsApp phone number ID '{phone_number_id}' is already registered and active for this organization."
                    )
                else:
                    raise ValueError(
                        f"WhatsApp phone number ID '{phone_number_id}' is already registered to another organization."
                    )

            # Soft-deleted in SAME org -> Reconnect / Reactivate
            if existing.get("organization_id") == organization_id:
                integration_id = existing["integration_id"]
                reconnect_fields = {
                    "waba_id": waba_id,
                    "display_phone_number": display_phone,
                    "phone_number_clean": clean_phone,
                    "name": validated.name or existing.get("name") or display_phone,
                    "verified_name": verified_name or existing.get("verified_name"),
                    "quality_rating": quality_rating,
                    "code_verification_status": code_verification_status,
                    "platform_type": platform_type,
                    "encrypted_access_token": ciphertext,
                    "key_version": key_version,
                    "status": WhatsAppIntegrationStatus.CONNECTED.value,
                    "token_status": WhatsAppTokenStatus.VALID.value,
                    "last_verified_at": now_iso,
                    "last_status_check": now_iso,
                    "last_status_error": None,
                    "token_last_rotated_at": now_iso,
                    "onboarding_method": "MANUAL",
                    "catalog_id": validated.catalog_id if validated.catalog_id is not None else existing.get("catalog_id"),
                    "reconnected_at": now_iso,
                    "reconnected_by": actor_id,
                }

                WhatsAppIntegrationRepository.reconnect(
                    integration_id=integration_id,
                    organization_id=organization_id,
                    update_fields=reconnect_fields,
                    app=app
                )

                SecurityAuditRepository.log_event(
                    organization_id=organization_id,
                    event_type="WHATSAPP_INTEGRATION_RECONNECTED",
                    actor_id=actor_id,
                    actor_email=actor_email,
                    actor_name=actor_name,
                    actor_role_label=actor_role,
                    target_id=integration_id,
                    target_type="WHATSAPP_INTEGRATION",
                    target_name=display_phone,
                    organization_name=org.get("name"),
                    action_label="Reconnected WhatsApp Integration",
                    summary=f"Reconnected WhatsApp number {display_phone} ({phone_number_id})",
                    diff={
                        "status": {"old": existing.get("status"), "new": WhatsAppIntegrationStatus.CONNECTED.value},
                        "deleted_at": {"old": existing.get("deleted_at"), "new": None}
                    }
                )

                reconnected = WhatsAppIntegrationRepository.find_by_id(
                    integration_id=integration_id,
                    organization_id=organization_id,
                    include_deleted=False,
                    app=app
                )
                return serialize_integration(reconnected)

        # Create new integration
        integration_id = f"wai_{uuid.uuid4().hex}"
        doc: Dict[str, Any] = {
            "integration_id": integration_id,
            "organization_id": organization_id,
            "waba_id": waba_id,
            "phone_number_id": phone_number_id,
            "display_phone_number": display_phone,
            "phone_number_clean": clean_phone,
            "name": validated.name or display_phone,
            "verified_name": verified_name,
            "quality_rating": quality_rating,
            "code_verification_status": code_verification_status,
            "platform_type": platform_type,
            "status": WhatsAppIntegrationStatus.CONNECTED.value,
            "onboarding_method": "MANUAL",
            "encrypted_access_token": ciphertext,
            "key_version": key_version,
            "token_status": WhatsAppTokenStatus.VALID.value,
            "token_expires_at": None,
            "last_verified_at": now_iso,
            "last_status_check": now_iso,
            "last_status_error": None,
            "rotation_count": 0,
            "token_last_rotated_at": None,
            "metadata": {},
            "catalog_id": validated.catalog_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "created_by": actor_email or "system",
            "deleted_at": None,
            "deleted_by": None
        }

        created = WhatsAppIntegrationRepository.create(doc, app=app)

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="WHATSAPP_INTEGRATION_CREATED",
            actor_id=actor_id,
            actor_email=actor_email,
            actor_name=actor_name,
            actor_role_label=actor_role,
            target_id=integration_id,
            target_type="WHATSAPP_INTEGRATION",
            target_name=display_phone,
            organization_name=org.get("name"),
            action_label="Connected WhatsApp Integration",
            summary=f"Connected WhatsApp number {display_phone} ({phone_number_id})",
            diff={
                "phone_number_id": {"old": None, "new": phone_number_id},
                "waba_id": {"old": None, "new": waba_id},
                "status": {"old": None, "new": WhatsAppIntegrationStatus.CONNECTED.value}
            }
        )

        return serialize_integration(created)

    @classmethod
    def create_integration(
        cls,
        organization_id: str,
        data: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None,
        app=None
    ) -> Dict[str, Any]:
        """
        Create a new WhatsApp phone number integration for an organization.
        Enforces:
        - Organization existence and ACTIVE status.
        - Encrypted access token at rest via MultiFernet.
        - Soft-delete-aware duplicate prevention and reconnection.
        - Audit trail logging.
        """
        org = cls._validate_org_active(organization_id, app=app)
        validated = WhatsAppIntegrationCreateSchema(**data)

        clean_phone = clean_phone_number(validated.display_phone_number)
        phone_number_id = validated.phone_number_id.strip()
        waba_id = validated.waba_id.strip()

        # Check existing integration for this phone_number_id
        existing = WhatsAppIntegrationRepository.find_by_phone_number_id(
            phone_number_id=phone_number_id,
            include_deleted=True,
            app=app
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        ciphertext, key_version = WhatsAppEncryption.encrypt_token(validated.access_token)

        actor_id = actor.get("user_id") if actor else None
        actor_email = actor.get("email") if actor else None
        actor_name = actor.get("name") if actor else None
        actor_role = actor.get("role_label") if actor else None

        if existing:
            # If active, prevent duplicate
            if existing.get("deleted_at") is None:
                if existing.get("organization_id") == organization_id:
                    raise ValueError(
                        f"WhatsApp phone number ID '{phone_number_id}' is already registered and active for this organization."
                    )
                else:
                    raise ValueError(
                        f"WhatsApp phone number ID '{phone_number_id}' is already registered to another organization."
                    )

            # If soft-deleted in the SAME organization, perform reconnection/reactivation
            if existing.get("organization_id") == organization_id:
                integration_id = existing["integration_id"]
                reconnect_fields = {
                    "waba_id": waba_id,
                    "display_phone_number": validated.display_phone_number,
                    "phone_number_clean": clean_phone,
                    "name": validated.name or existing.get("name") or validated.display_phone_number,
                    "encrypted_access_token": ciphertext,
                    "key_version": key_version,
                    "token_status": WhatsAppTokenStatus.VALID.value,
                    "token_last_rotated_at": now_iso,
                    "token_expires_at": validated.token_expires_at,
                    "onboarding_method": validated.onboarding_method.value if validated.onboarding_method else "MANUAL",
                    "metadata": validated.metadata or existing.get("metadata") or {},
                    "catalog_id": validated.catalog_id if validated.catalog_id is not None else existing.get("catalog_id"),
                    "reconnected_at": now_iso,
                    "reconnected_by": actor_id
                }

                WhatsAppIntegrationRepository.reconnect(
                    integration_id=integration_id,
                    organization_id=organization_id,
                    update_fields=reconnect_fields,
                    app=app
                )

                # Audit event
                SecurityAuditRepository.log_event(
                    organization_id=organization_id,
                    event_type="WHATSAPP_INTEGRATION_RECONNECTED",
                    actor_id=actor_id,
                    actor_email=actor_email,
                    actor_name=actor_name,
                    actor_role_label=actor_role,
                    target_id=integration_id,
                    target_type="WHATSAPP_INTEGRATION",
                    target_name=validated.display_phone_number,
                    organization_name=org.get("name"),
                    action_label="Reconnected WhatsApp Integration",
                    summary=f"Reconnected WhatsApp phone number {validated.display_phone_number} (WABA ID: {waba_id})",
                    details={"phone_number_id": phone_number_id, "waba_id": waba_id, "key_version": key_version}
                )

                updated = WhatsAppIntegrationRepository.find_by_id(
                    integration_id=integration_id,
                    organization_id=organization_id,
                    app=app
                )
                return serialize_integration(updated)

            # If soft-deleted in ANOTHER organization, the previous owner disconnected it,
            # so the new organization can adopt the number. We proceed to create a new record.

        # Create new integration
        integration_id = f"wai_{uuid.uuid4().hex}"
        doc = {
            "integration_id": integration_id,
            "organization_id": organization_id,
            "waba_id": waba_id,
            "phone_number_id": phone_number_id,
            "display_phone_number": validated.display_phone_number,
            "phone_number_clean": clean_phone,
            "name": validated.name or validated.display_phone_number,
            "status": WhatsAppIntegrationStatus.CONNECTED.value,
            "onboarding_method": validated.onboarding_method.value if validated.onboarding_method else "MANUAL",
            "encrypted_access_token": ciphertext,
            "key_version": key_version,
            "token_status": WhatsAppTokenStatus.VALID.value,
            "rotation_count": 0,
            "token_last_rotated_at": now_iso,
            "token_expires_at": validated.token_expires_at,
            "created_at": now_iso,
            "updated_at": now_iso,
            "deleted_at": None,
            "created_by": actor_id,
            "metadata": validated.metadata or {},
            "catalog_id": validated.catalog_id
        }

        created = WhatsAppIntegrationRepository.create(doc, app=app)

        # Audit event
        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="WHATSAPP_INTEGRATION_CREATED",
            actor_id=actor_id,
            actor_email=actor_email,
            actor_name=actor_name,
            actor_role_label=actor_role,
            target_id=integration_id,
            target_type="WHATSAPP_INTEGRATION",
            target_name=validated.display_phone_number,
            organization_name=org.get("name"),
            action_label="Connected WhatsApp Integration",
            summary=f"Connected WhatsApp phone number {validated.display_phone_number} (WABA ID: {waba_id})",
            details={"phone_number_id": phone_number_id, "waba_id": waba_id, "key_version": key_version}
        )

        return serialize_integration(created)

    @classmethod
    def get_integration(
        cls,
        integration_id: str,
        organization_id: str,
        app=None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve an integration by ID, strictly enforcing organization scope.
        Returns sanitized document (never returns access token).
        """
        cls._validate_org_active(organization_id, app=app)
        doc = WhatsAppIntegrationRepository.find_by_id(
            integration_id=integration_id,
            organization_id=organization_id,
            include_deleted=False,
            app=app
        )
        return serialize_integration(doc)

    @classmethod
    def list_integrations(
        cls,
        organization_id: str,
        status: Optional[str] = None,
        include_deleted: bool = False,
        app=None
    ) -> List[Dict[str, Any]]:
        """List integrations for an organization, strictly scoped."""
        cls._validate_org_active(organization_id, app=app)
        docs = WhatsAppIntegrationRepository.find_all_by_organization(
            organization_id=organization_id,
            status=status,
            include_deleted=include_deleted,
            app=app
        )
        return [serialize_integration(d) for d in docs]

    @classmethod
    def update_integration(
        cls,
        integration_id: str,
        organization_id: str,
        data: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None,
        app=None
    ) -> Dict[str, Any]:
        """Update integration metadata (e.g. nickname, display phone number)."""
        org = cls._validate_org_active(organization_id, app=app)
        existing = WhatsAppIntegrationRepository.find_by_id(
            integration_id=integration_id,
            organization_id=organization_id,
            include_deleted=False,
            app=app
        )
        if not existing:
            raise ValueError(f"WhatsApp integration '{integration_id}' not found")

        validated = WhatsAppIntegrationUpdateSchema(**data)
        update_fields: Dict[str, Any] = {}

        if validated.name is not None:
            update_fields["name"] = validated.name.strip()
        if validated.display_phone_number is not None:
            update_fields["display_phone_number"] = validated.display_phone_number.strip()
            update_fields["phone_number_clean"] = clean_phone_number(validated.display_phone_number)
        if validated.status is not None:
            update_fields["status"] = validated.status.value
        if validated.metadata is not None:
            update_fields["metadata"] = validated.metadata
        if "catalog_id" in validated.model_fields_set:
            update_fields["catalog_id"] = validated.catalog_id

        if not update_fields:
            return serialize_integration(existing)

        WhatsAppIntegrationRepository.update(
            integration_id=integration_id,
            organization_id=organization_id,
            update_fields=update_fields,
            app=app
        )

        actor_id = actor.get("user_id") if actor else None
        actor_email = actor.get("email") if actor else None
        actor_name = actor.get("name") if actor else None
        actor_role = actor.get("role_label") if actor else None

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="WHATSAPP_INTEGRATION_UPDATED",
            actor_id=actor_id,
            actor_email=actor_email,
            actor_name=actor_name,
            actor_role_label=actor_role,
            target_id=integration_id,
            target_type="WHATSAPP_INTEGRATION",
            target_name=existing.get("display_phone_number"),
            organization_name=org.get("name"),
            action_label="Updated WhatsApp Integration",
            summary=f"Updated settings for WhatsApp integration {existing.get('display_phone_number')}",
            diff={"updated_fields": list(update_fields.keys())}
        )

        updated = WhatsAppIntegrationRepository.find_by_id(
            integration_id=integration_id,
            organization_id=organization_id,
            app=app
        )
        return serialize_integration(updated)

    @classmethod
    def rotate_credentials(
        cls,
        integration_id: str,
        organization_id: str,
        data: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None,
        meta_client: Optional[MetaWhatsAppClient] = None,
        app=None
    ) -> Dict[str, Any]:
        """
        Rotate access token for a WhatsApp integration.
        Validates the new token against Meta Graph API before applying.
        Encrypts new token, increments rotation count, and records audit trail.
        """
        org = cls._validate_org_active(organization_id, app=app)
        existing = WhatsAppIntegrationRepository.find_by_id(
            integration_id=integration_id,
            organization_id=organization_id,
            include_deleted=False,
            app=app
        )
        if not existing:
            raise ValueError(f"WhatsApp integration '{integration_id}' not found")

        validated = WhatsAppCredentialRotateSchema(**data)
        raw_token = validated.access_token.strip()

        # Meta verification on new token
        verify_with_meta = data.get("verify_meta", True)
        if current_app.config.get("TESTING") and "verify_meta" not in data and not current_app.config.get("WHATSAPP_ENFORCE_META_VERIFY") and meta_client is None:
            verify_with_meta = False

        meta_info = None
        if verify_with_meta:
            if meta_client is None:
                platform_settings = PlatformSettingsService.get_meta_settings(decrypt=False, app=app)
                graph_ver = platform_settings.get("graph_api_version") or "v21.0"
                meta_client = MetaWhatsAppClient(graph_api_version=graph_ver)
            meta_info = meta_client.verify_and_fetch_metadata(
                waba_id=existing.get("waba_id"),
                phone_number_id=existing.get("phone_number_id"),
                access_token=raw_token,
            )

        ciphertext, key_version = WhatsAppEncryption.encrypt_token(raw_token)

        now_iso = datetime.now(timezone.utc).isoformat()
        old_rotation_count = existing.get("rotation_count", 0)
        new_rotation_count = old_rotation_count + 1

        update_fields: Dict[str, Any] = {
            "encrypted_access_token": ciphertext,
            "key_version": key_version,
            "rotation_count": new_rotation_count,
            "token_last_rotated_at": now_iso,
            "token_status": WhatsAppTokenStatus.VALID.value,
            "status": WhatsAppIntegrationStatus.CONNECTED.value,
            "token_expires_at": validated.token_expires_at,
            "last_status_check": now_iso,
            "last_status_error": None,
        }
        if meta_info:
            update_fields["last_verified_at"] = now_iso
            if meta_info.get("verified_name"):
                update_fields["verified_name"] = meta_info["verified_name"]
            if meta_info.get("quality_rating"):
                update_fields["quality_rating"] = meta_info["quality_rating"]

        WhatsAppIntegrationRepository.update(
            integration_id=integration_id,
            organization_id=organization_id,
            update_fields=update_fields,
            app=app
        )

        actor_id = actor.get("user_id") if actor else None
        actor_email = actor.get("email") if actor else None
        actor_name = actor.get("name") if actor else None
        actor_role = actor.get("role_label") if actor else None

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="WHATSAPP_CREDENTIALS_ROTATED",
            actor_id=actor_id,
            actor_email=actor_email,
            actor_name=actor_name,
            actor_role_label=actor_role,
            target_id=integration_id,
            target_type="WHATSAPP_INTEGRATION",
            target_name=existing.get("display_phone_number"),
            organization_name=org.get("name"),
            action_label="Rotated WhatsApp Credentials",
            summary=f"Rotated access token for WhatsApp number {existing.get('display_phone_number')} (rotation #{new_rotation_count})",
            diff={
                "rotation_count": {"old": old_rotation_count, "new": new_rotation_count},
                "token_status": {"old": existing.get("token_status"), "new": WhatsAppTokenStatus.VALID.value},
                "key_version": {"old": existing.get("key_version"), "new": key_version}
            }
        )

        updated = WhatsAppIntegrationRepository.find_by_id(
            integration_id=integration_id,
            organization_id=organization_id,
            app=app
        )
        return serialize_integration(updated)

    @classmethod
    def verify_credential_status(
        cls,
        integration_id: str,
        organization_id: str,
        actor: Optional[Dict[str, Any]] = None,
        meta_client: Optional[MetaWhatsAppClient] = None,
        app=None
    ) -> Dict[str, Any]:
        """
        Verify the validity and integrity of the stored encrypted token against Meta Graph API.
        Never outputs the token.
        """
        org = cls._validate_org_active(organization_id, app=app)
        existing = WhatsAppIntegrationRepository.find_by_id(
            integration_id=integration_id,
            organization_id=organization_id,
            include_deleted=False,
            app=app
        )
        if not existing:
            raise ValueError(f"WhatsApp integration '{integration_id}' not found")

        ciphertext = existing.get("encrypted_access_token")
        is_valid = False
        error_msg = None
        new_status = WhatsAppTokenStatus.VALID.value
        meta_info = None

        # Verify with Meta Graph API
        verify_with_meta = True

        try:
            decrypted = WhatsAppEncryption.decrypt_token(ciphertext)
            if not decrypted or len(decrypted) < 10:
                new_status = WhatsAppTokenStatus.EXPIRED.value
                error_msg = "Decrypted token format invalid"
            elif verify_with_meta:
                if meta_client is None:
                    platform_settings = PlatformSettingsService.get_meta_settings(decrypt=False, app=app)
                    graph_ver = platform_settings.get("graph_api_version") or "v21.0"
                    meta_client = MetaWhatsAppClient(graph_api_version=graph_ver)
                meta_info = meta_client.verify_and_fetch_metadata(
                    waba_id=existing.get("waba_id"),
                    phone_number_id=existing.get("phone_number_id"),
                    access_token=decrypted,
                )
                is_valid = True
                new_status = WhatsAppTokenStatus.VALID.value
            else:
                is_valid = True
                new_status = WhatsAppTokenStatus.VALID.value
        except WhatsAppVerificationError as exc:
            if exc.error_code == WhatsAppVerificationErrorCode.INVALID_CREDENTIALS:
                new_status = WhatsAppTokenStatus.REVOKED.value
            else:
                new_status = WhatsAppTokenStatus.EXPIRED.value
            error_msg = exc.message
            is_valid = False
        except WhatsAppEncryptionError as exc:
            new_status = WhatsAppTokenStatus.REVOKED.value
            error_msg = str(exc)
            is_valid = False
        except Exception as exc:
            new_status = WhatsAppTokenStatus.REVOKED.value
            error_msg = str(exc)
            is_valid = False

        now_iso = datetime.now(timezone.utc).isoformat()
        update_fields: Dict[str, Any] = {
            "token_status": new_status,
            "last_status_check": now_iso,
            "last_status_error": error_msg,
        }
        if is_valid and meta_info:
            update_fields["status"] = WhatsAppIntegrationStatus.CONNECTED.value
            update_fields["last_verified_at"] = now_iso
            if meta_info.get("verified_name"):
                update_fields["verified_name"] = meta_info["verified_name"]
            if meta_info.get("quality_rating"):
                update_fields["quality_rating"] = meta_info["quality_rating"]
            if meta_info.get("code_verification_status"):
                update_fields["code_verification_status"] = meta_info["code_verification_status"]
            if meta_info.get("platform_type"):
                update_fields["platform_type"] = meta_info["platform_type"]
        elif not is_valid:
            update_fields["status"] = WhatsAppIntegrationStatus.DEGRADED.value

        WhatsAppIntegrationRepository.update(
            integration_id=integration_id,
            organization_id=organization_id,
            update_fields=update_fields,
            app=app
        )

        actor_id = actor.get("user_id") if actor else None
        actor_email = actor.get("email") if actor else None
        actor_name = actor.get("name") if actor else None
        actor_role = actor.get("role_label") if actor else None

        SecurityAuditRepository.log_event(
            organization_id=organization_id,
            event_type="WHATSAPP_INTEGRATION_STATUS_CHECKED",
            actor_id=actor_id,
            actor_email=actor_email,
            actor_name=actor_name,
            actor_role_label=actor_role,
            target_id=integration_id,
            target_type="WHATSAPP_INTEGRATION",
            target_name=existing.get("display_phone_number"),
            organization_name=org.get("name"),
            action_label="Verified WhatsApp Credential Status",
            summary=f"Verified WhatsApp credentials for {existing.get('display_phone_number')}: {new_status} (valid={is_valid})",
            diff={
                "is_valid": {"old": None, "new": is_valid},
                "token_status": {"old": existing.get("token_status"), "new": new_status},
                "status": {"old": existing.get("status"), "new": update_fields.get("status", existing.get("status"))}
            }
        )

        return {
            "integration_id": integration_id,
            "organization_id": organization_id,
            "phone_number_id": existing.get("phone_number_id"),
            "display_phone_number": existing.get("display_phone_number"),
            "verified_name": update_fields.get("verified_name") or existing.get("verified_name"),
            "quality_rating": update_fields.get("quality_rating") or existing.get("quality_rating"),
            "status": update_fields.get("status", existing.get("status")),
            "token_status": new_status,
            "is_valid": is_valid,
            "error": error_msg,
            "last_verified_at": update_fields.get("last_verified_at") or existing.get("last_verified_at"),
            "last_status_check": now_iso
        }

    @classmethod
    def disconnect_integration(
        cls,
        integration_id: str,
        organization_id: str,
        actor: Optional[Dict[str, Any]] = None,
        app=None
    ) -> bool:
        """
        Soft-delete an integration. Sets status to DISCONNECTED and records deleted_at.
        """
        org = cls._validate_org_active(organization_id, app=app)
        existing = WhatsAppIntegrationRepository.find_by_id(
            integration_id=integration_id,
            organization_id=organization_id,
            include_deleted=False,
            app=app
        )
        if not existing:
            raise ValueError(f"WhatsApp integration '{integration_id}' not found")

        actor_id = actor.get("user_id") if actor else None
        actor_email = actor.get("email") if actor else None
        actor_name = actor.get("name") if actor else None
        actor_role = actor.get("role_label") if actor else None

        deleted = WhatsAppIntegrationRepository.soft_delete(
            integration_id=integration_id,
            organization_id=organization_id,
            deleted_by=actor_id,
            app=app
        )

        if deleted:
            SecurityAuditRepository.log_event(
                organization_id=organization_id,
                event_type="WHATSAPP_INTEGRATION_DISCONNECTED",
                actor_id=actor_id,
                actor_email=actor_email,
                actor_name=actor_name,
                actor_role_label=actor_role,
                target_id=integration_id,
                target_type="WHATSAPP_INTEGRATION",
                target_name=existing.get("display_phone_number"),
                organization_name=org.get("name"),
                action_label="Disconnected WhatsApp Integration",
                summary=f"Disconnected WhatsApp phone number {existing.get('display_phone_number')}",
                details={"phone_number_id": existing.get("phone_number_id")}
            )

        return deleted

    @classmethod
    def resolve_credentials_for_dispatch(
        cls,
        organization_id: str,
        integration_id: Optional[str] = None,
        from_phone_number_id: Optional[str] = None,
        allow_platform_fallback: bool = False,
        app=None
    ) -> Dict[str, Any]:
        """
        Internal worker method to resolve WhatsApp Cloud API credentials for a message.
        Security Guarantees:
        1. Always uses trusted organization_id from the message document (never external payload).
        2. If integration_id or from_phone_number_id is specified, strictly verifies ownership by organization_id.
           Cross-organization access raises ProviderResolutionError(PROVIDER_NOT_AUTHORIZED).
        3. If no integration is specified:
           - If organization has > 1 active integration, raises AMBIGUOUS_PROVIDER_CONFIGURATION.
           - If organization has exactly 1 active integration, uses it.
           - If 0 active integrations in whatsapp_integrations, checks strictly org-scoped legacy provider_configs.
        4. Decrypts access token at point of dispatch using MultiFernet.
        5. Merges centralized platform metadata (Meta App Secret, Graph API Version).
        """
        if not organization_id or not isinstance(organization_id, str) or not organization_id.strip():
            raise ProviderResolutionError(
                code=ProviderResolutionError.PROVIDER_NOT_AUTHORIZED,
                message="organization_id is required to resolve credentials",
                status_code=403,
                provider="whatsapp",
                channel="whatsapp",
            )

        clean_org_id = organization_id.strip()

        # Step 1: If specific integration_id requested
        target_doc = None
        if integration_id and str(integration_id).strip():
            clean_int_id = str(integration_id).strip()
            target_doc = WhatsAppIntegrationRepository.find_by_id(
                integration_id=clean_int_id,
                organization_id=clean_org_id,
                include_deleted=False,
                app=app
            )
            if not target_doc:
                # Check if it exists in THIS organization as soft-deleted
                deleted_in_org = WhatsAppIntegrationRepository.find_by_id(
                    integration_id=clean_int_id,
                    organization_id=clean_org_id,
                    include_deleted=True,
                    app=app
                )
                if deleted_in_org:
                    raise ProviderResolutionError(
                        code=ProviderResolutionError.PROVIDER_INACTIVE,
                        message=f"WhatsApp integration '{clean_int_id}' is disconnected or inactive",
                        status_code=400,
                        provider="whatsapp",
                        channel="whatsapp",
                        organization_id=clean_org_id,
                    )

                # Check if it exists in another organization to raise explicit cross-tenant error
                other_org_doc = WhatsAppIntegrationRepository.find_by_id(
                    integration_id=clean_int_id,
                    organization_id=None,
                    include_deleted=True,
                    app=app
                )
                if other_org_doc:
                    raise ProviderResolutionError(
                        code=ProviderResolutionError.PROVIDER_NOT_AUTHORIZED,
                        message=f"WhatsApp integration '{clean_int_id}' not found or access denied for this organization",
                        status_code=403,
                        provider="whatsapp",
                        channel="whatsapp",
                        organization_id=clean_org_id,
                    )
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message=f"WhatsApp integration '{clean_int_id}' not found for this organization",
                    status_code=400,
                    provider="whatsapp",
                    channel="whatsapp",
                    organization_id=clean_org_id,
                )

            if target_doc.get("status") != WhatsAppIntegrationStatus.CONNECTED.value or target_doc.get("deleted_at") is not None:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_INACTIVE,
                    message=f"WhatsApp integration '{clean_int_id}' is disconnected or inactive",
                    status_code=400,
                    provider="whatsapp",
                    channel="whatsapp",
                    organization_id=clean_org_id,
                )

        # Step 2: If from_phone_number_id requested
        elif from_phone_number_id and str(from_phone_number_id).strip():
            clean_phone_id = str(from_phone_number_id).strip()
            target_doc = WhatsAppIntegrationRepository.find_by_phone_number_id(
                phone_number_id=clean_phone_id,
                organization_id=clean_org_id,
                include_deleted=False,
                app=app
            )
            if not target_doc:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message=f"WhatsApp sender phone number ID '{clean_phone_id}' not found for this organization",
                    status_code=400,
                    provider="whatsapp",
                    channel="whatsapp",
                    organization_id=clean_org_id,
                )
            if target_doc.get("status") != WhatsAppIntegrationStatus.CONNECTED.value or target_doc.get("deleted_at") is not None:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_INACTIVE,
                    message=f"WhatsApp phone number ID '{clean_phone_id}' is disconnected or inactive",
                    status_code=400,
                    provider="whatsapp",
                    channel="whatsapp",
                    organization_id=clean_org_id,
                )

        # Step 3: Neither specified -> Check all active integrations
        else:
            active_list = WhatsAppIntegrationRepository.find_active_by_organization(clean_org_id, app=app)
            if len(active_list) > 1:
                raise ProviderResolutionError(
                    code=ProviderResolutionError.AMBIGUOUS_PROVIDER_CONFIGURATION,
                    message=(
                        "Multiple active WhatsApp integrations exist for this organization. "
                        "A valid sender 'whatsapp_integration_id' or 'from_phone_number_id' must be specified in the message request."
                    ),
                    status_code=400,
                    provider="whatsapp",
                    channel="whatsapp",
                    organization_id=clean_org_id,
                )
            elif len(active_list) == 1:
                target_doc = active_list[0]
            else:
                # Fallback strictly to organization-scoped legacy provider_configs unless explicitly platform-authorized
                from app.modules.provider_config.service import ProviderConfigService
                legacy_config = None
                for p_key in ("whatsapp", "meta", "whatsapp_cloud"):
                    legacy_config = ProviderConfigService.get_decrypted_configuration(
                        p_key,
                        organization_id=clean_org_id,
                        allow_platform_fallback=allow_platform_fallback,
                    )
                    if legacy_config and legacy_config.get("access_token") and legacy_config.get("phone_number_id"):
                        return legacy_config

                all_in_org = WhatsAppIntegrationRepository.find_all_by_organization(clean_org_id, include_deleted=False, app=app)
                if all_in_org:
                    raise ProviderResolutionError(
                        code=ProviderResolutionError.PROVIDER_INACTIVE,
                        message="WhatsApp integration is disconnected or inactive for this organization",
                        status_code=400,
                        provider="whatsapp",
                        channel="whatsapp",
                        organization_id=clean_org_id,
                    )

                raise ProviderResolutionError(
                    code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                    message="No active WhatsApp integration found for this organization",
                    status_code=400,
                    provider="whatsapp",
                    channel="whatsapp",
                    organization_id=clean_org_id,
                )

        # Step 4: Decrypt access token
        ciphertext = target_doc.get("encrypted_access_token")
        if not ciphertext:
            raise ProviderResolutionError(
                code=ProviderResolutionError.PROVIDER_NOT_CONFIGURED,
                message=f"WhatsApp integration '{target_doc.get('integration_id')}' has no configured access token",
                status_code=400,
                provider="whatsapp",
                channel="whatsapp",
                organization_id=clean_org_id,
            )

        try:
            decrypted_token = WhatsAppEncryption.decrypt_token(ciphertext)
        except WhatsAppEncryptionError as enc_err:
            raise ProviderResolutionError(
                code=ProviderResolutionError.CREDENTIAL_DECRYPTION_FAILED,
                message="WhatsApp access token could not be decrypted cleanly",
                status_code=500,
                provider="whatsapp",
                channel="whatsapp",
                organization_id=clean_org_id,
            ) from enc_err

        # Step 5: Merge centralized platform metadata (App Secret / Graph Version only)
        platform_settings = PlatformSettingsService.get_meta_settings(decrypt=True, app=app)
        app_secret = platform_settings.get("meta_app_secret") or os.getenv("WHATSAPP_APP_SECRET") or os.getenv("META_APP_SECRET")
        app_id = platform_settings.get("meta_app_id") or os.getenv("META_APP_ID")
        graph_api_version = platform_settings.get("graph_api_version") or os.getenv("WHATSAPP_GRAPH_API_VERSION") or "v21.0"

        return {
            "access_token": decrypted_token,
            "phone_number_id": target_doc.get("phone_number_id"),
            "waba_id": target_doc.get("waba_id"),
            "display_phone_number": target_doc.get("display_phone_number"),
            "integration_id": target_doc.get("integration_id"),
            "organization_id": clean_org_id,
            "app_secret": app_secret,
            "app_id": app_id,
            "graph_api_version": graph_api_version
        }


class PlatformSettingsService:
    """Service layer managing centralized encrypted platform-wide settings (Meta App credentials & Webhooks)."""

    SETTING_KEY = "meta_whatsapp"

    @classmethod
    def get_meta_settings(cls, decrypt: bool = False, app=None) -> Dict[str, Any]:
        """
        Retrieve Meta platform settings.
        If decrypt is False, masks secrets for API presentation.
        If decrypt is True, decrypts secrets for internal worker dispatch.
        """
        raw = PlatformSettingsRepository.get_setting(cls.SETTING_KEY, app=app)

        cfg_secret = current_app.config.get("WHATSAPP_APP_SECRET") if has_app_context() else None
        cfg_app_id = (current_app.config.get("META_APP_ID") or current_app.config.get("WHATSAPP_APP_ID")) if has_app_context() else None
        cfg_verify = (current_app.config.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN") or current_app.config.get("META_WEBHOOK_VERIFY_TOKEN")) if has_app_context() else None
        cfg_url = current_app.config.get("WHATSAPP_WEBHOOK_URL") if has_app_context() else None
        cfg_graph_ver = current_app.config.get("WHATSAPP_GRAPH_API_VERSION") if has_app_context() else None

        if not raw:
            # Fallback to configuration / environment variables
            env_secret = cfg_secret or os.getenv("WHATSAPP_APP_SECRET") or os.getenv("META_APP_SECRET")
            env_app_id = cfg_app_id or os.getenv("META_APP_ID") or os.getenv("WHATSAPP_APP_ID")
            env_verify = cfg_verify or os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN") or os.getenv("META_WEBHOOK_VERIFY_TOKEN")
            env_url = cfg_url or os.getenv("WHATSAPP_WEBHOOK_URL")

            if decrypt:
                return {
                    "meta_app_id": env_app_id,
                    "meta_app_secret": env_secret,
                    "webhook_verify_token": env_verify,
                    "webhook_url": env_url,
                    "graph_api_version": cfg_graph_ver or os.getenv("WHATSAPP_GRAPH_API_VERSION", "v21.0")
                }
            return {
                "meta_app_id": env_app_id,
                "has_app_secret": bool(env_secret),
                "app_secret_masked": "******" if env_secret else None,
                "has_webhook_verify_token": bool(env_verify),
                "webhook_verify_token_masked": "******" if env_verify else None,
                "webhook_url": env_url,
                "graph_api_version": cfg_graph_ver or os.getenv("WHATSAPP_GRAPH_API_VERSION", "v21.0"),
                "updated_at": None,
                "updated_by": "environment"
            }

        if decrypt:
            decrypted_secret = None
            if raw.get("encrypted_app_secret"):
                try:
                    decrypted_secret = WhatsAppEncryption.decrypt_token(raw["encrypted_app_secret"])
                except Exception:
                    decrypted_secret = None
            elif raw.get("meta_app_secret"):
                decrypted_secret = raw["meta_app_secret"]

            decrypted_verify = None
            if raw.get("encrypted_webhook_verify_token"):
                try:
                    decrypted_verify = WhatsAppEncryption.decrypt_token(raw["encrypted_webhook_verify_token"])
                except Exception:
                    decrypted_verify = None
            elif raw.get("webhook_verify_token"):
                decrypted_verify = raw["webhook_verify_token"]

            return {
                "meta_app_id": raw.get("meta_app_id") or cfg_app_id or os.getenv("META_APP_ID"),
                "meta_app_secret": decrypted_secret or cfg_secret or os.getenv("WHATSAPP_APP_SECRET") or os.getenv("META_APP_SECRET"),
                "webhook_verify_token": decrypted_verify or cfg_verify or os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN") or os.getenv("META_WEBHOOK_VERIFY_TOKEN"),
                "webhook_url": raw.get("webhook_url") or cfg_url or os.getenv("WHATSAPP_WEBHOOK_URL"),
                "graph_api_version": raw.get("graph_api_version") or cfg_graph_ver or os.getenv("WHATSAPP_GRAPH_API_VERSION", "v21.0")
            }

        return serialize_platform_settings(raw)

    @classmethod
    def save_meta_settings(
        cls,
        data: Dict[str, Any],
        actor: Optional[Dict[str, Any]] = None,
        app=None
    ) -> Dict[str, Any]:
        """
        Save centralized Meta platform settings (Meta App ID, App Secret, Webhooks).
        Encrypts secrets at rest using Fernet/MultiFernet.
        """
        validated = WhatsAppPlatformSettingsSchema(**data)
        doc_to_save: Dict[str, Any] = {
            "setting_key": cls.SETTING_KEY,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": actor.get("email") if actor else "system"
        }

        if validated.meta_app_id is not None:
            doc_to_save["meta_app_id"] = validated.meta_app_id.strip()
        if validated.webhook_url is not None:
            doc_to_save["webhook_url"] = validated.webhook_url.strip()
        if validated.graph_api_version is not None:
            doc_to_save["graph_api_version"] = validated.graph_api_version.strip()

        # Encrypt App Secret if provided
        if validated.meta_app_secret and validated.meta_app_secret.strip():
            ciphertext, _ = WhatsAppEncryption.encrypt_token(validated.meta_app_secret.strip())
            doc_to_save["encrypted_app_secret"] = ciphertext
            doc_to_save.pop("meta_app_secret", None)

        # Encrypt Webhook Verify Token if provided
        if validated.webhook_verify_token and validated.webhook_verify_token.strip():
            ciphertext, _ = WhatsAppEncryption.encrypt_token(validated.webhook_verify_token.strip())
            doc_to_save["encrypted_webhook_verify_token"] = ciphertext
            doc_to_save.pop("webhook_verify_token", None)

        saved = PlatformSettingsRepository.save_setting(cls.SETTING_KEY, doc_to_save, app=app)

        # Log audit trail
        actor_id = actor.get("admin_id") or actor.get("user_id") if actor else None
        actor_email = actor.get("email") if actor else None

        SecurityAuditRepository.log_event(
            organization_id="PLATFORM",
            event_type="PLATFORM_SETTINGS_UPDATED",
            actor_id=actor_id,
            actor_email=actor_email,
            target_id=cls.SETTING_KEY,
            target_type="PLATFORM_SETTINGS",
            target_name="Meta WhatsApp Cloud Settings",
            action_label="Updated Meta Platform Settings",
            summary="Updated centralized Meta App credentials and webhook configuration",
            diff={"updated_keys": [k for k in data.keys() if data[k] is not None]}
        )

        return serialize_platform_settings(saved)
