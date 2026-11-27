from datetime import datetime, timezone
from uuid import uuid4

from app.validators.dynamic_json_validator import (
    DynamicJSONValidator
)


class MessageEngine:

    @classmethod
    def prepare_message(cls, payload, template_rendered=False):

        
        # Exclude server-resolved binary media bytes if already attached by MediaService
        sanitized_for_validation = payload
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            data_copy = dict(payload["data"])
            changed = False
            for internal_media_key in ("resolved_media", "media_references"):
                if isinstance(data_copy.get(internal_media_key), list):
                    data_copy[internal_media_key] = [
                        {k: v for k, v in item.items() if k != "raw_bytes"} if isinstance(item, dict) else item
                        for item in data_copy[internal_media_key]
                    ]
                    changed = True
            if changed:
                sanitized_for_validation = dict(payload)
                sanitized_for_validation["data"] = data_copy

        validation = DynamicJSONValidator.analyze(
            sanitized_for_validation,
            allow_template_var_html=bool(template_rendered),
        )

        if not validation["valid"]:
            outcome = validation.get("status", DynamicJSONValidator.INVALID_STATUS)
            return {
                "success": False,
                "status": outcome,
                "status_code": 422 if outcome in (DynamicJSONValidator.THREAT_STATUS, DynamicJSONValidator.LIMIT_STATUS) else 400,
                "errors": validation["errors"],
                "threats": validation.get("threats", []),
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