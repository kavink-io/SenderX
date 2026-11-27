
import hashlib
import hmac
import logging
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.engine.message_engine import MessageEngine
from app.modules.messages.repository import MessageRepository
from app.engine.status_manager import StatusManager
from app.modules.templates.service import TemplateService
from flask import current_app

logger = logging.getLogger(__name__)


class MessageService:

    WHATSAPP_CUSTOMER_SERVICE_WINDOW = timedelta(hours=24)

    @staticmethod
    def _parse_whatsapp_provider_timestamp(timestamp):
        try:
            value = float(timestamp)
            return value if value > 0 else None
        except (TypeError, ValueError, OverflowError):
            return None

    @classmethod
    def check_whatsapp_customer_service_window(
        cls, recipient, organization_id, phone_number_id, integration_id, data, now=None
    ):
        """Return whether non-template messages may be sent to this tenant's recipient.

        Only provider-supplied inbound timestamps count. Ingestion time is never
        used as a fallback, so missing/invalid provider timestamps fail closed.
        """
        data = data if isinstance(data, dict) else {}
        msg_type = str(data.get("type") or "").strip().lower()
        is_template = msg_type == "template" or bool(data.get("template") or data.get("template_name"))
        if is_template:
            return {"allowed": True, "is_template": True, "latest_inbound_at": None}

        if not recipient or not organization_id or not phone_number_id or not integration_id:
            return {
                "allowed": False,
                "is_template": False,
                "latest_inbound_at": None,
                "reason": "Cannot verify WhatsApp customer service window: recipient, organization, connected phone number, or integration is missing.",
            }

        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now_timestamp = now.timestamp()
        collection = current_app.mongo_db["inbound_messages"]
        query = {
            "channel": "whatsapp",
            "organization_id": organization_id,
            "integration_id": str(integration_id).strip(),
            "phone_number_id": str(phone_number_id).strip(),
            "from_phone": re.sub(r"\D", "", str(recipient)),
        }
        latest = None
        for record in collection.find(query, {"_id": 0, "provider_timestamp": 1, "raw_data.timestamp": 1}):
            timestamp = record.get("provider_timestamp")
            if timestamp is None:
                raw = record.get("raw_data")
                timestamp = raw.get("timestamp") if isinstance(raw, dict) else None
            value = cls._parse_whatsapp_provider_timestamp(timestamp)
            if value is not None and value <= now_timestamp and (latest is None or value > latest):
                latest = value

        if latest is None:
            return {
                "allowed": False,
                "is_template": False,
                "latest_inbound_at": None,
                "reason": "Cannot send a WhatsApp free-form message: no valid inbound customer message timestamp is available. Use an approved Meta template or wait for a customer message.",
            }

        opened_at = datetime.fromtimestamp(latest, timezone.utc)
        is_open = now < opened_at + cls.WHATSAPP_CUSTOMER_SERVICE_WINDOW
        return {
            "allowed": is_open,
            "is_template": False,
            "latest_inbound_at": opened_at.isoformat(),
            **({} if is_open else {
                "reason": "Cannot send a WhatsApp free-form message: the 24-hour customer service window has closed. Use an approved Meta template.",
            }),
        }

    @classmethod
    def create_message(cls, payload, organization_id, application_id=None):

        # Fail closed if any caller attempts to smuggle platform fallback flags
        if isinstance(payload, dict):
            nested_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            if (
                "use_platform_provider" in payload
                or "allow_platform_fallback" in payload
                or "use_platform_provider" in nested_data
                or "allow_platform_fallback" in nested_data
            ):
                return {
                    "success": False,
                    "status_code": 403,
                    "message": "Platform-level provider fallback cannot be enabled by message payloads",
                    "errors": ["Platform-level provider fallback cannot be enabled by message payloads"],
                }

        # Handle multiple recipients if a list is provided
        recipients = payload.get("recipient")
        if isinstance(recipients, list) and len(recipients) > 1:
            created_messages = []
            for single_recip in recipients:
                sub_payload = dict(payload)
                sub_payload["recipient"] = single_recip
                sub_res = cls.create_message(sub_payload, organization_id, application_id=application_id)
                if not sub_res["success"]:
                    return sub_res
                created_messages.append(sub_res["message"])

            return {
                "success": True,
                "message": created_messages[0],
                "messages": created_messages,
                "message_ids": [m["message_id"] for m in created_messages],
                "count": len(created_messages),
                "validation": {"batch_recipients": len(created_messages)}
            }
        elif isinstance(recipients, list) and len(recipients) == 1:
            payload["recipient"] = recipients[0]

        # Normalize channel to lowercase
        if payload.get("channel") and isinstance(payload["channel"], str):
            payload["channel"] = payload["channel"].lower().strip()

        # Extract template parameters if provided
        template_id = payload.get("template_id")
        template_vars = payload.get("template_variables") if payload.get("template_variables") is not None else payload.get("variables")
        template_version = payload.get("template_version")

        # Also support template params specified inside payload["data"]
        if isinstance(payload.get("data"), dict):
            if not template_id:
                template_id = payload["data"].get("template_id")
            if template_vars is None:
                template_vars = payload["data"].get("template_variables") if payload["data"].get("template_variables") is not None else payload["data"].get("variables")
            if template_version is None:
                template_version = payload["data"].get("template_version")

        # Ensure payload has a data dict
        if "data" not in payload or not isinstance(payload.get("data"), dict):
            payload["data"] = {
                k: v for k, v in payload.items()
                if k not in ("recipient", "channel", "provider", "application_id", "template_id", "template_variables", "template_version", "variables")
            }

        # Conflict check: cannot specify template_id and raw HTML body together (5.6.5)
        raw_html = None
        if isinstance(payload.get("data"), dict):
            raw_html = payload["data"].get("html") or payload["data"].get("html_body")
        if not raw_html:
            raw_html = payload.get("html") or payload.get("html_body")

        if template_id and raw_html and str(raw_html).strip():
            return {
                "success": False,
                "status_code": 422,
                "message": "Conflicting message body specification: cannot provide both 'template_id' and raw 'html'/'html_body'. Please choose either a template or provide raw HTML content.",
                "errors": ["Choose either template_id or raw HTML body"]
            }

        # Early iterative security, resource-limit, and type validation before template/media processing
        from app.validators.dynamic_json_validator import DynamicJSONValidator
        limits = DynamicJSONValidator.resolve_limits()
        inspect_res = DynamicJSONValidator.inspect_limits_and_threats(
            payload,
            limits=limits,
            allow_template_var_html=bool(template_id),
        )
        if inspect_res["limit_errors"]:
            return {
                "success": False,
                "status_code": 422,
                "status": DynamicJSONValidator.LIMIT_STATUS,
                "message": f"Payload complexity limit exceeded: {'; '.join(inspect_res['limit_errors'])}",
                "errors": inspect_res["limit_errors"]
            }
        if inspect_res["type_errors"]:
            return {
                "success": False,
                "status_code": 422,
                "status": DynamicJSONValidator.INVALID_STATUS,
                "message": f"Unsupported payload data type: {'; '.join(inspect_res['type_errors'])}",
                "errors": inspect_res["type_errors"]
            }
        threats = inspect_res["threats"]
        if threats:
            return {
                "success": False,
                "status_code": 422,
                "status": DynamicJSONValidator.THREAT_STATUS,
                "message": f"Dangerous input pattern detected: {'; '.join(threats)}",
                "errors": threats
            }

        # Raw HTML inspection & sanitization on email channel when no template_id is used (5.6.1 Item 6)
        if not template_id and payload.get("channel") == "email" and raw_html:
            from app.modules.templates.security import TemplateSecurityInspector
            html_findings = TemplateSecurityInspector.inspect_html(str(raw_html))
            if html_findings:
                return {
                    "success": False,
                    "status_code": 422,
                    "message": f"Dangerous HTML pattern detected in email body: {'; '.join(html_findings)}",
                    "errors": html_findings
                }
            # Sanitize rich HTML using allowlist
            sanitized_html = TemplateSecurityInspector.sanitize_rich_html(str(raw_html))
            if isinstance(payload.get("data"), dict):
                if "html" in payload["data"]:
                    payload["data"]["html"] = sanitized_html
                if "html_body" in payload["data"]:
                    payload["data"]["html_body"] = sanitized_html
            if "html" in payload:
                payload["html"] = sanitized_html
            if "html_body" in payload:
                payload["html_body"] = sanitized_html

        template_metadata = None

        if template_id:
            # Resolve and render template with sandboxed Jinja2
            render_res = TemplateService.resolve_and_render_for_message(
                template_id=template_id,
                template_vars=template_vars or {},
                organization_id=organization_id,
                template_version=template_version
            )

            if not render_res["success"]:
                return {
                    "success": False,
                    "status_code": render_res.get("status_code", 422),
                    "message": render_res.get("message", "Template resolution failed"),
                    "errors": [render_res.get("message", "Template resolution failed")]
                }

            rendered = render_res["data"]
            data = payload.get("data")
            if not isinstance(data, dict):
                data = {}
                payload["data"] = data

            # Inject rendered content into data for adapters and workers
            data["subject"] = rendered["subject"]
            data["html"] = rendered["html_body"]
            data["html_body"] = rendered["html_body"]
            data["body"] = rendered["plain_text_body"]
            data["message"] = rendered["plain_text_body"]
            data["text"] = rendered["plain_text_body"]
            data["plain_text_body"] = rendered["plain_text_body"]
            data["template_id"] = template_id
            data["template_version"] = rendered["version"]

            template_metadata = {
                "template_id": template_id,
                "template_version": rendered["version"],
                "template_variables": template_vars or {},
                "template_snapshot": {
                    "template_id": template_id,
                    "version": rendered["version"],
                    "subject": rendered["subject"],
                    "html_body": rendered["html_body"],
                    "plain_text_body": rendered["plain_text_body"]
                }
            }

        # Resolve centralized media references if provided in message data
        data_block = payload.get("data")
        media_ids_to_resolve = []
        if isinstance(data_block, dict):
            if "media_ids" in data_block and isinstance(data_block["media_ids"], list):
                media_ids_to_resolve.extend(data_block["media_ids"])
            if "attachments" in data_block and isinstance(data_block["attachments"], list):
                for att in data_block["attachments"]:
                    if isinstance(att, dict) and att.get("media_id"):
                        media_ids_to_resolve.append(att["media_id"])

        if media_ids_to_resolve:
            channel = payload.get("channel", "email")
            provider = payload.get("provider")
            recipient = payload.get("recipient")
            from app.modules.media.service import MediaService
            try:
                unique_media_ids = list(dict.fromkeys(media_ids_to_resolve))
                resolved_media = MediaService.resolve_media_for_channel(
                    media_ids=unique_media_ids,
                    channel=channel,
                    organization_id=organization_id,
                    provider=provider,
                    recipient=recipient,
                    include_bytes=(channel in ("email", "whatsapp", "microsoft_teams", "teams"))
                )
                if channel == "email":
                    existing_att = data_block.get("attachments", [])
                    if not isinstance(existing_att, list):
                        existing_att = []
                    retained_att = [a for a in existing_att if not (isinstance(a, dict) and a.get("media_id"))]
                    for m in resolved_media:
                        retained_att.append({
                            "filename": m["filename"],
                            "mime_type": m["mime_type"],
                            "content": m["base64_content"],
                            "media_id": m["media_id"]
                        })
                    data_block["attachments"] = retained_att
                elif channel == "whatsapp":
                    data_block["resolved_media"] = [
                        {
                            "media_id": m["media_id"],
                            "filename": m["filename"],
                            "mime_type": m["mime_type"],
                            "size_bytes": m["size_bytes"],
                            "raw_bytes": m.get("raw_bytes"),
                            "storage_key": m.get("storage_key")
                        }
                        for m in resolved_media
                    ]
                elif channel in ("microsoft_teams", "teams"):
                    data_block["media_references"] = [
                        {
                            "media_id": m["media_id"],
                            "filename": m["filename"],
                            "mime_type": m["mime_type"],
                            "size_bytes": m["size_bytes"],
                            "raw_bytes": m.get("raw_bytes"),
                            "storage_key": m.get("storage_key")
                        }
                        for m in resolved_media
                    ]
                elif channel == "sms":
                    data_block["mms_media"] = [
                        {
                            "media_id": m["media_id"],
                            "filename": m["filename"],
                            "mime_type": m["mime_type"],
                            "size_bytes": m["size_bytes"],
                            "storage_key": m.get("storage_key")
                        }
                        for m in resolved_media
                    ]
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Media validation failed: {str(e)}",
                    "errors": [str(e)]
                }

        result = MessageEngine.prepare_message(
            payload,
            template_rendered=bool(template_metadata),
        )

        if not result["success"]:
            return result

        message = result["message"]

        # Never trust organization_id supplied by the client.
        message["organization_id"] = organization_id

        # Enforce authoritative application_id when provided and reject mismatches.
        body_app_id = payload.get("application_id") if isinstance(payload, dict) else None
        if body_app_id is not None and not isinstance(body_app_id, str):
            return {
                "success": False,
                "status_code": 400,
                "message": "application_id must be a string",
                "errors": ["application_id must be a string"],
            }

        if application_id is not None:
            clean_explicit_app = str(application_id).strip() or None
            if body_app_id and str(body_app_id).strip() and str(body_app_id).strip() != clean_explicit_app:
                return {
                    "success": False,
                    "status_code": 403,
                    "message": "Application ID mismatch",
                    "errors": ["Application ID mismatch"],
                }
            resolved_app_id = clean_explicit_app
        else:
            resolved_app_id = str(body_app_id).strip() if isinstance(body_app_id, str) and body_app_id.strip() else None

        if resolved_app_id and hasattr(current_app, "mongo_db") and current_app.mongo_db is not None:
            app_doc = current_app.mongo_db["connected_applications"].find_one({"application_id": resolved_app_id})
            if app_doc is not None and (
                app_doc.get("organization_id") != organization_id
                or app_doc.get("deleted_at")
                or str(app_doc.get("status", "")).upper() != "ACTIVE"
            ):
                return {
                    "success": False,
                    "status_code": 403,
                    "message": "Connected application is inactive or unauthorized",
                    "errors": ["Connected application is inactive or unauthorized"],
                }

        message["application_id"] = resolved_app_id

        if template_metadata:
            message.update(template_metadata)

        saved_message = MessageRepository.save(message)

        return {
            "success": True,
            "message": saved_message,
            "validation": result["validation"]
        }

    @staticmethod
    def _validate_persisted_application_active(application_id, organization_id):
        """Fail closed when a persisted connected application record is deleted, inactive, or cross-tenant."""
        if not application_id or not hasattr(current_app, "mongo_db") or current_app.mongo_db is None:
            return True, None
        app_col = current_app.mongo_db["connected_applications"]
        if not hasattr(app_col, "find_one"):
            return True, None
        app_doc = app_col.find_one({"application_id": application_id})
        if app_doc is None:
            return True, None
        if (
            app_doc.get("organization_id") != organization_id
            or app_doc.get("deleted_at")
            or str(app_doc.get("status", "")).upper() != "ACTIVE"
        ):
            return False, "Connected application is inactive, deleted, or does not belong to this organization"
        return True, None

    @staticmethod
    def get_message(message_id, organization_id, user_application_ids=None, forbid_cross_app=True):

        message = MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )

        if message:
            return message

        if user_application_ids is not None and forbid_cross_app:
            org_msg = MessageRepository.find_by_id(
                message_id,
                organization_id=organization_id,
            )
            if org_msg:
                return {
                    "_error": "FORBIDDEN",
                    "message": "Access denied for this application scope"
                }

        return None

    @staticmethod
    def get_all_messages(
        organization_id,
        limit=50,
        page=1,
        status=None,
        channel=None,
        provider=None,
        recipient=None,
        application_id=None,
        search=None,
        start_date=None,
        end_date=None,
        user_application_ids=None
    ):
        effective_app_id = application_id

        # Application scope enforcement for scoped users and API keys
        if user_application_ids is not None:
            if application_id:
                if application_id not in user_application_ids:
                    return {
                        "items": [],
                        "pagination": {
                            "total": 0,
                            "page": page,
                            "limit": limit,
                            "total_pages": 0
                        }
                    }
                effective_app_id = application_id
            else:
                effective_app_id = list(user_application_ids)

        return MessageRepository.find_all(
            organization_id=organization_id,
            limit=limit,
            page=page,
            status=status,
            channel=channel,
            provider=provider,
            recipient=recipient,
            application_id=effective_app_id,
            search=search,
            start_date=start_date,
            end_date=end_date
        )

    @classmethod
    def retry_message(cls, message_id, organization_id, user_application_ids=None):
        """
        Manually retry an eligible failed or dead message.
        - Verifies organization and application ownership directly in repository queries.
        - Rejects retry if message is currently processing, queued, sent, or delivered.
        - For DEAD messages in DLQ, delegates to DeadLetterService.retry_dead_letter.
        - For FAILED messages, updates status to QUEUED and dispatches Celery task with trusted scope.
        """
        message = MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )

        if not message:
            return {
                "success": False,
                "status_code": 404,
                "message": "Message not found"
            }

        trusted_app_id = message.get("application_id")
        if user_application_ids is not None and not trusted_app_id:
            return {
                "success": False,
                "status_code": 404,
                "message": "Message not found"
            }

        app_ok, app_err = cls._validate_persisted_application_active(trusted_app_id, organization_id)
        if not app_ok:
            return {
                "success": False,
                "status_code": 403,
                "message": app_err,
            }

        if str(message.get("last_error") or "").startswith("DELIVERY_OUTCOME_UNKNOWN:"):
            return {
                "success": False,
                "status_code": 409,
                "message": "Provider acceptance is uncertain; reconcile delivery status before retrying this message",
            }

        current_status = message.get("status")

        if current_status in ("SENT", "DELIVERED", "READ"):
            return {
                "success": False,
                "status_code": 400,
                "message": f"Cannot retry already delivered or sent message in status '{current_status}'"
            }

        if current_status in ("QUEUED", "PROCESSING"):
            return {
                "success": False,
                "status_code": 409,
                "message": f"Message is currently being processed ({current_status})"
            }

        if current_status == "DEAD":
            from app.modules.dead_letters.service import DeadLetterService
            dlq_res = DeadLetterService.retry_dead_letter(
                message_id=message_id,
                organization_id=organization_id,
                user_application_ids=user_application_ids,
                expected_application_id=trusted_app_id,
            )
            if dlq_res.get("success"):
                return dlq_res
            err_msg = str(dlq_res.get("message") or "").lower()
            if (
                dlq_res.get("status_code") in (403, 409)
                or "mismatch" in err_msg
                or "inactive" in err_msg
                or "already requested" in err_msg
                or "unauthorized" in err_msg
            ):
                return {
                    **dlq_res,
                    "status_code": dlq_res.get("status_code", 409 if "mismatch" in err_msg else 400),
                }

        scope_filter = trusted_app_id if trusted_app_id is not None else user_application_ids

        # Transition status to QUEUED with atomic ownership filter
        requeued = MessageRepository.requeue_failed_message(
            message_id=message_id,
            organization_id=organization_id,
            application_ids=scope_filter,
        )

        if not requeued and current_status == "DEAD":
            requeued = MessageRepository.requeue_dead_message(
                message_id=message_id,
                previous_retry_count=message.get("retry_count", 0),
                organization_id=organization_id,
                application_ids=scope_filter,
            )

        if not requeued:
            return {
                "success": False,
                "status_code": 400,
                "message": f"Could not transition message from status '{current_status}' to QUEUED for retry"
            }

        try:
            task = current_app.celery.send_task(
                "senderx.process_message",
                args=[message_id],
                kwargs={
                    "expected_organization_id": organization_id,
                    "expected_application_id": trusted_app_id,
                },
            )
            return {
                "success": True,
                "status_code": 200,
                "message": "Message successfully requeued for retry",
                "message_id": message_id,
                "application_id": trusted_app_id,
                "status": "QUEUED",
                "task_id": task.id
            }
        except Exception as e:
            current_app.logger.exception("Failed to dispatch Celery retry task: %s", e)
            return {
                "success": True,
                "status_code": 200,
                "message": "Message status marked QUEUED for retry (dispatch pending)",
                "message_id": message_id,
                "application_id": trusted_app_id,
                "status": "QUEUED"
            }

    @classmethod
    def queue_message(cls, message_id, organization_id, user_application_ids=None):
        """
        Safely queue a message for processing:
        - Verifies message exists and belongs to the authenticated organization and application scope.
        - Allows queueing only from valid initial states (CREATED, VALIDATED).
        - Prevents duplicate dispatches and concurrent queue requests.
        - Atomically transitions status to QUEUED.
        - Dispatches task to Celery carrying trusted organization_id and application_id.
        - Safely rolls back status if broker dispatch fails.
        """
        message = MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )

        if not message:
            return {
                "success": False,
                "status_code": 404,
                "message": "Message not found"
            }

        trusted_app_id = message.get("application_id")
        if user_application_ids is not None and not trusted_app_id:
            return {
                "success": False,
                "status_code": 404,
                "message": "Message not found"
            }

        app_ok, app_err = cls._validate_persisted_application_active(trusted_app_id, organization_id)
        if not app_ok:
            return {
                "success": False,
                "status_code": 403,
                "message": app_err,
            }

        scope_filter = trusted_app_id if trusted_app_id is not None else user_application_ids
        current_status = message.get("status")

        if current_status == "QUEUED":
            return {
                "success": False,
                "status_code": 409,
                "message": "Message is already queued",
                "message_id": message_id,
                "status": "QUEUED"
            }

        if current_status not in ("CREATED", "VALIDATED"):
            return {
                "success": False,
                "status_code": 400,
                "message": (
                    f"Cannot queue message in status '{current_status}'. "
                    "Message must be in CREATED or VALIDATED status."
                ),
                "message_id": message_id,
                "status": current_status
            }

        # Atomic conditional status update to prevent race conditions
        updated = MessageRepository.update_status(
            message_id=message_id,
            new_status="QUEUED",
            old_status=current_status,
            organization_id=organization_id,
            application_ids=scope_filter,
        )

        if not updated:
            refetched = MessageRepository.find_by_id(
                message_id,
                organization_id=organization_id,
                application_ids=scope_filter,
            )
            if refetched and refetched.get("status") == "QUEUED":
                return {
                    "success": False,
                    "status_code": 409,
                    "message": "Message is already queued",
                    "message_id": message_id,
                    "status": "QUEUED"
                }

            return {
                "success": False,
                "status_code": 409,
                "message": "Concurrent status change detected; could not queue message",
                "message_id": message_id
            }

        # Dispatch Celery task with trusted ownership metadata
        try:
            task = current_app.celery.send_task(
                "senderx.process_message",
                args=[message_id],
                kwargs={
                    "expected_organization_id": organization_id,
                    "expected_application_id": trusted_app_id,
                },
            )

            current_app.logger.info(
                "Message %s successfully queued with Celery task %s",
                message_id,
                task.id
            )

            return {
                "success": True,
                "status_code": 200,
                "message": "Message successfully queued for processing",
                "message_id": message_id,
                "application_id": trusted_app_id,
                "status": "QUEUED",
                "task_id": task.id
            }

        except Exception as error:
            current_app.logger.exception(
                "Celery dispatch failed for message %s. Rolling back status to %s",
                message_id,
                current_status
            )

            # Roll back status to original state
            MessageRepository.update_status(
                message_id=message_id,
                new_status=current_status,
                old_status="QUEUED",
                organization_id=organization_id,
                application_ids=scope_filter,
            )

            return {
                "success": False,
                "status_code": 503,
                "message": "Task dispatch to message broker failed; message status rolled back",
                "message_id": message_id,
                "status": current_status,
                "error": str(error)
            }

    @classmethod
    def update_status(cls, message_id, new_status, organization_id, user_application_ids=None):

        if new_status == "QUEUED":
            return cls.queue_message(message_id, organization_id, user_application_ids=user_application_ids)

        message = MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id,
            application_ids=user_application_ids,
        )

        if not message:
            return {
                "success": False,
                "status_code": 404,
                "message": "Message not found"
            }

        trusted_app_id = message.get("application_id")
        if user_application_ids is not None and not trusted_app_id:
            return {
                "success": False,
                "status_code": 404,
                "message": "Message not found"
            }

        scope_filter = trusted_app_id if trusted_app_id is not None else user_application_ids
        current_status = message.get("status")

        result = StatusManager.transition(
            current_status,
            new_status
        )

        if not result["success"]:
            return {
                "success": False,
                "status_code": 400,
                "message": result.get("message", "Invalid status transition")
            }

        updated = MessageRepository.update_status(
            message_id,
            new_status,
            current_status,
            organization_id=organization_id,
            application_ids=scope_filter,
        )

        if not updated:
            return {
                "success": False,
                "status_code": 400,
                "message": "Status update failed"
            }

        return {
            "success": True,
            "status_code": 200,
            "message": "Message status updated successfully",
            "data": MessageRepository.find_by_id(
                message_id,
                organization_id=organization_id,
                application_ids=scope_filter,
            )
        }

    _TWILIO_STATUS_MAP = {
        "delivered": "DELIVERED",
        "read": "READ",
        "failed": "FAILED",
        "undelivered": "FAILED",
        "canceled": "FAILED",
        "sent": "SENT",
        "sending": "SENT",
        "queued": "ACCEPTED",
        "accepted": "ACCEPTED",
        "scheduled": "ACCEPTED",
    }

    @classmethod
    def handle_twilio_callback(
        cls,
        callback_data=None,
        *,
        signature=None,
        callback_url=None,
        validation_params=None,
        endpoint_path=None,
        endpoint_kind="status_callback",
        is_json=False,
        has_body_sha256=False,
    ):
        """
        Process incoming Twilio webhook / StatusCallback events with fail-closed
        signature verification, tenant-safe integration lookup, strict scoped
        message resolution, and idempotent status transitions.
        """
        from app.modules.messages.twilio_webhook import (
            log_twilio_security_event,
            resolve_twilio_integration_for_callback,
            verify_twilio_signature,
        )

        # Fail fast if signature header is absent before parsing/decrypting integration creds
        if not isinstance(signature, str) or not signature.strip():
            log_twilio_security_event(
                event_type="TWILIO_WEBHOOK_INVALID_SIGNATURE",
                summary="Rejected Twilio callback missing X-Twilio-Signature header",
                endpoint=endpoint_path,
                reason_code="MISSING_SIGNATURE",
            )
            return {
                "success": False,
                "status_code": 401,
                "error_code": "MISSING_SIGNATURE",
                "message": "Missing X-Twilio-Signature header",
            }

        if is_json and not has_body_sha256:
            log_twilio_security_event(
                event_type="TWILIO_WEBHOOK_INVALID_SIGNATURE",
                summary="Rejected JSON Twilio callback without bodySHA256 verification digest",
                endpoint=endpoint_path,
                reason_code="INVALID_SIGNATURE",
            )
            return {
                "success": False,
                "status_code": 401,
                "error_code": "INVALID_SIGNATURE",
                "message": "Twilio JSON webhooks require signed bodySHA256 digest",
            }

        if not isinstance(callback_url, str) or not callback_url.strip():
            return {
                "success": False,
                "status_code": 400,
                "error_code": "INVALID_CALLBACK_URL",
                "message": "Callback URL is required for signature verification",
            }

        if not isinstance(callback_data, dict):
            return {"success": False, "status_code": 400, "message": "Invalid callback data"}

        provider_message_id = (
            callback_data.get("MessageSid")
            or callback_data.get("SmsSid")
            or callback_data.get("sms_sid")
            or callback_data.get("message_sid")
        )
        if isinstance(provider_message_id, str):
            provider_message_id = provider_message_id.strip()

        account_sid = (
            callback_data.get("AccountSid")
            or callback_data.get("account_sid")
        )

        # 1. Resolve integration & owning organization BEFORE touching message records
        integration_res = resolve_twilio_integration_for_callback(
            account_sid=account_sid,
            endpoint=endpoint_path,
            provider_message_id=provider_message_id,
        )
        if not integration_res.get("success"):
            return integration_res

        integration = integration_res["integration"]
        resolved_org_id = integration["organization_id"]
        resolved_config_id = integration.get("config_id")
        resolved_sid_digest = integration.get("account_sid_digest")
        auth_token = integration["auth_token"]

        # 2. Verify cryptographic X-Twilio-Signature against exact URL, params, and org Auth Token
        params_for_sig = validation_params if validation_params is not None else callback_data
        sig_ok, sig_err = verify_twilio_signature(
            auth_token=auth_token,
            callback_url=callback_url,
            params=params_for_sig,
            signature=signature,
            organization_id=resolved_org_id,
            integration_id=resolved_config_id,
            account_sid=account_sid,
            provider_message_id=provider_message_id,
            endpoint=endpoint_path,
        )
        if not sig_ok:
            return sig_err

        # 3. Validate callback payload specifics by endpoint responsibility
        if not provider_message_id:
            return {"success": False, "status_code": 400, "message": "MessageSid is required"}

        raw_status = (
            callback_data.get("MessageStatus")
            or callback_data.get("SmsStatus")
            or callback_data.get("status")
            or ""
        )
        if isinstance(raw_status, str):
            raw_status = raw_status.lower().strip()
        else:
            raw_status = ""

        # General Twilio webhook endpoint may receive non-status events (e.g. inbound SMS Body without status);
        # dedicated /callbacks/twilio status callback always requires an explicit delivery status.
        if not raw_status:
            if endpoint_kind == "webhook" and callback_data.get("Body") is not None and callback_data.get("From"):
                return {
                    "success": True,
                    "status_code": 200,
                    "event_type": "twilio_webhook_acknowledged",
                    "organization_id": resolved_org_id,
                    "provider_message_id": provider_message_id,
                    "updated": False,
                }
            return {
                "success": False,
                "status_code": 400,
                "error_code": "MISSING_MESSAGE_STATUS",
                "message": "MessageStatus is required",
            }

        new_status = cls._TWILIO_STATUS_MAP.get(raw_status)
        if not new_status:
            return {
                "success": False,
                "status_code": 400,
                "error_code": "INVALID_TWILIO_STATUS",
                "message": f"Unsupported Twilio status '{raw_status}'",
            }

        error_code = callback_data.get("ErrorCode") or callback_data.get("error_code")
        error_message = callback_data.get("ErrorMessage") or callback_data.get("error_message")
        callback_recipient = callback_data.get("To")

        # 4. Scoped message resolution & lifecycle transition update
        outcome_res = MessageRepository.resolve_and_update_twilio_delivery_status(
            organization_id=resolved_org_id,
            provider_message_id=provider_message_id,
            new_status=new_status,
            raw_status=raw_status,
            error_code=error_code,
            error_message=error_message,
            provider_config_id=resolved_config_id,
            provider_account_sid_digest=resolved_sid_digest,
            expected_recipient=callback_recipient,
        )

        outcome = outcome_res.get("outcome")

        if outcome == "ambiguous":
            log_twilio_security_event(
                event_type="TWILIO_WEBHOOK_AMBIGUOUS_MESSAGE",
                summary="Rejected Twilio callback because multiple message records matched provider_message_id in tenant scope",
                organization_id=resolved_org_id,
                integration_id=resolved_config_id,
                account_sid=account_sid,
                provider_message_id=provider_message_id,
                endpoint=endpoint_path,
                reason_code="AMBIGUOUS_MESSAGE_RECORD",
            )
            return {
                "success": False,
                "status_code": 409,
                "error_code": "AMBIGUOUS_MESSAGE_RECORD",
                "message": "Multiple message records matched callback identifier; update rejected",
                "updated": False,
            }

        if outcome == "not_found":
            log_twilio_security_event(
                event_type="TWILIO_WEBHOOK_UNMAPPED_MESSAGE",
                summary="Twilio callback referenced a MessageSid not found in verified organization scope",
                organization_id=resolved_org_id,
                integration_id=resolved_config_id,
                account_sid=account_sid,
                provider_message_id=provider_message_id,
                endpoint=endpoint_path,
                reason_code="MESSAGE_NOT_FOUND",
            )
            return {
                "success": False,
                "status_code": 404,
                "error_code": "MESSAGE_NOT_FOUND",
                "message": "Message not found for verified Twilio integration",
                "updated": False,
            }

        if outcome == "identity_mismatch":
            log_twilio_security_event(
                event_type="TWILIO_WEBHOOK_IDENTITY_MISMATCH",
                summary="Rejected Twilio callback due to integration or recipient identity mismatch",
                organization_id=resolved_org_id,
                integration_id=resolved_config_id,
                account_sid=account_sid,
                provider_message_id=provider_message_id,
                endpoint=endpoint_path,
                reason_code="IDENTITY_MISMATCH",
            )
            return {
                "success": False,
                "status_code": 409,
                "error_code": "IDENTITY_MISMATCH",
                "message": "Callback identity does not match stored message record",
                "updated": False,
            }

        if outcome == "rejected_transition":
            log_twilio_security_event(
                event_type="TWILIO_WEBHOOK_INVALID_TRANSITION",
                summary=(
                    f"Rejected regressive or invalid Twilio status transition "
                    f"{outcome_res.get('previous_status')} -> {outcome_res.get('attempted_status')}"
                ),
                organization_id=resolved_org_id,
                integration_id=resolved_config_id,
                account_sid=account_sid,
                provider_message_id=provider_message_id,
                endpoint=endpoint_path,
                reason_code="INVALID_STATUS_TRANSITION",
            )
            return {
                "success": False,
                "status_code": 409,
                "error_code": "INVALID_STATUS_TRANSITION",
                "message_id": outcome_res.get("message_id"),
                "provider_message_id": provider_message_id,
                "status": outcome_res.get("previous_status"),
                "attempted_status": new_status,
                "updated": False,
                "message": "Status transition rejected to preserve message lifecycle integrity",
            }

        if outcome == "duplicate":
            return {
                "success": True,
                "status_code": 200,
                "message_id": outcome_res.get("message_id"),
                "provider_message_id": provider_message_id,
                "status": outcome_res.get("status"),
                "raw_status": raw_status,
                "updated": False,
                "duplicate": True,
                "idempotent": True,
            }

        if outcome == "updated":
            return {
                "success": True,
                "status_code": 200,
                "message_id": outcome_res.get("message_id"),
                "provider_message_id": provider_message_id,
                "status": new_status,
                "raw_status": raw_status,
                "updated": True,
                "duplicate": False,
            }

        return {
            "success": False,
            "status_code": 409,
            "error_code": "STATUS_CONFLICT",
            "message": "Concurrent status modification prevented callback update",
            "updated": False,
        }

    @classmethod
    def verify_whatsapp_webhook(cls, hub_mode, hub_token, hub_challenge):
        """
        Verify Meta WhatsApp Cloud API Webhook handshake.
        GET /api/v1/messages/webhook/whatsapp
        """
        if not hub_mode or hub_mode != "subscribe":
            return {
                "success": False,
                "status_code": 403,
                "message": "Invalid hub.mode; expected 'subscribe'"
            }

        if not hub_token:
            return {
                "success": False,
                "status_code": 403,
                "message": "hub.verify_token is required"
            }

        if not isinstance(hub_challenge, str) or not hub_challenge:
            return {
                "success": False,
                "status_code": 400,
                "message": "hub.challenge is required"
            }

        from app.modules.whatsapp.service import PlatformSettingsService
        meta_settings = PlatformSettingsService.get_meta_settings(decrypt=True)
        expected_token = meta_settings.get("webhook_verify_token")

        if not expected_token or not str(expected_token).strip():
            logger.error("WhatsApp webhook verify token is not configured on platform")
            return {
                "success": False,
                "status_code": 503,
                "message": "Webhook verify token is not configured on platform"
            }

        provided_token = str(hub_token).strip()
        expected_token = str(expected_token).strip()
        if provided_token and hmac.compare_digest(provided_token, expected_token):
            return {
                "success": True,
                "status_code": 200,
                "challenge": hub_challenge
            }

        return {
            "success": False,
            "status_code": 403,
            "message": "Verification token does not match"
        }

    @classmethod
    def _normalize_whatsapp_interactive_event(
        cls,
        message: Dict[str, Any],
        organization_id: str,
        integration_id: str,
        phone_number_id: str,
    ) -> Dict[str, Any]:
        """Normalize known interactive responses while retaining unknown types safely."""
        message_type = str(message.get("type") or "").lower().strip()
        interactive = message.get("interactive")
        subtype = None
        selection = None

        if message_type == "interactive" and isinstance(interactive, dict):
            subtype = str(interactive.get("type") or "").lower().strip()
            if subtype in ("button_reply", "list_reply"):
                candidate = interactive.get(subtype)
                if isinstance(candidate, dict):
                    reply_id = candidate.get("id")
                    title = candidate.get("title")
                    if isinstance(reply_id, str) and reply_id.strip() and isinstance(title, str) and title.strip():
                        selection = {
                            "id": reply_id.strip(),
                            "title": title.strip(),
                        }
                        if subtype == "list_reply" and isinstance(candidate.get("description"), str):
                            selection["description"] = candidate["description"].strip()
            elif subtype == "nfm_reply":
                candidate = interactive.get("nfm_reply")
                if isinstance(candidate, dict):
                    response_value = candidate.get("response_json")
                    if isinstance(response_value, str):
                        try:
                            import json
                            response_value = json.loads(response_value)
                        except (TypeError, ValueError):
                            response_value = None
                    if isinstance(response_value, dict):
                        selection = {
                            "response": response_value,
                            "name": candidate.get("name"),
                            "body": candidate.get("body"),
                        }
        elif message_type == "button":
            # Accept the legacy webhook button shape as a button reply.
            subtype = "button_reply"
            candidate = message.get("button")
            if isinstance(candidate, dict):
                reply_id = candidate.get("payload") or candidate.get("id")
                title = candidate.get("text") or candidate.get("title")
                if isinstance(reply_id, str) and reply_id.strip() and isinstance(title, str) and title.strip():
                    selection = {"id": reply_id.strip(), "title": title.strip()}

        is_flow_reply = subtype == "nfm_reply" and selection is not None
        known_reply = subtype in ("button_reply", "list_reply") and selection is not None
        event = {
            "event_id": message.get("id"),
            "event_type": "whatsapp.flow.completed" if is_flow_reply else (f"whatsapp.{subtype}" if known_reply else "whatsapp.interactive.unknown"),
            "subtype": subtype if known_reply or is_flow_reply else (subtype or "unknown"),
            "organization_id": organization_id,
            "integration_id": integration_id,
            "phone_number_id": phone_number_id,
            "from_phone": message.get("from"),
            "timestamp": message.get("timestamp"),
            "provider_message_id": message.get("id"),
            "selection": selection,
        }
        if is_flow_reply:
            event["flow_response"] = selection["response"]
            if selection.get("name"):
                event["flow_name"] = selection["name"]
        if not known_reply and not is_flow_reply and subtype:
            event["unrecognized_type"] = subtype
        return event

    @classmethod
    def handle_whatsapp_webhook(cls, raw_payload: bytes, signature_header: Optional[str], json_data: Dict[str, Any]):
        """
        Process Meta WhatsApp webhook event payload.
        Verifies X-Hub-Signature-256 against centralized Meta platform settings,
        updates message delivery statuses with organization-level isolation,
        and saves inbound customer messages resolved via active WhatsApp integrations.
        """
        from app.modules.whatsapp.service import PlatformSettingsService
        from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
        from app.adapters.whatsapp.whatsapp_utils import verify_meta_signature

        # 1. Authoritative Meta platform settings
        meta_settings = PlatformSettingsService.get_meta_settings(decrypt=True)
        app_secret = meta_settings.get("meta_app_secret")

        # Require a configured Meta App Secret
        if not app_secret or not str(app_secret).strip():
            logger.error("Meta App Secret is not configured on platform")
            return {
                "success": False,
                "status_code": 503,
                "message": "Meta App Secret is not configured on platform"
            }

        # Require X-Hub-Signature-256
        if not signature_header:
            return {
                "success": False,
                "status_code": 401,
                "message": "Missing X-Hub-Signature-256 header"
            }

        # Strict signature verification
        if not verify_meta_signature(raw_payload, signature_header, app_secret):
            return {
                "success": False,
                "status_code": 401,
                "message": "Invalid webhook signature"
            }

        if not isinstance(json_data, dict):
            return {"success": False, "status_code": 400, "message": "Invalid webhook payload JSON"}

        # Validate webhook object (Meta WhatsApp payloads always have object: "whatsapp_business_account")
        webhook_obj = json_data.get("object")
        if webhook_obj and webhook_obj != "whatsapp_business_account":
            logger.warning("Ignoring non-whatsapp webhook object: %s", webhook_obj)
            return {
                "success": True,
                "status_code": 200,
                "message": f"Ignored non-whatsapp webhook object: {webhook_obj}",
                "processed_statuses": 0,
                "processed_messages": 0
            }

        # 2. Process Entries
        processed_statuses = 0
        processed_messages = 0

        entries = json_data.get("entry")
        if not isinstance(entries, list):
            return {"success": False, "status_code": 400, "message": "Invalid entry list in payload"}

        retryable_failures = 0
        ignored_events = 0

        for entry in entries:
            if not isinstance(entry, dict):
                ignored_events += 1
                continue
            waba_id = entry.get("id")
            changes = entry.get("changes", [])
            if not isinstance(changes, list):
                ignored_events += 1
                continue

            for ch in changes:
                if not isinstance(ch, dict):
                    ignored_events += 1
                    continue
                val = ch.get("value", {})
                if not isinstance(val, dict):
                    ignored_events += 1
                    continue
                metadata = val.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id") if isinstance(metadata, dict) else None

                # Resolve organization strictly from phone_number_id via WhatsAppIntegrationRepository
                resolved_org_id = None
                if phone_number_id:
                    clean_phone_id = str(phone_number_id).strip()
                    try:
                        integration = WhatsAppIntegrationRepository.find_by_phone_number_id(
                            clean_phone_id,
                            include_deleted=False,
                        )
                    except Exception:
                        retryable_failures += 1
                        logger.exception("WhatsApp integration lookup failed for phone_number_id %s", clean_phone_id)
                        continue
                    if integration and integration.get("status") == "CONNECTED":
                        configured_waba_id = integration.get("waba_id")
                        if waba_id and configured_waba_id and str(waba_id).strip() != str(configured_waba_id).strip():
                            logger.warning(
                                "WhatsApp webhook WABA ID does not match integration for phone_number_id %s",
                                clean_phone_id,
                            )
                        else:
                            resolved_org_id = integration.get("organization_id")
                    else:
                        logger.warning(
                            "WhatsApp webhook event received for unmapped or non-connected phone_number_id: %s",
                            clean_phone_id
                        )

                # Process status updates (sent, delivered, read, failed)
                statuses = val.get("statuses", [])
                if not isinstance(statuses, list):
                    ignored_events += 1
                    statuses = []
                for st in statuses:
                    if not isinstance(st, dict):
                        ignored_events += 1
                        continue
                    wamid = st.get("id")
                    raw_status_value = st.get("status")
                    if not isinstance(wamid, str) or not wamid.strip() or not isinstance(raw_status_value, str) or not raw_status_value.strip():
                        ignored_events += 1
                        continue
                    wamid = wamid.strip()
                    raw_status = raw_status_value.lower().strip()
                    errors = st.get("errors", [])
                    err_code = errors[0].get("code") if (isinstance(errors, list) and errors and isinstance(errors[0], dict)) else None
                    err_msg = (errors[0].get("message") or errors[0].get("title")) if (isinstance(errors, list) and errors and isinstance(errors[0], dict)) else None
                    if raw_status == "delivered":
                        norm_status = "DELIVERED"
                    elif raw_status == "read":
                        norm_status = "READ"
                    elif raw_status == "failed":
                        norm_status = "FAILED"
                    elif raw_status == "sent":
                        norm_status = "SENT"
                    else:
                        norm_status = raw_status.upper()

                    if not resolved_org_id:
                        logger.warning(
                            "Skipping status update for wamid %s: phone_number_id %s has no active connected integration",
                            wamid, phone_number_id
                        )
                        ignored_events += 1
                        continue

                    try:
                        updated = MessageRepository.update_delivery_status(
                            provider_message_id=wamid,
                            new_status=norm_status,
                            raw_status=raw_status,
                            error_code=err_code,
                            error_message=err_msg,
                            organization_id=resolved_org_id
                        )
                        if updated:
                            processed_statuses += 1
                        else:
                            ignored_events += 1
                    except Exception:
                        retryable_failures += 1
                        logger.exception("WhatsApp status webhook processing failed for provider message %s", wamid)

                # Process inbound customer messages
                messages = val.get("messages", [])
                if not isinstance(messages, list):
                    ignored_events += 1
                    messages = []
                for msg in messages:
                    if not isinstance(msg, dict):
                        ignored_events += 1
                        continue
                    wamid = msg.get("id")
                    from_phone = msg.get("from")
                    if not isinstance(wamid, str) or not wamid.strip() or not isinstance(from_phone, str) or not from_phone.strip():
                        ignored_events += 1
                        continue
                    wamid = wamid.strip()
                    msg_type = msg.get("type", "text")
                    if not isinstance(msg_type, str):
                        msg_type = "unknown"
                    if msg_type == "text" and isinstance(msg.get("text"), dict):
                        content = msg.get("text", {}).get("body")
                    else:
                        content = msg.get(msg_type)

                    try:
                        integration = WhatsAppIntegrationRepository.find_by_phone_number_id(
                            str(phone_number_id).strip() if phone_number_id else "",
                            include_deleted=False,
                        ) if phone_number_id else None
                        structured_event = None
                        if str(msg_type).lower().strip() in ("interactive", "button") and integration:
                            structured_event = cls._normalize_whatsapp_interactive_event(
                                message=msg,
                                organization_id=integration.get("organization_id"),
                                integration_id=integration.get("integration_id"),
                                phone_number_id=str(phone_number_id).strip(),
                            )

                        saved = cls.save_inbound_message(
                            channel="whatsapp",
                            provider="meta",
                            phone_number_id=phone_number_id,
                            waba_id=waba_id,
                            from_phone=from_phone.strip(),
                            provider_message_id=wamid,
                            message_type=msg_type,
                            content=content,
                            raw_data=msg,
                            structured_event=structured_event,
                        )
                        if saved and saved.get("provider_message_id"):
                            processed_messages += 1
                            if structured_event and structured_event.get("event_type") == "whatsapp.flow.completed":
                                from app.modules.users.audit_repository import SecurityAuditRepository
                                SecurityAuditRepository.log_event(
                                    organization_id=integration.get("organization_id"),
                                    event_type="WHATSAPP_FLOW_COMPLETED",
                                    target_id=integration.get("integration_id"),
                                    target_type="WHATSAPP_INTEGRATION",
                                    action_label="WhatsApp Flow completed",
                                    summary="A WhatsApp Flow completion response was received",
                                    details={"provider_message_id": wamid},
                                )
                        else:
                            ignored_events += 1
                    except Exception:
                        retryable_failures += 1
                        logger.exception("WhatsApp inbound webhook processing failed for provider message %s", wamid)

        response = {
            "success": retryable_failures == 0,
            "status_code": 503 if retryable_failures else 200,
            "message": "Webhook processing failed temporarily; retry delivery" if retryable_failures else "Webhook processed successfully",
            "processed_statuses": processed_statuses,
            "processed_messages": processed_messages
        }
        if ignored_events:
            response["ignored_events"] = ignored_events
        if retryable_failures:
            response["retryable_failures"] = retryable_failures
        return response

    @classmethod
    def save_inbound_message(
        cls,
        channel: str,
        provider: str,
        phone_number_id: Optional[str],
        waba_id: Optional[str],
        from_phone: str,
        provider_message_id: str,
        message_type: str,
        content: Any,
        raw_data: Dict[str, Any],
        structured_event: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Persist inbound customer message to the 'inbound_messages' MongoDB collection.
        Resolves tenant organization ID strictly via active connected WhatsAppIntegration.
        Rejects unmapped or non-connected phone numbers and prevents duplicate event insertion.
        """
        from app.modules.whatsapp.repository import WhatsAppIntegrationRepository

        if not phone_number_id:
            logger.warning("WhatsApp inbound message rejected: missing phone_number_id")
            return {
                "success": False,
                "status_code": 400,
                "message": "Missing phone_number_id for WhatsApp inbound message"
            }

        clean_phone_id = str(phone_number_id).strip()
        integration = WhatsAppIntegrationRepository.find_by_phone_number_id(clean_phone_id, include_deleted=False)

        if not integration or integration.get("status") != "CONNECTED":
            logger.warning(
                "WhatsApp inbound message rejected: no active connected integration found for phone_number_id %s",
                clean_phone_id
            )
            return {
                "success": False,
                "status_code": 404,
                "message": "No active connected integration found for phone_number_id"
            }

        organization_id = integration.get("organization_id")
        if not organization_id:
            logger.warning(
                "WhatsApp inbound message rejected: integration for phone_number_id %s lacks organization_id",
                clean_phone_id
            )
            return {
                "success": False,
                "status_code": 400,
                "message": "Integration missing organization_id"
            }

        configured_waba_id = integration.get("waba_id")
        if waba_id and configured_waba_id and str(waba_id).strip() != str(configured_waba_id).strip():
            logger.warning(
                "WhatsApp inbound message rejected: WABA ID does not match integration for phone_number_id %s",
                clean_phone_id,
            )
            return {
                "success": False,
                "status_code": 403,
                "message": "Webhook WABA ID does not match the connected integration",
            }

        collection = current_app.mongo_db["inbound_messages"]

        # Check provider-ID ownership before writing sensitive Flow data to its
        # encrypted collection; a cross-tenant collision must create no record.
        existing = collection.find_one({"provider_message_id": provider_message_id}, {"_id": 0})
        if existing:
            if (
                existing.get("organization_id") != organization_id
                or existing.get("phone_number_id") != clean_phone_id
                or (existing.get("integration_id") and existing.get("integration_id") != integration.get("integration_id"))
            ):
                logger.warning("WhatsApp inbound message ID is already associated with a different tenant")
                return {
                    "success": False,
                    "status_code": 409,
                    "message": "Provider message ID is already associated with another integration",
                }
            return existing

        is_flow_completion = bool(
            structured_event
            and structured_event.get("event_type") == "whatsapp.flow.completed"
            and isinstance(structured_event.get("flow_response"), dict)
        )
        stored_raw_data = raw_data
        stored_content = content
        stored_event = structured_event
        if is_flow_completion:
            from app.modules.whatsapp.flows import WhatsAppFlowService

            WhatsAppFlowService.store_completion(
                organization_id,
                integration.get("integration_id"),
                provider_message_id,
                structured_event["flow_response"],
            )
            stored_raw_data = json.loads(json.dumps(raw_data))
            try:
                stored_raw_data["interactive"]["nfm_reply"]["response_json"] = "[ENCRYPTED_FLOW_RESPONSE]"
            except (KeyError, TypeError):
                pass
            stored_content = None
            stored_event = json.loads(json.dumps(structured_event))
            stored_event.pop("flow_response", None)
            if isinstance(stored_event.get("selection"), dict):
                stored_event["selection"].pop("response", None)

        doc = {
            "organization_id": organization_id,
            "channel": channel,
            "provider": provider,
            "phone_number_id": clean_phone_id,
            "integration_id": integration.get("integration_id"),
            "waba_id": waba_id,
            "from_phone": from_phone,
            "provider_message_id": provider_message_id,
            "message_type": message_type,
            "content": stored_content,
            "raw_data": stored_raw_data,
            "provider_timestamp": cls._parse_whatsapp_provider_timestamp(raw_data.get("timestamp") if isinstance(raw_data, dict) else None),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "processed": False
        }
        if stored_event is not None:
            doc["structured_event"] = stored_event
            doc["event_type"] = stored_event.get("event_type")
        if is_flow_completion:
            # Version 2 identifies the redacted envelope plus encrypted
            # response stored in whatsapp_flow_responses. Existing records
            # remain untouched in their version 1 shape.
            doc["payload_storage_version"] = 2

        # A deterministic MongoDB _id makes concurrent webhook retries idempotent
        # without requiring a new collection or an index migration.
        doc["_id"] = "wa-inbound:" + hashlib.sha256(
            f"{provider}:{provider_message_id}".encode("utf-8")
        ).hexdigest()

        from pymongo.errors import DuplicateKeyError
        try:
            collection.insert_one(doc)
        except DuplicateKeyError:
            existing = collection.find_one({"provider_message_id": provider_message_id}, {"_id": 0})
            if (
                existing
                and existing.get("organization_id") == organization_id
                and existing.get("phone_number_id") == clean_phone_id
                and existing.get("integration_id") == integration.get("integration_id")
            ):
                return existing
            return {
                "success": False,
                "status_code": 409,
                "message": "Provider message ID is already associated with another integration",
            }
        doc.pop("_id", None)
        return doc


