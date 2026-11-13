
class MessageStatus:
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
    DEAD = "DEAD"


class StatusManager:

    TRANSITIONS = {
        "CREATED": [
            "VALIDATED",
            "FAILED",
            "CANCELLED",
            "QUEUED"
        ],

        "VALIDATED": [
            "QUEUED",
            "FAILED",
            "CANCELLED"
        ],

        "QUEUED": [
            "PROCESSING",
            "CANCELLED"
        ],

        "PROCESSING": [
            "SENT",
            "FAILED",
            "RETRYING",
            "DEAD"
        ],

        "RETRYING": [
            "PROCESSING",
            "FAILED",
            "DEAD"
        ],

        "SENT": [
            "DELIVERED",
            "READ",
            "FAILED"
        ],

        "DELIVERED": [
            "READ",
            "FAILED"
        ],

        "READ": [],

        "FAILED": [
            "RETRYING",
            "DEAD"
        ],

        "CANCELLED": [],

        "DEAD": [
            "QUEUED"
        ]
    }

    @classmethod
    def can_transition(cls, current_status, new_status):

        allowed = cls.TRANSITIONS.get(
            current_status,
            []
        )

        return new_status in allowed

    @classmethod
    def transition(cls, current_status, new_status):

        if not cls.can_transition(
            current_status,
            new_status
        ):
            return {
                "success": False,
                "message": (
                    f"Invalid status transition: "
                    f"{current_status} -> {new_status}"
                )
            }

        return {
            "success": True,
            "status": new_status
        }
