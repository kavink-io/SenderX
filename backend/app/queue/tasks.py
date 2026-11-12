
from celery import shared_task
from flask import current_app

from app.engine.retry_manager import RetryManager
from app.engine.status_manager import StatusManager
from app.adapters.adapter_registry import AdapterRegistry
from app.modules.messages.repository import MessageRepository
from app.modules.dead_letters.repository import DeadLetterRepository


@shared_task(name="senderx.test_task")
def test_task(message):
    current_app.logger.info(
        f"SenderX Background Task: {message}"
    )

    return {
        "success": True,
        "message": message
    }


@shared_task(bind=True, name="senderx.process_message", max_retries=3)
def process_message(self, message_id):

    message = MessageRepository.find_by_id(message_id)

    if not message:
        return {
            "success": False,
            "message": "Message not found"
        }

    current_status = message.get("status")

    if current_status not in ["QUEUED", "RETRYING"]:
        return {
            "success": False,
            "message": f"Message cannot be processed: {current_status}"
        }

    transition = StatusManager.transition(
        current_status,
        "PROCESSING"
    )

    if not transition["success"]:
        return transition

    updated = MessageRepository.update_status(
        message_id,
        "PROCESSING",
        current_status
    )

    if not updated:
        return {
            "success": False,
            "message": "Could not update message status"
        }

    current_app.logger.info(
        f"Processing message: {message_id}"
    )

    try:
        provider = message.get("provider")

        if not provider:
            raise ValueError("Message provider is required")

        adapter = AdapterRegistry.get_adapter(provider)

        result = adapter.send(message)

        if not result.get("success"):
            raise RuntimeError(
                "Provider did not accept the message"
            )

        saved = MessageRepository.mark_sent(
            message_id=message_id,
            provider=provider,
            provider_message_id=result.get("provider_message_id")
        )

        if not saved:
            current_app.logger.error(
                f"Could not save SENT status for {message_id}"
            )

            return {
                "success": False,
                "message": "Provider accepted email, but status update failed"
            }

        current_app.logger.info(
            f"Message {message_id} accepted by {provider}"
        )

        return {
            "success": True,
            "message_id": message_id,
            "status": "SENT",
            "provider": provider,
            "provider_message_id": result.get("provider_message_id")
        }

    except Exception as error:

        retry_count = self.request.retries
        error_message = str(error)

        retryable = RetryManager.is_retryable_error(error)

        # Permanent errors must not be retried.
        if not retryable:

            saved = MessageRepository.mark_failed(
                message_id=message_id,
                retry_count=retry_count,
                error=error_message
            )

            current_app.logger.error(
                f"Permanent failure for {message_id}: {error_message}"
            )

            return {
                "success": False,
                "message_id": message_id,
                "status": "FAILED" if saved else "STATUS_UPDATE_FAILED",
                "retry_count": retry_count,
                "error": error_message
            }

        # Temporary error: check retry limit.
        retry_info = RetryManager.get_retry_status(retry_count)

        # All retry attempts exhausted.
        if not retry_info["success"]:

            saved = MessageRepository.update_retry_info(
                message_id=message_id,
                retry_count=retry_count,
                old_status="PROCESSING",
                new_status="DEAD",
                error=error_message
            )

            if not saved:
                current_app.logger.error(
                    f"Could not mark message {message_id} as DEAD"
                )

                return {
                    "success": False,
                    "message_id": message_id,
                    "status": "STATUS_UPDATE_FAILED"
                }

            # Fetch the latest message, including DEAD status
            dead_message = MessageRepository.find_by_id(message_id)

            try:
                DeadLetterRepository.save_from_message(
                    message=dead_message,
                    error=error_message
                )

                current_app.logger.error(
                    f"Message {message_id} moved to Dead Letter Queue"
                )

            except Exception:
                current_app.logger.exception(
                    f"Failed to store message {message_id} in DLQ"
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
                "retry_count": retry_count,
                "error": error_message
            }

        # Retry is available.
        delay = retry_info["delay"]
        next_retry_count = retry_info["retry_count"]

        saved = MessageRepository.update_retry_info(
            message_id=message_id,
            retry_count=next_retry_count,
            old_status="PROCESSING",
            new_status="RETRYING",
            error=error_message
        )

        if not saved:
            current_app.logger.error(
                f"Could not save retry information for {message_id}"
            )

            return {
                "success": False,
                "message": "Could not save retry information"
            }

        current_app.logger.warning(
            f"Message {message_id} retrying in {delay} seconds. "
            f"Retry {next_retry_count} of {RetryManager.MAX_RETRIES}"
        )

        raise self.retry(
            exc=error,
            countdown=delay
        )


@shared_task(
    bind=True,
    name="senderx.retry_test_task",
    max_retries=3
)
def retry_test_task(self):

    retry_count = self.request.retries

    current_app.logger.warning(
        f"Retry test attempt: {retry_count + 1}"
    )

    try:
        raise ConnectionError(
            "Simulated provider connection failure"
        )

    except Exception as error:

        retry_info = RetryManager.get_retry_status(
            retry_count
        )

        if not retry_info["success"]:
            return {
                "success": False,
                "status": "DEAD",
                "error": str(error)
            }

        delay = retry_info["delay"]

        current_app.logger.warning(
            f"Retrying in {delay} seconds"
        )

        raise self.retry(
            exc=error,
            countdown=delay
        )
