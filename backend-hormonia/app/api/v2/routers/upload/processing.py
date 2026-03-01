"""
File processing operations for upload module.

Contains:
- Image metadata extraction
- Image processing (thumbnails, previews, resizing)
- Processing status tracking
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.schemas.v2.upload import (
    ImageMetadata,
    ImageFormat,
    ProcessingInfo,
    ProcessingStatus,
    UploadOptionsRequest,
)
from app.utils.logging import get_logger
from app.utils.timezone import now_sao_paulo

logger = get_logger(__name__)


def get_image_metadata(file_path: Path) -> Optional[ImageMetadata]:
    """
    Extract image metadata.

    Args:
        file_path: Path to image file

    Returns:
        ImageMetadata or None if not an image
    """
    try:
        from PIL import Image

        with Image.open(file_path) as img:
            # Get format
            format_str = img.format.lower() if img.format else "unknown"
            try:
                img_format = ImageFormat(format_str)
            except ValueError:
                img_format = ImageFormat.JPEG  # Default

            return ImageMetadata(
                width=img.width,
                height=img.height,
                format=img_format,
                has_alpha=img.mode in ("RGBA", "LA", "PA"),
                color_mode=img.mode,
            )
    except Exception as e:
        logger.warning(f"Failed to extract image metadata: {e}")
        return None


async def process_image(
    file_path: Path,
    options: UploadOptionsRequest,
) -> ProcessingInfo:
    """
    Process uploaded image (thumbnails, previews, etc).

    Args:
        file_path: Path to image file
        options: Processing options

    Returns:
        ProcessingInfo with results
    """
    start_time = now_sao_paulo()
    processing_info = ProcessingInfo(
        status=ProcessingStatus.PROCESSING,
        virus_scan_clean=None,
        processing_time_ms=0,
    )

    try:
        from PIL import Image

        # Open image
        with Image.open(file_path) as img:
            base_dir = file_path.parent
            base_name = file_path.stem

            # Generate thumbnail (128x128)
            if options.generate_thumbnail:
                thumb_path = (
                    base_dir / "thumbnails" / f"{base_name}_thumb{file_path.suffix}"
                )
                thumb_path.parent.mkdir(exist_ok=True)
                img_copy = img.copy()
                img_copy.thumbnail((128, 128))
                img_copy.save(thumb_path, quality=options.quality)
                processing_info.thumbnail_url = f"/uploads/thumbnails/{thumb_path.name}"

            # Generate preview (800x600)
            if options.generate_preview:
                preview_path = (
                    base_dir / "previews" / f"{base_name}_preview{file_path.suffix}"
                )
                preview_path.parent.mkdir(exist_ok=True)
                img_copy = img.copy()
                img_copy.thumbnail((800, 600))
                img_copy.save(preview_path, quality=options.quality)
                processing_info.preview_url = f"/uploads/previews/{preview_path.name}"

            # Resize if requested
            if options.resize_width or options.resize_height:
                resized_path = (
                    base_dir / "resized" / f"{base_name}_resized{file_path.suffix}"
                )
                resized_path.parent.mkdir(exist_ok=True)

                # Calculate new dimensions maintaining aspect ratio
                width, height = img.size
                if options.resize_width and options.resize_height:
                    new_size = (options.resize_width, options.resize_height)
                elif options.resize_width:
                    ratio = options.resize_width / width
                    new_size = (options.resize_width, int(height * ratio))
                else:  # resize_height
                    ratio = options.resize_height / height
                    new_size = (int(width * ratio), options.resize_height)

                img_copy = img.copy()
                img_copy.thumbnail(new_size)
                img_copy.save(resized_path, quality=options.quality)
                processing_info.resized_url = f"/uploads/resized/{resized_path.name}"

        processing_info.status = ProcessingStatus.COMPLETED

    except Exception as e:
        logger.error(f"Image processing failed: {e}", exc_info=True)
        processing_info.status = ProcessingStatus.FAILED

    # Calculate processing time
    end_time = now_sao_paulo()
    processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
    processing_info.processing_time_ms = processing_time_ms

    return processing_info
