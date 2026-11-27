"""
SenderX Ingested Payload & Routing Service
Handles channel-based routing, immutable original storage, versioned edits,
DLQ delegation, pre-dispatch validation, and idempotent retries.
"""

from copy import deepcopy
from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
import uuid

from flask import current_app

from app.modules.payloads.models import (
    PayloadFailureCode,
    PayloadStatus,
    SUPPORTED_ROUTING_CHANNELS,
    CHANNEL_ALIASES,
    redact_sensitive_payload,
    validate_json_structure_and_limits,
    validate_channel_and_routing_fields,
)
from app.modules.payloads.repository import PayloadRepository
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.messages.service import MessageService


class PayloadService:
    """
    Service coordinating ingestion, channel routing, immutable payload preservation,
    versioned modifications, pre-dispatch validation, and DLQ management.
    """

    @classmethod
    def ingest_payload(
        cls,
        raw_json: Any,
        organization_id: str,
        application_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest external JSON request:
        1. Validate structure, size (<= 10MB), and depth (<= 20).
        2. Immutably preserve original JSON in ingested_payloads.
        3. Enforce channel-based routing:
           - Missing / unsupported / invalid fields -> move to DLQ.
           - Valid -> route to MessageService and queue.
        4. Maintain full audit trail.
        """
        # Reject mismatched application_id embedded inside raw JSON
        if isinstance(raw_json, dict) and raw_json.get("application_id") is not None:
            raw_app = raw_json.get("application_id")
            if not isinstance(raw_app, str):
                return {"success": False, "status_code": 400, "message": "application_id must be a string"}
            if application_id and raw_app.strip() and raw_app.strip() != str(application_id).strip():
                return {
                    "success": False,
                    "status_code": 403,
                    "message": "Application ID mismatch in payload body",
                }
            if not application_id and raw_app.strip():
                application_id = raw_app.strip()

        payload_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # -------------------------------------------------------------------
        # Step 1: Structural & DoS Validation (Root object, size, depth)
        # -------------------------------------------------------------------
        is_struct_valid, struct_code, struct_err = validate_json_structure_and_limits(raw_json)
        if not is_struct_valid:
            # Cannot safely parse as JSON object -> record in DLQ
            safe_payload = raw_json if isinstance(raw_json, dict) else {"raw_body": str(raw_json)}
            payload_doc = {
                "payload_id": payload_id,
                "organization_id": organization_id,
                "application_id": application_id,
                "channel": None,
                "original_payload": safe_payload,
                "current_payload": safe_payload,
                "version": 1,
                "received_at": now,
                "validation_status": "INVALID",
                "validation_errors": [struct_err],
                "status": PayloadStatus.IN_DLQ,
                "failure_code": struct_code,
                "failure_reason": struct_err,
                "created_by": user_id or "SYSTEM"
            }
            PayloadRepository.create(payload_doc)
            DeadLetterRepository.save_from_payload(
                payload_record=payload_doc,
                failure_code=struct_code,
                failure_reason=struct_err,
                organization_id=organization_id
            )
            PayloadRepository.log_audit(
                payload_id=payload_id,
                organization_id=organization_id,
                event_type="REQUEST_RECEIVED",
                details={"application_id": application_id, "size_valid": False},
                performed_by=user_id or "SYSTEM",
                version=1
            )
            PayloadRepository.log_audit(
                payload_id=payload_id,
                organization_id=organization_id,
                event_type="MOVED_TO_DLQ",
                details={"failure_code": struct_code, "reason": struct_err},
                performed_by="SYSTEM",
                version=1
            )
            return {
                "success": False,
                "status_code": 400,
                "payload_id": payload_id,
                "status": PayloadStatus.IN_DLQ,
                "failure_code": struct_code,
                "message": f"Payload structure invalid: {struct_err}. Moved to DLQ."
            }

        # -------------------------------------------------------------------
        # Step 2: Channel and Field Analysis
        # -------------------------------------------------------------------
        is_route_valid, normalized_channel, route_code, route_err = validate_channel_and_routing_fields(raw_json)

        original_copy = deepcopy(raw_json)
        current_copy = deepcopy(original_copy)
        if normalized_channel:
            current_copy["channel"] = normalized_channel

        payload_doc = {
            "payload_id": payload_id,
            "organization_id": organization_id,
            "application_id": application_id,
            "channel": normalized_channel,
            "original_payload": original_copy,
            "current_payload": current_copy,
            "version": 1,
            "received_at": now,
            "validation_status": "VALID" if is_route_valid else "INVALID",
            "validation_errors": [route_err] if route_err else [],
            "status": PayloadStatus.INGESTED if is_route_valid else PayloadStatus.IN_DLQ,
            "failure_code": route_code,
            "failure_reason": route_err,
            "created_by": user_id or "SYSTEM"
        }

        # Audit: Request received
        PayloadRepository.log_audit(
            payload_id=payload_id,
            organization_id=organization_id,
            event_type="REQUEST_RECEIVED",
            details={
                "application_id": application_id,
                "channel_declared": raw_json.get("channel"),
                "has_recipient": bool(raw_json.get("recipient")),
                "has_data": bool(raw_json.get("data"))
            },
            performed_by=user_id or "SYSTEM",
            version=1
        )

        # -------------------------------------------------------------------
        # Step 3: Handle Routing Failure (Missing / Unsupported / Missing fields)
        # -------------------------------------------------------------------
        if not is_route_valid:
            payload_doc["status"] = PayloadStatus.IN_DLQ
            created_record = PayloadRepository.create(payload_doc)
            DeadLetterRepository.save_from_payload(
                payload_record=created_record,
                failure_code=route_code,
                failure_reason=route_err,
                organization_id=organization_id
            )
            PayloadRepository.log_audit(
                payload_id=payload_id,
                organization_id=organization_id,
                event_type="VALIDATION_FAILED",
                details={"failure_code": route_code, "reason": route_err},
                performed_by="SYSTEM",
                version=1
            )
            PayloadRepository.log_audit(
                payload_id=payload_id,
                organization_id=organization_id,
                event_type="MOVED_TO_DLQ",
                details={"failure_code": route_code, "reason": route_err},
                performed_by="SYSTEM",
                version=1
            )
            return {
                "success": False,
                "status_code": 400,
                "payload_id": payload_id,
                "status": PayloadStatus.IN_DLQ,
                "channel": normalized_channel,
                "failure_code": route_code,
                "message": f"Payload routing failed: {route_err}. Moved to DLQ."
            }

        # -------------------------------------------------------------------
        # Step 4: Production Mock Provider Guard
        # -------------------------------------------------------------------
        app_env = current_app.config.get("APP_ENV", "development").lower()
        requested_provider = (raw_json.get("provider") or "").lower().strip()
        if app_env == "production" and requested_provider == "mock":
            err_msg = "Mock provider is forbidden in production environment"
            payload_doc["validation_status"] = "INVALID"
            payload_doc["validation_errors"] = [err_msg]
            payload_doc["status"] = PayloadStatus.IN_DLQ
            payload_doc["failure_code"] = PayloadFailureCode.ROUTING_FAILED
            payload_doc["failure_reason"] = err_msg
            created_record = PayloadRepository.create(payload_doc)
            DeadLetterRepository.save_from_payload(
                payload_record=created_record,
                failure_code=PayloadFailureCode.ROUTING_FAILED,
                failure_reason=err_msg,
                organization_id=organization_id
            )
            return {
                "success": False,
                "status_code": 400,
                "payload_id": payload_id,
                "status": PayloadStatus.IN_DLQ,
                "failure_code": PayloadFailureCode.ROUTING_FAILED,
                "message": err_msg
            }

        # -------------------------------------------------------------------
        # Step 5: Route to Existing Message Dispatch Architecture
        # -------------------------------------------------------------------
        # Normalize payload channel in outgoing message object
        dispatch_payload = dict(raw_json)
        dispatch_payload["channel"] = normalized_channel

        message_res = MessageService.create_message(
            payload=dispatch_payload,
            organization_id=organization_id,
            application_id=application_id,
        )

        if not message_res.get("success"):
            err_details = message_res.get("message", "Message creation failed")
            payload_doc["validation_status"] = "INVALID"
            payload_doc["validation_errors"] = message_res.get("errors", [err_details])
            payload_doc["status"] = PayloadStatus.IN_DLQ
            payload_doc["failure_code"] = PayloadFailureCode.VALIDATION_FAILED
            payload_doc["failure_reason"] = err_details

            created_record = PayloadRepository.create(payload_doc)
            DeadLetterRepository.save_from_payload(
                payload_record=created_record,
                failure_code=PayloadFailureCode.VALIDATION_FAILED,
                failure_reason=err_details,
                organization_id=organization_id
            )
            PayloadRepository.log_audit(
                payload_id=payload_id,
                organization_id=organization_id,
                event_type="VALIDATION_FAILED",
                details={"errors": payload_doc["validation_errors"]},
                performed_by="SYSTEM",
                version=1
            )
            PayloadRepository.log_audit(
                payload_id=payload_id,
                organization_id=organization_id,
                event_type="MOVED_TO_DLQ",
                details={"reason": err_details},
                performed_by="SYSTEM",
                version=1
            )
            return {
                "success": False,
                "status_code": 400,
                "payload_id": payload_id,
                "status": PayloadStatus.IN_DLQ,
                "failure_code": PayloadFailureCode.VALIDATION_FAILED,
                "message": f"Message creation failed: {err_details}. Moved to DLQ.",
                "errors": payload_doc["validation_errors"]
            }

        created_message = message_res.get("message", {})
        message_id = created_message.get("message_id")

        # Automatically queue message in broker within trusted application scope
        queue_res = MessageService.queue_message(
            message_id=message_id,
            organization_id=organization_id,
            user_application_ids=[application_id] if application_id else None,
        )

        payload_doc["status"] = PayloadStatus.ROUTED
        payload_doc["message_id"] = message_id
        payload_record = PayloadRepository.create(payload_doc)

        PayloadRepository.log_audit(
            payload_id=payload_id,
            organization_id=organization_id,
            event_type="VALIDATION_PASSED",
            details={"channel": normalized_channel},
            performed_by="SYSTEM",
            version=1
        )
        is_queued = bool(queue_res.get("success", False)) if isinstance(queue_res, dict) else True

        PayloadRepository.log_audit(
            payload_id=payload_id,
            organization_id=organization_id,
            event_type="ROUTED_TO_CHANNEL",
            details={
                "channel": normalized_channel,
                "message_id": message_id,
                "queued": is_queued
            },
            performed_by="SYSTEM",
            version=1
        )

        return {
            "success": True,
            "status_code": 201,
            "payload_id": payload_id,
            "message_id": message_id,
            "channel": normalized_channel,
            "status": PayloadStatus.ROUTED,
            "message": "Payload ingested and routed successfully"
        }

    # -----------------------------------------------------------------------
    # 2. RETRIEVAL & QUERYING
    # -----------------------------------------------------------------------

    @staticmethod
    def _effective_single_scope(user_application_ids: Optional[List[str]], trusted_app_id: Optional[str]):
        if trusted_app_id is not None:
            return trusted_app_id
        return user_application_ids

    @classmethod
    def get_payload(
        cls,
        payload_id: str,
        organization_id: str,
        user_application_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Fetch a specific payload by ID strictly scoped to organization and application access."""
        record = PayloadRepository.find_by_id(
            payload_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )
        if not record:
            return {"success": False, "status_code": 404, "message": "Payload request not found"}
        if user_application_ids is not None and not record.get("application_id"):
            return {"success": False, "status_code": 404, "message": "Payload request not found"}

        return {
            "success": True,
            "status_code": 200,
            "data": redact_sensitive_payload(record)
        }

    @classmethod
    def list_payloads(
        cls,
        organization_id: str,
        limit: int = 50,
        page: int = 1,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        validation_status: Optional[str] = None,
        application_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_application_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """List received JSON requests with pagination, filters, and redaction."""
        effective_app_filter: Any = application_id
        if user_application_ids is not None:
            if application_id:
                if application_id not in user_application_ids:
                    return {
                        "success": True,
                        "status_code": 200,
                        "data": {
                            "items": [],
                            "pagination": {
                                "page": 1,
                                "limit": 50,
                                "total": 0,
                                "pages": 1,
                                "has_next": False,
                                "has_prev": False,
                            },
                        },
                    }
                effective_app_filter = application_id
            else:
                effective_app_filter = list(user_application_ids)

        res = PayloadRepository.find_all(
            organization_id=organization_id,
            limit=limit,
            page=page,
            status=status,
            channel=channel,
            validation_status=validation_status,
            application_id=effective_app_filter,
            start_date=start_date,
            end_date=end_date
        )
        res["items"] = [redact_sensitive_payload(item) for item in res["items"]]
        return {
            "success": True,
            "status_code": 200,
            "data": res
        }

    @classmethod
    def get_version_history(
        cls,
        payload_id: str,
        organization_id: str,
        user_application_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve complete version history for a given payload within authorized scope."""
        record = PayloadRepository.find_by_id(
            payload_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )
        if not record:
            return {"success": False, "status_code": 404, "message": "Payload request not found"}
        if user_application_ids is not None and not record.get("application_id"):
            return {"success": False, "status_code": 404, "message": "Payload request not found"}

        versions = record.get("versions", [])
        return {
            "success": True,
            "status_code": 200,
            "payload_id": payload_id,
            "application_id": record.get("application_id"),
            "current_version": record.get("version", 1),
            "versions": [redact_sensitive_payload(v) for v in versions]
        }

    # -----------------------------------------------------------------------
    # 3. VERSIONED EDITING (DOES NOT AUTO-DISPATCH)
    # -----------------------------------------------------------------------

    @classmethod
    def edit_payload(
        cls,
        payload_id: str,
        organization_id: str,
        edited_json: Any,
        user_id: str,
        reason: str,
        user_application_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new payload version:
        - Preserves previous versions, original immutable payload, and ownership.
        - Rejects attempts to alter application_id or organization_id.
        - Records editor's user_id, timestamp, and reason.
        - Validates edited JSON (stores validation result).
        - DO NOT dispatch automatically! Requires explicit retry action.
        """
        record = PayloadRepository.find_by_id(
            payload_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )
        if not record:
            return {"success": False, "status_code": 404, "message": "Payload request not found"}

        trusted_app_id = record.get("application_id")
        if user_application_ids is not None and not trusted_app_id:
            return {"success": False, "status_code": 404, "message": "Payload request not found"}

        if isinstance(edited_json, dict):
            if "organization_id" in edited_json and edited_json.get("organization_id") is not None:
                if str(edited_json.get("organization_id")).strip() != str(organization_id).strip():
                    return {
                        "success": False,
                        "status_code": 403,
                        "message": "Cannot modify payload organization_id",
                    }
            if "application_id" in edited_json and edited_json.get("application_id") is not None:
                if not isinstance(edited_json.get("application_id"), str):
                    return {"success": False, "status_code": 400, "message": "application_id must be a string"}
                edited_app = edited_json.get("application_id").strip()
                if edited_app != (str(trusted_app_id).strip() if trusted_app_id else ""):
                    return {
                        "success": False,
                        "status_code": 403,
                        "message": "Cannot modify payload application_id",
                    }

        current_status = record.get("status")
        if current_status in [PayloadStatus.DISPATCHING, PayloadStatus.DISPATCHED]:
            return {
                "success": False,
                "status_code": 409,
                "message": f"Cannot edit payload in {current_status} status. Dispatched payloads are immutable."
            }

        editable_statuses = [PayloadStatus.IN_DLQ, PayloadStatus.EDITED, PayloadStatus.FAILED]
        if current_status not in editable_statuses:
            return {
                "success": False,
                "status_code": 409,
                "message": f"Cannot edit payload in {current_status} status. Only payloads in IN_DLQ, EDITED, or FAILED status can be edited."
            }

        # Validate structure, size, depth
        is_struct_valid, struct_code, struct_err = validate_json_structure_and_limits(edited_json)
        if not is_struct_valid:
            return {
                "success": False,
                "status_code": 400,
                "message": f"Edited payload structure invalid: {struct_err}"
            }

        # Validate routing & channel fields + security threats
        from app.validators.dynamic_json_validator import DynamicJSONValidator

        is_valid, norm_channel, route_code, route_err = validate_channel_and_routing_fields(edited_json)
        _, threats = DynamicJSONValidator.scan_for_markup_and_threats(edited_json)
        validation_errors = []
        if route_err:
            validation_errors.append(route_err)
        if threats:
            validation_errors.extend(threats)
            is_valid = False
        validation_status = "VALID" if is_valid else "INVALID"

        edited_payload_to_store = deepcopy(edited_json)
        if norm_channel:
            edited_payload_to_store["channel"] = norm_channel
        if trusted_app_id is not None:
            edited_payload_to_store["application_id"] = trusted_app_id
        else:
            edited_payload_to_store.pop("application_id", None)
        edited_payload_to_store.pop("organization_id", None)

        scope_filter = cls._effective_single_scope(user_application_ids, trusted_app_id)
        updated = PayloadRepository.add_version(
            payload_id=payload_id,
            organization_id=organization_id,
            new_payload=edited_payload_to_store,
            edited_by=user_id,
            reason=reason,
            validation_status=validation_status,
            validation_errors=validation_errors,
            new_channel=norm_channel,
            application_ids=scope_filter,
        )

        if not updated:
            return {"success": False, "status_code": 500, "message": "Failed to save edited payload version"}

        # Sync edited payload to DLQ if record exists within same organization + application
        DeadLetterRepository.update_payload_in_dlq(
            payload_id=payload_id,
            organization_id=organization_id,
            current_payload=edited_payload_to_store,
            payload_version=updated["version"],
            channel=norm_channel,
            recipient=edited_payload_to_store.get("recipient"),
            application_ids=scope_filter,
        )

        # Audit logs
        PayloadRepository.log_audit(
            payload_id=payload_id,
            organization_id=organization_id,
            event_type="PAYLOAD_EDITED",
            details={
                "version": updated["version"],
                "reason": reason,
                "channel": norm_channel,
                "application_id": trusted_app_id,
            },
            performed_by=user_id,
            version=updated["version"],
            application_id=trusted_app_id,
        )
        PayloadRepository.log_audit(
            payload_id=payload_id,
            organization_id=organization_id,
            event_type="VALIDATION_AFTER_EDIT",
            details={
                "version": updated["version"],
                "validation_status": validation_status,
                "errors": validation_errors,
                "application_id": trusted_app_id,
            },
            performed_by=user_id,
            version=updated["version"],
            application_id=trusted_app_id,
        )

        return {
            "success": True,
            "status_code": 200,
            "message": f"Payload edited successfully to version {updated['version']}. Automatic dispatch was NOT triggered.",
            "data": redact_sensitive_payload(updated),
            "validation": {
                "valid": is_valid,
                "channel": norm_channel,
                "errors": validation_errors
            }
        }

    # -----------------------------------------------------------------------
    # 4. PRE-DISPATCH VALIDATION
    # -----------------------------------------------------------------------

    @classmethod
    def validate_payload(
        cls,
        payload_id: str,
        organization_id: str,
        version_num: Optional[int] = None,
        user_application_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Validate an edited payload without dispatching."""
        record = PayloadRepository.find_by_id(
            payload_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )
        if not record:
            return {"success": False, "status_code": 404, "message": "Payload request not found"}
        if user_application_ids is not None and not record.get("application_id"):
            return {"success": False, "status_code": 404, "message": "Payload request not found"}

        # Target payload version
        target_payload = record.get("current_payload")
        if version_num is not None:
            target_payload = None
            for v in record.get("versions", []):
                if v.get("version") == version_num:
                    target_payload = v.get("payload")
                    break

        if not target_payload:
            return {"success": False, "status_code": 404, "message": f"Version {version_num} not found"}

        is_struct_valid, _, struct_err = validate_json_structure_and_limits(target_payload)
        if not is_struct_valid:
            return {
                "success": True,
                "status_code": 200,
                "valid": False,
                "errors": [struct_err],
                "payload_id": payload_id
            }

        from app.validators.dynamic_json_validator import DynamicJSONValidator

        is_route_valid, channel, _, route_err = validate_channel_and_routing_fields(target_payload)
        _, threats = DynamicJSONValidator.scan_for_markup_and_threats(target_payload)
        errors = [route_err] if route_err else []
        if threats:
            errors.extend(threats)
            is_route_valid = False

        return {
            "success": True,
            "status_code": 200,
            "valid": is_route_valid,
            "status": DynamicJSONValidator.THREAT_STATUS if threats else (
                DynamicJSONValidator.VALID_STATUS if is_route_valid else DynamicJSONValidator.INVALID_STATUS
            ),
            "threats": threats,
            "channel": channel,
            "errors": errors,
            "payload_id": payload_id,
            "version": version_num or record.get("version", 1)
        }

    # -----------------------------------------------------------------------
    # 5. IDEMPOTENT RETRY & DISPATCH
    # -----------------------------------------------------------------------

    @classmethod
    def retry_payload(
        cls,
        payload_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
        user_application_ids: Optional[List[str]] = None,
        expected_application_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Explicit action to revalidate and dispatch an eligible payload.
        Idempotent: prevents duplicate dispatch and preserves original application ownership.
        """
        record = PayloadRepository.find_by_id(
            payload_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )
        if not record:
            return {"success": False, "status_code": 404, "message": "Payload request not found"}

        trusted_app_id = record.get("application_id")
        if user_application_ids is not None and not trusted_app_id:
            return {"success": False, "status_code": 404, "message": "Payload request not found"}

        if expected_application_id is not None and str(trusted_app_id or "") != str(expected_application_id):
            return {
                "success": False,
                "status_code": 409,
                "message": "Ambiguous or mismatched application ownership on payload record",
            }

        app_ok, app_err = MessageService._validate_persisted_application_active(trusted_app_id, organization_id)
        if not app_ok:
            return {"success": False, "status_code": 403, "message": app_err}

        scope_filter = cls._effective_single_scope(user_application_ids, trusted_app_id)
        current_status = record.get("status")
        if current_status == PayloadStatus.DISPATCHED:
            return {
                "success": False,
                "status_code": 409,
                "message": f"Payload {payload_id} has already been dispatched. Duplicate dispatch prevented.",
                "message_id": record.get("message_id")
            }

        if current_status == PayloadStatus.DISPATCHING:
            return {
                "success": False,
                "status_code": 409,
                "message": f"Payload {payload_id} is currently being dispatched"
            }

        # 1. Revalidate current payload version
        current_payload = record.get("current_payload") or {}
        if isinstance(current_payload, dict) and current_payload.get("application_id"):
            if str(current_payload.get("application_id")).strip() != str(trusted_app_id or "").strip():
                return {
                    "success": False,
                    "status_code": 409,
                    "message": "Payload body application_id conflicts with persisted ownership",
                }

        is_struct_valid, _, struct_err = validate_json_structure_and_limits(current_payload)
        if not is_struct_valid:
            PayloadRepository.log_audit(
                payload_id=payload_id,
                organization_id=organization_id,
                event_type="RETRY_ATTEMPTED",
                details={"outcome": "FAILED_PRE_DISPATCH_VALIDATION", "error": struct_err, "application_id": trusted_app_id},
                performed_by=user_id or "SYSTEM",
                version=record.get("version", 1),
                application_id=trusted_app_id,
            )
            return {
                "success": False,
                "status_code": 400,
                "message": f"Cannot dispatch payload: {struct_err}"
            }

        is_route_valid, channel, route_code, route_err = validate_channel_and_routing_fields(current_payload)
        from app.validators.dynamic_json_validator import DynamicJSONValidator
        _, threats = DynamicJSONValidator.scan_for_markup_and_threats(current_payload)
        if not is_route_valid or threats:
            combined_err = route_err or "; ".join(threats)
            PayloadRepository.log_audit(
                payload_id=payload_id,
                organization_id=organization_id,
                event_type="RETRY_ATTEMPTED",
                details={"outcome": "FAILED_PRE_DISPATCH_VALIDATION", "error": combined_err, "application_id": trusted_app_id},
                performed_by=user_id or "SYSTEM",
                version=record.get("version", 1),
                application_id=trusted_app_id,
            )
            return {
                "success": False,
                "status_code": 422 if threats else 400,
                "message": f"Cannot dispatch payload with validation errors: {combined_err}",
                "errors": ([route_err] if route_err else []) + threats
            }

        # 2. Atomic state transition to DISPATCHING with ownership filter
        transitioned = PayloadRepository.transition_to_dispatching_atomically(
            payload_id=payload_id,
            organization_id=organization_id,
            application_ids=scope_filter,
        )
        if not transitioned:
            return {
                "success": False,
                "status_code": 409,
                "message": "Payload is already dispatching or not eligible for retry"
            }

        PayloadRepository.log_audit(
            payload_id=payload_id,
            organization_id=organization_id,
            event_type="RETRY_ATTEMPTED",
            details={"version": record.get("version", 1), "channel": channel, "application_id": trusted_app_id},
            performed_by=user_id or "SYSTEM",
            version=record.get("version", 1),
            application_id=trusted_app_id,
        )

        # 3. Create message and queue dispatch strictly preserving persisted application_id
        dispatch_payload = dict(current_payload)
        dispatch_payload["channel"] = channel
        if trusted_app_id is not None:
            dispatch_payload["application_id"] = trusted_app_id
        else:
            dispatch_payload.pop("application_id", None)
        dispatch_payload.pop("organization_id", None)

        msg_res = MessageService.create_message(
            payload=dispatch_payload,
            organization_id=organization_id,
            application_id=trusted_app_id,
        )

        if not msg_res.get("success"):
            err_details = msg_res.get("message", "Message creation failed during retry")
            PayloadRepository.update_status(
                payload_id=payload_id,
                new_status=PayloadStatus.FAILED,
                organization_id=organization_id,
                failure_code=PayloadFailureCode.VALIDATION_FAILED,
                failure_reason=err_details,
                application_ids=scope_filter,
            )
            PayloadRepository.log_audit(
                payload_id=payload_id,
                organization_id=organization_id,
                event_type="DISPATCH_FAILED",
                details={"error": err_details, "application_id": trusted_app_id},
                performed_by=user_id or "SYSTEM",
                version=record.get("version", 1),
                application_id=trusted_app_id,
            )
            return {
                "success": False,
                "status_code": 400,
                "message": f"Retry dispatch failed: {err_details}",
                "errors": msg_res.get("errors", [err_details])
            }

        created_msg = msg_res.get("message", {})
        message_id = created_msg.get("message_id")

        # Queue message in Celery broker within trusted scope
        MessageService.queue_message(
            message_id=message_id,
            organization_id=organization_id,
            user_application_ids=[trusted_app_id] if trusted_app_id else user_application_ids,
        )

        # Update payload status with ownership filter
        PayloadRepository.update_status(
            payload_id=payload_id,
            new_status=PayloadStatus.DISPATCHED,
            organization_id=organization_id,
            message_id=message_id,
            application_ids=scope_filter,
        )

        # Resolve DLQ record if present within ownership filter
        DeadLetterRepository.resolve_routing_dlq(
            payload_id=payload_id,
            organization_id=organization_id,
            message_id=message_id,
            application_ids=scope_filter,
        )

        PayloadRepository.log_audit(
            payload_id=payload_id,
            organization_id=organization_id,
            event_type="DISPATCH_SUCCESS",
            details={"message_id": message_id, "channel": channel, "application_id": trusted_app_id},
            performed_by=user_id or "SYSTEM",
            version=record.get("version", 1),
            application_id=trusted_app_id,
        )

        return {
            "success": True,
            "status_code": 200,
            "payload_id": payload_id,
            "message_id": message_id,
            "application_id": trusted_app_id,
            "channel": channel,
            "status": PayloadStatus.DISPATCHED,
            "message": "Payload successfully revalidated, created, and dispatched"
        }

    # -----------------------------------------------------------------------
    # 6. AUDIT TRAIL QUERYING
    # -----------------------------------------------------------------------

    @classmethod
    def get_audit_trail(
        cls,
        payload_id: str,
        organization_id: str,
        user_application_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve audit log entries for a payload within authorized scope."""
        record = PayloadRepository.find_by_id(
            payload_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )
        if not record:
            return {"success": False, "status_code": 404, "message": "Payload request not found"}
        if user_application_ids is not None and not record.get("application_id"):
            return {"success": False, "status_code": 404, "message": "Payload request not found"}

        logs = PayloadRepository.get_audit_logs(payload_id, organization_id=organization_id)
        return {
            "success": True,
            "status_code": 200,
            "payload_id": payload_id,
            "application_id": record.get("application_id"),
            "audit_trail": logs
        }
