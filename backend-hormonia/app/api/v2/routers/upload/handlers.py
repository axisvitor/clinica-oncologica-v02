"""
Route handlers for upload module.

Contains:
- Upload file endpoint
- Get upload info endpoint
- Delete upload endpoint
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import (
    HTTPException,
    status,
    UploadFile,
    File,
    Query,
    BackgroundTasks,
    Depends,
)

from app.database import get_db
from app.models.user import User
from app.dependencies.auth_dependencies import get_current_user_object_from_session
from app.schemas.v2.upload import (
    UploadOptionsRequest,
    UploadResponse,
    FileMetadata,
    FileCategory,
    StorageProvider,
    ProcessingStatus,
    ProcessingInfo,
)
from app.schemas.v2.common import FieldSelector
from app.utils.logging import get_logger

from .config import (
    MAX_FILE_SIZE_ABSOLUTE,
    CACHE_TTL_METADATA,
    UPLOAD_DIR,
)
from .dependencies import (
    get_redis_client,
    generate_cache_key,
    check_rate_limit,
    check_user_quota,
)
from .validators import validate_file_type, get_file_category
from .storage import save_upload_file
from .processing import get_image_metadata, process_image
from .security import scan_virus, validate_mime_type, scan_file_security

logger = get_logger(__name__)


async def upload_file_handler(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload"),
    generate_thumbnail: bool = Query(False, description="Generate thumbnail for images"),
    generate_preview: bool = Query(False, description="Generate preview for images"),
    resize_width: Optional[int] = Query(None, ge=100, le=4000, description="Resize width"),
    resize_height: Optional[int] = Query(None, ge=100, le=4000, description="Resize height"),
    quality: int = Query(85, ge=1, le=100, description="Image quality"),
    scan_virus_flag: bool = Query(True, description="Enable virus scanning"),
    public: bool = Query(False, description="Make file publicly accessible"),
    fields: Optional[str] = Query(None, description="Fields to return"),
    current_user: User = Depends(get_current_user_object_from_session),
    db = Depends(get_db),
) -> Dict[str, Any]:
    """
    Upload a file with optional processing.

    Args:
        background_tasks: FastAPI background tasks
        file: Uploaded file
        generate_thumbnail: Generate thumbnail
        generate_preview: Generate preview
        resize_width: Resize width
        resize_height: Resize height
        quality: Image compression quality
        scan_virus_flag: Enable virus scanning
        public: Make file public
        fields: Fields to return
        current_user: Authenticated user
        db: Database session

    Returns:
        Upload response with file info

    Raises:
        HTTPException: If upload fails
    """
    redis_client = await get_redis_client()
    start_time = datetime.utcnow()

    try:
        logger.info(
            f"Upload request from user {current_user.id}: "
            f"{file.filename} ({file.content_type})"
        )

        # Get file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        # Validate file size
        if file_size > MAX_FILE_SIZE_ABSOLUTE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size} bytes) exceeds maximum ({MAX_FILE_SIZE_ABSOLUTE} bytes)",
            )

        # Check rate limit
        await check_rate_limit(redis_client, current_user.id, file_size)

        # Check user quota
        await check_user_quota(db, current_user.id, file_size, redis_client)

        # Validate file type
        validate_file_type(
            file.filename or "upload",
            file.content_type or "application/octet-stream",
        )

        # Determine category
        category = get_file_category(file.content_type or "application/octet-stream")

        # Save file temporarily for security scanning
        file_path, safe_filename, checksum = await save_upload_file(
            file, category, current_user.id
        )

        try:
            # ===== SECURITY SCANNING (CVE Fixes) =====

            # 1. MIME type validation (CVE-CLINIC-2025-002)
            await validate_mime_type(
                file_path, file.content_type or "application/octet-stream"
            )

            # 2. File security scan (CVE-CLINIC-2025-003 + PDF JavaScript)
            await scan_file_security(file_path)

            # 3. Virus scan with ClamAV (if enabled)
            if scan_virus_flag:
                await scan_virus(file_path)

            # ===== END SECURITY SCANNING =====

        except HTTPException:
            # Security check failed - delete file and re-raise
            if file_path.exists():
                file_path.unlink()
            raise

        # Create upload ID
        upload_id = uuid.uuid4()

        # Build file metadata
        file_metadata = FileMetadata(
            id=upload_id,
            filename=file.filename or "upload",
            safe_filename=safe_filename,
            content_type=file.content_type or "application/octet-stream",
            category=category,
            size=file_size,
            checksum=checksum,
        )

        # Get image metadata if applicable
        image_metadata = None
        if category == FileCategory.IMAGE:
            image_metadata = get_image_metadata(file_path)

        # Process image if requested
        processing_info = ProcessingInfo(
            status=ProcessingStatus.PENDING,
            virus_scan_clean=None,
        )

        if category == FileCategory.IMAGE and (
            generate_thumbnail or generate_preview or resize_width or resize_height
        ):
            options = UploadOptionsRequest(
                generate_thumbnail=generate_thumbnail,
                generate_preview=generate_preview,
                resize_width=resize_width,
                resize_height=resize_height,
                quality=quality,
                scan_virus=scan_virus_flag,
                storage_provider=StorageProvider.LOCAL,
                public=public,
            )
            processing_info = await process_image(file_path, options)
        else:
            processing_info.status = ProcessingStatus.COMPLETED

        # Virus scan if requested
        if scan_virus_flag:
            is_clean = await scan_virus(file_path)
            processing_info.virus_scan_clean = is_clean
            if not is_clean:
                # Delete infected file
                file_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File failed virus scan",
                )

        # Build response
        storage_path = str(file_path.relative_to(UPLOAD_DIR))
        public_url = f"/uploads/{storage_path}"

        response_data = UploadResponse(
            id=upload_id,
            url=public_url,
            download_url=f"/api/v2/upload/{upload_id}/download",
            file=file_metadata,
            image_metadata=image_metadata,
            processing=processing_info,
            storage_provider=StorageProvider.LOCAL,
            storage_path=storage_path,
            uploaded_by=current_user.id,
            uploaded_at=datetime.utcnow(),
            is_public=public,
            expires_at=None,
            custom_metadata=None,
        )

        # Cache metadata
        if redis_client:
            try:
                cache_key = generate_cache_key("metadata", upload_id=str(upload_id))
                await redis_client.setex(
                    cache_key,
                    CACHE_TTL_METADATA,
                    response_data.model_dump_json(),
                )
            except Exception as e:
                logger.warning(f"Failed to cache upload metadata: {e}")

        logger.info(
            f"Upload completed: {file_path} ({file_size} bytes) in "
            f"{(datetime.utcnow() - start_time).total_seconds():.2f}s"
        )

        # Apply field selection
        response_dict = response_data.model_dump()
        if fields:
            field_set = FieldSelector.parse_fields(fields)
            response_dict = FieldSelector.filter_dict(response_dict, field_set)

        return response_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


async def get_upload_info_handler(
    upload_id,
    fields: Optional[str] = None,
    current_user: User = None,
) -> Dict[str, Any]:
    """
    Get upload information.

    Args:
        upload_id: Upload ID
        fields: Fields to return
        current_user: Authenticated user

    Returns:
        Upload information

    Raises:
        HTTPException: If upload not found
    """
    redis_client = await get_redis_client()

    try:
        # Try cache first
        if redis_client:
            cache_key = generate_cache_key("metadata", upload_id=str(upload_id))
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for upload {upload_id}")
                response_data = UploadResponse.model_validate_json(cached)

                # Apply field selection
                response_dict = response_data.model_dump()
                if fields:
                    field_set = FieldSelector.parse_fields(fields)
                    response_dict = FieldSelector.filter_dict(response_dict, field_set)

                return response_dict

        # TODO: Query from database in production
        # For now, return 404 if not in cache
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload {upload_id} not found",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get upload info failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get upload info: {str(e)}",
        )


async def delete_upload_handler(
    upload_id,
    current_user: User,
) -> None:
    """
    Delete an uploaded file.

    Args:
        upload_id: Upload ID
        current_user: Authenticated user

    Raises:
        HTTPException: If deletion fails
    """
    redis_client = await get_redis_client()

    try:
        logger.info(f"Delete request from user {current_user.id} for upload {upload_id}")

        # Get upload info from cache
        upload_info = None
        if redis_client:
            cache_key = generate_cache_key("metadata", upload_id=str(upload_id))
            cached = await redis_client.get(cache_key)
            if cached:
                upload_info = UploadResponse.model_validate_json(cached)

        if not upload_info:
            # TODO: Query from database in production
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Upload {upload_id} not found",
            )

        # Verify ownership (or admin)
        if upload_info.uploaded_by != current_user.id:
            # Check if admin (simplified check)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this file",
            )

        # Delete main file
        file_path = UPLOAD_DIR / upload_info.storage_path
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file: {file_path}")

        # Delete thumbnails and previews
        if upload_info.processing:
            for url_field in ["thumbnail_url", "preview_url", "resized_url"]:
                url = getattr(upload_info.processing, url_field, None)
                if url:
                    # Extract path from URL
                    path_parts = url.split("/uploads/", 1)
                    if len(path_parts) == 2:
                        derived_path = UPLOAD_DIR / path_parts[1]
                        if derived_path.exists():
                            derived_path.unlink()
                            logger.info(f"Deleted derived file: {derived_path}")

        # Clear cache
        if redis_client:
            try:
                cache_key = generate_cache_key("metadata", upload_id=str(upload_id))
                await redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Failed to clear cache: {e}")

        logger.info(f"Upload {upload_id} deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete failed: {str(e)}",
        )
