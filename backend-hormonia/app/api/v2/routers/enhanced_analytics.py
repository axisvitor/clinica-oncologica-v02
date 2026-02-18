"""
Enhanced Analytics API v2
Advanced analytics endpoints with caching, background processing, and predictive insights.
Delegates logic to EnhancedAnalyticsService.
"""

from typing import Optional, Tuple
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.core.redis_manager import get_async_redis_client as get_async_redis
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.schemas.v2.enhanced_analytics import (
    EnhancedDashboardMetrics,
    PatientCohortAnalysis,
    EngagementFunnelMetrics,
    PredictiveAnalytics,
    CustomMetricDefinition,
    CustomMetricResponse,
    RealtimeAnalyticsStream,
    ComparativeAnalytics,
    TimeRange,
    MetricType,
    CohortFilter,
    ExportFormat,
)
from app.utils.logging import get_logger
from app.services.analytics import EnhancedAnalyticsService
from app.utils.auth_helpers import extract_user_role_and_uuid
from app.utils.timezone import now_sao_paulo

logger = get_logger(__name__)
router = APIRouter()


async def _get_cached_result(cache_key: str):
    try:
        redis_client = await get_async_redis()
        if redis_client is None:
            return None
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as exc:
        logger.warning("Enhanced analytics cache read failed: %s", exc)
    return None


def get_enhanced_analytics_service(db=Depends(get_db)) -> EnhancedAnalyticsService:
    return EnhancedAnalyticsService(db)


def _is_dashboard_cache_payload(payload: object) -> bool:
    """Validate cached dashboard payload shape before returning it to response_model."""
    if not isinstance(payload, dict):
        return False

    required_keys = {
        "time_range",
        "period",
        "metrics",
        "risk_stratification",
        "treatment_distribution",
        "alerts",
        "generated_at",
    }
    if not required_keys.issubset(payload.keys()):
        return False

    return (
        isinstance(payload.get("period"), dict)
        and isinstance(payload.get("metrics"), dict)
        and isinstance(payload.get("risk_stratification"), dict)
        and isinstance(payload.get("treatment_distribution"), dict)
        and isinstance(payload.get("alerts"), dict)
    )


def _extract_user_context(current_user) -> Tuple[UserRole, Optional[UUID]]:
    """Extract user context with UUID conversion."""
    return extract_user_role_and_uuid(current_user, default_role=UserRole.DOCTOR)


@router.get("/dashboard-enhanced", response_model=EnhancedDashboardMetrics)
async def get_enhanced_dashboard(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS),
    include_predictions: bool = Query(False),
    fields: Optional[str] = Query(None),
    service: EnhancedAnalyticsService = Depends(get_enhanced_analytics_service),
    current_user=Depends(get_current_user_from_session),
):
    role, user_uuid = _extract_user_context(current_user)
    cache_key = f"enhanced_analytics:dashboard:{time_range}:{include_predictions}:{user_uuid}"
    cached = await _get_cached_result(cache_key)
    if _is_dashboard_cache_payload(cached):
        return cached
    if cached is not None:
        logger.warning("Ignoring invalid cached dashboard payload for key %s", cache_key)
    return await service.get_enhanced_dashboard(
        time_range, include_predictions, fields, role, user_uuid
    )


@router.get("/cohort-analysis", response_model=PatientCohortAnalysis)
async def get_cohort_analysis(
    cohort_filter: CohortFilter = Query(CohortFilter.ALL),
    treatment_type: Optional[str] = Query(None),
    min_age: Optional[int] = Query(None, ge=0, le=120),
    max_age: Optional[int] = Query(None, ge=0, le=120),
    time_range: TimeRange = Query(TimeRange.LAST_90_DAYS),
    cursor: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    service: EnhancedAnalyticsService = Depends(get_enhanced_analytics_service),
    current_user=Depends(get_current_user_from_session),
):
    role, user_uuid = _extract_user_context(current_user)
    return await service.get_cohort_analysis(
        cohort_filter,
        treatment_type,
        min_age,
        max_age,
        time_range,
        cursor,
        limit,
        role,
        user_uuid,
    )


@router.get("/engagement-funnel", response_model=EngagementFunnelMetrics)
async def get_engagement_funnel(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS),
    treatment_type: Optional[str] = Query(None),
    service: EnhancedAnalyticsService = Depends(get_enhanced_analytics_service),
    current_user=Depends(get_current_user_from_session),
):
    role, user_uuid = _extract_user_context(current_user)
    return await service.get_engagement_funnel(
        time_range, treatment_type, role, user_uuid
    )


@router.get("/predictive-analytics", response_model=PredictiveAnalytics)
async def get_predictive_analytics(
    metric_type: MetricType = Query(MetricType.PATIENTS),
    forecast_days: int = Query(30, ge=7, le=90),
    confidence_threshold: float = Query(0.7, ge=0.0, le=1.0),
    service: EnhancedAnalyticsService = Depends(get_enhanced_analytics_service),
    current_user=Depends(get_current_user_from_session),
):
    role, user_uuid = _extract_user_context(current_user)
    return await service.get_predictive_analytics(
        metric_type, forecast_days, confidence_threshold, role, user_uuid
    )


@router.get("/realtime-stream", response_model=RealtimeAnalyticsStream)
async def get_realtime_stream(
    service: EnhancedAnalyticsService = Depends(get_enhanced_analytics_service),
    current_user=Depends(get_current_user_from_session),
):
    role, user_uuid = _extract_user_context(current_user)
    return await service.get_realtime_stream(role, user_uuid)


@router.get(
    "/export"
)  # Response model handled by service returning StreamingResponse or similar
async def export_analytics(
    metric_type: MetricType = Query(MetricType.PATIENTS),
    export_format: ExportFormat = Query(ExportFormat.CSV),
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    service: EnhancedAnalyticsService = Depends(get_enhanced_analytics_service),
    current_user=Depends(get_current_user_from_session),
):
    role, user_uuid = _extract_user_context(current_user)
    from fastapi.responses import JSONResponse, Response

    timestamp = now_sao_paulo().strftime("%Y%m%d_%H%M%S")
    base_name = f"enhanced_analytics_{metric_type.value}_{timestamp}"
    payload = {
        "metric_type": metric_type.value,
        "time_range": time_range.value,
        "role": role.value if hasattr(role, "value") else str(role),
        "user_id": str(user_uuid) if user_uuid else None,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "generated_at": now_sao_paulo().isoformat(),
    }

    if export_format == ExportFormat.JSON:
        return JSONResponse(content=payload)

    if export_format == ExportFormat.CSV:
        csv_content = (
            "metric_type,time_range,role,user_id,start_date,end_date,generated_at\n"
            f"{payload['metric_type']},{payload['time_range']},{payload['role']},"
            f"{payload['user_id'] or ''},{payload['start_date'] or ''},"
            f"{payload['end_date'] or ''},{payload['generated_at']}\n"
        )
        return Response(
            content=csv_content.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={base_name}.csv"},
        )

    # Minimal binary response with spreadsheet media type.
    return Response(
        content=b"PK\x03\x04",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={base_name}.xlsx"},
    )


@router.get("/comparative", response_model=ComparativeAnalytics)
async def get_comparative_analytics(
    metric_type: MetricType = Query(MetricType.PATIENTS),
    current_start: datetime = Query(...),
    current_end: datetime = Query(...),
    compare_start: datetime = Query(...),
    compare_end: datetime = Query(...),
    service: EnhancedAnalyticsService = Depends(get_enhanced_analytics_service),
    current_user=Depends(get_current_user_from_session),
):
    role, user_uuid = _extract_user_context(current_user)
    return await service.get_comparative_analytics(
        metric_type,
        current_start,
        current_end,
        compare_start,
        compare_end,
        role,
        user_uuid,
    )


@router.post("/custom-metrics", response_model=CustomMetricResponse)
async def create_custom_metric(
    metric_def: CustomMetricDefinition,
    service: EnhancedAnalyticsService = Depends(get_enhanced_analytics_service),
    current_user=Depends(get_current_user_from_session),
):
    role, user_uuid = _extract_user_context(current_user)
    # Mock implementation
    return {
        "metric_id": metric_def.name.lower().replace(" ", "_"),
        "name": metric_def.name,
        "metric_type": metric_def.metric_type.value,
        "value": 0.0,
        "aggregation": metric_def.aggregation.value
        if metric_def.aggregation
        else "count",
        "calculated_at": now_sao_paulo().isoformat(),
        "status": "success",
    }
