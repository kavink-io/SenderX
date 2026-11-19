
from celery import shared_task
from flask import current_app

from app.engine.status_manager import StatusManager
from app.engine.retry_manager import RetryManager

from app.modules.messages.repository import MessageRepository
from app.modules.dead_letters.repository import DeadLetterRepository

from app.adapters.adapter_registry import AdapterRegistry


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

        adapter = AdapterRegistry.get_adapter(
            provider=provider,
            channel=channel,
            organization_id=organization_id
        )

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
        error_message = str(error)

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
