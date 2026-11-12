
from app.engine.message_engine import MessageEngine
from app.modules.messages.repository import MessageRepository
from app.engine.status_manager import StatusManager
from flask import current_app


class MessageService:

    @staticmethod
    def create_message(payload, organization_id):

        result = MessageEngine.prepare_message(payload)

        if not result["success"]:
            return result

        message = result["message"]

        # Never trust organization_id supplied by the client.
        message["organization_id"] = organization_id

        saved_message = MessageRepository.save(message)

        return {
            "success": True,
            "message": saved_message,
            "validation": result["validation"]
        }

    @staticmethod
    def get_message(message_id, organization_id):

        return MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id
        )

    @staticmethod
    def get_all_messages(organization_id, limit=50):

        return MessageRepository.find_all(
            limit=limit,
            organization_id=organization_id
        )

    @staticmethod
    def update_status(message_id, new_status, organization_id):

        message = MessageRepository.find_by_id(
            message_id,
            organization_id=organization_id
        )

        if not message:
            return {
                "success": False,
                "message": "Message not found"
            }

        current_status = message.get("status")

        result = StatusManager.transition(
            current_status,
            new_status
        )

        if not result["success"]:
            return result

        updated = MessageRepository.update_status(
            message_id,
            new_status,
            current_status,
            organization_id=organization_id
        )

        if not updated:
            return {
                "success": False,
                "message": "Status update failed"
            }

        response = {
            "success": True,
            "message": "Message status updated successfully",
            "data": MessageRepository.find_by_id(
                message_id,
                organization_id=organization_id
            )
        }

        if new_status == "QUEUED":

            try:
                task = current_app.celery.send_task(
                    "senderx.process_message",
                    args=[message_id]
                )

                response["queue"] = {
                    "dispatched": True,
                    "task_id": task.id
                }

            except Exception as error:
                current_app.logger.error(
                    "Failed to dispatch message to Celery (%s)",
                    type(error).__name__
                )

                response["queue"] = {
                    "dispatched": False,
                    "message": (
                        "Message saved as QUEUED, "
                        "but task dispatch failed"
                    )
                }

        return response
