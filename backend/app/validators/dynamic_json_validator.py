import json


class DynamicJSONValidator:

    MAX_SIZE_BYTES = 10 * 1024 * 1024
    MAX_DEPTH = 20

    ALLOWED_CHANNELS = {
        "email",
        "whatsapp",
        "sms",
        "telegram",
        "slack",
        "microsoft_teams",
        "teams",
        "msteams",
        "webhook"
    }

    @classmethod
    def get_depth(cls, value, depth=1):

        if isinstance(value, dict):
            if not value:
                return depth

            return max(
                cls.get_depth(item, depth + 1)
                for item in value.values()
            )

        if isinstance(value, list):
            if not value:
                return depth

            return max(
                cls.get_depth(item, depth + 1)
                for item in value
            )

        return depth

    @staticmethod
    def get_data_type(value):

        if value is None:
            return "null"

        if isinstance(value, bool):
            return "boolean"

        if isinstance(value, str):
            return "string"

        if isinstance(value, int):
            return "integer"

        if isinstance(value, float):
            return "float"

        if isinstance(value, list):
            return "array"

        if isinstance(value, dict):
            return "object"

        return "unknown"

    @classmethod
    def analyze(cls, payload):

        errors = []

        if not isinstance(payload, dict):
            return {
                "valid": False,
                "errors": ["JSON root must be an object"]
            }

        try:
            serialized = json.dumps(payload, allow_nan=False)
        except (TypeError, ValueError):
            return {
                "valid": False,
                "errors": ["Invalid JSON data"]
            }

        if len(serialized.encode("utf-8")) > cls.MAX_SIZE_BYTES:
            errors.append("JSON payload exceeds 10 MB")

        if cls.get_depth(payload) > cls.MAX_DEPTH:
            errors.append("JSON nesting exceeds maximum depth")

        channel = payload.get("channel")

        if not isinstance(channel, str) or channel not in cls.ALLOWED_CHANNELS:
            errors.append("Unsupported or missing communication channel")

        recipient = payload.get("recipient")

        if recipient is None or recipient == "":
            errors.append("Recipient is required")

        data = payload.get("data")

        if not isinstance(data, dict) or not data:
            errors.append("Data must be a non-empty JSON object")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "analysis": cls.analyze_fields(payload)
            if not errors else None
        }

    @classmethod
    def analyze_fields(cls, value, path=""):

        result = []

        if isinstance(value, dict):

            for key, item in value.items():

                current_path = f"{path}.{key}" if path else key

                result.append({
                    "field": current_path,
                    "type": cls.get_data_type(item)
                })

                if isinstance(item, (dict, list)):
                    result.extend(
                        cls.analyze_fields(item, current_path)
                    )

        elif isinstance(value, list):

            for index, item in enumerate(value):

                current_path = f"{path}[{index}]"

                result.append({
                    "field": current_path,
                    "type": cls.get_data_type(item)
                })

                if isinstance(item, (dict, list)):
                    result.extend(
                        cls.analyze_fields(item, current_path)
                    )

        return result