from datetime import datetime, timezone
from uuid import uuid4

from app.validators.dynamic_json_validator import (
    DynamicJSONValidator
)


class MessageEngine:

    @classmethod
    def prepare_message(cls, payload):

        
        validation = DynamicJSONValidator.analyze(payload)

        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"]
            }

      
        message = {
            "message_id": str(uuid4()),
            "channel": payload["channel"],
            "recipient": payload["recipient"],
            "data": payload["data"],
            "provider": payload.get("provider"),
            "status": "CREATED",
            "created_at": datetime.now(
                timezone.utc
            ).isoformat()
        }

        
        return {
            "success": True,
            "message": message,
            "validation": validation["analysis"]
        }