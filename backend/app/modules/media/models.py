"""
SenderX Media Pydantic Data Models
Validation and serialization schemas for media items, uploads, queries, and metadata.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MediaMetadataModel(BaseModel):
    media_id: str = Field(..., description="Unique media identifier (UUID)")
    organization_id: str = Field(..., description="Organization scope owner")
    filename: str = Field(..., description="Sanitized safe filename on storage")
    original_filename: str = Field(..., description="Original client-supplied filename")
    mime_type: str = Field(..., description="Verified canonical MIME type")
    file_extension: str = Field(..., description="File extension with leading dot")
    size_bytes: int = Field(..., description="File size in bytes")
    checksum_sha256: str = Field(..., description="SHA-256 cryptographic digest")
    storage_backend: str = Field(..., description="Storage engine: 'local' or 's3'")
    storage_key: str = Field(..., description="Isolated object key in storage")
    status: str = Field("ACTIVE", description="Media lifecycle status: ACTIVE, EXPIRED, DELETED")
    scan_status: str = Field("NOT_CONFIGURED", description="Malware scan status: CLEAN, INFECTED, NOT_CONFIGURED, FAILED")
    scan_details: Optional[str] = Field(None, description="Malware scan diagnostic details")
    purpose: Optional[str] = Field(None, max_length=128, description="Intended purpose (e.g., email_attachment, avatar)")
    channel_compatibility: Dict[str, bool] = Field(default_factory=dict, description="Channel delivery compatibility flags")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    created_by: Optional[str] = Field(None, description="User ID or admin who uploaded the file")
    expires_at: Optional[str] = Field(None, description="ISO 8601 expiration timestamp for automatic cleanup")
    usage_count: int = Field(0, description="Number of times this media was referenced across messages")


class UploadResponseModel(BaseModel):
    success: bool = True
    message: str = "Media uploaded successfully"
    media: MediaMetadataModel
    download_url: str


class BulkUploadResponseModel(BaseModel):
    success: bool = True
    uploaded: List[MediaMetadataModel] = Field(default_factory=list)
    failed: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
