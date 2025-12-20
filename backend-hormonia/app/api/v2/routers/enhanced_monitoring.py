"""
Enhanced Monitoring API v2
Comprehensive monitoring endpoints with cursor pagination, Redis caching, and rate limiting.
Delegates logic to MonitoringService.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import PlainTextResponse

from app.database import get_db
from app.models.user import User, UserRole
from app.dependencies import get_request_context, RequestContext
from app.infrastructure.cache.cache_decorators import async_cache
from app.schemas.v2.enhanced_monitoring import (
    MonitoringHealthResponse,
    SystemMetricsResponse,
    SystemInfoResponse,
    APMGlobalStatsResponse,
    APMEndpointListResponse,
    APMEndpointDetailResponse,
    DatabaseOverviewResponse,
    SlowQueryListResponse,
    TableStatsListResponse,
    ResourceStatsResponse,
    ResourceHistoricalResponse,
    BusinessMetricsSummaryResponse,
    PatientMetricsResponse,
    MetricTypeStatsResponse,
    AnomalyListResponse,
    AnomalySummaryResponse,
    DashboardStatusResponse,
    AlertListResponse,
    AlertSeverity,
    PerformanceOverviewResponse,
    GrafanaQueryRequest,
    GrafanaQueryResponse,
    MonitoringConfigResponse,
    MonitoringConfigUpdateRequest,
    StatsResetResponse,
    ServiceActionResponse,
    MetricType,
)
from app.api.v2.dependencies import get_pagination_params, get_field_selection
from app.services.monitoring_service import MonitoringService
from app.monitoring.config import get_monitoring_config
from app.monitoring.manager import get_monitoring_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Cache TTLs
CACHE_TTL_REALTIME = 60
CACHE_TTL_AGGREGATED = 300
CACHE_TTL_HISTORICAL = 900
CACHE_TTL_CONFIG = 1800
CACHE_TTL_STATIC = 3600


def get_monitoring_service() -> MonitoringService:
    return MonitoringService()


async def get_admin_user(
    db=Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> User:
    # TODO: Replace with actual auth integration
    user = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active).first()
    if not user:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for monitoring operations",
        )
    return user


@router.get("/health", response_model=MonitoringHealthResponse)
@async_cache(cache_type="monitoring_health", ttl=CACHE_TTL_REALTIME)
async def get_monitoring_health(
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_monitoring_health()


@router.get("/metrics/overview", response_model=SystemMetricsResponse)
@async_cache(cache_type="monitoring_overview", ttl=CACHE_TTL_AGGREGATED)
async def get_metrics_overview(
    current_user: User = Depends(get_admin_user),
    fields: Optional[List[str]] = Depends(get_field_selection),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_metrics_overview(fields)


@router.get("/system/info", response_model=SystemInfoResponse)
@async_cache(cache_type="system_info", ttl=CACHE_TTL_STATIC)
async def get_system_info(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_system_info()


@router.get("/apm/global", response_model=APMGlobalStatsResponse)
@async_cache(cache_type="apm_global", ttl=CACHE_TTL_AGGREGATED)
async def get_apm_global_stats(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_apm_global_stats()


@router.get("/apm/endpoints", response_model=APMEndpointListResponse)
@async_cache(cache_type="apm_endpoints", ttl=CACHE_TTL_AGGREGATED)
async def get_apm_endpoints_stats(
    current_user: User = Depends(get_admin_user),
    pagination: Dict = Depends(get_pagination_params),
    sort_by: str = Query(
        "total_requests", pattern="^(total_requests|error_rate|avg_latency)$"
    ),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_apm_endpoints_stats(pagination, sort_by)


@router.get(
    "/apm/endpoint/{endpoint_path:path}", response_model=APMEndpointDetailResponse
)
@async_cache(cache_type="apm_endpoint", ttl=CACHE_TTL_AGGREGATED)
async def get_apm_endpoint_stats(
    endpoint_path: str,
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_apm_endpoint_stats(endpoint_path)


@router.get("/database/overview", response_model=DatabaseOverviewResponse)
@async_cache(cache_type="db_overview", ttl=CACHE_TTL_AGGREGATED)
async def get_database_overview(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_database_overview()


@router.get("/database/slow-queries", response_model=SlowQueryListResponse)
@async_cache(cache_type="slow_queries", ttl=CACHE_TTL_AGGREGATED)
async def get_slow_queries(
    current_user: User = Depends(get_admin_user),
    pagination: Dict = Depends(get_pagination_params),
    min_duration_ms: float = Query(100, ge=0),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_slow_queries(pagination, min_duration_ms)


@router.get("/database/tables", response_model=TableStatsListResponse)
@async_cache(cache_type="table_stats", ttl=CACHE_TTL_AGGREGATED)
async def get_table_stats(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_table_stats()


@router.get("/resources/current", response_model=ResourceStatsResponse)
@async_cache(cache_type="resource_current", ttl=CACHE_TTL_REALTIME)
async def get_current_resources(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_current_resources()


@router.get("/resources/historical", response_model=ResourceHistoricalResponse)
@async_cache(cache_type="resource_historical", ttl=CACHE_TTL_HISTORICAL)
async def get_historical_resources(
    minutes: int = Query(60, ge=1, le=1440),
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_historical_resources(minutes)


@router.get("/business/summary", response_model=BusinessMetricsSummaryResponse)
@async_cache(cache_type="business_summary", ttl=CACHE_TTL_AGGREGATED)
async def get_business_metrics_summary(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_business_metrics_summary(hours)


@router.get("/business/patient/{patient_id}", response_model=PatientMetricsResponse)
@async_cache(cache_type="patient_metrics", ttl=CACHE_TTL_AGGREGATED)
async def get_patient_metrics(
    patient_id: str,
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_patient_metrics(patient_id, hours)


@router.get("/business/metric/{metric_type}", response_model=MetricTypeStatsResponse)
@async_cache(cache_type="metric_type", ttl=CACHE_TTL_AGGREGATED)
async def get_business_metric_stats(
    metric_type: MetricType,
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_business_metric_stats(metric_type, hours)


@router.get("/anomalies/recent", response_model=AnomalyListResponse)
@async_cache(cache_type="anomalies_recent", ttl=CACHE_TTL_REALTIME)
async def get_recent_anomalies(
    hours: int = Query(24, ge=1, le=168),
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    metric: Optional[str] = Query(None),
    current_user: User = Depends(get_admin_user),
    pagination: Dict = Depends(get_pagination_params),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_recent_anomalies(hours, severity, metric, pagination)


@router.get("/anomalies/summary", response_model=AnomalySummaryResponse)
@async_cache(cache_type="anomalies_summary", ttl=CACHE_TTL_AGGREGATED)
async def get_anomalies_summary(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_anomalies_summary(hours)


@router.get("/dashboard/status", response_model=DashboardStatusResponse)
@async_cache(cache_type="dashboard_status", ttl=CACHE_TTL_REALTIME)
async def get_dashboard_status(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_dashboard_status()


@router.websocket("/dashboard/stream")
async def dashboard_websocket_endpoint(websocket: WebSocket):
    manager = get_monitoring_manager()
    if not manager.dashboard:
        await websocket.close(code=1003, reason="Dashboard not available")
        return

    client_id = f"dashboard_{int(datetime.now(timezone.utc).timestamp() * 1000000)}"
    try:
        await manager.dashboard.handle_websocket_connection(websocket, client_id)
    except WebSocketDisconnect:
        logger.info(f"Dashboard WebSocket client {client_id} disconnected")
    except Exception as e:
        logger.error(f"Dashboard WebSocket error for client {client_id}: {e}")
        await websocket.close(code=1011, reason="Internal error")


@router.get("/alerts/active", response_model=AlertListResponse)
@async_cache(cache_type="alerts_active", ttl=CACHE_TTL_REALTIME)
async def get_active_alerts(
    current_user: User = Depends(get_admin_user),
    severity: Optional[AlertSeverity] = Query(None),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_active_alerts(severity)


@router.get("/performance/overview", response_model=PerformanceOverviewResponse)
@async_cache(cache_type="performance_overview", ttl=CACHE_TTL_AGGREGATED)
async def get_performance_overview(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.get_performance_overview()


@router.get("/export/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics():
    manager = get_monitoring_manager()
    if not manager.metrics_exporter:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Metrics exporter not available")
    return manager.metrics_exporter.get_prometheus_metrics()


@router.post("/export/grafana/query", response_model=GrafanaQueryResponse)
async def query_grafana_metrics(
    request_data: GrafanaQueryRequest,
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.query_grafana_metrics(request_data)


@router.get("/config", response_model=MonitoringConfigResponse)
@async_cache(cache_type="monitoring_config", ttl=CACHE_TTL_CONFIG)
async def get_monitoring_config_endpoint(current_user: User = Depends(get_admin_user)):
    config = get_monitoring_config()
    return MonitoringConfigResponse(**config.dict())


@router.put("/config", response_model=MonitoringConfigResponse)
async def update_monitoring_config(
    config_update: MonitoringConfigUpdateRequest,
    current_user: User = Depends(get_admin_user),
    db=Depends(get_db),
):
    config = get_monitoring_config()
    # Apply updates
    if config_update.apm_enabled is not None:
        config.apm_enabled = config_update.apm_enabled
    if config_update.db_monitoring_enabled is not None:
        config.db_monitoring_enabled = config_update.db_monitoring_enabled
    if config_update.resource_monitoring_enabled is not None:
        config.resource_monitoring_enabled = config_update.resource_monitoring_enabled

    logger.info(f"Monitoring configuration updated by user {current_user.id}")
    return MonitoringConfigResponse(**config.dict())


@router.post("/actions/reset-stats", response_model=StatsResetResponse)
async def reset_monitoring_stats(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.reset_monitoring_stats(str(current_user.id))


@router.post("/actions/start", response_model=ServiceActionResponse)
async def start_monitoring_services(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.start_monitoring_services(str(current_user.id))


@router.post("/actions/stop", response_model=ServiceActionResponse)
async def stop_monitoring_services(
    current_user: User = Depends(get_admin_user),
    service: MonitoringService = Depends(get_monitoring_service),
):
    return await service.stop_monitoring_services(str(current_user.id))
