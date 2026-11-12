
from flask import current_app

from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.messages.repository import MessageRepository


class DeadLetterService:

    @staticmethod
    def get_all_dead_letters(
        limit=50,
        page=1,
        status=None,
        message_id=None,
        recipient=None,
        provider=None
    ):
        try:
            limit = int(limit)
            page = int(page)

            if limit < 1 or limit > 100:
                return {
                    "success": False,
                    "message": "Limit must be between 1 and 100"
                }

            if page < 1:
                return {
                    "success": False,
                    "message": "Page must be greater than or equal to 1"
                }

            result = DeadLetterRepository.find_all(
                limit=limit,
                page=page,
                status=status,
                message_id=message_id,
                recipient=recipient,
                provider=provider,
                include_metadata=True
            )

            return {
                "success": True,
                "count": len(result["items"]),
                "total_count": result["pagination"]["total"],
                "pagination": result["pagination"],
                "filters": {
                    "status": status,
                    "message_id": message_id,
                    "recipient": recipient,
                    "provider": provider
                },
                "data": result["items"]
            }

        except (TypeError, ValueError):
            return {
                "success": False,
                "message": "Invalid pagination or filter value"
            }

        except Exception:
            current_app.logger.exception(
                "Failed to retrieve dead letters"
            )

            return {
                "success": False,
                "message": "Failed to retrieve dead letters"
            }

    @staticmethod
    def get_statistics():
        try:
            statistics = DeadLetterRepository.get_statistics()

            return {
                "success": True,
                "data": statistics
            }

        except Exception:
            current_app.logger.exception(
                "Failed to retrieve DLQ statistics"
            )

            return {
                "success": False,
                "message": "Failed to retrieve DLQ statistics"
            }

    @staticmethod
    def get_provider_analytics():
        try:
            analytics = DeadLetterRepository.get_provider_analytics()

            return {
                "success": True,
                "data": analytics
            }

        except Exception:
            current_app.logger.exception(
                "Failed to retrieve provider analytics"
            )

            return {
                "success": False,
                "message": "Failed to retrieve provider analytics"
            }

    @staticmethod
    def get_dead_letter(message_id):
        try:
            dead_letter = DeadLetterRepository.find_by_message_id(
                message_id
            )

            if not dead_letter:
                return {
                    "success": False,
                    "message": "Dead letter not found"
                }

            return {
                "success": True,
                "data": dead_letter
            }

        except Exception:
            current_app.logger.exception(
                "Failed to retrieve dead letter %s",
                message_id
            )

            return {
                "success": False,
                "message": "Failed to retrieve dead letter"
            }

    @staticmethod
    def get_retry_history(message_id):
        try:
            dead_letter = DeadLetterRepository.find_by_message_id(
                message_id
            )

            if not dead_letter:
                return {
                    "success": False,
                    "message": "Dead letter not found"
                }

            manual_retry_history = dead_letter.get(
                "manual_retry_history", []
            )

            failure_cycles = dead_letter.get(
                "failure_cycles", []
            )

            status_history = dead_letter.get(
                "status_history", []
            )

            return {
                "success": True,
                "message_id": message_id,
                "summary": {
                    "manual_retry_count": dead_letter.get(
                        "manual_retry_count", 0
                    ),
                    "automatic_retry_count": dead_letter.get(
                        "retry_count", 0
                    ),
                    "total_manual_attempts": len(
                        manual_retry_history
                    ),
                    "total_failure_cycles": len(
                        failure_cycles
                    )
                },
                "manual_retry_history": manual_retry_history,
                "failure_cycles": failure_cycles,
                "status_history": status_history
            }

        except Exception:
            current_app.logger.exception(
                "Failed to retrieve retry history for %s",
                message_id
            )

            return {
                "success": False,
                "message": "Failed to retrieve retry history"
            }

    @staticmethod
    def delete_dead_letter(message_id, confirm=False):
        try:
            if confirm is not True:
                return {
                    "success": False,
                    "message": "Explicit deletion confirmation is required"
                }

            dead_letter = DeadLetterRepository.find_by_message_id(
                message_id
            )

            if not dead_letter:
                return {
                    "success": False,
                    "message": "Dead letter not found"
                }

            if dead_letter.get("dead_letter_status") != "PENDING_REVIEW":
                return {
                    "success": False,
                    "message": "Only PENDING_REVIEW messages can be deleted"
                }

            deleted = DeadLetterRepository.delete_by_message_id(
                message_id
            )

            if not deleted:
                return {
                    "success": False,
                    "message": "Deletion failed. DLQ status may have changed"
                }

            current_app.logger.warning(
                "Dead letter permanently deleted: %s",
                message_id
            )

            return {
                "success": True,
                "message": "Dead letter permanently deleted",
                "message_id": message_id,
                "original_message_preserved": True
            }

        except Exception:
            current_app.logger.exception(
                "Failed to delete dead letter %s",
                message_id
            )

            return {
                "success": False,
                "message": "Failed to delete dead letter"
            }

    @staticmethod
    def retry_dead_letter(message_id):

        reserved = False
        requeued = False
        dispatched = False

        previous_retry_count = 0
        previous_manual_retry_count = 0

        try:
            # 1. Retrieve DLQ record.
            dead_letter = DeadLetterRepository.find_by_message_id(
                message_id
            )

            if not dead_letter:
                return {
                    "success": False,
                    "message": "Dead letter not found"
                }

            if dead_letter.get("dead_letter_status") != "PENDING_REVIEW":
                return {
                    "success": False,
                    "message": "Dead letter is not available for retry"
                }

            # 2. Retrieve original message.
            message = MessageRepository.find_by_id(message_id)

            if not message:
                return {
                    "success": False,
                    "message": "Original message not found"
                }

            if message.get("status") != "DEAD":
                return {
                    "success": False,
                    "message": "Original message is not in DEAD status"
                }

            previous_retry_count = message.get("retry_count", 0)
            previous_manual_retry_count = message.get(
                "manual_retry_count", 0
            )

            # 3. Reserve DLQ and persist dispatch intent.
            dispatch = DeadLetterRepository.mark_retry_requested(
                message_id
            )

            if not dispatch:
                return {
                    "success": False,
                    "message": "Retry already requested or DLQ status changed"
                }

            reserved = True
            task_id = dispatch["task_id"]

            # 4. Requeue original message.
            requeued = MessageRepository.requeue_dead_message(
                message_id,
                previous_retry_count
            )

            if not requeued:
                restored = DeadLetterRepository.restore_pending_review(
                    message_id
                )

                return {
                    "success": False,
                    "message": "Could not requeue original message",
                    "dlq_restored": restored
                }

            # 5. Publish using the pre-generated task ID.
            try:
                task = current_app.celery.send_task(
                    "senderx.process_message",
                    args=[message_id],
                    task_id=task_id
                )

                dispatched = True

            except Exception as error:
                current_app.logger.exception(
                    "Manual retry dispatch outcome uncertain for %s",
                    message_id
                )

                # Do NOT roll back here.
                # The broker may have accepted the task before the
                # publishing error was reported.

                return {
                    "success": False,
                    "message": "Dispatch outcome uncertain; recovery required",
                    "message_id": message_id,
                    "task_id": task_id,
                    "dispatch_state": "DISPATCHING",
                    "error": str(error)
                }

            # 6. Record successful dispatch.
            audit_updated = DeadLetterRepository.mark_retry_queued(
                message_id,
                task.id
            )

            if not audit_updated:
                current_app.logger.error(
                    "Task %s was published but DLQ update failed for %s",
                    task.id,
                    message_id
                )

                return {
                    "success": True,
                    "message": "Task published; DLQ reconciliation required",
                    "message_id": message_id,
                    "task_id": task.id,
                    "dispatch_state": "DISPATCHING",
                    "audit_updated": False
                }

            return {
                "success": True,
                "message": "Manual retry successfully queued",
                "message_id": message_id,
                "previous_retry_count": previous_retry_count,
                "previous_manual_retry_count": previous_manual_retry_count,
                "current_retry_count": 0,
                "status": "QUEUED",
                "task_id": task.id,
                "audit_updated": True
            }

        except Exception:
            current_app.logger.exception(
                "Unexpected error during manual retry for %s",
                message_id
            )

            # Only compensate before a dispatch has been attempted.
            if reserved and requeued and not dispatched:
                try:
                    rollback_success = MessageRepository.rollback_manual_retry(
                        message_id,
                        previous_retry_count,
                        previous_manual_retry_count
                    )

                    restored = DeadLetterRepository.restore_pending_review(
                        message_id
                    )

                except Exception:
                    current_app.logger.exception(
                        "Pre-dispatch compensation failed for %s",
                        message_id
                    )

                    rollback_success = False
                    restored = False

                return {
                    "success": False,
                    "message": "Manual retry failed before dispatch",
                    "rollback_success": rollback_success,
                    "dlq_restored": restored
                }

            return {
                "success": False,
                "message": "Unexpected error; inspect dispatch state",
                "message_id": message_id
            }
    @staticmethod
    def get_failure_trends(
        start_date=None,
        end_date=None,
        provider=None
    ):
        try:
            trends = DeadLetterRepository.get_daily_failure_trends(
                start_date=start_date,
                end_date=end_date,
                provider=provider
            )

            return {
                "success": True,
                "count": len(trends),
                "data": trends
            }

        except ValueError:
            raise

        except Exception:
            current_app.logger.exception(
                "Failed to retrieve DLQ failure trends"
            )

            return {
                "success": False,
                "message": "Unable to retrieve failure trends"
            }


    @staticmethod
    def recover_stale_dispatches(minutes=5, limit=100):

        try:
            # 1. Find stale dispatch records.
            stale_records = DeadLetterRepository.find_stale_dispatches(
                minutes=minutes,
                limit=limit
            )

            recovered = []
            skipped = []

            # 2. Mark each record for investigation.
            for record in stale_records:

                message_id = record.get("message_id")
                task_id = record.get("manual_retry_task_id")

                if not message_id or not task_id:
                    skipped.append({
                        "message_id": message_id,
                        "reason": "Missing message ID or task ID"
                    })
                    continue

                updated = DeadLetterRepository.mark_dispatch_recovery_required(
                    message_id,
                    task_id
                )

                if updated:
                    recovered.append({
                        "message_id": message_id,
                        "task_id": task_id,
                        "status": "RECOVERY_REQUIRED"
                    })
                else:
                    skipped.append({
                        "message_id": message_id,
                        "reason": "Record changed during recovery"
                    })

            return {
                "success": True,
                "message": "Stale dispatch scan completed",
                "total_found": len(stale_records),
                "total_marked": len(recovered),
                "total_skipped": len(skipped),
                "recovered": recovered,
                "skipped": skipped
            }

        except Exception:
            current_app.logger.exception(
                "Stale dispatch recovery failed"
            )

            return {
                "success": False,
                "message": "Stale dispatch recovery failed"
            }   

    @staticmethod
    def inspect_dispatch_task(task_id):

        try:
            celery = current_app.celery

            result = celery.AsyncResult(task_id)

            return {
                "success": True,
                "task_id": task_id,
                "state": result.state,
                "ready": result.ready(),
                "successful": result.successful(),
                "failed": result.failed()
            }

        except Exception:
            current_app.logger.exception(
                "Could not inspect Celery task %s",
                task_id
            )

            return {
                "success": False,
                "task_id": task_id,
                "message": "Could not inspect Celery task"
            }     
    @staticmethod
    def inspect_recovery_required():

        try:
            records = DeadLetterRepository._collection().find(
                {
                    "manual_retry_dispatch_state": "RECOVERY_REQUIRED"
                },
                {
                    "_id": 0,
                    "message_id": 1,
                    "manual_retry_task_id": 1,
                    "manual_retry_count": 1
                }
            )

            results = []

            for record in records:

                task_id = record.get("manual_retry_task_id")

                if not task_id:
                    continue

                task_info = DeadLetterService.inspect_dispatch_task(
                    task_id
                )

                results.append({
                    "message_id": record.get("message_id"),
                    "task_id": task_id,
                    "task_state": task_info.get("state"),
                    "inspection_success": task_info.get("success")
                })

            return {
                "success": True,
                "total": len(results),
                "data": results
            }

        except Exception:
            current_app.logger.exception(
                "Recovery inspection failed"
            )

            return {
                "success": False,
                "message": "Recovery inspection failed"
            }

    
    @staticmethod
    def reconcile_recovery_required():

        try:
            records = DeadLetterRepository._collection().find(
                {
                    "manual_retry_dispatch_state": "RECOVERY_REQUIRED"
                },
                {
                    "_id": 0,
                    "message_id": 1,
                    "manual_retry_task_id": 1,
                    "manual_retry_count": 1
                }
            )

            results = []

            for record in records:

                message_id = record.get("message_id")
                task_id = record.get("manual_retry_task_id")

                if not message_id or not task_id:
                    results.append({
                        "message_id": message_id,
                        "task_id": task_id,
                        "classification": "INVALID_RECORD",
                        "recommended_action": "MANUAL_INVESTIGATION"
                    })
                    continue

                # 1. Inspect Celery task state.
                task_info = DeadLetterService.inspect_dispatch_task(
                    task_id
                )

                if not task_info.get("success"):
                    results.append({
                        "message_id": message_id,
                        "task_id": task_id,
                        "classification": "TASK_STATE_UNAVAILABLE",
                        "recommended_action": "MANUAL_INVESTIGATION"
                    })
                    continue

                task_state = task_info.get("state")

                # 2. Inspect original MongoDB message.
                message = MessageRepository.find_by_id(message_id)

                if not message:
                    classification = "MESSAGE_NOT_FOUND"
                    action = "MANUAL_INVESTIGATION"
                    message_status = None

                else:
                    message_status = message.get("status")

                    # 3. MongoDB message status takes priority.
                    if message_status in ["SENT", "DELIVERED", "READ"]:

                        classification = "MESSAGE_COMPLETED"
                        action = "VERIFY_AND_CLOSE_RECOVERY"

                    elif message_status == "DEAD":

                        classification = "MESSAGE_DEAD"
                        action = "INSPECT_DLQ_BEFORE_RETRY"

                    elif message_status == "PROCESSING":

                        classification = "MESSAGE_PROCESSING"
                        action = "WAIT_AND_MONITOR"

                    elif message_status == "RETRYING":

                        classification = "AUTOMATIC_RETRY_IN_PROGRESS"
                        action = "WAIT_AND_MONITOR"

                    elif message_status == "FAILED":

                        classification = "MESSAGE_FAILED"
                        action = "INSPECT_FAILURE_BEFORE_RETRY"

                    elif message_status == "QUEUED":

                        if task_state == "STARTED":
                            classification = "CELERY_TASK_RUNNING"
                            action = "WAIT_AND_MONITOR"

                        elif task_state == "RETRY":
                            classification = "CELERY_RETRY_SCHEDULED"
                            action = "WAIT_AND_MONITOR"

                        elif task_state == "FAILURE":
                            classification = "CELERY_TASK_FAILED"
                            action = "INSPECT_FAILURE_BEFORE_RETRY"

                        elif task_state == "REVOKED":
                            classification = "CELERY_TASK_REVOKED"
                            action = "MANUAL_INVESTIGATION"

                        elif task_state == "SUCCESS":
                            classification = "TASK_COMPLETED_MESSAGE_UNCONFIRMED"
                            action = "VERIFY_MESSAGE_AND_PROVIDER"

                        elif task_state == "PENDING":
                            classification = "TASK_STATE_UNKNOWN"
                            action = "DO_NOT_REPUBLISH_AUTOMATICALLY"

                        else:
                            classification = "MESSAGE_QUEUED_TASK_UNCONFIRMED"
                            action = "VERIFY_BROKER_AND_TASK"

                    else:
                        classification = "UNEXPECTED_STATE"
                        action = "MANUAL_INVESTIGATION"

                # 4. Build reconciliation result.
                results.append({
                    "message_id": message_id,
                    "task_id": task_id,
                    "celery_state": task_state,
                    "message_status": message_status,
                    "classification": classification,
                    "recommended_action": action
                })

            return {
                "success": True,
                "total": len(results),
                "data": results
            }

        except Exception:
            current_app.logger.exception(
                "Recovery reconciliation failed"
            )

            return {
                "success": False,
                "message": "Recovery reconciliation failed"
            }

    @staticmethod
    def resolve_recovery(message_id, resolved_by, notes=None):

        try:
            # 1. Find the DLQ record.
            dead_letter = DeadLetterRepository.find_by_message_id(
                message_id
            )

            if not dead_letter:
                return {
                    "success": False,
                    "message": "Dead letter not found"
                }

            # 2. Verify recovery state.
            if (
                dead_letter.get("dead_letter_status") != "RETRY_REQUESTED"
                or dead_letter.get("manual_retry_dispatch_state")
                != "RECOVERY_REQUIRED"
            ):
                return {
                    "success": False,
                    "message": "Record is not awaiting recovery resolution"
                }

            task_id = dead_letter.get("manual_retry_task_id")

            if not task_id:
                return {
                    "success": False,
                    "message": "Celery task ID is missing"
                }

            # 3. Inspect Celery task.
            task_info = DeadLetterService.inspect_dispatch_task(task_id)

            if not task_info.get("success"):
                return {
                    "success": False,
                    "message": "Could not verify Celery task"
                }

            if task_info.get("state") != "SUCCESS":
                return {
                    "success": False,
                    "message": "Celery task has not completed successfully"
                }

            # 4. Verify original message.
            message = MessageRepository.find_by_id(message_id)

            if not message:
                return {
                    "success": False,
                    "message": "Original message not found"
                }

            message_status = message.get("status")

            if message_status not in ["SENT", "DELIVERED", "READ"]:
                return {
                    "success": False,
                    "message": "Message is not in a completed state",
                    "message_status": message_status
                }

            # 5. Resolve recovery record.
            resolved = DeadLetterRepository.resolve_recovery(
                message_id=message_id,
                task_id=task_id,
                resolved_by=resolved_by,
                notes=notes
            )

            if not resolved:
                return {
                    "success": False,
                    "message": "Recovery record changed or could not be resolved"
                }

            current_app.logger.info(
                "Recovery resolved for message %s by %s",
                message_id,
                resolved_by
            )

            return {
                "success": True,
                "message": "Recovery successfully resolved",
                "message_id": message_id,
                "task_id": task_id,
                "message_status": message_status,
                "recovery_status": "RESOLVED"
            }

        except Exception:
            current_app.logger.exception(
                "Recovery resolution failed for %s",
                message_id
            )

            return {
                "success": False,
                "message": "Recovery resolution failed"
            }
