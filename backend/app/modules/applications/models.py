"""
SenderX Connected Applications Models & Validation
Defines schema, status enums, environments, and validation helpers for connected external apps.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid


class ApplicationStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEACTIVATED = "DEACTIVATED"

    ALL_STATUSES = {ACTIVE, INACTIVE, DEACTIVATED}


class ApplicationEnvironment:
    LIVE = "live"
    TEST = "test"
    ALL = "all"

    VALID_ENVIRONMENTS = {LIVE, TEST, ALL}


def generate_application_id() -> str:
    """Generate an immutable, unique application identifier prefixed with 'app_'."""
    return f"app_{uuid.uuid4().hex[:16]}"


def validate_application_input(data: Dict[str, Any], is_update: bool = False) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate application registration/update input payload.
    Returns (is_valid, error_message, sanitized_data).
    """
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object", {}

    sanitized: Dict[str, Any] = {}

    if not is_update or "name" in data:
        name = data.get("name")
        if not name or not isinstance(name, str):
            return False, "Application name is required and must be a string", {}
        name = name.strip()
        if len(name) < 2 or len(name) > 100:
            return False, "Application name must be between 2 and 100 characters", {}
        sanitized["name"] = name

    if "description" in data:
        desc = data.get("description")
        if desc is not None:
            if not isinstance(desc, str):
                return False, "Description must be a string", {}
            desc = desc.strip()
            if len(desc) > 500:
                return False, "Description cannot exceed 500 characters", {}
            sanitized["description"] = desc
        else:
            sanitized["description"] = ""
    elif not is_update:
        sanitized["description"] = ""

    if "environment" in data:
        env = data.get("environment")
        if not isinstance(env, str) or env.strip().lower() not in ApplicationEnvironment.VALID_ENVIRONMENTS:
            return False, f"Invalid environment. Must be one of: {sorted(list(ApplicationEnvironment.VALID_ENVIRONMENTS))}", {}
        sanitized["environment"] = env.strip().lower()
    elif not is_update:
        sanitized["environment"] = ApplicationEnvironment.ALL

    return True, None, sanitized
