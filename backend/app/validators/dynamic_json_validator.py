"""
SenderX Dynamic JSON Validator & Security Analyzer.

Iterative (stack-based, non-recursive) payload analyzer enforcing:
- Configurable resource-exhaustion bounds (byte size, nesting depth, node count,
  array length, object key count, string length).
- Strict JSON data type enforcement (no NaN, Infinity, bytes, sets, or custom objects).
- Security threat detection (XSS scripts, event handlers, dangerous URI schemes,
  header CRLF injection, null bytes, prototype keys, and MongoDB operator keys).
- Clear outcome classification where detected threats or limit breaches NEVER yield valid=True.
"""

from collections import deque
import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, has_app_context


class DynamicJSONValidator:

    # Default validation limits (overridable via Flask Config)
    MAX_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB analyzer default
    INGEST_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB ingestion default
    MAX_DEPTH = 20
    MAX_NODES = 5000
    MAX_ARRAY_LENGTH = 1000
    MAX_OBJECT_KEYS = 500
    MAX_STRING_LENGTH = 200000

    VALID_STATUS = "VALID"
    INVALID_STATUS = "INVALID_PAYLOAD"
    THREAT_STATUS = "SECURITY_THREAT_DETECTED"
    LIMIT_STATUS = "RESOURCE_LIMIT_EXCEEDED"
    INTERNAL_ERROR_STATUS = "INTERNAL_ERROR"

    ALLOWED_CHANNELS = {
        "email",
        "whatsapp",
        "sms",
        "telegram",
        "slack",
        "microsoft_teams",
        "teams",
        "msteams",
        "webhook",
    }

    CHANNEL_CANONICAL_MAP = {
        "microsoft_teams": "teams",
        "msteams": "teams",
        "teams": "teams",
        "email": "email",
        "sms": "sms",
        "whatsapp": "whatsapp",
        "telegram": "telegram",
        "slack": "slack",
        "webhook": "webhook",
    }

    # Markup detection patterns
    HTML_TAG_PATTERN = re.compile(r"<[a-zA-Z][^>]*>", re.IGNORECASE)
    STYLE_BLOCK_PATTERN = re.compile(r"<style\b", re.IGNORECASE)
    INLINE_STYLE_PATTERN = re.compile(r"\bstyle\s*=", re.IGNORECASE)
    DANGEROUS_PROTO_PATTERN = re.compile(
        r"(?:^|[\s\"'=(:])(?:javascript|vbscript):|data:\s*(?:text/html|application/javascript|text/javascript)",
        re.IGNORECASE,
    )

    # Critical threat patterns
    SCRIPT_TAG_PATTERN = re.compile(r"<\s*/?\s*script\b", re.IGNORECASE)
    DANGEROUS_TAG_PATTERN = re.compile(r"<\s*(?:iframe|object|embed|applet|base|meta)\b", re.IGNORECASE)
    EVENT_HANDLER_PATTERN = re.compile(
        r"(?:^|[\s<\"'/])on(?:"
        r"abort|afterprint|animation\w*|auxclick|before\w*|blur|canplay\w*|change|click|close|"
        r"contextmenu|copy|cuechange|cut|dblclick|drag\w*|drop|durationchange|emptied|ended|"
        r"error|focus\w*|formdata|gotpointercapture|hashchange|input|invalid|key\w*|load\w*|"
        r"lostpointercapture|message|mouse\w*|offline|online|page\w*|paste|pause|play\w*|"
        r"pointer\w*|popstate|progress|ratechange|reset|resize|scroll|search|seek\w*|select\w*|"
        r"show|slotchange|stalled|storage|submit|suspend|timeupdate|toggle|touch\w*|"
        r"transition\w*|unload|volumechange|waiting|wheel"
        r")\s*=",
        re.IGNORECASE,
    )
    SSTI_DUNDER_PATTERN = re.compile(
        r"\{\{[^}]*__(?:class|mro|subclasses|globals|builtins|import|init|dict)__[^}]*\}\}",
        re.IGNORECASE,
    )

    UNSAFE_PROTOTYPE_KEYS = {"__proto__", "prototype", "constructor"}
    HEADER_FIELDS = {"subject", "recipient", "to", "from", "reply_to", "email", "cc", "bcc"}
    EMAIL_FORMAT_REGEX = re.compile(r"^[^@\s\r\n]+@[^@\s\r\n]+\.[^@\s\r\n]+$")

    @classmethod
    def resolve_limits(cls, overrides: Optional[Dict[str, int]] = None, for_ingestion: bool = False) -> Dict[str, int]:
        cfg = current_app.config if has_app_context() else {}
        default_bytes = (
            cfg.get("PAYLOAD_INGEST_MAX_BYTES", cls.INGEST_MAX_SIZE_BYTES)
            if for_ingestion
            else cfg.get("VALIDATION_MAX_BODY_BYTES", cls.MAX_SIZE_BYTES)
        )
        limits = {
            "max_bytes": int(default_bytes),
            "max_depth": int(cfg.get("VALIDATION_MAX_DEPTH", cls.MAX_DEPTH)),
            "max_nodes": int(cfg.get("VALIDATION_MAX_NODES", cls.MAX_NODES)),
            "max_array_length": int(cfg.get("VALIDATION_MAX_ARRAY_LENGTH", cls.MAX_ARRAY_LENGTH)),
            "max_object_keys": int(cfg.get("VALIDATION_MAX_OBJECT_KEYS", cls.MAX_OBJECT_KEYS)),
            "max_string_length": int(cfg.get("VALIDATION_MAX_STRING_LENGTH", cls.MAX_STRING_LENGTH)),
        }
        if isinstance(overrides, dict):
            for key, val in overrides.items():
                if key in limits and isinstance(val, int) and val > 0:
                    limits[key] = val
        return limits

    @staticmethod
    def get_data_type(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, str):
            return "string"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return "unsupported"
            return "float"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "unsupported"

    @classmethod
    def get_depth(cls, value: Any, depth: int = 1) -> int:
        """Iteratively compute maximum nesting depth without recursion."""
        if not isinstance(value, (dict, list)):
            return depth

        max_seen = depth
        stack = deque([(value, depth)])
        while stack:
            current, current_depth = stack.pop()
            if current_depth > max_seen:
                max_seen = current_depth
            if isinstance(current, dict):
                for item in current.values():
                    if isinstance(item, (dict, list)):
                        stack.append((item, current_depth + 1))
                    elif current_depth + 1 > max_seen:
                        pass
            elif isinstance(current, list):
                for item in current:
                    if isinstance(item, (dict, list)):
                        stack.append((item, current_depth + 1))
        return max_seen

    @classmethod
    def _safe_key_label(cls, key: Any, parent_path: str) -> str:
        raw = str(key)
        # Do not echo overly long or control-char raw key names
        cleaned = re.sub(r"[\x00-\x1f\x7f]", "", raw)[:64]
        return f"{parent_path}.{cleaned}" if parent_path else cleaned

    @classmethod
    def inspect_limits_and_threats(
        cls,
        payload: Any,
        limits: Optional[Dict[str, int]] = None,
        allow_template_var_html: bool = False,
    ) -> Dict[str, Any]:
        """
        Single iterative pass collecting:
        - structural resource-limit errors (depth, nodes, array length, object keys, string length)
        - unsupported data type errors
        - markup field paths
        - security threats (XSS, dangerous URIs, SSTI probes, header CRLF, null bytes,
          prototype keys, and MongoDB `$`-operator keys)
        - bounded field schema summary (`analysis` and `detected_fields`)
        """
        eff_limits = limits or cls.resolve_limits()
        max_depth = eff_limits["max_depth"]
        max_nodes = eff_limits["max_nodes"]
        max_array_len = eff_limits["max_array_length"]
        max_obj_keys = eff_limits["max_object_keys"]
        max_str_len = eff_limits["max_string_length"]

        limit_errors: List[str] = []
        type_errors: List[str] = []
        markup_fields: List[str] = []
        threats: List[str] = []
        analysis_fields: List[Dict[str, str]] = []
        detected_fields: Dict[str, str] = {}

        if isinstance(payload, dict):
            top_keys = [str(k) for k in payload.keys() if isinstance(k, str) and not k.startswith("$")]
            for tk in top_keys[:max_obj_keys]:
                detected_fields[re.sub(r"[\x00-\x1f\x7f]", "", tk)[:64]] = cls.get_data_type(payload[tk])

        node_count = 0
        depth_exceeded = False
        nodes_exceeded = False
        array_exceeded = False
        keys_exceeded = False
        str_exceeded = False

        # Stack items: (value, path, depth, last_key)
        stack = deque([(payload, "", 1, "")])

        while stack:
            value, path, depth, last_key = stack.popleft()
            node_count += 1

            if node_count > max_nodes:
                if not nodes_exceeded:
                    limit_errors.append(f"JSON node count exceeds maximum limit of {max_nodes}")
                    nodes_exceeded = True
                break

            if depth > max_depth:
                if not depth_exceeded:
                    limit_errors.append(f"JSON nesting exceeds maximum depth of {max_depth}")
                    depth_exceeded = True
                continue

            if path:
                dtype = cls.get_data_type(value)
                analysis_fields.append({"field": path, "type": dtype})
                if dtype == "unsupported":
                    type_errors.append(f"Unsupported data type in field '{path}'")
                    continue
            else:
                if cls.get_data_type(value) == "unsupported":
                    type_errors.append("Unsupported data type at root payload")
                    continue

            if isinstance(value, str):
                if len(value) > max_str_len:
                    if not str_exceeded:
                        limit_errors.append(
                            f"String value in '{path or 'root'}' exceeds maximum length of {max_str_len} characters"
                        )
                        str_exceeded = True
                    continue

                if "\x00" in value:
                    threats.append(f"Null byte detected in '{path or 'root'}'")

                has_html = bool(cls.HTML_TAG_PATTERN.search(value))
                has_style = bool(cls.STYLE_BLOCK_PATTERN.search(value) or cls.INLINE_STYLE_PATTERN.search(value))
                has_dangerous_proto = bool(cls.DANGEROUS_PROTO_PATTERN.search(value))

                if has_html or has_style or has_dangerous_proto:
                    markup_fields.append(path)

                is_escaped_template_var = allow_template_var_html and any(
                    path.startswith(prefix)
                    for prefix in (
                        "variables.",
                        "data.variables.",
                        "template_variables.",
                        "data.template_variables.",
                        "data.subject",
                        "data.body",
                        "data.message",
                        "data.text",
                        "data.plain_text_body",
                    )
                )
                if not is_escaped_template_var:
                    if cls.SCRIPT_TAG_PATTERN.search(value):
                        threats.append(f"Script tag injection detected in '{path}'")
                    if cls.DANGEROUS_TAG_PATTERN.search(value):
                        threats.append(f"Dangerous embedded HTML tag detected in '{path}'")
                    if cls.EVENT_HANDLER_PATTERN.search(value):
                        threats.append(f"Event handler execution attribute detected in '{path}'")
                if cls.DANGEROUS_PROTO_PATTERN.search(value):
                    threats.append(f"Dangerous script protocol detected in '{path}'")
                if cls.SSTI_DUNDER_PATTERN.search(value):
                    threats.append(f"Unsafe template expression detected in '{path}'")

                field_name = (last_key or (path.split(".")[-1] if path else "")).lower()
                if field_name in cls.HEADER_FIELDS and ("\r" in value or "\n" in value):
                    threats.append(f"Illegal newline characters in header field '{path}' (header injection blocked)")

            elif isinstance(value, dict):
                if len(value) > max_obj_keys:
                    if not keys_exceeded:
                        limit_errors.append(
                            f"Object at '{path or 'root'}' exceeds maximum property count of {max_obj_keys}"
                        )
                        keys_exceeded = True
                    continue

                for k, v in value.items():
                    if not isinstance(k, str):
                        type_errors.append(f"Object keys must be strings in '{path or 'root'}'")
                        continue
                    safe_path = cls._safe_key_label(k, path)
                    if "\x00" in k:
                        threats.append(f"Null byte in property name near '{path or 'root'}'")
                        continue
                    if k.startswith("$"):
                        threats.append(f"Unsafe operator key detected at '{path or 'root'}'")
                        continue
                    if k.lower() in cls.UNSAFE_PROTOTYPE_KEYS:
                        threats.append(f"Unsafe prototype property key detected at '{path or 'root'}'")
                        continue
                    stack.append((v, safe_path, depth + 1, k))

            elif isinstance(value, list):
                if len(value) > max_array_len:
                    if not array_exceeded:
                        limit_errors.append(
                            f"Array at '{path or 'root'}' exceeds maximum length of {max_array_len} elements"
                        )
                        array_exceeded = True
                    continue

                for idx, item in enumerate(value):
                    item_path = f"{path}[{idx}]" if path else f"[{idx}]"
                    stack.append((item, item_path, depth + 1, last_key))

        return {
            "limit_errors": limit_errors,
            "type_errors": type_errors,
            "markup_fields": markup_fields,
            "threats": threats,
            "analysis_fields": analysis_fields,
            "detected_fields": detected_fields,
        }

    @classmethod
    def scan_for_markup_and_threats(cls, value: Any, path: str = "") -> Tuple[List[str], List[str]]:
        """
        Iteratively scan JSON values and keys for HTML/CSS markup and dangerous injection threats.
        """
        inspect_res = cls.inspect_limits_and_threats(value)
        return inspect_res["markup_fields"], inspect_res["threats"]

    @classmethod
    def analyze_fields(cls, value: Any, path: str = "") -> List[Dict[str, str]]:
        """Iteratively inspect field paths and primitive JSON data types."""
        inspect_res = cls.inspect_limits_and_threats(value)
        return inspect_res["analysis_fields"]

    @classmethod
    def _validate_channel(cls, payload: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
        errors: List[str] = []
        raw_channel = payload.get("channel")
        if not isinstance(raw_channel, str) or not raw_channel.strip():
            errors.append("Unsupported or missing communication channel")
            return None, errors

        clean_channel = raw_channel.strip().lower()
        if clean_channel not in cls.ALLOWED_CHANNELS:
            errors.append("Unsupported or missing communication channel")
            return None, errors

        canonical_channel = cls.CHANNEL_CANONICAL_MAP.get(clean_channel, clean_channel)

        # Reject conflicting/ambiguous secondary channel indicators
        secondary_candidates: List[Any] = []
        for alt_key in ("routing_channel", "target_channel", "channel_type"):
            if alt_key in payload and payload[alt_key] is not None:
                secondary_candidates.append(payload[alt_key])
        if isinstance(payload.get("data"), dict) and payload["data"].get("channel") is not None:
            secondary_candidates.append(payload["data"].get("channel"))

        for sec in secondary_candidates:
            if not isinstance(sec, str) or not sec.strip():
                errors.append("Malformed or ambiguous channel specification")
                return canonical_channel, errors
            sec_clean = sec.strip().lower()
            sec_canon = cls.CHANNEL_CANONICAL_MAP.get(sec_clean, sec_clean)
            if sec_canon != canonical_channel:
                errors.append("Ambiguous or conflicting channel specification")
                return canonical_channel, errors

        return canonical_channel, errors

    @classmethod
    def _validate_recipient(cls, payload: Dict[str, Any], canonical_channel: Optional[str]) -> List[str]:
        recipient = payload.get("recipient")
        if recipient is None:
            return ["Recipient is required"]

        if isinstance(recipient, str):
            clean = recipient.strip()
            if not clean:
                return ["Recipient is required"]
            recipients = [clean]
        elif isinstance(recipient, list):
            if not recipient:
                return ["Recipient list cannot be empty"]
            recipients = []
            for entry in recipient:
                if not isinstance(entry, str) or not entry.strip():
                    return ["All recipient entries must be non-empty strings"]
                recipients.append(entry.strip())
        else:
            return ["Recipient must be a string or list of strings"]

        if canonical_channel == "email":
            for addr in recipients:
                if not cls.EMAIL_FORMAT_REGEX.match(addr):
                    return ["Recipient must be a valid email address for email channel"]
        elif canonical_channel in ("sms", "whatsapp"):
            for phone in recipients:
                digits = re.sub(r"\D", "", phone)
                if len(digits) < 7 or len(digits) > 15:
                    return [f"Recipient must be a valid phone number for {canonical_channel} channel"]

        return []

    @classmethod
    def analyze(
        cls,
        payload: Any,
        limits: Optional[Dict[str, int]] = None,
        allow_template_var_html: bool = False,
    ) -> Dict[str, Any]:
        eff_limits = cls.resolve_limits(limits)

        if not isinstance(payload, dict):
            return {
                "valid": False,
                "status": cls.INVALID_STATUS,
                "errors": ["JSON root must be an object"],
                "threats": [],
                "limit_errors": [],
                "contains_markup": False,
                "markup_fields": [],
                "channel": None,
                "detected_fields": {},
                "analysis": None,
            }

        # 1. Iterative resource limits, types & threat inspection (never recursive)
        inspect_res = cls.inspect_limits_and_threats(
            payload,
            limits=eff_limits,
            allow_template_var_html=allow_template_var_html,
        )
        limit_errors: List[str] = list(inspect_res["limit_errors"])
        type_errors: List[str] = list(inspect_res["type_errors"])
        threats: List[str] = list(inspect_res["threats"])
        markup_fields: List[str] = list(inspect_res["markup_fields"])

        # Short-circuit expensive serialization if iterative node/depth/string bounds already failed
        if not limit_errors and not type_errors:
            try:
                serialized = json.dumps(payload, allow_nan=False)
                byte_len = len(serialized.encode("utf-8"))
                if byte_len > eff_limits["max_bytes"]:
                    limit_errors.append(
                        f"JSON payload exceeds maximum allowed size of {eff_limits['max_bytes']} bytes"
                    )
            except (TypeError, ValueError, OverflowError):
                type_errors.append("Invalid JSON data or unsupported data types")

        # 2. Schema, channel, recipient, and data object validation
        schema_errors: List[str] = list(type_errors)
        canonical_channel = None
        if not limit_errors:
            canonical_channel, channel_errors = cls._validate_channel(payload)
            schema_errors.extend(channel_errors)
            schema_errors.extend(cls._validate_recipient(payload, canonical_channel))

            has_explicit_data = "data" in payload
            data = payload.get("data")
            has_template_mode = (
                not has_explicit_data
                and isinstance(payload.get("template_id"), str)
                and bool(payload.get("template_id").strip())
                and (
                    (isinstance(payload.get("variables"), dict) and len(payload["variables"]) > 0)
                    or (isinstance(payload.get("template_variables"), dict) and len(payload["template_variables"]) > 0)
                )
            )
            if not has_template_mode:
                if not isinstance(data, dict) or not data:
                    schema_errors.append("Data must be a non-empty JSON object")

        # 3. Critical rule: ANY threat or limit error or schema error MUST produce valid=False
        all_errors = limit_errors + threats + schema_errors
        is_valid = len(limit_errors) == 0 and len(threats) == 0 and len(schema_errors) == 0

        if limit_errors:
            status = cls.LIMIT_STATUS
        elif threats:
            status = cls.THREAT_STATUS
        elif schema_errors:
            status = cls.INVALID_STATUS
        else:
            status = cls.VALID_STATUS

        return {
            "valid": is_valid,
            "status": status,
            "errors": all_errors,
            "threats": threats,
            "limit_errors": limit_errors,
            "contains_markup": len(markup_fields) > 0,
            "markup_fields": markup_fields,
            "channel": canonical_channel,
            "detected_fields": inspect_res["detected_fields"] if is_valid else {},
            "analysis": inspect_res["analysis_fields"] if is_valid else None,
        }
