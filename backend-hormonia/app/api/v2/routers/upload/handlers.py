"""
Route handlers for upload module.

Contains:
- Upload file endpoint
- Gated upload download endpoint
- Get upload info endpoint
- Delete upload endpoint
"""

from __future__ import annotations

import uuid
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
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.models.user import User, UserRole
from app.models.upload import Upload
from app.dependencies.auth_dependencies import get_current_user_object_from_session
from app.schemas.v2.upload import (
    UploadOptionsRequest,
    UploadResponse,
    FileMetadata,
    FileCategory,
    ImageMetadata,
    StorageProvider,
    ProcessingStatus,
    ProcessingInfo,
)
from app.schemas.v2.common import FieldSelector
from app.utils.logging import get_logger

from . import config as upload_config
from .config import (
    MAX_FILE_SIZE_ABSOLUTE,
    CACHE_TTL_METADATA,
    UnsafeUploadPath,
    gated_download_url,
    resolve_local_upload_path,
    response_url_for_upload,
)
from .dependencies import (
    get_redis_client,
    generate_cache_key,
    check_rate_limit,
    check_user_quota,
)
from .active_content import (
    ACTIVE_CONTENT_SAMPLE_BYTES,
    REASON_ACTIVE_ACTUAL_MIME,
    REASON_ACTIVE_DECLARED_MIME,
    detect_active_content_bytes,
)
from .validators import validate_file_type, get_file_category
from .storage import save_upload_file
from .processing import get_image_metadata, process_image
from .security import scan_virus, validate_mime_type, scan_file_security
from app.utils.timezone import now_sao_paulo

logger = get_logger(__name__)

# Compatibility seam for legacy tests that monkeypatch this module directly.
UPLOAD_DIR = upload_config.UPLOAD_DIR

_ACTIVE_CONTENT_DENIAL_DETAIL = "File type is not allowed for security reasons"


def _active_content_denial_status(reason: str | None) -> int:
    if reason in {REASON_ACTIVE_DECLARED_MIME, REASON_ACTIVE_ACTUAL_MIME}:
        return status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    return status.HTTP_400_BAD_REQUEST


def _deny_active_content_upload(
    *,
    upload_id,
    user_id,
    reason: str,
    response_status: int,
    start_time,
) -> None:
    logger.warning(
        "upload_active_content_denied",
        extra={
            "upload_id": str(upload_id),
            "user_id": str(user_id),
            "reason": reason,
            "status": response_status,
            "duration_ms": int((now_sao_paulo() - start_time).total_seconds() * 1000),
        },
    )
    raise HTTPException(
        status_code=response_status,
        detail=_ACTIVE_CONTENT_DENIAL_DETAIL,
    )


def _validate_no_active_content_before_persistence(
    *,
    file: UploadFile,
    upload_id,
    user_id,
    start_time,
) -> None:
    """Reject active web content using only a bounded sample and safe diagnostics."""

    try:
        sample = file.file.read(ACTIVE_CONTENT_SAMPLE_BYTES)
    except Exception:
        _deny_active_content_upload(
            upload_id=upload_id,
            user_id=user_id,
            reason="sample_failed",
            response_status=status.HTTP_400_BAD_REQUEST,
            start_time=start_time,
        )

    try:
        file.file.seek(0)
    except Exception:
        _deny_active_content_upload(
            upload_id=upload_id,
            user_id=user_id,
            reason="sample_reset_failed",
            response_status=status.HTTP_400_BAD_REQUEST,
            start_time=start_time,
        )

    result = detect_active_content_bytes(
        sample,
        declared_mime=file.content_type or "application/octet-stream",
        filename=file.filename or "upload",
    )
    if not result.is_active:
        return

    reason = result.reason or "active_content"
    _deny_active_content_upload(
        upload_id=upload_id,
        user_id=user_id,
        reason=reason,
        response_status=_active_content_denial_status(reason),
        start_time=start_time,
    )


def _safe_role_value(user: User | None) -> str:
    role = getattr(user, "role", None)
    if hasattr(role, "value"):
        return str(role.value)
    return str(role or "")


def _is_admin(user: User | None) -> bool:
    role = getattr(user, "role", None)
    return role == UserRole.ADMIN or _safe_role_value(user).lower() == UserRole.ADMIN.value


def _authorize_upload_record(upload_record: Upload, current_user: User) -> None:
    if upload_record.user_id == current_user.id or _is_admin(current_user):
        return

    logger.warning(
        "upload_access_denied",
        extra={
            "upload_id": str(upload_record.id),
            "user_id": str(getattr(current_user, "id", "unknown")),
            "reason": "foreign_owner",
            "status": status.HTTP_403_FORBIDDEN,
        },
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden",
    )


async def _load_upload_record(upload_id, db: AsyncSession | None) -> Upload | None:
    if db is None:
        logger.warning(
            "upload_lookup_failed",
            extra={
                "upload_id": str(upload_id),
                "reason": "missing_db_session",
                "status": status.HTTP_404_NOT_FOUND,
            },
        )
        return None

    result = await db.execute(
        select(Upload).where(Upload.id == upload_id, Upload.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def _get_authorized_upload_record(
    upload_id,
    current_user: User,
    db: AsyncSession | None,
) -> Upload:
    upload_record = await _load_upload_record(upload_id, db)
    if not upload_record:
        logger.info(
            "upload_lookup_not_found",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(getattr(current_user, "id", "unknown")),
                "reason": "missing_or_deleted",
                "status": status.HTTP_404_NOT_FOUND,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )

    _authorize_upload_record(upload_record, current_user)
    return upload_record


def _storage_provider(value: str | None) -> StorageProvider:
    try:
        return StorageProvider(value or StorageProvider.LOCAL.value)
    except ValueError:
        return StorageProvider.LOCAL


def _metadata_dict(upload_record: Upload) -> dict[str, Any]:
    metadata = upload_record.file_metadata or {}
    return metadata if isinstance(metadata, dict) else {}


def _file_category(upload_record: Upload) -> FileCategory:
    metadata = _metadata_dict(upload_record)
    category = metadata.get("category")
    if category:
        try:
            return FileCategory(category)
        except ValueError:
            pass
    return get_file_category(upload_record.file_type or "application/octet-stream")


def _image_metadata(upload_record: Upload) -> ImageMetadata | None:
    metadata = _metadata_dict(upload_record).get("image_metadata")
    if not metadata:
        return None
    try:
        return ImageMetadata.model_validate(metadata)
    except Exception:
        return None


def _processing_info(upload_record: Upload) -> ProcessingInfo:
    metadata = _metadata_dict(upload_record)
    processing = metadata.get("processing")
    if isinstance(processing, dict):
        try:
            return ProcessingInfo.model_validate(processing)
        except Exception:
            pass

    return ProcessingInfo(
        status=ProcessingStatus.COMPLETED,
        virus_scan_clean=upload_record.virus_clean,
    )


def _build_upload_response(upload_record: Upload) -> UploadResponse:
    """Build UploadResponse payload from Upload ORM record."""

    metadata = _metadata_dict(upload_record)
    is_public = bool(upload_record.is_public)
    safe_filename = metadata.get("safe_filename") or Path(
        str(upload_record.storage_path)
    ).name
    file_type = upload_record.file_type or "application/octet-stream"

    return UploadResponse(
        id=upload_record.id,
        url=response_url_for_upload(
            upload_record.id,
            upload_record.storage_path,
            public=is_public,
        ),
        download_url=gated_download_url(upload_record.id),
        file=FileMetadata(
            id=upload_record.id,
            filename=upload_record.file_name,
            safe_filename=safe_filename,
            content_type=file_type,
            category=_file_category(upload_record),
            size=upload_record.file_size,
            checksum=upload_record.content_hash,
        ),
        image_metadata=_image_metadata(upload_record),
        processing=_processing_info(upload_record),
        storage_provider=_storage_provider(upload_record.storage_provider),
        storage_path=upload_record.storage_path,
        uploaded_by=upload_record.user_id,
        uploaded_at=upload_record.created_at,
        is_public=is_public,
        expires_at=None,
        custom_metadata=metadata,
    )


def _apply_field_selection(response_data: UploadResponse, fields: Optional[str]) -> Dict[str, Any]:
    response_dict = response_data.model_dump()
    if fields:
        field_set = FieldSelector.parse_fields(fields)
        response_dict = FieldSelector.filter_dict(response_dict, field_set)
    return response_dict


def _generic_download_filename(upload_record: Upload) -> str:
    suffix = Path(upload_record.file_name or upload_record.storage_path or "").suffix
    if len(suffix) > 16 or any(ch in suffix for ch in ("/", "\\", ":")):
        suffix = ""
    return f"upload-{upload_record.id}{suffix}"


def _delete_known_derivatives(file_path: Path, upload_id) -> None:
    """Best-effort cleanup for derivatives stored beside the source file."""

    for subdir in ("thumbnails", "previews", "resized"):
        derived_dir = file_path.parent / subdir
        if not derived_dir.is_dir():
            continue
        for derived_file in derived_dir.glob(f"{file_path.stem}_*{file_path.suffix}"):
            try:
                if derived_file.is_file():
                    derived_file.unlink()
                    logger.info(
                        "upload_derivative_deleted",
                        extra={"upload_id": str(upload_id), "status": "deleted"},
                    )
            except OSError as exc:
                logger.warning(
                    "upload_derivative_delete_failed",
                    extra={
                        "upload_id": str(upload_id),
                        "reason": exc.__class__.__name__,
                        "status": "skipped",
                    },
                )


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
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Upload a file with optional processing."""

    redis_client = await get_redis_client()
    start_time = now_sao_paulo()
    file_path: Path | None = None
    upload_id = uuid.uuid4()

    try:
        logger.info(
            "upload_request_received",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(current_user.id),
                "visibility": "public" if public else "private",
                "content_type": file.content_type or "application/octet-stream",
            },
        )

        # Get file size without loading the full upload into memory.
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        # Validate file size
        if file_size > MAX_FILE_SIZE_ABSOLUTE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File exceeds maximum allowed size",
            )

        # Check rate limit and quota before writing bytes.
        await check_rate_limit(redis_client, current_user.id, file_size)
        await check_user_quota(db, current_user.id, file_size, redis_client)

        _validate_no_active_content_before_persistence(
            file=file,
            upload_id=upload_id,
            user_id=current_user.id,
            start_time=start_time,
        )

        validate_file_type(
            file.filename or "upload",
            file.content_type or "application/octet-stream",
        )

        category = get_file_category(file.content_type or "application/octet-stream")

        file_path, safe_filename, checksum, storage_path = await save_upload_file(
            file,
            category,
            current_user.id,
            public=public,
        )

        try:
            # SECURITY SCANNING (CVE fixes)
            await validate_mime_type(
                file_path,
                file.content_type or "application/octet-stream",
            )
            await scan_file_security(file_path)
            if scan_virus_flag:
                await scan_virus(file_path)
        except HTTPException:
            if file_path.exists():
                file_path.unlink()
            raise

        file_metadata = FileMetadata(
            id=upload_id,
            filename=file.filename or "upload",
            safe_filename=safe_filename,
            content_type=file.content_type or "application/octet-stream",
            category=category,
            size=file_size,
            checksum=checksum,
        )

        image_metadata = get_image_metadata(file_path) if category == FileCategory.IMAGE else None

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

        if scan_virus_flag:
            is_clean = await scan_virus(file_path)
            processing_info.virus_scan_clean = is_clean
            if not is_clean:
                file_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File failed security scan",
                )

        response_data = UploadResponse(
            id=upload_id,
            url=response_url_for_upload(upload_id, storage_path, public=public),
            download_url=gated_download_url(upload_id),
            file=file_metadata,
            image_metadata=image_metadata,
            processing=processing_info,
            storage_provider=StorageProvider.LOCAL,
            storage_path=storage_path,
            uploaded_by=current_user.id,
            uploaded_at=now_sao_paulo(),
            is_public=public,
            expires_at=None,
            custom_metadata=None,
        )

        upload_record = Upload(
            id=upload_id,
            user_id=current_user.id,
            file_name=file.filename or "upload",
            file_size=file_size,
            file_type=file.content_type,
            storage_path=storage_path,
            storage_provider="local",
            content_hash=checksum,
            file_metadata={
                "category": category.value if hasattr(category, "value") else str(category),
                "safe_filename": safe_filename,
                "visibility": "public" if public else "private",
                "image_metadata": image_metadata.model_dump() if image_metadata else None,
                "processing": processing_info.model_dump(),
            },
            is_public=public,
            virus_scanned=scan_virus_flag,
            virus_clean=processing_info.virus_scan_clean,
        )
        db.add(upload_record)
        await db.commit()
        logger.info(
            "upload_record_persisted",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(current_user.id),
                "status": "persisted",
            },
        )

        if redis_client:
            try:
                cache_key = generate_cache_key("metadata", upload_id=str(upload_id))
                await redis_client.setex(
                    cache_key,
                    CACHE_TTL_METADATA,
                    response_data.model_dump_json(),
                )
            except Exception as e:
                logger.warning(
                    "upload_metadata_cache_failed",
                    extra={
                        "upload_id": str(upload_id),
                        "reason": e.__class__.__name__,
                        "status": "skipped",
                    },
                )

        logger.info(
            "upload_completed",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(current_user.id),
                "status": "completed",
                "bytes": file_size,
                "duration_ms": int((now_sao_paulo() - start_time).total_seconds() * 1000),
            },
        )

        return _apply_field_selection(response_data, fields)

    except HTTPException:
        raise
    except Exception as e:
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        logger.error(
            "upload_failed",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(getattr(current_user, "id", "unknown")),
                "reason": e.__class__.__name__,
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed",
        )


async def download_upload_handler(
    upload_id,
    current_user: User,
    db: AsyncSession | None,
) -> FileResponse:
    """Stream an uploaded file after authentication and owner/admin authorization."""

    upload_record = await _get_authorized_upload_record(upload_id, current_user, db)

    try:
        resolved = resolve_local_upload_path(
            upload_record.storage_path,
            public=bool(upload_record.is_public),
            require_exists=True,
        )
    except UnsafeUploadPath:
        logger.warning(
            "upload_download_denied",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(current_user.id),
                "reason": "unsafe_storage_path",
                "status": status.HTTP_404_NOT_FOUND,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )
    except FileNotFoundError:
        logger.info(
            "upload_download_missing_file",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(current_user.id),
                "reason": "missing_file",
                "status": status.HTTP_404_NOT_FOUND,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )

    if not resolved.path.is_file():
        logger.info(
            "upload_download_missing_file",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(current_user.id),
                "reason": "not_file",
                "status": status.HTTP_404_NOT_FOUND,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )

    logger.info(
        "upload_download_authorized",
        extra={
            "upload_id": str(upload_id),
            "user_id": str(current_user.id),
            "status": status.HTTP_200_OK,
        },
    )
    return FileResponse(
        path=resolved.path,
        media_type=upload_record.file_type or "application/octet-stream",
        filename=_generic_download_filename(upload_record),
    )


async def get_upload_info_handler(
    upload_id,
    fields: Optional[str] = None,
    current_user: User = None,
    db: AsyncSession | None = None,
) -> Dict[str, Any]:
    """Get authorization-checked upload metadata."""

    redis_client = await get_redis_client()

    try:
        upload_record = await _get_authorized_upload_record(upload_id, current_user, db)
        response_data = _build_upload_response(upload_record)

        if redis_client:
            try:
                cache_key = generate_cache_key("metadata", upload_id=str(upload_id))
                await redis_client.setex(
                    cache_key,
                    CACHE_TTL_METADATA,
                    response_data.model_dump_json(),
                )
            except Exception as e:
                logger.warning(
                    "upload_metadata_cache_failed",
                    extra={
                        "upload_id": str(upload_id),
                        "reason": e.__class__.__name__,
                        "status": "skipped",
                    },
                )

        return _apply_field_selection(response_data, fields)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "upload_info_failed",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(getattr(current_user, "id", "unknown")),
                "reason": e.__class__.__name__,
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get upload info",
        )


async def delete_upload_handler(
    upload_id,
    current_user: User,
    db: AsyncSession | None = None,
) -> None:
    """Delete an uploaded file after owner/admin authorization."""

    redis_client = await get_redis_client()

    try:
        logger.info(
            "upload_delete_requested",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(current_user.id),
                "status": "requested",
            },
        )

        upload_record = await _get_authorized_upload_record(upload_id, current_user, db)

        try:
            resolved = resolve_local_upload_path(
                upload_record.storage_path,
                public=bool(upload_record.is_public),
                require_exists=False,
            )
        except UnsafeUploadPath:
            logger.warning(
                "upload_delete_denied",
                extra={
                    "upload_id": str(upload_id),
                    "user_id": str(current_user.id),
                    "reason": "unsafe_storage_path",
                    "status": status.HTTP_404_NOT_FOUND,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload not found",
            )

        if resolved.path.exists() and resolved.path.is_file():
            resolved.path.unlink()
            logger.info(
                "upload_file_deleted",
                extra={"upload_id": str(upload_id), "status": "deleted"},
            )
            _delete_known_derivatives(resolved.path, upload_id)

        upload_record.deleted_at = now_sao_paulo()
        if db is not None:
            await db.commit()
            logger.info(
                "upload_record_soft_deleted",
                extra={"upload_id": str(upload_id), "status": "deleted"},
            )

        if redis_client:
            try:
                cache_key = generate_cache_key("metadata", upload_id=str(upload_id))
                await redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(
                    "upload_metadata_cache_clear_failed",
                    extra={
                        "upload_id": str(upload_id),
                        "reason": e.__class__.__name__,
                        "status": "skipped",
                    },
                )

        logger.info(
            "upload_deleted",
            extra={"upload_id": str(upload_id), "user_id": str(current_user.id), "status": "deleted"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "upload_delete_failed",
            extra={
                "upload_id": str(upload_id),
                "user_id": str(getattr(current_user, "id", "unknown")),
                "reason": e.__class__.__name__,
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
        if db is not None:
            await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Delete failed",
        )
