
import os
from datetime import datetime, timezone

from app.engine.message_engine import MessageEngine
from app.modules.messages.repository import MessageRepository
from app.engine.status_manager import StatusManager
from app.modules.templates.service import TemplateService
from flask import current_app


class MessageService:

    @classmethod
    def create_message(cls, payload, organization_id, application_id=None):

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

        # Extract template parameters if provided
        template_id = payload.get("template_id")
        template_vars = payload.get("template_variables")
        template_version = payload.get("template_version")

        # Also support template params specified inside payload["data"]
        if isinstance(payload.get("data"), dict):
            if not template_id:
                template_id = payload["data"].get("template_id")
            if template_vars is None:
                template_vars = payload["data"].get("template_variables")
            if template_version is None:
                template_version = payload["data"].get("template_version")

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

        result = MessageEngine.prepare_message(payload)

        if not result["success"]:
            return result

        message = result["message"]

        # Never trust organization_id supplied by the client.
        message["organization_id"] = organization_id

        # Associate application_id if supplied
        app_id = application_id or payload.get("application_id")
        if app_id:
            message["application_id"] = str(app_id).strip()

        if template_metadata:
            message.update(template_metadata)

        saved_message = MessageRepository.save(message)

        return {
            "success": True,
            "message": saved_message,
            "validation": result["validation"]
        }

    @staticmethod
    def get_message(message_id, organization_id, user_application_ids=None):

        message = MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id
        )

        if not message:
            return None

        # Enforce application scope for employees
        if user_application_ids:
            msg_app = message.get("application_id")
            if not msg_app or msg_app not in user_application_ids:
                return {
                    "_error": "FORBIDDEN",
                    "message": "Access denied for this application scope"
                }

        return message

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

        # Application scope enforcement for employees
        if user_application_ids:
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
        - Verifies organization ownership and employee application scope.
        - Rejects retry if message is currently processing, queued, sent, or delivered.
        - For DEAD messages in DLQ, delegates to DeadLetterService.retry_dead_letter.
        - For FAILED messages, updates status to QUEUED and dispatches Celery task.
        """
        message = MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id
        )

        if not message:
            return {
                "success": False,
                "status_code": 404,
                "message": "Message not found"
            }

        # Check employee application scope
        if user_application_ids:
            msg_app = message.get("application_id")
            if not msg_app or msg_app not in user_application_ids:
                return {
                    "success": False,
                    "status_code": 403,
                    "message": "You do not have permission to retry messages for this application scope"
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
            try:
                from app.modules.dead_letters.service import DeadLetterService
                dlq_res = DeadLetterService.retry_dead_letter(
                    message_id=message_id,
                    organization_id=organization_id
                )
                if dlq_res.get("success"):
                    return dlq_res
            except Exception as dlq_err:
                current_app.logger.warning("DLQ retry failed, trying direct requeue: %s", dlq_err)

        # Transition status to QUEUED
        requeued = MessageRepository.requeue_failed_message(
            message_id=message_id,
            organization_id=organization_id
        )

        if not requeued:
            if current_status == "DEAD":
                requeued = MessageRepository.requeue_dead_message(
                    message_id=message_id,
                    previous_retry_count=message.get("retry_count", 0),
                    organization_id=organization_id
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
                args=[message_id]
            )
            return {
                "success": True,
                "status_code": 200,
                "message": "Message successfully requeued for retry",
                "message_id": message_id,
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
                "status": "QUEUED"
            }

    @classmethod
    def queue_message(cls, message_id, organization_id):
        """
        Safely queue a message for processing:
        - Verifies message exists and belongs to the authenticated organization.
        - Allows queueing only from valid initial states (CREATED, VALIDATED).
        - Prevents duplicate dispatches and concurrent queue requests.
        - Atomically transitions status to QUEUED.
        - Dispatches task to Celery.
        - Safely rolls back status if broker dispatch fails.
        """
        message = MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id
        )

        if not message:
            return {
                "success": False,
                "status_code": 404,
                "message": "Message not found"
            }

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
            organization_id=organization_id
        )

        if not updated:
            refetched = MessageRepository.find_by_id(
                message_id,
                organization_id=organization_id
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

        # Dispatch Celery task
        try:
            task = current_app.celery.send_task(
                "senderx.process_message",
                args=[message_id]
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
                organization_id=organization_id
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
    def update_status(cls, message_id, new_status, organization_id):

        if new_status == "QUEUED":
            return cls.queue_message(message_id, organization_id)

        message = MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id
        )

        if not message:
            return {
                "success": False,
                "status_code": 404,
                "message": "Message not found"
            }

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
            organization_id=organization_id
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
                organization_id=organization_id
            )
        }

    @classmethod
    def handle_twilio_callback(cls, callback_data):
        """
        Process incoming Twilio StatusCallback events.
        Updates message delivery status, handles carrier errors, and records status history.
        """
        if not isinstance(callback_data, dict):
            return {"success": False, "status_code": 400, "message": "Invalid callback data"}

        provider_message_id = (
            callback_data.get("MessageSid")
            or callback_data.get("SmsSid")
            or callback_data.get("sms_sid")
            or callback_data.get("message_sid")
        )
        if not provider_message_id:
            return {"success": False, "status_code": 400, "message": "MessageSid is required"}

        raw_status = (
            callback_data.get("MessageStatus")
            or callback_data.get("SmsStatus")
            or callback_data.get("status")
            or ""
        ).lower().strip()

        error_code = callback_data.get("ErrorCode") or callback_data.get("error_code")
        error_message = callback_data.get("ErrorMessage") or callback_data.get("error_message")

        # Map Twilio status to SenderX status
        if raw_status == "delivered":
            new_status = "DELIVERED"
        elif raw_status in ("failed", "undelivered"):
            new_status = "FAILED"
        elif raw_status in ("sent", "sending"):
            new_status = "SENT"
        elif raw_status in ("queued", "accepted", "scheduled"):
            new_status = "ACCEPTED"
        else:
            new_status = raw_status.upper() or "ACCEPTED"

        message = MessageRepository.find_by_provider_message_id(provider_message_id)
        if not message:
            return {
                "success": False,
                "status_code": 404,
                "message": f"Message with provider_message_id '{provider_message_id}' not found"
            }

        updated = MessageRepository.update_delivery_status(
            provider_message_id=provider_message_id,
            new_status=new_status,
            raw_status=raw_status,
            error_code=error_code,
            error_message=error_message
        )

        return {
            "success": True,
            "status_code": 200,
            "message_id": message.get("message_id"),
            "provider_message_id": provider_message_id,
            "status": new_status,
            "raw_status": raw_status,
            "updated": updated
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

        # Check configured verify tokens across env and provider_configs
        valid_tokens = set()
        env_token = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN") or os.getenv("META_WEBHOOK_VERIFY_TOKEN")
        if env_token:
            valid_tokens.add(env_token.strip())

        cfg_token = current_app.config.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
        if cfg_token:
            valid_tokens.add(cfg_token.strip())

        # Also inspect stored provider configurations
        try:
            collection = current_app.mongo_db["provider_configs"]
            docs = collection.find({"provider": {"$in": ["meta", "whatsapp", "whatsapp_cloud"]}})
            for doc in docs:
                org_id = doc.get("organization_id")
                try:
                    decrypted = ProviderConfigService.get_decrypted_configuration(
                        doc.get("provider"),
                        organization_id=org_id
                    )
                    if decrypted and decrypted.get("webhook_verify_token"):
                        valid_tokens.add(decrypted["webhook_verify_token"].strip())
                except Exception:
                    pass
        except Exception:
            pass

        if hub_token.strip() in valid_tokens:
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
    def handle_whatsapp_webhook(cls, raw_payload: bytes, signature_header: Optional[str], json_data: Dict[str, Any]):
        """
        Process Meta WhatsApp webhook event payload.
        Verifies X-Hub-Signature-256, updates message delivery statuses,
        and saves inbound customer messages.
        """
        if not isinstance(json_data, dict):
            return {"success": False, "status_code": 400, "message": "Invalid webhook payload JSON"}

        # 1. Resolve App Secret for signature verification
        app_secret = (
            current_app.config.get("WHATSAPP_APP_SECRET")
            or os.getenv("WHATSAPP_APP_SECRET")
            or os.getenv("META_APP_SECRET")
        )

        # If not in env, try to resolve from provider_configs
        if not app_secret:
            try:
                collection = current_app.mongo_db["provider_configs"]
                docs = collection.find({"provider": {"$in": ["meta", "whatsapp", "whatsapp_cloud"]}})
                for doc in docs:
                    org_id = doc.get("organization_id")
                    try:
                        decrypted = ProviderConfigService.get_decrypted_configuration(
                            doc.get("provider"),
                            organization_id=org_id
                        )
                        if decrypted and decrypted.get("app_secret"):
                            app_secret = decrypted["app_secret"]
                            break
                    except Exception:
                        pass
            except Exception:
                pass

        # If app_secret is configured, strictly enforce signature verification
        if app_secret:
            from app.adapters.whatsapp.whatsapp_utils import verify_meta_signature
            if not signature_header:
                return {
                    "success": False,
                    "status_code": 401,
                    "message": "Missing X-Hub-Signature-256 header"
                }
            if not verify_meta_signature(raw_payload, signature_header, app_secret):
                return {
                    "success": False,
                    "status_code": 401,
                    "message": "Invalid webhook signature"
                }

        # 2. Process Entries
        processed_statuses = 0
        processed_messages = 0

        entries = json_data.get("entry", [])
        for entry in entries:
            waba_id = entry.get("id")
            changes = entry.get("changes", [])
            for ch in changes:
                val = ch.get("value", {})
                metadata = val.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id")

                # Process status updates (sent, delivered, read, failed)
                statuses = val.get("statuses", [])
                for st in statuses:
                    wamid = st.get("id")
                    raw_status = (st.get("status") or "").lower().strip()
                    errors = st.get("errors", [])
                    err_code = errors[0].get("code") if errors else None
                    err_msg = errors[0].get("message") or errors[0].get("title") if errors else None

                    if raw_status == "delivered":
                        norm_status = "DELIVERED"
                    elif raw_status == "read":
                        norm_status = "READ"
                    elif raw_status == "failed":
                        norm_status = "FAILED"
                    elif raw_status == "sent":
                        norm_status = "SENT"
                    else:
                        norm_status = raw_status.upper() or "ACCEPTED"

                    updated = MessageRepository.update_delivery_status(
                        provider_message_id=wamid,
                        new_status=norm_status,
                        raw_status=raw_status,
                        error_code=err_code,
                        error_message=err_msg
                    )
                    if updated:
                        processed_statuses += 1

                # Process inbound customer messages
                messages = val.get("messages", [])
                for msg in messages:
                    wamid = msg.get("id")
                    from_phone = msg.get("from")
                    msg_type = msg.get("type", "text")
                    if msg_type == "text" and isinstance(msg.get("text"), dict):
                        content = msg.get("text", {}).get("body")
                    else:
                        content = msg.get(msg_type)

                    cls.save_inbound_message(
                        channel="whatsapp",
                        provider="meta",
                        phone_number_id=phone_number_id,
                        waba_id=waba_id,
                        from_phone=from_phone,
                        provider_message_id=wamid,
                        message_type=msg_type,
                        content=content,
                        raw_data=msg
                    )
                    processed_messages += 1

        return {
            "success": True,
            "status_code": 200,
            "message": "Webhook processed successfully",
            "processed_statuses": processed_statuses,
            "processed_messages": processed_messages
        }

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
        raw_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Persist inbound customer message to the 'inbound_messages' MongoDB collection.
        Resolves tenant organization ID where possible and prevents duplicate event insertion.
        """
        collection = current_app.mongo_db["inbound_messages"]

        # Deduplication check
        existing = collection.find_one({"provider_message_id": provider_message_id}, {"_id": 0})
        if existing:
            return existing

        # Resolve organization_id from provider_configs
        organization_id = None
        try:
            configs_col = current_app.mongo_db["provider_configs"]
            candidates = list(configs_col.find({"provider": {"$in": ["meta", "whatsapp", "whatsapp_cloud"]}}))
            for c in candidates:
                org_id = c.get("organization_id")
                try:
                    decrypted = ProviderConfigService.get_decrypted_configuration(
                        c.get("provider"),
                        organization_id=org_id
                    )
                    if decrypted:
                        if phone_number_id and decrypted.get("phone_number_id") == phone_number_id:
                            organization_id = org_id
                            break
                        if waba_id and decrypted.get("business_account_id") == waba_id:
                            organization_id = org_id
                            break
                except Exception:
                    pass
        except Exception:
            pass

        doc = {
            "organization_id": organization_id,
            "channel": channel,
            "provider": provider,
            "phone_number_id": phone_number_id,
            "waba_id": waba_id,
            "from_phone": from_phone,
            "provider_message_id": provider_message_id,
            "message_type": message_type,
            "content": content,
            "raw_data": raw_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "processed": False
        }

        collection.insert_one(doc)
        doc.pop("_id", None)
        return doc


