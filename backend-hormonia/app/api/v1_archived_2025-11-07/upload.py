"""
Media upload endpoints for Hormonia Backend System.

Handles file uploads for WhatsApp media, avatars, and other content.
Supports various file types with validation and storage.
"""
from datetime import datetime
from typing import Optional
from pathlib import Path
import shutil
import uuid
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.dependencies import get_thread_safe_db as get_db, get_current_user
from app.models.user import User
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Upload configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB default
ALLOWED_MIME_TYPES = {
    # Images
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp',
    # Videos
    'video/mp4', 'video/mpeg', 'video/quicktime', 'video/webm',
    # Audio
    'audio/mpeg', 'audio/mp3', 'audio/ogg', 'audio/wav', 'audio/webm',
    # Documents
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    # Text
    'text/plain', 'text/csv'
}

# Get upload directory from settings or use default
UPLOAD_DIR = Path(getattr(settings, 'UPLOAD_DIR', 'uploads'))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class UploadResponse(BaseModel):
    """Upload response schema matching frontend expectations."""
    url: str
    type: str
    size: int
    filename: Optional[str] = None
    uploaded_at: datetime = datetime.utcnow()


class UploadError(BaseModel):
    """Upload error response."""
    detail: str
    error_code: str


def validate_file(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> None:
    """
    Validate uploaded file for size and type.

    Args:
        file: Uploaded file
        max_size: Maximum allowed file size in bytes

    Raises:
        HTTPException: If file is invalid
    """
    # Check file size by reading in chunks
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)"
        )

    # Validate MIME type
    content_type = file.content_type
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{content_type}' is not supported"
        )


def get_file_category(content_type: str) -> str:
    """
    Determine file category from MIME type.

    Args:
        content_type: MIME type of the file

    Returns:
        Category string (image, video, audio, document, text)
    """
    if content_type.startswith('image/'):
        return 'image'
    elif content_type.startswith('video/'):
        return 'video'
    elif content_type.startswith('audio/'):
        return 'audio'
    elif content_type.startswith('text/'):
        return 'text'
    else:
        return 'document'


def generate_safe_filename(original_filename: str, content_type: str) -> str:
    """
    Generate a safe, unique filename.

    Args:
        original_filename: Original filename from upload
        content_type: MIME type of the file

    Returns:
        Safe filename with UUID and extension
    """
    # Get extension from original filename or MIME type
    ext = Path(original_filename).suffix
    if not ext:
        # Try to get extension from MIME type
        ext = mimetypes.guess_extension(content_type) or ''

    # Generate unique filename
    unique_id = uuid.uuid4().hex
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    safe_filename = f"{timestamp}_{unique_id}{ext}"

    return safe_filename


async def save_upload_file(file: UploadFile, category: str) -> tuple[Path, str]:
    """
    Save uploaded file to disk.

    Args:
        file: Uploaded file
        category: File category (image, video, etc.)

    Returns:
        Tuple of (file_path, public_url)
    """
    # Create category subdirectory
    category_dir = UPLOAD_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)

    # Generate safe filename
    safe_filename = generate_safe_filename(file.filename or 'upload', file.content_type or 'application/octet-stream')
    file_path = category_dir / safe_filename

    # Save file
    try:
        with file_path.open('wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    # Generate public URL
    # In production, this would be a CDN URL or signed URL
    # For now, use relative path that can be served by static file handler
    public_url = f"/uploads/{category}/{safe_filename}"

    return file_path, public_url


@router.post(
    "/media",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Media File",
    description="""
    Upload media files (images, videos, audio, documents) for WhatsApp or other uses.

    Supported file types:
    - Images: JPEG, PNG, GIF, WebP
    - Videos: MP4, MPEG, QuickTime, WebM
    - Audio: MP3, OGG, WAV, WebM
    - Documents: PDF, Word, Excel
    - Text: Plain text, CSV

    Maximum file size: 10MB
    """,
    responses={
        201: {"description": "File uploaded successfully"},
        400: {"model": UploadError, "description": "Invalid file"},
        413: {"model": UploadError, "description": "File too large"},
        415: {"model": UploadError, "description": "Unsupported file type"}
    }
)
async def upload_media(
    file: UploadFile = File(..., description="Media file to upload"),
    max_size: Optional[int] = Query(MAX_FILE_SIZE, description="Maximum file size in bytes", le=50*1024*1024),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UploadResponse:
    """
    Upload a media file.

    This endpoint is used by WhatsApp integration and other features
    that need to upload images, videos, audio, or documents.

    Args:
        file: Uploaded file
        max_size: Maximum allowed file size (default: 10MB, max: 50MB)
        current_user: Authenticated user
        db: Database session

    Returns:
        UploadResponse with file URL, type, and size

    Raises:
        HTTPException: If file is invalid, too large, or unsupported type
    """
    try:
        logger.info(f"Upload request from user {current_user.id}: {file.filename} ({file.content_type})")

        # Validate file
        validate_file(file, max_size)

        # Determine category
        category = get_file_category(file.content_type or 'application/octet-stream')

        # Save file
        file_path, public_url = await save_upload_file(file, category)

        # Get final file size
        file_size = file_path.stat().st_size

        logger.info(f"File uploaded successfully: {file_path} -> {public_url}")

        return UploadResponse(
            url=public_url,
            type=file.content_type or 'application/octet-stream',
            size=file_size,
            filename=file.filename,
            uploaded_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.delete(
    "/media",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Media File",
    description="Delete a previously uploaded media file"
)
async def delete_media(
    url: str = Query(..., description="URL of the file to delete"),
    current_user: User = Depends(get_current_user)
) -> None:
    """
    Delete an uploaded media file.

    Args:
        url: Public URL of the file to delete
        current_user: Authenticated user

    Raises:
        HTTPException: If file not found or deletion fails
    """
    try:
        # Extract relative path from URL
        if url.startswith('/uploads/'):
            relative_path = url[len('/uploads/'):]
            file_path = UPLOAD_DIR / relative_path

            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                logger.info(f"File deleted by user {current_user.id}: {file_path}")
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file URL"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete failed: {str(e)}"
        )


@router.get(
    "/media/info",
    response_model=UploadResponse,
    summary="Get Media File Info",
    description="Get information about an uploaded media file"
)
async def get_media_info(
    url: str = Query(..., description="URL of the file"),
    current_user: User = Depends(get_current_user)
) -> UploadResponse:
    """
    Get information about an uploaded file.

    Args:
        url: Public URL of the file
        current_user: Authenticated user

    Returns:
        File information

    Raises:
        HTTPException: If file not found
    """
    try:
        # Extract relative path from URL
        if url.startswith('/uploads/'):
            relative_path = url[len('/uploads/'):]
            file_path = UPLOAD_DIR / relative_path

            if file_path.exists() and file_path.is_file():
                stat = file_path.stat()
                content_type = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'

                return UploadResponse(
                    url=url,
                    type=content_type,
                    size=stat.st_size,
                    filename=file_path.name,
                    uploaded_at=datetime.fromtimestamp(stat.st_mtime)
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file URL"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get info failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file info: {str(e)}"
        )
