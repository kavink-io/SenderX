"""
SenderX Template Pydantic Models
Data validation for email template creation, updating, previewing, and variables.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import re


class DynamicVariableModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="Variable name (alphanumeric and underscore)")
    description: Optional[str] = Field(None, max_length=256)
    required: bool = True
    default: Optional[Any] = None
    sample_value: Optional[Any] = None

    @field_validator("name")
    @classmethod
    def validate_variable_name(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError(f"Invalid variable name '{v}'. Must start with letter/underscore and contain only letters, numbers, and underscores.")
        return v


class TemplateCreateModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Template display name")
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field("general", max_length=64)
    channel: Optional[str] = Field("email", max_length=32, description="Target channel (email, sms, whatsapp, telegram, all)")
    subject: Optional[str] = Field(None, max_length=500, description="Subject template string (required for email)")
    html_body: Optional[str] = Field("", max_length=1024 * 1024, description="HTML body template (max 1MB)")
    plain_text_body: Optional[str] = Field("", max_length=1024 * 1024, description="Plain text body template (max 1MB)")
    variables: Optional[List[DynamicVariableModel]] = Field(default_factory=list)
    header: Optional[str] = Field(None, max_length=64 * 1024)
    footer: Optional[str] = Field(None, max_length=64 * 1024)

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Template name cannot be blank")
        return v

    @field_validator("subject")
    @classmethod
    def sanitize_subject(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return ""
        return v


class TemplateUpdateModel(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=64)
    channel: Optional[str] = Field(None, max_length=32)
    subject: Optional[str] = Field(None, min_length=1, max_length=500)
    html_body: Optional[str] = Field(None, max_length=1024 * 1024)
    plain_text_body: Optional[str] = Field(None, max_length=1024 * 1024)
    variables: Optional[List[DynamicVariableModel]] = None
    header: Optional[str] = Field(None, max_length=64 * 1024)
    footer: Optional[str] = Field(None, max_length=64 * 1024)


class TemplatePreviewModel(BaseModel):
    sample_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
