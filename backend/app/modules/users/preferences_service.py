import re
from copy import deepcopy

from app.modules.users.preferences_repository import UserPreferencesRepository


HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class UserPreferencesService:
    """Validation and per-user persistence service for UI appearance & layout preferences."""

    VALID_THEME_MODES = ("light", "dark", "system")
    VALID_FONT_FAMILIES = ("inter", "system", "mono")
    VALID_FONT_SCALES = ("small", "medium", "large")
    VALID_DIRECTIONS = ("ltr", "rtl")
    VALID_NAV_LAYOUTS = ("vertical", "horizontal", "compact", "mini")
    VALID_SIDEBAR_MODES = ("expanded", "collapsed")
    VALID_SIDEBAR_POSITIONS = ("fixed", "sticky")
    VALID_DENSITIES = ("compact", "comfortable", "spacious")

    DEFAULT_APPEARANCE = {
        "theme_mode": "light",
        "accent_color": "#635BDB",
        "font_family": "inter",
        "font_scale": "medium",
    }

    DEFAULT_LAYOUT = {
        "direction": "ltr",
        "navigation_layout": "vertical",
        "sidebar_mode": "expanded",
        "sidebar_position": "fixed",
        "sidebar_collapsible": True,
        "density": "comfortable",
    }

    APPEARANCE_KEY_ALIASES = {
        "theme_mode": "theme_mode",
        "themeMode": "theme_mode",
        "accent_color": "accent_color",
        "accentColor": "accent_color",
        "font_family": "font_family",
        "fontFamily": "font_family",
        "font_scale": "font_scale",
        "fontScale": "font_scale",
    }

    LAYOUT_KEY_ALIASES = {
        "direction": "direction",
        "navigation_layout": "navigation_layout",
        "navigationLayout": "navigation_layout",
        "sidebar_mode": "sidebar_mode",
        "sidebarMode": "sidebar_mode",
        "sidebar_position": "sidebar_position",
        "sidebarPosition": "sidebar_position",
        "sidebar_collapsible": "sidebar_collapsible",
        "sidebarCollapsible": "sidebar_collapsible",
        "density": "density",
    }

    @classmethod
    def default_preferences(cls, user_id, organization_id=None):
        return {
            "user_id": user_id,
            "organization_id": organization_id,
            "appearance": deepcopy(cls.DEFAULT_APPEARANCE),
            "layout": deepcopy(cls.DEFAULT_LAYOUT),
            "updated_at": None,
        }

    @classmethod
    def _normalize_doc(cls, user_id, organization_id, doc):
        base = cls.default_preferences(user_id, organization_id)
        if not doc:
            return base
        stored_app = doc.get("appearance") or {}
        stored_layout = doc.get("layout") or {}
        for key, value in stored_app.items():
            if key in base["appearance"]:
                base["appearance"][key] = value
        for key, value in stored_layout.items():
            if key in base["layout"]:
                base["layout"][key] = value
        base["updated_at"] = doc.get("updated_at")
        return base

    @classmethod
    def _validate_appearance_section(cls, raw_appearance):
        if not isinstance(raw_appearance, dict):
            return None, "appearance must be a JSON object"
        validated = {}
        for raw_key, value in raw_appearance.items():
            canonical = cls.APPEARANCE_KEY_ALIASES.get(raw_key)
            if not canonical:
                return None, f"Unsupported appearance preference '{raw_key}'"
            if canonical == "theme_mode":
                if not isinstance(value, str) or value.lower() not in cls.VALID_THEME_MODES:
                    return None, f"theme_mode must be one of {', '.join(cls.VALID_THEME_MODES)}"
                validated[canonical] = value.lower()
            elif canonical == "accent_color":
                if not isinstance(value, str) or not HEX_COLOR_RE.match(value.strip()):
                    return None, "accent_color must be a valid 6-digit hex color (e.g. #635BDB)"
                validated[canonical] = value.strip().upper()
            elif canonical == "font_family":
                if not isinstance(value, str) or value.lower() not in cls.VALID_FONT_FAMILIES:
                    return None, f"font_family must be one of {', '.join(cls.VALID_FONT_FAMILIES)}"
                validated[canonical] = value.lower()
            elif canonical == "font_scale":
                if not isinstance(value, str) or value.lower() not in cls.VALID_FONT_SCALES:
                    return None, f"font_scale must be one of {', '.join(cls.VALID_FONT_SCALES)}"
                validated[canonical] = value.lower()
        return validated, None

    @classmethod
    def _validate_layout_section(cls, raw_layout):
        if not isinstance(raw_layout, dict):
            return None, "layout must be a JSON object"
        validated = {}
        for raw_key, value in raw_layout.items():
            canonical = cls.LAYOUT_KEY_ALIASES.get(raw_key)
            if not canonical:
                return None, f"Unsupported layout preference '{raw_key}'"
            if canonical == "direction":
                if not isinstance(value, str) or value.lower() not in cls.VALID_DIRECTIONS:
                    return None, f"direction must be one of {', '.join(cls.VALID_DIRECTIONS)}"
                validated[canonical] = value.lower()
            elif canonical == "navigation_layout":
                if not isinstance(value, str) or value.lower() not in cls.VALID_NAV_LAYOUTS:
                    return None, f"navigation_layout must be one of {', '.join(cls.VALID_NAV_LAYOUTS)}"
                validated[canonical] = value.lower()
            elif canonical == "sidebar_mode":
                if not isinstance(value, str) or value.lower() not in cls.VALID_SIDEBAR_MODES:
                    return None, f"sidebar_mode must be one of {', '.join(cls.VALID_SIDEBAR_MODES)}"
                validated[canonical] = value.lower()
            elif canonical == "sidebar_position":
                if not isinstance(value, str) or value.lower() not in cls.VALID_SIDEBAR_POSITIONS:
                    return None, f"sidebar_position must be one of {', '.join(cls.VALID_SIDEBAR_POSITIONS)}"
                validated[canonical] = value.lower()
            elif canonical == "sidebar_collapsible":
                if not isinstance(value, bool):
                    return None, "sidebar_collapsible must be a boolean"
                validated[canonical] = value
            elif canonical == "density":
                if not isinstance(value, str) or value.lower() not in cls.VALID_DENSITIES:
                    return None, f"density must be one of {', '.join(cls.VALID_DENSITIES)}"
                validated[canonical] = value.lower()
        return validated, None

    @classmethod
    def _parse_and_validate_payload(cls, payload, user_id, organization_id):
        if not isinstance(payload, dict):
            return None, None, "Request payload must be a JSON object", 400

        if "user_id" in payload and payload["user_id"] != user_id:
            return None, None, "Cannot modify preferences for another user", 403
        if "organization_id" in payload and payload["organization_id"] != organization_id:
            return None, None, "Cannot modify preferences for another organization", 403

        allowed_top_keys = {"appearance", "layout", "user_id", "organization_id"}
        unknown_top = set(payload.keys()) - allowed_top_keys
        if unknown_top:
            key_list = ", ".join(sorted(unknown_top))
            return None, None, f"Unsupported top-level preference fields: {key_list}", 400

        if "appearance" not in payload and "layout" not in payload:
            return None, None, "At least one of 'appearance' or 'layout' is required", 400

        app_updates = {}
        layout_updates = {}

        if "appearance" in payload:
            app_updates, err = cls._validate_appearance_section(payload["appearance"])
            if err:
                return None, None, err, 400

        if "layout" in payload:
            layout_updates, err = cls._validate_layout_section(payload["layout"])
            if err:
                return None, None, err, 400

        return app_updates, layout_updates, None, 200

    @classmethod
    def get_preferences(cls, user_id, organization_id=None):
        doc = UserPreferencesRepository.find_by_user(user_id, organization_id)
        return {
            "success": True,
            "data": cls._normalize_doc(user_id, organization_id, doc),
        }

    @classmethod
    def save_preferences(cls, user_id, organization_id, payload, replace=False):
        app_updates, layout_updates, error_message, status_code = cls._parse_and_validate_payload(
            payload, user_id, organization_id
        )
        if error_message:
            return {
                "success": False,
                "message": error_message,
                "status_code": status_code,
            }

        if replace:
            base = cls.default_preferences(user_id, organization_id)
        else:
            existing = UserPreferencesRepository.find_by_user(user_id, organization_id)
            base = cls._normalize_doc(user_id, organization_id, existing)

        merged_appearance = {**base["appearance"], **(app_updates or {})}
        merged_layout = {**base["layout"], **(layout_updates or {})}

        saved = UserPreferencesRepository.upsert_for_user(
            user_id=user_id,
            organization_id=organization_id,
            appearance=merged_appearance,
            layout=merged_layout,
        )
        return {
            "success": True,
            "message": "Preferences saved",
            "data": cls._normalize_doc(user_id, organization_id, saved),
        }
