"""
Upload Schemas for API v2
Modern upload schemas with validation, metadata tracking, and cloud storage support.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, validator, HttpUrl

# ============================================================================
# Enums
# ============================================================================


class FileCategory(str, Enum):
    """File category classification."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    TEXT = "text"
    OTHER = "other"


class ImageFormat(str, Enum):
    """Supported image formats."""
    JPEG = "jpeg"
    JPG = "jpg"
    PNG = "png"
    GIF = "gif"
    WEBP = "webp"


class StorageProvider(str, Enum):
    """Cloud storage providers."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"


class ProcessingStatus(str, Enum):
    """File processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Request Models
# ============================================================================


class UploadOptionsRequest(BaseModel):
    """Upload configuration options."""

    max_size: Optional[int] = Field(
        None,
        ge=1,
        le=50 * 1024 * 1024,  # 50MB max
        description="Maximum file size in bytes (default: 10MB)"
    )

    generate_thumbnail: bool = Field(
        False,
        description="Generate thumbnail for images (128x128)"
    )

    generate_preview: bool = Field(
        False,
        description="Generate preview for images (800x600)"
    )

    resize_width: Optional[int] = Field(
        None,
        ge=100,
        le=4000,
        description="Resize image width (maintains aspect ratio)"
    )

    resize_height: Optional[int] = Field(
        None,
        ge=100,
        le=4000,
        description="Resize image height (maintains aspect ratio)"
    )

    quality: int = Field(
        85,
        ge=1,
        le=100,
        description="Image compression quality (1-100)"
    )

    scan_virus: bool = Field(
        True,
        description="Enable virus scanning"
    )

    storage_provider: StorageProvider = Field(
        StorageProvider.LOCAL,
        description="Storage provider to use"
    )

    public: bool = Field(
        False,
        description="Make file publicly accessible"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata to store with file"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "max_size": 10485760,
                "generate_thumbnail": True,
                "generate_preview": True,
                "resize_width": 1200,
                "quality": 85,
                "scan_virus": True,
                "storage_provider": "local",
                "public": False,
                "metadata": {
                    "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                    "upload_type": "avatar"
                }
            }
        }


class DirectUploadRequest(BaseModel):
    """Request for direct-to-cloud upload URL."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename"
    )

    content_type: str = Field(
        ...,
        description="MIME type of the file"
    )

    file_size: int = Field(
        ...,
        ge=1,
        le=50 * 1024 * 1024,
        description="File size in bytes"
    )

    storage_provider: StorageProvider = Field(
        StorageProvider.S3,
        description="Target storage provider"
    )

    expires_in: int = Field(
        3600,
        ge=60,
        le=86400,
        description="URL expiration time in seconds (1 min - 24 hours)"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Metadata to associate with upload"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "patient-scan.jpg",
                "content_type": "image/jpeg",
                "file_size": 2048576,
                "storage_provider": "s3",
                "expires_in": 3600,
                "metadata": {
                    "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                    "scan_type": "ct"
                }
            }
        }


# ============================================================================
# Response Models
# ============================================================================


class FileMetadata(BaseModel):
    """File metadata information."""

    id: UUID = Field(description="Upload record ID")
    filename: str = Field(description="Original filename")
    safe_filename: str = Field(description="Sanitized filename on disk")
    content_type: str = Field(description="MIME type")
    category: FileCategory = Field(description="File category")
    size: int = Field(description="File size in bytes")
    checksum: Optional[str] = Field(None, description="File checksum (MD5)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "filename": "patient-photo.jpg",
                "safe_filename": "20250107_143022_a1b2c3d4.jpg",
                "content_type": "image/jpeg",
                "category": "image",
                "size": 2048576,
                "checksum": "5d41402abc4b2a76b9719d911017c592"
            }
        }


class ImageMetadata(BaseModel):
    """Image-specific metadata."""

    width: int = Field(description="Image width in pixels")
    height: int = Field(description="Image height in pixels")
    format: ImageFormat = Field(description="Image format")
    has_alpha: bool = Field(description="Has alpha channel")
    color_mode: str = Field(description="Color mode (RGB, RGBA, etc)")

    class Config:
        json_schema_extra = {
            "example": {
                "width": 1920,
                "height": 1080,
                "format": "jpeg",
                "has_alpha": False,
                "color_mode": "RGB"
            }
        }


class ProcessingInfo(BaseModel):
    """File processing information."""

    status: ProcessingStatus = Field(description="Processing status")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL")
    preview_url: Optional[str] = Field(None, description="Preview URL")
    resized_url: Optional[str] = Field(None, description="Resized image URL")
    virus_scan_clean: Optional[bool] = Field(None, description="Virus scan result")
    processing_time_ms: Optional[int] = Field(None, description="Processing time")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed",
                "thumbnail_url": "/uploads/thumbnails/20250107_143022_a1b2c3d4_thumb.jpg",
                "preview_url": "/uploads/previews/20250107_143022_a1b2c3d4_preview.jpg",
                "resized_url": None,
                "virus_scan_clean": True,
                "processing_time_ms": 250
            }
        }


class UploadResponse(BaseModel):
    """Upload response with URLs and metadata."""

    # Core info
    id: UUID = Field(description="Upload record ID")
    url: str = Field(description="File URL")
    download_url: Optional[str] = Field(None, description="Download URL with token")

    # File metadata
    file: FileMetadata = Field(description="File metadata")

    # Optional metadata
    image_metadata: Optional[ImageMetadata] = Field(
        None,
        description="Image metadata (for images only)"
    )

    # Processing info
    processing: ProcessingInfo = Field(description="Processing information")

    # Storage info
    storage_provider: StorageProvider = Field(description="Storage provider used")
    storage_path: str = Field(description="Storage path/key")

    # User info
    uploaded_by: UUID = Field(description="User who uploaded the file")
    uploaded_at: datetime = Field(description="Upload timestamp")

    # Access control
    is_public: bool = Field(description="Whether file is publicly accessible")
    expires_at: Optional[datetime] = Field(None, description="Expiration time")

    # Custom metadata
    custom_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "url": "/uploads/images/20250107_143022_a1b2c3d4.jpg",
                "download_url": "/api/v2/upload/123e4567-e89b-12d3-a456-426614174000/download?token=xyz",
                "file": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "filename": "patient-photo.jpg",
                    "safe_filename": "20250107_143022_a1b2c3d4.jpg",
                    "content_type": "image/jpeg",
                    "category": "image",
                    "size": 2048576,
                    "checksum": "5d41402abc4b2a76b9719d911017c592"
                },
                "image_metadata": {
                    "width": 1920,
                    "height": 1080,
                    "format": "jpeg",
                    "has_alpha": False,
                    "color_mode": "RGB"
                },
                "processing": {
                    "status": "completed",
                    "thumbnail_url": "/uploads/thumbnails/20250107_143022_a1b2c3d4_thumb.jpg",
                    "preview_url": "/uploads/previews/20250107_143022_a1b2c3d4_preview.jpg",
                    "resized_url": None,
                    "virus_scan_clean": True,
                    "processing_time_ms": 250
                },
                "storage_provider": "local",
                "storage_path": "uploads/images/20250107_143022_a1b2c3d4.jpg",
                "uploaded_by": "456e7890-e89b-12d3-a456-426614174000",
                "uploaded_at": "2025-01-07T14:30:22Z",
                "is_public": False,
                "expires_at": None,
                "custom_metadata": {
                    "patient_id": "789e0123-e89b-12d3-a456-426614174000"
                }
            }
        }


class DirectUploadResponse(BaseModel):
    """Direct upload URL response."""

    upload_id: UUID = Field(description="Upload record ID")
    upload_url: HttpUrl = Field(description="Pre-signed upload URL")
    upload_fields: Optional[Dict[str, str]] = Field(
        None,
        description="Additional form fields for POST upload"
    )
    expires_at: datetime = Field(description="URL expiration time")
    max_file_size: int = Field(description="Maximum allowed file size")

    class Config:
        json_schema_extra = {
            "example": {
                "upload_id": "123e4567-e89b-12d3-a456-426614174000",
                "upload_url": "https://s3.amazonaws.com/bucket/path?signature=xyz",
                "upload_fields": {
                    "key": "uploads/20250107_143022_a1b2c3d4.jpg",
                    "policy": "eyJleHBpcmF0aW9uI...",
                    "signature": "abc123..."
                },
                "expires_at": "2025-01-07T15:30:22Z",
                "max_file_size": 10485760
            }
        }


class UploadStatsResponse(BaseModel):
    """Upload statistics for a user."""

    total_uploads: int = Field(description="Total files uploaded")
    total_size: int = Field(description="Total size in bytes")
    quota_used: int = Field(description="Quota used in bytes")
    quota_limit: Optional[int] = Field(None, description="Quota limit in bytes")
    uploads_by_category: Dict[str, int] = Field(description="Uploads per category")
    uploads_by_month: Dict[str, int] = Field(description="Uploads per month")

    class Config:
        json_schema_extra = {
            "example": {
                "total_uploads": 42,
                "total_size": 52428800,
                "quota_used": 52428800,
                "quota_limit": 1073741824,
                "uploads_by_category": {
                    "image": 35,
                    "document": 7
                },
                "uploads_by_month": {
                    "2025-01": 42
                }
            }
        }


# ============================================================================
# Error Models
# ============================================================================


class UploadError(BaseModel):
    """Upload error response."""

    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "FileTooLarge",
                "message": "File size exceeds maximum allowed size",
                "details": {
                    "file_size": 15728640,
                    "max_size": 10485760
                }
            }
        }


class ValidationError(BaseModel):
    """Validation error details."""

    field: str = Field(description="Field name")
    message: str = Field(description="Error message")
    value: Optional[Any] = Field(None, description="Invalid value")

    class Config:
        json_schema_extra = {
            "example": {
                "field": "content_type",
                "message": "Unsupported file type",
                "value": "application/x-executable"
            }
        }


class UploadValidationError(BaseModel):
    """Upload validation error response."""

    error: str = Field(default="ValidationError", description="Error type")
    message: str = Field(description="Error message")
    errors: List[ValidationError] = Field(description="Validation errors")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "File validation failed",
                "errors": [
                    {
                        "field": "content_type",
                        "message": "Unsupported file type",
                        "value": "application/x-executable"
                    }
                ]
            }
        }
