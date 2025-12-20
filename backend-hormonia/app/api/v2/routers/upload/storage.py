"""
File storage operations for upload module.

Contains:
- File saving to disk
- Filename generation
- Checksum calculation
- File path management
"""

import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple
from uuid import UUID

from fastapi import UploadFile

from app.schemas.v2.upload import FileCategory
from app.utils.logging import get_logger

from .config import UPLOAD_DIR
from .validators import guess_extension

logger = get_logger(__name__)


def generate_safe_filename(original_filename: str, content_type: str) -> str:
    """
    Generate unique, safe filename.

    Args:
        original_filename: Original filename
        content_type: MIME type

    Returns:
        Safe filename with UUID and timestamp
    """
    # Get extension
    ext = Path(original_filename).suffix.lower()
    if not ext:
        ext = guess_extension(content_type)

    # Generate unique filename
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{unique_id}{ext}"

    return safe_filename


def calculate_checksum(file_path: Path) -> str:
    """
    Calculate MD5 checksum of file.

    Args:
        file_path: Path to file

    Returns:
        MD5 checksum hex string
    """
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


async def save_upload_file(
    file: UploadFile,
    category: FileCategory,
    user_id: UUID,
) -> Tuple[Path, str, str]:
    """
    Save uploaded file to disk.

    Args:
        file: Uploaded file
        category: File category
        user_id: User ID

    Returns:
        Tuple of (file_path, safe_filename, checksum)
    """
    # Create directory structure: uploads/{category}/{user_id}/
    category_dir = UPLOAD_DIR / category.value / str(user_id)
    category_dir.mkdir(parents=True, exist_ok=True)

    # Generate safe filename
    safe_filename = generate_safe_filename(
        file.filename or "upload", file.content_type or "application/octet-stream"
    )
    file_path = category_dir / safe_filename

    # Save file
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    # Calculate checksum
    checksum = calculate_checksum(file_path)

    return file_path, safe_filename, checksum
