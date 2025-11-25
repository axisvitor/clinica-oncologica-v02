"""
File validation utilities for upload module.

Contains:
- File type validation
- MIME type validation
- Extension validation
- Filename sanitization
- Category determination
"""

import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status

from app.schemas.v2.upload import FileCategory
from app.utils.logging import get_logger

from .config import ALLOWED_MIME_TYPES, DANGEROUS_EXTENSIONS

logger = get_logger(__name__)


def validate_file_type(filename: str, content_type: str) -> None:
    """
    Validate file type and extension.

    Args:
        filename: Original filename
        content_type: MIME type

    Raises:
        HTTPException: If file type is invalid or dangerous
    """
    # Check MIME type
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{content_type}' is not supported",
        )

    # Check extension
    ext = Path(filename).suffix.lower()
    if ext in DANGEROUS_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' is not allowed for security reasons",
        )


def get_file_category(content_type: str) -> FileCategory:
    """
    Determine file category from MIME type.

    Args:
        content_type: MIME type

    Returns:
        FileCategory enum value
    """
    if content_type.startswith("image/"):
        return FileCategory.IMAGE
    elif content_type.startswith("video/"):
        return FileCategory.VIDEO
    elif content_type.startswith("audio/"):
        return FileCategory.AUDIO
    elif content_type.startswith("text/"):
        return FileCategory.TEXT
    elif content_type in {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }:
        return FileCategory.DOCUMENT
    else:
        return FileCategory.OTHER


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = Path(filename).name

    # Replace unsafe characters
    safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    sanitized = "".join(c if c in safe_chars else "_" for c in filename)

    # Limit length
    if len(sanitized) > 255:
        ext = Path(sanitized).suffix
        sanitized = sanitized[: 255 - len(ext)] + ext

    return sanitized


def guess_extension(content_type: str) -> str:
    """
    Guess file extension from MIME type.

    Args:
        content_type: MIME type

    Returns:
        File extension (with dot) or empty string
    """
    ext = mimetypes.guess_extension(content_type)
    return ext or ""
