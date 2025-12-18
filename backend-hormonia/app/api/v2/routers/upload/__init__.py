"""
Upload API v2 - Modern file upload with caching, processing, and cloud storage.

Features:
- Redis caching (metadata: 30min, file info: 1h)
- Rate limiting (10-20 uploads/hour based on size)
- Image processing (thumbnails, previews, resizing)
- Virus scanning integration
- Cloud storage support (S3, GCS, Azure)
- Direct-to-cloud upload URLs
- User quota enforcement
- Field selection via ?fields=
- Comprehensive security validation

This module is organized as a package with the following structure:
- config.py: Constants and configuration
- validators.py: File validation utilities
- storage.py: File storage operations
- processing.py: Image processing
- security.py: Security scanning (virus, MIME, file security)
- dependencies.py: FastAPI dependencies (Redis, rate limiting, quota)
- handlers.py: Route handlers

All endpoints are re-exported from this __init__.py for backward compatibility.
"""

from uuid import UUID
from typing import Optional, Dict, Any

from fastapi import (
    APIRouter,
    Depends,
    status,
    UploadFile,
    File,
    Query,
    BackgroundTasks,
)

from app.models.user import User
from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_object_from_session
from app.schemas.v2.upload import (
    UploadResponse,
    UploadError,
)

from .handlers import (
    upload_file_handler,
    get_upload_info_handler,
    delete_upload_handler,
)

# Initialize main router
router = APIRouter(prefix="/upload", tags=["Upload v2"])


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload File",
    description="""
    Upload a file with optional processing.

    Features:
    - Automatic virus scanning
    - Image processing (thumbnails, previews, resizing)
    - User quota enforcement
    - Rate limiting (10-20 uploads/hour)
    - Redis caching (30min metadata)
    - Cloud storage support

    Supported file types:
    - Images: JPEG, PNG, GIF, WebP
    - Videos: MP4, MPEG, QuickTime, WebM
    - Audio: MP3, OGG, WAV, WebM
    - Documents: PDF, Word, Excel, PowerPoint
    - Text: Plain text, CSV

    Maximum file size: 50MB
    """,
    responses={
        201: {"description": "File uploaded successfully"},
        400: {"model": UploadError, "description": "Invalid file"},
        413: {"model": UploadError, "description": "File too large"},
        415: {"model": UploadError, "description": "Unsupported file type"},
        429: {"model": UploadError, "description": "Rate limit exceeded"},
    },
)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload"),
    generate_thumbnail: bool = Query(
        False, description="Generate thumbnail for images"
    ),
    generate_preview: bool = Query(False, description="Generate preview for images"),
    resize_width: Optional[int] = Query(
        None, ge=100, le=4000, description="Resize width"
    ),
    resize_height: Optional[int] = Query(
        None, ge=100, le=4000, description="Resize height"
    ),
    quality: int = Query(85, ge=1, le=100, description="Image quality"),
    scan_virus: bool = Query(True, description="Enable virus scanning"),
    public: bool = Query(False, description="Make file publicly accessible"),
    fields: Optional[str] = Query(None, description="Fields to return"),
    current_user: User = Depends(get_current_user_object_from_session),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Upload a file with optional processing."""
    return await upload_file_handler(
        background_tasks=background_tasks,
        file=file,
        generate_thumbnail=generate_thumbnail,
        generate_preview=generate_preview,
        resize_width=resize_width,
        resize_height=resize_height,
        quality=quality,
        scan_virus_flag=scan_virus,
        public=public,
        fields=fields,
        current_user=current_user,
        db=db,
    )


@router.get(
    "/{upload_id}",
    response_model=UploadResponse,
    summary="Get Upload Info",
    description="""
    Get information about an uploaded file.

    Features:
    - Redis caching (1 hour)
    - Field selection via ?fields=
    - Supports all uploaded files
    """,
    responses={
        200: {"description": "Upload info retrieved"},
        404: {"model": UploadError, "description": "Upload not found"},
    },
)
async def get_upload_info(
    upload_id: UUID,
    fields: Optional[str] = Query(None, description="Fields to return"),
    current_user: User = Depends(get_current_user_object_from_session),
) -> Dict[str, Any]:
    """Get upload information."""
    return await get_upload_info_handler(
        upload_id=upload_id,
        fields=fields,
        current_user=current_user,
    )


@router.delete(
    "/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Upload",
    description="""
    Delete an uploaded file.

    Features:
    - Deletes file from storage
    - Removes thumbnails and previews
    - Clears cache
    - Updates user quota
    """,
    responses={
        204: {"description": "File deleted successfully"},
        404: {"model": UploadError, "description": "Upload not found"},
    },
)
async def delete_upload(
    upload_id: UUID,
    current_user: User = Depends(get_current_user_object_from_session),
) -> None:
    """Delete an uploaded file."""
    return await delete_upload_handler(
        upload_id=upload_id,
        current_user=current_user,
    )


# ============================================================================
# Re-exports for backward compatibility
# ============================================================================

# Export handlers for direct use if needed
__all__ = [
    "router",
    "upload_file",
    "get_upload_info",
    "delete_upload",
]
