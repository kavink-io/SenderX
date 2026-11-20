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
            "application_id": payload.get("application_id"),
            "contains_markup": validation.get("contains_markup", False),
            "validation_notes": ["contains_markup"] if validation.get("contains_markup") else [],
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