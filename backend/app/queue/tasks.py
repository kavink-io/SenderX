
from celery import shared_task
from flask import current_app

from app.engine.status_manager import StatusManager
from app.engine.retry_manager import RetryManager

from app.modules.messages.repository import MessageRepository
from app.modules.dead_letters.repository import DeadLetterRepository

from app.adapters.adapter_registry import AdapterRegistry
from app.modules.dead_letters.sanitizer import sanitize_dlq_error


@shared_task(
    bind=True,
    name="senderx.send_auth_otp_email",
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3}
)
def send_auth_otp_email(self, encrypted_payload, provider):
    from app.modules.auth.otp_service import OTPService

    try:
        OTPService.send_email(encrypted_payload, provider)
    except Exception as error:
        current_app.logger.error(
            "Authentication email delivery failed for provider %s (%s)",
            provider,
            type(error).__name__
        )
        raise RuntimeError("Authentication email delivery failed") from None


# ======================================================
# PROCESS MESSAGE
# ======================================================

@shared_task(
    bind=True,
    name="senderx.process_message",
    max_retries=3
)
def process_message(self, message_id):

    # --------------------------------------------------
    # 1. Retrieve message and trusted organization ID
    # --------------------------------------------------

    message = MessageRepository.find_by_id(message_id)

    if not message:
        return {
            "success": False,
            "message": "Message not found"
        }

    organization_id = message.get("organization_id")
    current_status = message.get("status")

    if current_status not in ["QUEUED", "RETRYING"]:
        return {
            "success": False,
            "message": f"Message cannot be processed: {current_status}"
        }

    # --------------------------------------------------
    # 2. Validate status transition
    # --------------------------------------------------

    transition = StatusManager.transition(
        current_status,
        "PROCESSING"
    )

    if not transition["success"]:
        return transition

    # --------------------------------------------------
    # 3. Update message status with tenant scope
    # --------------------------------------------------

    updated = MessageRepository.update_status(
        message_id=message_id,
        new_status="PROCESSING",
        old_status=current_status,
        organization_id=organization_id
    )

    if not updated:
        return {
            "success": False,
            "message": "Could not update message status"
        }

    current_app.logger.info(
        "Processing message: %s | Organization: %s",
        message_id,
        organization_id
    )

    try:

        # --------------------------------------------------
        # 4. Send through configured provider
        # --------------------------------------------------

        provider = message.get("provider")
        channel = message.get("channel")

        if not provider and channel not in ("email", "sms", "whatsapp", "microsoft_teams", "teams"):
            raise ValueError("Message provider is required")

        extra_kwargs = {}
        whatsapp_integration = None
        whatsapp_legacy_template = False
        whatsapp_data = None
        if channel == "whatsapp":
            data_dict = message.get("data") if isinstance(message.get("data"), dict) else {}
            whatsapp_data = data_dict
            int_id = (
                message.get("whatsapp_integration_id")
                or message.get("integration_id")
                or data_dict.get("whatsapp_integration_id")
                or data_dict.get("integration_id")
            )
            from_phone = (
                message.get("from_phone_number_id")
                or message.get("from")
                or data_dict.get("from_phone_number_id")
                or data_dict.get("from")
            )
            if int_id:
                extra_kwargs["integration_id"] = str(int_id).strip()
            if from_phone:
                extra_kwargs["from_phone_number_id"] = str(from_phone).strip()

            # Enforce Meta's 24-hour customer service window at dispatch time,
            # using the tenant's connected integration and provider timestamps.
            from app.modules.whatsapp.repository import WhatsAppIntegrationRepository
            from app.modules.messages.service import MessageService

            integration = None
            if int_id:
                integration = WhatsAppIntegrationRepository.find_by_id(
                    str(int_id).strip(), organization_id=organization_id,
                    include_deleted=False,
                )
            elif from_phone:
                integration = WhatsAppIntegrationRepository.find_by_phone_number_id(
                    str(from_phone).strip(), organization_id=organization_id,
                    include_deleted=False,
                )
            else:
                integrations = WhatsAppIntegrationRepository.find_active_by_organization(organization_id)
                if len(integrations) == 1:
                    integration = integrations[0]

            is_template_message = (
                str(data_dict.get("type") or "").strip().lower() == "template"
                or bool(data_dict.get("template") or data_dict.get("template_name"))
            )
            if (not integration or integration.get("status") != "CONNECTED") and is_template_message and not int_id and not from_phone:
                # Preserve the legacy organization-level provider configuration path
                # only when this organization has never managed a WhatsApp integration.
                # Platform/global credentials and implicit fallback are not sufficient
                # to establish a safe tenant boundary here.
                known_integrations = WhatsAppIntegrationRepository.find_all_by_organization(
                    organization_id, include_deleted=True
                )
                provider_keys = [provider, "meta", "whatsapp", "whatsapp_cloud"]
                has_org_credentials = False
                for provider_key in dict.fromkeys(key for key in provider_keys if key):
                    configured = current_app.mongo_db["provider_configs"].find_one({
                        "provider": str(provider_key).lower().strip(),
                        "organization_id": organization_id,
                        "configured": True,
                    }, {"_id": 1})
                    if configured:
                        from app.modules.provider_config.service import ProviderConfigService
                        scoped_credentials = ProviderConfigService.get_decrypted_configuration(
                            str(provider_key).lower().strip(), organization_id=organization_id
                        )
                        has_org_credentials = bool(
                            isinstance(scoped_credentials, dict)
                            and scoped_credentials.get("access_token")
                            and scoped_credentials.get("phone_number_id")
                        )
                        if has_org_credentials:
                            break
                if not known_integrations and has_org_credentials:
                    whatsapp_legacy_template = True

            if (not integration or integration.get("status") != "CONNECTED") and not whatsapp_legacy_template:
                raise ValueError(
                    "Cannot verify WhatsApp customer service window: a connected tenant integration is required."
                )
            whatsapp_integration = integration

            interactive = data_dict.get("interactive") if isinstance(data_dict.get("interactive"), dict) else {}
            interactive_type = str(interactive.get("type") or "").strip().lower()
            if interactive_type in {"product", "product_list", "catalog_message"}:
                if not integration or integration.get("status") != "CONNECTED":
                    raise ValueError("WhatsApp product and catalog messages require a connected tenant integration")
                configured_catalog_id = integration.get("catalog_id")
                if not configured_catalog_id:
                    raise ValueError("WhatsApp product and catalog messages require a catalog ID configured on the selected integration")
                action = interactive.get("action")
                if not isinstance(action, dict):
                    raise ValueError("WhatsApp product and catalog messages require a valid interactive action")
                if interactive_type in {"product", "product_list"}:
                    supplied_catalog_id = action.get("catalog_id")
                    if supplied_catalog_id is not None and str(supplied_catalog_id).strip() != str(configured_catalog_id).strip():
                        raise ValueError("Message catalog_id does not match the selected WhatsApp integration catalog")
                    # The selected tenant integration is authoritative for the Meta catalog.
                    action["catalog_id"] = str(configured_catalog_id)

        adapter = AdapterRegistry.get_adapter(
            provider=provider,
            channel=channel,
            organization_id=organization_id,
            **extra_kwargs
        )

        # Final tenant-scoped window query is deliberately adjacent to send().
        # It runs on every task attempt, so delayed/retried messages see the latest
        # persisted inbound customer timestamp.
        if channel == "whatsapp" and not whatsapp_legacy_template:
            from app.modules.messages.service import MessageService

            window = MessageService.check_whatsapp_customer_service_window(
                recipient=message.get("recipient"),
                organization_id=organization_id,
                phone_number_id=whatsapp_integration.get("phone_number_id"),
                integration_id=whatsapp_integration.get("integration_id"),
                data=whatsapp_data,
            )
            if not window["allowed"]:
                raise ValueError(window["reason"])

        result = adapter.send(message)

        if not result.get("success"):
            raise RuntimeError(
                "Provider did not accept the message"
            )

        # --------------------------------------------------
        # 5. Mark message as SENT
        # --------------------------------------------------

        actual_provider = result.get("provider") or provider or "unknown"

        saved = MessageRepository.mark_sent(
            message_id=message_id,
            provider=actual_provider,
            provider_message_id=result.get(
                "provider_message_id"
            ),
            organization_id=organization_id
        )

        if not saved:

            current_app.logger.error(
                "Could not save SENT status for %s",
                message_id
            )

            return {
                "success": False,
                "message": (
                    "Provider accepted message, "
                    "but status update failed"
                ),
                "message_id": message_id,
                "status": "STATUS_UPDATE_FAILED"
            }

        current_app.logger.info(
            "Message %s accepted by provider %s",
            message_id,
            provider
        )

        # --------------------------------------------------
        # 5.1 Resolve DLQ after successful manual retry
        # --------------------------------------------------

        try:

            dlq_record = DeadLetterRepository.find_by_message_id(
                message_id,
                organization_id=organization_id
            )

            if (
                dlq_record
                and dlq_record.get("dead_letter_status") == "RETRY_QUEUED"
                and dlq_record.get("manual_retry_dispatch_state") == "QUEUED"
            ):

                # The Celery task ID is stable across automatic
                # retries of the same task.
                manual_task_id = self.request.id

                stored_task_id = dlq_record.get(
                    "manual_retry_task_id"
                )

                # Ensure this worker belongs to the queued
                # manual retry request.
                if manual_task_id == stored_task_id:

                    resolved = (
                        DeadLetterRepository.mark_manual_retry_completed(
                            message_id=message_id,
                            task_id=manual_task_id,
                            provider_message_id=result.get(
                                "provider_message_id"
                            ),
                            organization_id=organization_id
                        )
                    )

                    if resolved:

                        current_app.logger.info(
                            "DLQ record successfully resolved: %s",
                            message_id
                        )

                    else:

                        current_app.logger.error(
                            "Message SENT, but DLQ resolution failed: %s",
                            message_id
                        )

                else:

                    current_app.logger.warning(
                        "DLQ task ID mismatch for message %s",
                        message_id
                    )

        except Exception:

            # A DLQ update failure must not turn a successfully
            # delivered message into a failed message.
            current_app.logger.exception(
                "Message SENT, but DLQ resolution encountered "
                "an error: %s",
                message_id
            )

        # --------------------------------------------------
        # 6. Return successful delivery
        # --------------------------------------------------

        return {
            "success": True,
            "message_id": message_id,
            "status": "SENT",
            "provider": provider,
            "provider_message_id": result.get(
                "provider_message_id"
            )
        }

    except Exception as error:

        retry_count = self.request.retries
        error_message = sanitize_dlq_error(str(error))

        current_app.logger.error(
            "Message processing error: %s | Retry: %s | Error: %s",
            message_id,
            retry_count,
            error_message
        )

        retryable = RetryManager.is_retryable_error(error)

        # --------------------------------------------------
        # 7. Permanent errors are not retried
        # --------------------------------------------------

        if not retryable:

            saved = MessageRepository.mark_failed(
                message_id=message_id,
                retry_count=retry_count,
                error=error_message,
                organization_id=organization_id
            )

            current_app.logger.error(
                "Permanent failure for message %s: %s",
                message_id,
                error_message
            )

            return {
                "success": False,
                "message_id": message_id,
                "status": (
                    "FAILED" if saved
                    else "STATUS_UPDATE_FAILED"
                ),
                "retry_count": retry_count,
                "error": error_message
            }

        # --------------------------------------------------
        # 8. Check automatic retry limit
        # --------------------------------------------------

        retry_after = getattr(error, "retry_after", None)
        retry_info = RetryManager.get_retry_status(
            retry_count,
            retry_after=retry_after
        )

        # --------------------------------------------------
        # 9. Automatic retries exhausted
        # --------------------------------------------------

        if not retry_info["success"]:

            saved = MessageRepository.update_retry_info(
                message_id=message_id,
                retry_count=retry_count,
                old_status="PROCESSING",
                new_status="DEAD",
                error=error_message,
                organization_id=organization_id
            )

            if not saved:

                current_app.logger.error(
                    "Could not mark message %s as DEAD",
                    message_id
                )

                return {
                    "success": False,
                    "message_id": message_id,
                    "status": "STATUS_UPDATE_FAILED"
                }

            # Fetch latest DEAD message.
            dead_message = MessageRepository.find_by_id(
                message_id,
                organization_id=organization_id
            )

            if not dead_message:

                current_app.logger.error(
                    "Could not retrieve DEAD message %s",
                    message_id
                )

                return {
                    "success": False,
                    "message_id": message_id,
                    "status": "DEAD",
                    "dlq_saved": False
                }

            # --------------------------------------------------
            # 10. Verify trusted tenant information
            # --------------------------------------------------

            current_app.logger.info(
                "DLQ DEBUG | message_id=%s | organization_id=%s",
                message_id,
                organization_id
            )

            if dead_message.get("organization_id") != organization_id:

                current_app.logger.error(
                    "Organization ID mismatch for message %s",
                    message_id
                )

                return {
                    "success": False,
                    "message_id": message_id,
                    "status": "DEAD",
                    "dlq_saved": False,
                    "error": "Organization ID mismatch"
                }

            # --------------------------------------------------
            # 11. Save message in Dead Letter Queue
            # --------------------------------------------------

            try:

                dlq_record = DeadLetterRepository.save_from_message(
                    message=dead_message,
                    error=error_message,
                    organization_id=organization_id
                )

                if not dlq_record:
                    raise RuntimeError(
                        "DLQ repository returned no saved record"
                    )

                if dlq_record.get("organization_id") != organization_id:
                    raise RuntimeError(
                        "Saved DLQ record has incorrect organization ID"
                    )

                current_app.logger.info(
                    "Message %s successfully saved in DLQ",
                    message_id
                )

            except Exception:

                current_app.logger.exception(
                    "Failed to store message %s in DLQ",
                    message_id
                )

                return {
                    "success": False,
                    "message_id": message_id,
                    "status": "DEAD",
                    "dlq_saved": False,
                    "error": error_message
                }

            return {
                "success": False,
                "message_id": message_id,
                "status": "DEAD",
                "dlq_saved": True,
                "organization_id": organization_id,
                "retry_count": retry_count,
                "error": error_message
            }

        # --------------------------------------------------
        # 12. Automatic retry is available
        # --------------------------------------------------

        delay = retry_info["delay"]
        next_retry_count = retry_info["retry_count"]

        saved = MessageRepository.update_retry_info(
            message_id=message_id,
            retry_count=next_retry_count,
            old_status="PROCESSING",
            new_status="RETRYING",
            error=error_message,
            organization_id=organization_id
        )

        if not saved:

            current_app.logger.error(
                "Could not save retry information for %s",
                message_id
            )

            return {
                "success": False,
                "message": "Could not save retry information"
            }

        current_app.logger.warning(
            "Message %s retrying in %s seconds. Retry %s of %s",
            message_id,
            delay,
            next_retry_count,
            RetryManager.MAX_RETRIES
        )

        # Celery will retry the same task using the same task ID.
        raise self.retry(
            exc=error,
            countdown=delay
        )


# ======================================================
# RETRY TEST TASK
# ======================================================

@shared_task(
    bind=True,
    name="senderx.retry_test_task",
    max_retries=3
)
def retry_test_task(self):

    retry_count = self.request.retries

    current_app.logger.info(
        "Retry test task running. Attempt: %s",
        retry_count + 1
    )

    try:

        # Simulate a temporary network failure.
        raise ConnectionError(
            "Simulated temporary network failure"
        )

    except Exception as error:

        retry_after = getattr(error, "retry_after", None)
        retry_info = RetryManager.get_retry_status(
            retry_count,
            retry_after=retry_after
        )

        if not retry_info["success"]:

            current_app.logger.error(
                "Retry test task exhausted all retries"
            )

            return {
                "success": False,
                "status": "FAILED",
                "retry_count": retry_count,
                "error": str(error)
            }

        delay = retry_info["delay"]

        current_app.logger.warning(
            "Retry test task will retry in %s seconds",
            delay
        )

        raise self.retry(
            exc=error,
            countdown=delay
        )
