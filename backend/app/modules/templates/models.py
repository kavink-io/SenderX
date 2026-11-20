"""
SenderX Template Pydantic Models
Data validation for email template creation, updating, previewing, and variables.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re


class DynamicVariableModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="Variable name (alphanumeric and underscore)")
    type: Optional[str] = Field("text", description="Variable format: text, url, color, rich")
    description: Optional[str] = Field(None, max_length=256)
    required: bool = True
    default: Optional[Any] = None
    sample_value: Optional[Any] = None
    max_length: Optional[int] = Field(1000, ge=1, le=50000, description="Max allowed character length")

    @field_validator("name")
    @classmethod
    def validate_variable_name(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError(f"Invalid variable name '{v}'. Must start with letter/underscore and contain only letters, numbers, and underscores.")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> str:
        if not v:
            return "text"
        clean = v.lower().strip()
        if clean in ("text", "string"):
            return "text"
        if clean not in ("text", "url", "color", "rich"):
            raise ValueError(f"Invalid variable type '{v}'. Allowed types are 'text', 'url', 'color', 'rich'.")
        return clean


class TemplateCreateModel(BaseModel):
    name: str = Field(..., min_length=2, max_length=80, description="Template display name (2-80 chars)")
    description: Optional[str] = Field(None, max_length=300)
    category: Optional[str] = Field("general", max_length=64)
    channel: Optional[str] = Field("email", max_length=32, description="Target channel (email, sms, whatsapp, all)")
    subject: Optional[str] = Field(None, max_length=500, description="Subject template string (required for email)")
    html_body: Optional[str] = Field("", max_length=200 * 1024, description="HTML body template (max 200 KB)")
    css: Optional[str] = Field("", max_length=50 * 1024, description="CSS stylesheet (max 50 KB)")
    plain_text_body: Optional[str] = Field("", max_length=200 * 1024, description="Plain text body template")
    variables: Optional[List[DynamicVariableModel]] = Field(default_factory=list)
    strict_variables: Optional[bool] = Field(False, description="Whether to reject undeclared variable keys on dispatch")
    header: Optional[str] = Field(None, max_length=64 * 1024)
    footer: Optional[str] = Field(None, max_length=64 * 1024)

    @model_validator(mode="before")
    @classmethod
    def remap_html_field(cls, values):
        if isinstance(values, dict):
            if "html" in values and "html_body" not in values:
                values["html_body"] = values.get("html")
        return values

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 80:
            raise ValueError("Template name must be between 2 and 80 characters")
        return v

    @field_validator("subject")
    @classmethod
    def sanitize_subject(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return ""
        return v

    @field_validator("variables")
    @classmethod
    def validate_variables_count(cls, v: Optional[List[DynamicVariableModel]]) -> List[DynamicVariableModel]:
        if v and len(v) > 50:
            raise ValueError("A template may define a maximum of 50 dynamic variables")
        return v or []


class TemplateUpdateModel(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=80)
    description: Optional[str] = Field(None, max_length=300)
    category: Optional[str] = Field(None, max_length=64)
    channel: Optional[str] = Field(None, max_length=32)
    subject: Optional[str] = Field(None, min_length=1, max_length=500)
    html_body: Optional[str] = Field(None, max_length=200 * 1024)
    css: Optional[str] = Field(None, max_length=50 * 1024)
    plain_text_body: Optional[str] = Field(None, max_length=200 * 1024)
    variables: Optional[List[DynamicVariableModel]] = None
    strict_variables: Optional[bool] = None
    header: Optional[str] = Field(None, max_length=64 * 1024)
    footer: Optional[str] = Field(None, max_length=64 * 1024)

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 2 or len(v) > 80:
                raise ValueError("Template name must be between 2 and 80 characters")
        return v

    @field_validator("variables")
    @classmethod
    def validate_variables_count(cls, v: Optional[List[DynamicVariableModel]]) -> Optional[List[DynamicVariableModel]]:
        if v and len(v) > 50:
            raise ValueError("A template may define a maximum of 50 dynamic variables")
        return v

    @model_validator(mode="before")
    @classmethod
    def remap_html_field(cls, values):
        if isinstance(values, dict):
            if "html" in values and "html_body" not in values:
                values["html_body"] = values.get("html")
        return values


class TemplatePreviewModel(BaseModel):
    template_id: Optional[str] = None
    subject: Optional[str] = None
    html_body: Optional[str] = None
    css: Optional[str] = None
    plain_text_body: Optional[str] = None
    variables: Optional[List[DynamicVariableModel]] = None
    sample_data: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def remap_html_field(cls, values):
        if isinstance(values, dict):
            if "html" in values and "html_body" not in values:
                values["html_body"] = values.get("html")
        return values


class TemplateValidateModel(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    html_body: Optional[str] = None
    css: Optional[str] = None
    variables: Optional[List[DynamicVariableModel]] = None
    strict_variables: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def remap_html_field(cls, values):
        if isinstance(values, dict):
            if "html" in values and "html_body" not in values:
                values["html_body"] = values.get("html")
        return values
