import json
import re


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

    # Markup detection patterns
    HTML_TAG_PATTERN = re.compile(r"<[a-zA-Z][^>]*>", re.IGNORECASE)
    STYLE_BLOCK_PATTERN = re.compile(r"<style\b", re.IGNORECASE)
    INLINE_STYLE_PATTERN = re.compile(r"\bstyle\s*=", re.IGNORECASE)
    DANGEROUS_PROTO_PATTERN = re.compile(r"(?:javascript|vbscript|data):", re.IGNORECASE)

    # Critical threat patterns
    SCRIPT_TAG_PATTERN = re.compile(r"<\s*script\b", re.IGNORECASE)
    EVENT_HANDLER_PATTERN = re.compile(r"\bon[a-zA-Z]+\s*=", re.IGNORECASE)

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
    def scan_for_markup_and_threats(cls, value, path=""):
        """
        Recursively scan incoming JSON values for HTML/CSS markup and dangerous patterns.
        """
        markup_fields = []
        threats = []

        if isinstance(value, str):
            has_html = bool(cls.HTML_TAG_PATTERN.search(value))
            has_style = bool(cls.STYLE_BLOCK_PATTERN.search(value) or cls.INLINE_STYLE_PATTERN.search(value))
            has_dangerous_proto = bool(cls.DANGEROUS_PROTO_PATTERN.search(value))

            if has_html or has_style or has_dangerous_proto:
                markup_fields.append(path)

            # Detect dangerous injection patterns
            field_name = path.split(".")[-1].lower() if path else ""
            is_template_var = any(path.startswith(prefix) for prefix in ("variables.", "data.variables.", "template_variables.", "data.template_variables."))

            if not is_template_var:
                if cls.SCRIPT_TAG_PATTERN.search(value):
                    threats.append(f"Script tag injection detected in '{path}'")
                if cls.EVENT_HANDLER_PATTERN.search(value):
                    threats.append(f"Event handler execution attribute detected in '{path}'")
                if "javascript:" in value.lower() or "vbscript:" in value.lower():
                    threats.append(f"Dangerous script protocol detected in '{path}'")

            # Header injection checks in subject/recipient/header fields
            if field_name in ("subject", "recipient", "to", "from", "reply_to", "email"):
                if "\r" in value or "\n" in value:
                    threats.append(f"Illegal newline characters in header field '{path}' (header injection blocked)")

        elif isinstance(value, dict):
            for k, v in value.items():
                cur_path = f"{path}.{k}" if path else k
                m_sub, t_sub = cls.scan_for_markup_and_threats(v, cur_path)
                markup_fields.extend(m_sub)
                threats.extend(t_sub)

        elif isinstance(value, list):
            for idx, item in enumerate(value):
                cur_path = f"{path}[{idx}]"
                m_sub, t_sub = cls.scan_for_markup_and_threats(item, cur_path)
                markup_fields.extend(m_sub)
                threats.extend(t_sub)

        return markup_fields, threats

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

        # Scan for HTML/CSS markup and dangerous injection threats
        markup_fields, threats = cls.scan_for_markup_and_threats(payload)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "contains_markup": len(markup_fields) > 0,
            "markup_fields": markup_fields,
            "threats": threats,
            "analysis": cls.analyze_fields(payload) if not errors else None
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
                    result.extend(cls.analyze_fields(item, current_path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                current_path = f"{path}[{index}]"
                result.append({
                    "field": current_path,
                    "type": cls.get_data_type(item)
                })
                if isinstance(item, (dict, list)):
                    result.extend(cls.analyze_fields(item, current_path))
        return result
