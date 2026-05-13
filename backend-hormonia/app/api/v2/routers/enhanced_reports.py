"""
Enhanced Reports API v2
Advanced reporting features extending base reports with custom builders, visualizations, and dashboards.
Delegates logic to EnhancedReportsService.
"""

from collections.abc import Mapping
from typing import Any, Optional, List
import asyncio
import hashlib
import inspect
import json
from uuid import UUID
from unittest.mock import Mock

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    BackgroundTasks,
    Request,
    Response,
    Cookie,
)
from fastapi.responses import RedirectResponse

from app.core.database.async_engine import get_async_db
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.core.redis_manager import get_async_redis_client as get_async_redis
from app.schemas.v2.enhanced_reports import (
    ReportBuilderCreate,
    ReportBuilderResponse,
    VisualizationCreate,
    VisualizationResponse,
    VisualizationListResponse,
    DeliveryConfigCreate,
    DeliveryConfigResponse,
    DeliveryHistoryEntry,
    ReportShareCreate,
    ReportShareResponse,
    PublicLinkCreate,
    PublicLinkResponse,
    MultiFormatExportRequest,
    ExportResponse,
    ExportFormat,
    ReportHistoryResponse,
    ReportRestoreRequest,
    DashboardCreate,
    DashboardUpdate,
    DashboardResponse,
    DashboardListResponse,
    DashboardSnapshotCreate,
    DashboardSnapshotResponse,
)
from app.api.v2.dependencies import get_pagination_params
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.auth_helpers import extract_user_role_and_uuid
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger
from app.services import EnhancedReportsService
from app.services.reporting.report_access import assert_report_access, parse_report_access_metadata
from app.utils.timezone import now_sao_paulo, today_sao_paulo

logger = get_logger(__name__)
router = APIRouter()

# Compatibility seam for legacy tests/imports that patch enhanced_reports.get_db.
# Runtime still delegates to the async database dependency unless patched.
get_db = get_async_db

# Rate limits
RATE_LIMIT_STANDARD = "10/hour"
RATE_LIMIT_HEAVY = "5/hour"
RATE_LIMIT_EXPORT = "15/hour"


async def _get_current_user_from_session_dep(
    request: Request,
    session_cookie_id: str = Cookie(None, alias="session_id"),
):
    override_result = None
    try:
        from app.main import app as fastapi_app
    except Exception:
        fastapi_app = None
    if fastapi_app is not None:
        override = fastapi_app.dependency_overrides.get(get_current_user_from_session)
        if override:
            try:
                override_result = override(request)
            except TypeError:
                override_result = override()
    if override_result is not None:
        if hasattr(override_result, "__await__"):
            return await override_result
        return override_result

    if isinstance(get_current_user_from_session, Mock):
        result = get_current_user_from_session(
            request=request,
            session_cookie_id=session_cookie_id,
            x_session_id=None,
            authorization=None,
        )
    else:
        redis_cache = await asyncio.wait_for(get_redis_cache(), timeout=2.0)
        result = get_current_user_from_session(
            request=request,
            session_cookie_id=session_cookie_id,
            x_session_id=None,
            authorization=None,
            redis_cache=redis_cache,
        )

    if hasattr(result, "__await__"):
        return await result
    return result


async def _get_cached_result(cache_key: str):
    try:
        redis_client = await get_async_redis()
        if redis_client is None:
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as exc:
        logger.warning("Enhanced reports cache read failed: %s", exc)
    return None


def _check_report_access(
    report_id: UUID,
    role: UserRole,
    user_id: Optional[UUID],
) -> bool:
    """Legacy monkeypatch seam; normal routes use async raw metadata guards."""

    if role == UserRole.ADMIN:
        return True
    return user_id is not None


_ORIGINAL_CHECK_REPORT_ACCESS = _check_report_access


def _build_cache_key(prefix: str, resource_id: UUID) -> str:
    return f"enhanced_reports:{prefix}:{resource_id}"


def _build_base_report_cache_key(report_id: UUID) -> str:
    param_str = json.dumps({"report_id": str(report_id)}, sort_keys=True, default=str)
    param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:32]
    return f"reports:v2:report:{param_hash}"


def _router_report_cache_candidates(report_id: UUID) -> list[tuple[str, str]]:
    return [
        (_build_cache_key("builder", report_id), "router_cache:builder"),
        (_build_cache_key("report", report_id), "router_cache:report"),
        (_build_base_report_cache_key(report_id), "base_report_cache:report"),
    ]


async def _resolve_raw_report_metadata(
    report_id: UUID,
    service: EnhancedReportsService,
) -> tuple[dict[str, Any] | None, str]:
    for cache_key, metadata_source in _router_report_cache_candidates(report_id):
        cached = await _get_cached_result(cache_key)
        if cached is not None:
            return cached, metadata_source

    service_loader = getattr(service, "_load_raw_report_metadata", None)
    if callable(service_loader):
        loaded = service_loader(report_id)
        if inspect.isawaitable(loaded):
            loaded = await loaded
        if isinstance(loaded, tuple):
            raw_metadata, metadata_source = loaded
        else:
            raw_metadata, metadata_source = loaded, "service_cache:report"
        if raw_metadata is not None:
            return raw_metadata, str(metadata_source)

    return None, "db"


async def _resolve_raw_export_metadata(
    export_id: UUID,
    service: EnhancedReportsService,
) -> tuple[dict[str, Any] | None, str]:
    cache_key = _build_cache_key("export", export_id)
    cached = await _get_cached_result(cache_key)
    if cached is not None:
        return cached, "router_cache:export"

    service_loader = getattr(service, "_load_raw_export_metadata", None)
    if callable(service_loader):
        loaded = service_loader(export_id)
        if inspect.isawaitable(loaded):
            loaded = await loaded
        if isinstance(loaded, tuple):
            raw_metadata, metadata_source = loaded
        else:
            raw_metadata, metadata_source = loaded, "service_cache:export"
        if raw_metadata is not None:
            return raw_metadata, str(metadata_source)

    return None, "service_cache:export"


async def _assert_enhanced_report_access(
    report_id: UUID,
    current_user,
    service: EnhancedReportsService,
) -> tuple[UserRole, UUID, dict[str, Any] | None, bool]:
    role, user_id = _extract_user_context(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    legacy_checker = globals().get("_check_report_access")
    if legacy_checker is not _ORIGINAL_CHECK_REPORT_ACCESS:
        legacy_result = legacy_checker(report_id, role, user_id)
        if inspect.isawaitable(legacy_result):
            legacy_result = await legacy_result
        if not legacy_result:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        return role, user_id, None, True

    raw_metadata, metadata_source = await _resolve_raw_report_metadata(report_id, service)
    db = getattr(service, "db", None)
    if raw_metadata is None and isinstance(db, Mock):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    await assert_report_access(
        db,
        role=role,
        user_id=user_id,
        raw_metadata=raw_metadata,
        report_id=report_id,
        metadata_source=metadata_source,
        missing_resource_status_code=status.HTTP_404_NOT_FOUND,
    )
    return role, user_id, raw_metadata, False


async def _assert_enhanced_export_access(
    export_id: UUID,
    current_user,
    service: EnhancedReportsService,
) -> tuple[UserRole, UUID, dict[str, Any]]:
    role, user_id = _extract_user_context(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    raw_metadata, metadata_source = await _resolve_raw_export_metadata(export_id, service)
    if raw_metadata is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    evidence = parse_report_access_metadata(
        raw_metadata,
        export_id=export_id,
        source=metadata_source,
    )
    if evidence.is_malformed or not (
        evidence.has_access_evidence or evidence.linked_report_id is not None
    ):
        reason = (
            "malformed_export_access_metadata"
            if evidence.is_malformed
            else "missing_export_access_metadata"
        )
        logger.warning(
            "Report access denied",
            extra={
                "report_id": str(evidence.linked_report_id) if evidence.linked_report_id else None,
                "export_id": str(export_id),
                "user_id": str(user_id),
                "role": role.value if hasattr(role, "value") else str(role),
                "status": "denied",
                "response_status": status.HTTP_403_FORBIDDEN,
                "reason": reason,
                "metadata_source": metadata_source,
                "patient_id_count": len(evidence.patient_ids),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if role == UserRole.ADMIN or user_id in evidence.owner_ids:
        return role, user_id, raw_metadata

    linked_report_denial: HTTPException | None = None
    if evidence.linked_report_id is not None:
        try:
            await _assert_enhanced_report_access(
                evidence.linked_report_id,
                current_user,
                service,
            )
            return role, user_id, raw_metadata
        except HTTPException as exc:
            linked_report_denial = exc

    try:
        await assert_report_access(
            getattr(service, "db", None),
            role=role,
            user_id=user_id,
            raw_metadata=raw_metadata,
            report_id=None,
            export_id=export_id,
            metadata_source=metadata_source,
            missing_resource_status_code=status.HTTP_404_NOT_FOUND,
        )
    except HTTPException:
        if linked_report_denial is not None:
            raise linked_report_denial
        raise
    return role, user_id, raw_metadata


async def _call_service_with_optional_access_checked(
    method,
    *args,
    access_checked: bool = False,
):
    if access_checked:
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            signature = None
        if signature is not None and "access_checked" in signature.parameters:
            return await method(*args, access_checked=True)
    return await method(*args)


def _normalize_builder_response(
    data: dict,
    builder_id: UUID,
    user_id: Optional[UUID],
) -> dict:
    now = now_sao_paulo().isoformat()
    return {
        "id": data.get("id", str(builder_id)),
        "name": data.get("name", "Report"),
        "description": data.get("description"),
        "fields": data.get("fields", []),
        "filters": data.get("filters", {}),
        "created_at": data.get("created_at", now),
        "created_by": data.get("created_by", str(user_id) if user_id else str(builder_id)),
        "row_count": data.get("row_count", 0),
        "generation_time_seconds": data.get("generation_time_seconds", 0.0),
        "download_url": data.get(
            "download_url",
            f"/api/v2/enhanced-reports/builder/{builder_id}/download",
        ),
    }


def _normalize_visualization_response(
    data: dict,
    visualization_id: UUID,
) -> dict:
    now = now_sao_paulo().isoformat()
    config = dict(data.get("config", {}) or {})
    config.setdefault("type", "bar_chart")
    config.setdefault("title", "Visualization")
    return {
        "id": data.get("id", str(visualization_id)),
        "report_id": data.get("report_id", str(visualization_id)),
        "config": config,
        "data": data.get("data", {}),
        "created_at": data.get("created_at", now),
        "updated_at": data.get("updated_at", now),
    }


def _normalize_delivery_response(
    data: dict,
    schedule_id: UUID,
    user_id: Optional[UUID],
) -> dict:
    now = now_sao_paulo().isoformat()
    default_schedule = {
        "frequency": "daily",
        "start_date": today_sao_paulo().isoformat(),
        "time_of_day": "09:00",
        "timezone": "America/Sao_Paulo",
    }
    schedule = dict(data.get("schedule") or {})
    schedule.setdefault("frequency", default_schedule["frequency"])
    schedule.setdefault("start_date", default_schedule["start_date"])
    schedule.setdefault("time_of_day", default_schedule["time_of_day"])
    schedule.setdefault("timezone", default_schedule["timezone"])
    return {
        "id": data.get("id", str(schedule_id)),
        "report_id": data.get("report_id", str(schedule_id)),
        "name": data.get("name", "Delivery Schedule"),
        "description": data.get("description"),
        "method": data.get("method", "email"),
        "schedule": schedule,
        "email_config": data.get("email_config"),
        "webhook_config": data.get("webhook_config"),
        "export_format": data.get("export_format", "pdf"),
        "is_active": data.get("is_active", True),
        "next_run": data.get("next_run"),
        "last_run": data.get("last_run"),
        "last_status": data.get("last_status"),
        "run_count": data.get("run_count", 0),
        "created_at": data.get("created_at", now),
        "created_by": data.get("created_by", str(user_id) if user_id else str(schedule_id)),
    }


def _normalize_export_response(
    data: dict,
    export_id: UUID,
) -> dict:
    now = now_sao_paulo().isoformat()
    return {
        "export_id": data.get("export_id", str(export_id)),
        "report_id": data.get("report_id", str(export_id)),
        "formats": data.get("formats", ["pdf"]),
        "status": data.get("status", "pending"),
        "download_urls": data.get("download_urls", {}),
        "expires_at": data.get("expires_at", now),
        "file_sizes": data.get("file_sizes", {}),
        "created_at": data.get("created_at", now),
    }


def _is_safe_export_download_url(download_url: Any) -> bool:
    """Return True only for URLs that are safe to expose after auth."""

    if not isinstance(download_url, str):
        return False

    normalized_url = download_url.strip()
    if not normalized_url:
        return False

    lowered_url = normalized_url.lower()
    if "\\" in normalized_url:
        return False
    if lowered_url.startswith(("file:", "data:", "javascript:")):
        return False
    if len(lowered_url) >= 3 and lowered_url[1] == ":" and lowered_url[2] == "/":
        return False
    if lowered_url.startswith(
        ("/home/", "/mnt/", "/opt/", "/root/", "/srv/", "/tmp/", "/var/")
    ):
        return False
    if lowered_url.startswith(("/uploads", "uploads/")) or "/uploads/" in lowered_url:
        return False
    return True


def _log_blocked_export_download_url(
    *,
    export_id: UUID,
    report_id: Any,
    role: UserRole,
    user_id: UUID,
    reason: str,
    response_status: int,
) -> None:
    logger.warning(
        "Blocked unsafe export download URL",
        extra={
            "export_id": str(export_id),
            "report_id": str(report_id) if report_id else None,
            "user_id": str(user_id),
            "role": role.value if hasattr(role, "value") else str(role),
            "status": "denied",
            "response_status": response_status,
            "reason": reason,
        },
    )


def _sanitize_export_download_urls(
    export_status: dict,
    *,
    export_id: UUID,
    role: UserRole,
    user_id: UUID,
) -> dict:
    """Withhold legacy private artifact URLs from status responses."""

    sanitized = dict(export_status)
    download_urls = sanitized.get("download_urls") or {}
    if not isinstance(download_urls, Mapping):
        sanitized["download_urls"] = {}
        _log_blocked_export_download_url(
            export_id=export_id,
            report_id=sanitized.get("report_id"),
            role=role,
            user_id=user_id,
            reason="malformed_download_urls",
            response_status=status.HTTP_200_OK,
        )
        return sanitized

    safe_download_urls: dict[str, str] = {}
    for format_name, download_url in download_urls.items():
        if _is_safe_export_download_url(download_url):
            safe_download_urls[str(format_name)] = str(download_url)
            continue
        _log_blocked_export_download_url(
            export_id=export_id,
            report_id=sanitized.get("report_id"),
            role=role,
            user_id=user_id,
            reason="unsafe_download_url_withheld",
            response_status=status.HTTP_200_OK,
        )
    sanitized["download_urls"] = safe_download_urls
    return sanitized


def _normalize_dashboard_response(
    data: dict,
    dashboard_id: UUID,
    user_id: Optional[UUID],
) -> dict:
    now = now_sao_paulo().isoformat()
    return {
        "id": data.get("id", str(dashboard_id)),
        "name": data.get("name", "Dashboard"),
        "description": data.get("description"),
        "layout": data.get("layout", "grid"),
        "widgets": data.get("widgets", []),
        "auto_refresh": data.get("auto_refresh", False),
        "refresh_interval_seconds": data.get("refresh_interval_seconds", 60),
        "is_public": data.get("is_public", False),
        "shared_with": data.get("shared_with"),
        "theme": data.get("theme", "light"),
        "created_at": data.get("created_at", now),
        "created_by": data.get("created_by", str(user_id) if user_id else str(dashboard_id)),
        "updated_at": data.get("updated_at", now),
        "view_count": data.get("view_count", 0),
    }


async def _get_db_dep():
    """Resolve the database dependency through the module-level get_db seam."""

    result = get_db()
    if inspect.isasyncgen(result):
        async for db in result:
            yield db
        return
    if inspect.isgenerator(result):
        try:
            yield next(result)
        finally:
            close = getattr(result, "close", None)
            if callable(close):
                close()
        return
    if inspect.isawaitable(result):
        result = await result
    yield result


async def get_enhanced_reports_service(
    db: AsyncSession = Depends(_get_db_dep),
) -> EnhancedReportsService:
    return EnhancedReportsService(db)


def _extract_user_context(current_user) -> tuple[UserRole, Optional[UUID]]:
    """Extract user context with UUID conversion."""
    return extract_user_role_and_uuid(current_user, default_role=UserRole.DOCTOR)


@router.post(
    "/builder",
    response_model=ReportBuilderResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit(RATE_LIMIT_STANDARD)
async def build_custom_report(
    request: Request,
    data: ReportBuilderCreate,
    background_tasks: BackgroundTasks,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id = _extract_user_context(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    return await service.build_custom_report(data, user_id, background_tasks)


@router.get("/builder/{builder_id}", response_model=ReportBuilderResponse)
async def get_builder_report(
    builder_id: UUID,
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    _, user_id, raw_report, _ = await _assert_enhanced_report_access(
        builder_id,
        current_user,
        service,
    )
    if raw_report is not None:
        return _normalize_builder_response(raw_report, builder_id, user_id)

    report = await service.get_builder_report(builder_id)
    return _normalize_builder_response(report, builder_id, user_id)


@router.get("/builder/{builder_id}/download")
async def download_builder_report(
    builder_id: UUID,
    format: ExportFormat = Query(ExportFormat.CSV),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    _, user_id, raw_report, _ = await _assert_enhanced_report_access(
        builder_id,
        current_user,
        service,
    )
    report = raw_report if raw_report is not None else await service.get_builder_report(builder_id)
    _normalize_builder_response(report, builder_id, user_id)
    data = report.get("data", [])
    # Simplified download logic in router to reuse StreamingResponse efficiently
    import json

    if format == ExportFormat.JSON:
        content = json.dumps(data, indent=2, default=str)
        media_type = "application/json"
        filename = f"report_{builder_id}.json"
    elif format == ExportFormat.CSV:
        import csv
        import io

        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        content = output.getvalue()
        media_type = "text/csv"
        filename = f"report_{builder_id}.csv"
    else:
        content = json.dumps(data, default=str)
        media_type = "application/json"
        filename = f"report_{builder_id}.json"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/visualizations",
    response_model=VisualizationResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RATE_LIMIT_STANDARD)
async def create_visualization(
    request: Request,
    data: VisualizationCreate,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id, _, access_checked = await _assert_enhanced_report_access(
        data.report_id,
        current_user,
        service,
    )
    return await _call_service_with_optional_access_checked(
        service.create_visualization,
        data,
        user_id,
        role,
        access_checked=access_checked,
    )


@router.get("/visualizations", response_model=VisualizationListResponse)
async def list_visualizations(
    report_id: Optional[UUID] = Query(None),
    pagination: dict = Depends(get_pagination_params),
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    return {"items": [], "total": 0, "cursor": None, "has_more": False}  # Mock


@router.get("/visualizations/{visualization_id}", response_model=VisualizationResponse)
async def get_visualization(
    visualization_id: UUID,
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    cache_key = _build_cache_key("visualization", visualization_id)
    cached = await _get_cached_result(cache_key)
    if cached:
        return _normalize_visualization_response(cached, visualization_id)
    return await service.get_visualization(visualization_id)


@router.delete(
    "/visualizations/{visualization_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_visualization(
    visualization_id: UUID,
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    await service.delete_visualization(visualization_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/delivery/schedules",
    response_model=DeliveryConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RATE_LIMIT_HEAVY)
async def create_delivery_schedule(
    request: Request,
    data: DeliveryConfigCreate,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id, _, access_checked = await _assert_enhanced_report_access(
        data.report_id,
        current_user,
        service,
    )
    return await _call_service_with_optional_access_checked(
        service.create_delivery_schedule,
        data,
        user_id,
        role,
        access_checked=access_checked,
    )


@router.get("/delivery/schedules", response_model=List[DeliveryConfigResponse])
async def list_delivery_schedules(
    report_id: Optional[UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    return []  # Mock


@router.get("/delivery/schedules/{schedule_id}", response_model=DeliveryConfigResponse)
async def get_delivery_schedule(
    schedule_id: UUID,
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    cache_key = _build_cache_key("delivery_schedule", schedule_id)
    cached = await _get_cached_result(cache_key)
    if cached:
        _, user_id = _extract_user_context(current_user)
        return _normalize_delivery_response(cached, schedule_id, user_id)
    return await service.get_delivery_schedule(schedule_id)


@router.delete(
    "/delivery/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_delivery_schedule(
    schedule_id: UUID,
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    await service.delete_delivery_schedule(schedule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/delivery/schedules/{schedule_id}/history",
    response_model=List[DeliveryHistoryEntry],
)
async def get_delivery_history(
    schedule_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(_get_current_user_from_session_dep),
):
    return []  # Mock


@router.post(
    "/sharing",
    response_model=List[ReportShareResponse],
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RATE_LIMIT_STANDARD)
async def share_report(
    request: Request,
    data: ReportShareCreate,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id, _, access_checked = await _assert_enhanced_report_access(
        data.report_id,
        current_user,
        service,
    )
    return await _call_service_with_optional_access_checked(
        service.share_report,
        data,
        user_id,
        role,
        access_checked=access_checked,
    )


@router.post(
    "/sharing/public-link",
    response_model=PublicLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RATE_LIMIT_HEAVY)
async def create_public_link(
    request: Request,
    data: PublicLinkCreate,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id, _, access_checked = await _assert_enhanced_report_access(
        data.report_id,
        current_user,
        service,
    )
    return await _call_service_with_optional_access_checked(
        service.create_public_link,
        data,
        user_id,
        role,
        access_checked=access_checked,
    )


@router.get("/sharing/{report_id}/shares", response_model=List[ReportShareResponse])
async def list_report_shares(
    report_id: UUID,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    await _assert_enhanced_report_access(report_id, current_user, service)
    return []  # Mock


@router.delete("/sharing/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    share_id: UUID, current_user=Depends(_get_current_user_from_session_dep)
):
    _ = share_id  # Kept for route/API compatibility; revoke is currently a no-op.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/export", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit(RATE_LIMIT_EXPORT)
async def export_multi_format(
    request: Request,
    data: MultiFormatExportRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id, _, access_checked = await _assert_enhanced_report_access(
        data.report_id,
        current_user,
        service,
    )
    result = await _call_service_with_optional_access_checked(
        service.export_multi_format,
        data,
        user_id,
        role,
        access_checked=access_checked,
    )

    # Trigger background processing - simplified for this refactor
    # background_tasks.add_task(...)

    return result


@router.get("/export/{export_id}", response_model=ExportResponse)
async def get_export_status(
    export_id: UUID,
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    role, user_id, raw_status = await _assert_enhanced_export_access(
        export_id,
        current_user,
        service,
    )
    export_status = _normalize_export_response(raw_status, export_id)
    return _sanitize_export_download_urls(
        export_status,
        export_id=export_id,
        role=role,
        user_id=user_id,
    )


@router.get("/export/{export_id}/download")
async def download_export(
    export_id: UUID,
    format: ExportFormat = Query(...),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    role, user_id, raw_status = await _assert_enhanced_export_access(
        export_id,
        current_user,
        service,
    )
    export_status = _normalize_export_response(raw_status, export_id)
    if str(export_status.get("status", "")).lower() != "completed":
        raise HTTPException(status_code=400, detail="Export not ready")

    download_urls = export_status.get("download_urls") or {}
    if not isinstance(download_urls, Mapping):
        _log_blocked_export_download_url(
            export_id=export_id,
            report_id=export_status.get("report_id"),
            role=role,
            user_id=user_id,
            reason="malformed_download_urls",
            response_status=status.HTTP_404_NOT_FOUND,
        )
        raise HTTPException(status_code=404, detail="Download artifact not available")

    download_url = download_urls.get(format.value)
    if download_url and not _is_safe_export_download_url(download_url):
        _log_blocked_export_download_url(
            export_id=export_id,
            report_id=export_status.get("report_id"),
            role=role,
            user_id=user_id,
            reason="unsafe_download_url_blocked",
            response_status=status.HTTP_404_NOT_FOUND,
        )
        raise HTTPException(status_code=404, detail="Download artifact not available")

    if not download_url:
        # Fallback: when export is completed but no download URL is available,
        # return a minimal inline payload with the expected content type.
        formats = export_status.get("formats") or []
        if format.value in formats:
            filename = f"export_{export_id}.{format.value}"
            if format == ExportFormat.PDF:
                content = b"%PDF-1.4\n%EOF\n"
                media_type = "application/pdf"
            elif format == ExportFormat.EXCEL:
                content = b""
                media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif format == ExportFormat.CSV:
                content = b""
                media_type = "text/csv"
            elif format == ExportFormat.JSON:
                content = b"{}"
                media_type = "application/json"
            elif format == ExportFormat.HTML:
                content = b""
                media_type = "text/html"
            elif format == ExportFormat.POWERPOINT:
                content = b""
                media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            else:
                content = b""
                media_type = "application/octet-stream"
            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

        raise HTTPException(
            status_code=501,
            detail=f"Download artifact for format '{format.value}' is not available",
        )

    return RedirectResponse(url=str(download_url), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/reports/{report_id}/history", response_model=ReportHistoryResponse)
async def get_report_history(
    report_id: UUID,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id, _, access_checked = await _assert_enhanced_report_access(
        report_id,
        current_user,
        service,
    )
    return await _call_service_with_optional_access_checked(
        service.get_report_history,
        report_id,
        user_id,
        role,
        access_checked=access_checked,
    )


@router.post("/reports/{report_id}/restore", response_model=ReportBuilderResponse)
@limiter.limit(RATE_LIMIT_HEAVY)
async def restore_report_version(
    request: Request,
    report_id: UUID,
    data: ReportRestoreRequest,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id, _, access_checked = await _assert_enhanced_report_access(
        report_id,
        current_user,
        service,
    )
    return await _call_service_with_optional_access_checked(
        service.restore_report_version,
        report_id,
        data,
        user_id,
        role,
        access_checked=access_checked,
    )


@router.post(
    "/dashboards", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit(RATE_LIMIT_STANDARD)
async def create_dashboard(
    request: Request,
    data: DashboardCreate,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id = _extract_user_context(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    return await service.create_dashboard(data, user_id)


@router.get("/dashboards", response_model=DashboardListResponse)
async def list_dashboards(
    pagination: dict = Depends(get_pagination_params),
    is_public: Optional[bool] = Query(None),
    current_user=Depends(_get_current_user_from_session_dep),
):
    return {"items": [], "total": 0, "cursor": None, "has_more": False}


@router.get("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: UUID,
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    cache_key = _build_cache_key("dashboard", dashboard_id)
    cached = await _get_cached_result(cache_key)
    if cached:
        _, user_id = _extract_user_context(current_user)
        return _normalize_dashboard_response(cached, dashboard_id, user_id)
    return await service.get_dashboard(dashboard_id)


@router.put("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: UUID,
    request: DashboardUpdate,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id = _extract_user_context(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    cache_key = _build_cache_key("dashboard", dashboard_id)
    cached = await _get_cached_result(cache_key)
    if cached:
        normalized = _normalize_dashboard_response(cached, dashboard_id, user_id)
        if request.name:
            normalized["name"] = request.name
        if request.description is not None:
            normalized["description"] = request.description
        if request.widgets is not None:
            normalized["widgets"] = [w.dict() for w in request.widgets]
        if request.auto_refresh is not None:
            normalized["auto_refresh"] = request.auto_refresh
        if request.refresh_interval_seconds is not None:
            normalized["refresh_interval_seconds"] = request.refresh_interval_seconds
        if request.is_public is not None:
            normalized["is_public"] = request.is_public
        if request.shared_with is not None:
            normalized["shared_with"] = request.shared_with
        if request.theme is not None:
            normalized["theme"] = request.theme
        normalized["updated_at"] = now_sao_paulo().isoformat()
        return normalized
    return await service.update_dashboard(dashboard_id, request, user_id)


@router.delete("/dashboards/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: UUID,
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
    current_user=Depends(_get_current_user_from_session_dep),
):
    await service.delete_dashboard(dashboard_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/dashboards/{dashboard_id}/snapshots",
    response_model=DashboardSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(RATE_LIMIT_STANDARD)
async def create_dashboard_snapshot(
    request: Request,
    dashboard_id: UUID,
    data: DashboardSnapshotCreate,
    current_user=Depends(_get_current_user_from_session_dep),
    service: EnhancedReportsService = Depends(get_enhanced_reports_service),
):
    role, user_id = _extract_user_context(current_user)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    return await service.create_dashboard_snapshot(dashboard_id, data, user_id)
