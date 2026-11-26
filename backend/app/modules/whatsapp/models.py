"""
SenderX WhatsApp Multi-Tenant Data Models and Schemas
Defines validation schemas, status enums, and secure serialization helpers.
Guarantees access tokens and platform secrets are NEVER returned in API responses or logs.
"""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class WhatsAppIntegrationStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    PENDING = "PENDING"
    DEGRADED = "DEGRADED"
    REVOKED = "REVOKED"


class WhatsAppOnboardingMethod(str, Enum):
    EMBEDDED_SIGNUP = "EMBEDDED_SIGNUP"
    MANUAL = "MANUAL"


class WhatsAppTokenStatus(str, Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    ROTATED = "ROTATED"


def clean_phone_number(val: str) -> str:
    """Normalize phone number to E.164 string format (+[1-9][0-9]{6,14})."""
    if not val or not isinstance(val, str):
        raise ValueError("Phone number must be a non-empty string")
    cleaned = re.sub(r"[\s\-\(\)\.]", "", val.strip())
    if not cleaned.startswith("+"):
        if cleaned.isdigit():
            cleaned = "+" + cleaned
        else:
            raise ValueError(f"Invalid phone number format: '{val}'")
    if not re.match(r"^\+[1-9]\d{6,14}$", cleaned):
        raise ValueError(
            f"Phone number '{val}' must be in E.164 international format (+[country code][number], 7-15 digits)"
        )
    return cleaned


class WhatsAppIntegrationCreateSchema(BaseModel):
    waba_id: str = Field(..., min_length=5, max_length=64, description="WhatsApp Business Account ID")
    phone_number_id: str = Field(..., min_length=5, max_length=64, description="Meta Phone Number ID")
    display_phone_number: str = Field(..., min_length=5, max_length=32, description="Display phone number")
    name: Optional[str] = Field(None, max_length=120, description="Optional nickname for this number")
    access_token: str = Field(..., min_length=10, description="Organization WhatsApp Cloud API access token")
    onboarding_method: Optional[WhatsAppOnboardingMethod] = WhatsAppOnboardingMethod.MANUAL
    token_expires_at: Optional[Union[float, int, datetime]] = None
    metadata: Optional[Dict[str, Any]] = None
    catalog_id: Optional[str] = Field(None, min_length=1, max_length=64, description="Meta product catalog ID linked to this WhatsApp integration")

    @field_validator("waba_id", "phone_number_id")
    @classmethod
    def validate_meta_ids(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.match(r"^[a-zA-Z0-9_\-]+$", cleaned):
            raise ValueError("ID must contain only alphanumeric characters, dashes, or underscores")
        return cleaned

    @field_validator("catalog_id")
    @classmethod
    def validate_catalog_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        if not re.fullmatch(r"\d+", cleaned):
            raise ValueError("Catalog ID must contain only digits")
        return cleaned

    @field_validator("display_phone_number")
    @classmethod
    def validate_display_phone(cls, v: str) -> str:
        # Validates that it resolves to a valid E.164 number
        clean_phone_number(v)
        return v.strip()


class WhatsAppIntegrationUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    display_phone_number: Optional[str] = Field(None, max_length=32)
    status: Optional[WhatsAppIntegrationStatus] = None
    metadata: Optional[Dict[str, Any]] = None
    catalog_id: Optional[str] = Field(None, min_length=1, max_length=64)

    @field_validator("display_phone_number")
    @classmethod
    def validate_display_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean_phone_number(v)
            return v.strip()
        return v

    @field_validator("catalog_id")
    @classmethod
    def validate_catalog_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        if not re.fullmatch(r"\d+", cleaned):
            raise ValueError("Catalog ID must contain only digits")
        return cleaned


class WhatsAppManualConnectSchema(BaseModel):
    """
    Schema for manual connection of an organization-specific WhatsApp Business Account.
    Accepts WABA ID, Phone Number ID, Access Token, and optional nickname.
    """
    waba_id: str = Field(..., min_length=5, max_length=64, description="WhatsApp Business Account ID")
    phone_number_id: str = Field(..., min_length=5, max_length=64, description="Meta Phone Number ID")
    access_token: str = Field(..., min_length=10, description="WhatsApp Cloud API access token")
    name: Optional[str] = Field(None, max_length=120, description="Optional nickname for this phone number")
    display_phone_number: Optional[str] = Field(None, max_length=32, description="Optional override/hint for display phone number")
    catalog_id: Optional[str] = Field(None, min_length=1, max_length=64, description="Meta product catalog ID linked to this WhatsApp integration")

    @field_validator("waba_id", "phone_number_id")
    @classmethod
    def validate_meta_ids(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.match(r"^[a-zA-Z0-9_\-]+$", cleaned):
            raise ValueError("ID must contain only alphanumeric characters, dashes, or underscores")
        return cleaned

    @field_validator("access_token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 10:
            raise ValueError("Access token must be at least 10 characters long")
        return cleaned

    @field_validator("catalog_id")
    @classmethod
    def validate_catalog_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        if not re.fullmatch(r"\d+", cleaned):
            raise ValueError("Catalog ID must contain only digits")
        return cleaned


class WhatsAppCredentialRotateSchema(BaseModel):
    access_token: str = Field(..., min_length=10, description="New WhatsApp Cloud API access token")
    token_expires_at: Optional[Union[float, int, datetime]] = None


class WhatsAppPlatformSettingsSchema(BaseModel):
    meta_app_id: Optional[str] = Field(None, max_length=64)
    meta_app_secret: Optional[str] = Field(None, max_length=128)
    webhook_verify_token: Optional[str] = Field(None, max_length=128)
    webhook_url: Optional[str] = Field(None, max_length=256)
    graph_api_version: Optional[str] = Field("v21.0", max_length=16)


def serialize_integration(doc: Optional[Dict[str, Any]], mask_secrets: bool = True) -> Optional[Dict[str, Any]]:
    """
    Serializes a WhatsApp integration MongoDB document for API responses.
    Guarantees raw access tokens and encrypted ciphertext are NEVER returned.
    """
    if not doc:
        return None

    res = dict(doc)
    res.pop("_id", None)
    res.pop("encrypted_access_token", None)
    res.pop("encrypted_flow_private_key", None)
    res.pop("encrypted_flow_private_keys", None)
    res.pop("access_token", None)

    # Convert timestamps to ISO string if datetime
    for k in ("created_at", "updated_at", "deleted_at", "token_last_rotated_at", "last_verified_at", "last_status_check", "reconnected_at"):
        if isinstance(res.get(k), datetime):
            res[k] = res[k].isoformat()

    res["has_access_token"] = bool(doc.get("encrypted_access_token"))
    res["token_status"] = doc.get("token_status", WhatsAppTokenStatus.VALID.value)
    res["rotation_count"] = doc.get("rotation_count", 0)

    return res


def serialize_platform_settings(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Serializes centralized platform settings for platform admin API responses.
    Never returns raw secrets.
    """
    if not doc:
        return {
            "meta_app_id": None,
            "has_app_secret": False,
            "has_webhook_verify_token": False,
            "webhook_url": None,
            "graph_api_version": "v21.0",
            "updated_at": None,
            "updated_by": None
        }

    return {
        "meta_app_id": doc.get("meta_app_id"),
        "has_app_secret": bool(doc.get("encrypted_app_secret") or doc.get("meta_app_secret")),
        "app_secret_masked": "******" if (doc.get("encrypted_app_secret") or doc.get("meta_app_secret")) else None,
        "has_webhook_verify_token": bool(doc.get("encrypted_webhook_verify_token") or doc.get("webhook_verify_token")),
        "webhook_verify_token_masked": "******" if (doc.get("encrypted_webhook_verify_token") or doc.get("webhook_verify_token")) else None,
        "webhook_url": doc.get("webhook_url"),
        "graph_api_version": doc.get("graph_api_version", "v21.0"),
        "updated_at": doc.get("updated_at").isoformat() if isinstance(doc.get("updated_at"), datetime) else doc.get("updated_at"),
        "updated_by": doc.get("updated_by")
    }
