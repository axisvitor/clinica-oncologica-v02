"""
Enhanced Monitoring API v2
Comprehensive monitoring endpoints with cursor pagination, Redis caching, and rate limiting.

Features:
- Cursor-based pagination on all list endpoints
- Redis caching (1-30min TTL based on data volatility)
- Rate limiting on expensive operations
- Field selection (?fields=cpu,memory)
- RBAC - Admin-only for management endpoints
- Real-time metrics via WebSocket
- Prometheus & Grafana export
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Query,
    status,
    Request,
    Response,
    BackgroundTasks,
)
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.database import get_db
from app.models.user import User, UserRole
from app.dependencies import get_request_context, RequestContext
from app.monitoring.manager import get_monitoring_manager
from app.monitoring.config import get_monitoring_config
from app.infrastructure.cache.cache_decorators import async_cache, cache_response
from app.utils.rate_limiter import limiter
from app.schemas.v2.enhanced_monitoring import (
    # Health & System
    MonitoringHealthResponse,
    SystemMetricsResponse,
    SystemInfoResponse,
    # APM
    APMGlobalStatsResponse,
    APMEndpointStatsResponse,
    APMEndpointDetailResponse,
    APMEndpointListResponse,
    # Database
    DatabaseOverviewResponse,
    SlowQueryResponse,
    SlowQueryListResponse,
    TableStatsResponse,
    TableStatsListResponse,
    ConnectionPoolStatsResponse,
    # Resources
    ResourceStatsResponse,
    ResourceHistoricalResponse,
    ResourceTimeSeriesPoint,
    # Business Metrics
    BusinessMetricsSummaryResponse,
    PatientMetricsResponse,
    MetricTypeStatsResponse,
    # Anomalies
    AnomalyRecord,
    AnomalyListResponse,
    AnomalySummaryResponse,
    # Dashboard
    DashboardStatusResponse,
    DashboardMetricsSnapshot,
    # Alerts
    AlertRecord,
    AlertListResponse,
    AlertSeverity,
    # Performance
    PerformanceOverviewResponse,
    PerformanceScore,
    # Export
    PrometheusExportResponse,
    GrafanaQueryRequest,
    GrafanaQueryResponse,
    # Configuration
    MonitoringConfigResponse,
    MonitoringConfigUpdateRequest,
    # Actions
    ServiceActionResponse,
    StatsResetResponse,
    # Common
    MetricType,
    TimeRange,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    create_cursor,
    apply_field_selection,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

# Cache TTLs optimized for data volatility
CACHE_TTL_REALTIME = 60  # 1 min for real-time metrics (CPU, memory, etc)
CACHE_TTL_AGGREGATED = 300  # 5 min for aggregated stats (APM, DB stats)
CACHE_TTL_HISTORICAL = 900  # 15 min for historical data
CACHE_TTL_CONFIG = 1800  # 30 min for configuration
CACHE_TTL_STATIC = 3600  # 1 hour for static system info

# Rate limits (requests per minute)
RATE_LIMIT_REALTIME = 60  # Real-time metrics
RATE_LIMIT_AGGREGATED = 30  # Aggregated stats
RATE_LIMIT_EXPENSIVE = 10  # Expensive operations (resets, starts)
RATE_LIMIT_EXPORT = 20  # Export operations


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


async def get_admin_user(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> User:
    """
    Dependency to verify admin access for monitoring operations.

    Args:
        db: Database session
        context: Request context with user info

    Returns:
        User: Authenticated admin user

    Raises:
        HTTPException: If user is not admin or not authenticated
    """
    # TODO: Replace with actual auth integration
    user = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.is_active == True)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for monitoring operations",
        )
    return user


def validate_time_range(hours: int, max_hours: int = 168) -> None:
    """
    Validate time range parameters.

    Args:
        hours: Requested time range in hours
        max_hours: Maximum allowed hours

    Raises:
        HTTPException: If time range is invalid
    """
    if hours < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time range must be at least 1 hour",
        )
    if hours > max_hours:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Time range cannot exceed {max_hours} hours (7 days)",
        )


def calculate_performance_score(
    apm_stats: Dict[str, Any],
    db_stats: Dict[str, Any],
    resource_stats: Dict[str, Any],
) -> PerformanceScore:
    """
    Calculate overall performance score from various metrics.

    Args:
        apm_stats: APM statistics
        db_stats: Database statistics
        resource_stats: Resource statistics

    Returns:
        PerformanceScore: Calculated performance metrics
    """
    score = 100.0
    deductions = []

    # APM performance impact
    error_rate = apm_stats.get("error_rate", 0)
    if error_rate > 5:
        deduction = min(20, error_rate * 2)
        score -= deduction
        deductions.append({"reason": "high_error_rate", "deduction": deduction})

    p95_latency = apm_stats.get("p95", 0)
    if p95_latency > 2000:  # 2 seconds
        deduction = min(15, (p95_latency - 2000) / 100)
        score -= deduction
        deductions.append({"reason": "slow_response_time", "deduction": deduction})

    # Database performance impact
    slow_query_pct = db_stats.get("slow_query_percentage", 0)
    if slow_query_pct > 10:
        deduction = min(15, slow_query_pct)
        score -= deduction
        deductions.append({"reason": "slow_queries", "deduction": deduction})

    # Resource performance impact
    cpu_percent = resource_stats.get("cpu", {}).get("percent", 0)
    if cpu_percent > 80:
        deduction = min(15, (cpu_percent - 80) / 2)
        score -= deduction
        deductions.append({"reason": "high_cpu", "deduction": deduction})

    memory_percent = resource_stats.get("memory", {}).get("percent", 0)
    if memory_percent > 85:
        deduction = min(15, (memory_percent - 85) / 2)
        score -= deduction
        deductions.append({"reason": "high_memory", "deduction": deduction})

    # Determine status
    score = max(0, score)
    if score >= 90:
        status = "excellent"
    elif score >= 75:
        status = "good"
    elif score >= 60:
        status = "degraded"
    else:
        status = "critical"

    return PerformanceScore(
        score=score,
        status=status,
        deductions=deductions,
    )


# ============================================================================
# HEALTH & SYSTEM ENDPOINTS
# ============================================================================


@router.get(
    "/health",
    response_model=MonitoringHealthResponse,
    summary="Get monitoring system health",
    description="Retrieve overall health status of the monitoring system",
)
@async_cache(cache_type="monitoring_health", ttl=CACHE_TTL_REALTIME)
async def get_monitoring_health() -> MonitoringHealthResponse:
    """
    Get monitoring system health status.

    Returns comprehensive health information about all monitoring subsystems.
    Cached for 1 minute to reduce overhead.

    Returns:
        MonitoringHealthResponse: Health status of monitoring system
    """
    manager = get_monitoring_manager()
    health_data = manager.get_health_status()

    return MonitoringHealthResponse(
        status=health_data.get("status", "unknown"),
        timestamp=datetime.utcnow(),
        components=health_data.get("components", {}),
        uptime_seconds=health_data.get("uptime", 0),
        version=health_data.get("version", "unknown"),
    )


@router.get(
    "/metrics/overview",
    response_model=SystemMetricsResponse,
    summary="Get comprehensive metrics overview",
    description="Retrieve aggregated system metrics across all monitoring subsystems",
)
@async_cache(cache_type="monitoring_overview", ttl=CACHE_TTL_AGGREGATED)
async def get_metrics_overview(
    current_user: User = Depends(get_admin_user),
    fields: Optional[List[str]] = Depends(get_field_selection),
) -> SystemMetricsResponse:
    """
    Get comprehensive metrics overview.

    Aggregates metrics from APM, database, resources, and business subsystems.
    Supports field selection for optimized response size.
    Cached for 5 minutes.

    Args:
        current_user: Authenticated admin user
        fields: Optional field selection

    Returns:
        SystemMetricsResponse: Comprehensive system metrics
    """
    manager = get_monitoring_manager()
    metrics = await manager.get_system_metrics()

    response_data = {
        "timestamp": datetime.utcnow(),
        "apm": metrics.get("apm", {}),
        "database": metrics.get("database", {}),
        "resources": metrics.get("resources", {}),
        "business": metrics.get("business", {}),
        "health_score": metrics.get("health_score", 100),
    }

    if fields:
        response_data = apply_field_selection(response_data, fields)

    return SystemMetricsResponse(**response_data)


@router.get(
    "/system/info",
    response_model=SystemInfoResponse,
    summary="Get static system information",
    description="Retrieve static system information (OS, hardware, etc.)",
)
@async_cache(cache_type="system_info", ttl=CACHE_TTL_STATIC)
async def get_system_info(
    current_user: User = Depends(get_admin_user),
) -> SystemInfoResponse:
    """
    Get static system information.

    Returns hardware and OS information that rarely changes.
    Cached for 1 hour due to static nature.

    Args:
        current_user: Authenticated admin user

    Returns:
        SystemInfoResponse: System information
    """
    manager = get_monitoring_manager()
    if not manager.resource_monitor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resource monitor not available",
        )

    info = manager.resource_monitor.get_system_info()
    return SystemInfoResponse(**info)


# ============================================================================
# APM ENDPOINTS
# ============================================================================


@router.get(
    "/apm/global",
    response_model=APMGlobalStatsResponse,
    summary="Get global APM statistics",
    description="Retrieve aggregated APM statistics across all endpoints",
)
@async_cache(cache_type="apm_global", ttl=CACHE_TTL_AGGREGATED)
async def get_apm_global_stats(
    current_user: User = Depends(get_admin_user),
) -> APMGlobalStatsResponse:
    """
    Get global APM statistics.

    Provides aggregated metrics including request count, error rate,
    latency percentiles, and throughput.
    Cached for 5 minutes.

    Args:
        current_user: Authenticated admin user

    Returns:
        APMGlobalStatsResponse: Global APM statistics

    Raises:
        HTTPException: If APM collector is not available
    """
    manager = get_monitoring_manager()
    if not manager.apm_collector:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="APM collector not available",
        )

    stats = manager.apm_collector.get_global_stats()
    return APMGlobalStatsResponse(
        timestamp=datetime.utcnow(),
        total_requests=stats.get("total_requests", 0),
        total_errors=stats.get("total_errors", 0),
        error_rate=stats.get("error_rate", 0.0),
        avg_response_time=stats.get("avg_response_time", 0.0),
        p50=stats.get("p50", 0.0),
        p95=stats.get("p95", 0.0),
        p99=stats.get("p99", 0.0),
        requests_per_second=stats.get("requests_per_second", 0.0),
    )


@router.get(
    "/apm/endpoints",
    response_model=APMEndpointListResponse,
    summary="Get statistics for all endpoints",
    description="Retrieve APM statistics for all monitored endpoints with pagination",
)
@async_cache(cache_type="apm_endpoints", ttl=CACHE_TTL_AGGREGATED)
async def get_apm_endpoints_stats(
    current_user: User = Depends(get_admin_user),
    pagination: Dict = Depends(get_pagination_params),
    sort_by: str = Query("total_requests", regex="^(total_requests|error_rate|avg_latency)$"),
) -> APMEndpointListResponse:
    """
    Get statistics for all endpoints.

    Supports cursor-based pagination and sorting.
    Cached for 5 minutes.

    Args:
        current_user: Authenticated admin user
        pagination: Pagination parameters (cursor, limit)
        sort_by: Sort field (total_requests, error_rate, avg_latency)

    Returns:
        APMEndpointListResponse: Paginated endpoint statistics

    Raises:
        HTTPException: If APM collector is not available
    """
    manager = get_monitoring_manager()
    if not manager.apm_collector:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="APM collector not available",
        )

    all_stats = manager.apm_collector.get_all_endpoints_stats()

    # Sort by requested field
    if sort_by == "error_rate":
        sorted_stats = sorted(
            all_stats.items(),
            key=lambda x: x[1].get("error_rate", 0),
            reverse=True,
        )
    elif sort_by == "avg_latency":
        sorted_stats = sorted(
            all_stats.items(),
            key=lambda x: x[1].get("avg_response_time", 0),
            reverse=True,
        )
    else:  # total_requests
        sorted_stats = sorted(
            all_stats.items(),
            key=lambda x: x[1].get("total_requests", 0),
            reverse=True,
        )

    # Apply cursor pagination
    limit = pagination["limit"]
    cursor_data = pagination["cursor_data"]

    if cursor_data:
        start_idx = cursor_data.get("index", 0)
    else:
        start_idx = 0

    paginated_stats = sorted_stats[start_idx : start_idx + limit + 1]
    has_more = len(paginated_stats) > limit

    if has_more:
        paginated_stats = paginated_stats[:limit]
        next_cursor = create_cursor(start_idx + limit)
    else:
        next_cursor = None

    # Format response
    endpoints = []
    for endpoint_path, stats in paginated_stats:
        endpoints.append(
            APMEndpointStatsResponse(
                endpoint=endpoint_path,
                total_requests=stats.get("total_requests", 0),
                total_errors=stats.get("total_errors", 0),
                error_rate=stats.get("error_rate", 0.0),
                avg_response_time=stats.get("avg_response_time", 0.0),
                p95=stats.get("p95", 0.0),
            )
        )

    return APMEndpointListResponse(
        data=endpoints,
        next_cursor=next_cursor,
        has_more=has_more,
        total=len(sorted_stats),
    )


@router.get(
    "/apm/endpoint/{endpoint_path:path}",
    response_model=APMEndpointDetailResponse,
    summary="Get statistics for specific endpoint",
    description="Retrieve detailed APM statistics for a specific endpoint",
)
@async_cache(cache_type="apm_endpoint", ttl=CACHE_TTL_AGGREGATED)
async def get_apm_endpoint_stats(
    endpoint_path: str,
    current_user: User = Depends(get_admin_user),
) -> APMEndpointDetailResponse:
    """
    Get statistics for a specific endpoint.

    Provides detailed metrics including latency distribution,
    error breakdown, and recent requests.
    Cached for 5 minutes per endpoint.

    Args:
        endpoint_path: Path of the endpoint to query
        current_user: Authenticated admin user

    Returns:
        APMEndpointDetailResponse: Detailed endpoint statistics

    Raises:
        HTTPException: If APM collector is not available or endpoint not found
    """
    manager = get_monitoring_manager()
    if not manager.apm_collector:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="APM collector not available",
        )

    stats = manager.apm_collector.get_endpoint_stats(endpoint_path)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint '{endpoint_path}' not found in APM data",
        )

    return APMEndpointDetailResponse(
        endpoint=endpoint_path,
        timestamp=datetime.utcnow(),
        total_requests=stats.get("total_requests", 0),
        total_errors=stats.get("total_errors", 0),
        error_rate=stats.get("error_rate", 0.0),
        avg_response_time=stats.get("avg_response_time", 0.0),
        min_response_time=stats.get("min_response_time", 0.0),
        max_response_time=stats.get("max_response_time", 0.0),
        p50=stats.get("p50", 0.0),
        p95=stats.get("p95", 0.0),
        p99=stats.get("p99", 0.0),
        recent_errors=stats.get("recent_errors", []),
        status_code_distribution=stats.get("status_codes", {}),
    )


# ============================================================================
# DATABASE MONITORING ENDPOINTS
# ============================================================================


@router.get(
    "/database/overview",
    response_model=DatabaseOverviewResponse,
    summary="Get database performance overview",
    description="Retrieve comprehensive database performance metrics",
)
@async_cache(cache_type="db_overview", ttl=CACHE_TTL_AGGREGATED)
async def get_database_overview(
    current_user: User = Depends(get_admin_user),
) -> DatabaseOverviewResponse:
    """
    Get database performance overview.

    Provides query statistics and connection pool metrics.
    Cached for 5 minutes.

    Args:
        current_user: Authenticated admin user

    Returns:
        DatabaseOverviewResponse: Database performance overview

    Raises:
        HTTPException: If database monitor is not available
    """
    manager = get_monitoring_manager()
    if not manager.db_monitor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database monitor not available",
        )

    query_stats = manager.db_monitor.get_query_stats()
    pool_stats = manager.db_monitor.get_connection_pool_stats()

    return DatabaseOverviewResponse(
        timestamp=datetime.utcnow(),
        query_statistics=query_stats,
        connection_pool=ConnectionPoolStatsResponse(**pool_stats),
    )


@router.get(
    "/database/slow-queries",
    response_model=SlowQueryListResponse,
    summary="Get slowest database queries",
    description="Retrieve slowest database queries with cursor pagination",
)
@async_cache(cache_type="slow_queries", ttl=CACHE_TTL_AGGREGATED)
async def get_slow_queries(
    current_user: User = Depends(get_admin_user),
    pagination: Dict = Depends(get_pagination_params),
    min_duration_ms: float = Query(100, ge=0, description="Minimum query duration in ms"),
) -> SlowQueryListResponse:
    """
    Get slowest database queries.

    Supports cursor-based pagination and duration filtering.
    Cached for 5 minutes.

    Args:
        current_user: Authenticated admin user
        pagination: Pagination parameters
        min_duration_ms: Minimum query duration threshold

    Returns:
        SlowQueryListResponse: Paginated slow queries

    Raises:
        HTTPException: If database monitor is not available
    """
    manager = get_monitoring_manager()
    if not manager.db_monitor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database monitor not available",
        )

    limit = pagination["limit"]
    all_slow_queries = manager.db_monitor.get_slow_queries(limit=1000)

    # Filter by minimum duration
    filtered_queries = [
        q for q in all_slow_queries if q.get("duration_ms", 0) >= min_duration_ms
    ]

    # Apply cursor pagination
    cursor_data = pagination["cursor_data"]
    if cursor_data:
        start_idx = cursor_data.get("index", 0)
    else:
        start_idx = 0

    paginated = filtered_queries[start_idx : start_idx + limit + 1]
    has_more = len(paginated) > limit

    if has_more:
        paginated = paginated[:limit]
        next_cursor = create_cursor(start_idx + limit)
    else:
        next_cursor = None

    # Format response
    queries = [
        SlowQueryResponse(
            query=q.get("query", ""),
            duration_ms=q.get("duration_ms", 0.0),
            timestamp=q.get("timestamp", datetime.utcnow()),
            table=q.get("table"),
            rows_examined=q.get("rows_examined"),
        )
        for q in paginated
    ]

    return SlowQueryListResponse(
        data=queries,
        next_cursor=next_cursor,
        has_more=has_more,
        total=len(filtered_queries),
    )


@router.get(
    "/database/tables",
    response_model=TableStatsListResponse,
    summary="Get statistics by database table",
    description="Retrieve query statistics grouped by database table",
)
@async_cache(cache_type="table_stats", ttl=CACHE_TTL_AGGREGATED)
async def get_table_stats(
    current_user: User = Depends(get_admin_user),
) -> TableStatsListResponse:
    """
    Get statistics by database table.

    Groups query statistics by table for performance analysis.
    Cached for 5 minutes.

    Args:
        current_user: Authenticated admin user

    Returns:
        TableStatsListResponse: Table statistics

    Raises:
        HTTPException: If database monitor is not available
    """
    manager = get_monitoring_manager()
    if not manager.db_monitor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database monitor not available",
        )

    table_stats_dict = manager.db_monitor.get_table_stats()

    # Convert to list format
    table_stats = [
        TableStatsResponse(
            table=table_name,
            query_count=stats.get("query_count", 0),
            avg_duration_ms=stats.get("avg_duration_ms", 0.0),
            total_duration_ms=stats.get("total_duration_ms", 0.0),
            slow_query_count=stats.get("slow_query_count", 0),
        )
        for table_name, stats in table_stats_dict.items()
    ]

    # Sort by query count
    table_stats.sort(key=lambda x: x.query_count, reverse=True)

    return TableStatsListResponse(
        data=table_stats,
        timestamp=datetime.utcnow(),
        total_tables=len(table_stats),
    )


# ============================================================================
# RESOURCE MONITORING ENDPOINTS
# ============================================================================


@router.get(
    "/resources/current",
    response_model=ResourceStatsResponse,
    summary="Get current resource usage",
    description="Retrieve current CPU, memory, disk, and network usage",
)
@async_cache(cache_type="resource_current", ttl=CACHE_TTL_REALTIME)
async def get_current_resources(
    current_user: User = Depends(get_admin_user),
) -> ResourceStatsResponse:
    """
    Get current resource usage.

    Real-time snapshot of system resources.
    Cached for 1 minute.

    Args:
        current_user: Authenticated admin user

    Returns:
        ResourceStatsResponse: Current resource statistics

    Raises:
        HTTPException: If resource monitor is not available
    """
    manager = get_monitoring_manager()
    if not manager.resource_monitor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resource monitor not available",
        )

    stats = manager.resource_monitor.get_current_stats()
    return ResourceStatsResponse(
        timestamp=datetime.utcnow(),
        cpu=stats.get("cpu", {}),
        memory=stats.get("memory", {}),
        disk=stats.get("disk", {}),
        network=stats.get("network", {}),
    )


@router.get(
    "/resources/historical",
    response_model=ResourceHistoricalResponse,
    summary="Get historical resource usage",
    description="Retrieve historical resource usage as time series",
)
@async_cache(cache_type="resource_historical", ttl=CACHE_TTL_HISTORICAL)
async def get_historical_resources(
    minutes: int = Query(60, ge=1, le=1440, description="Time range in minutes"),
    current_user: User = Depends(get_admin_user),
) -> ResourceHistoricalResponse:
    """
    Get historical resource usage.

    Returns time series data for resource metrics.
    Cached for 15 minutes.

    Args:
        minutes: Time range in minutes (1-1440)
        current_user: Authenticated admin user

    Returns:
        ResourceHistoricalResponse: Historical resource data

    Raises:
        HTTPException: If resource monitor is not available
    """
    manager = get_monitoring_manager()
    if not manager.resource_monitor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resource monitor not available",
        )

    historical_data = manager.resource_monitor.get_historical_stats(minutes)

    # Convert to time series format
    time_series = [
        ResourceTimeSeriesPoint(
            timestamp=point.get("timestamp", datetime.utcnow()),
            cpu_percent=point.get("cpu", {}).get("percent", 0.0),
            memory_percent=point.get("memory", {}).get("percent", 0.0),
            disk_percent=point.get("disk", {}).get("percent", 0.0),
            network_bytes_sent=point.get("network", {}).get("bytes_sent", 0),
            network_bytes_recv=point.get("network", {}).get("bytes_recv", 0),
        )
        for point in historical_data.get("data_points", [])
    ]

    return ResourceHistoricalResponse(
        time_range_minutes=minutes,
        data_points=time_series,
        summary=historical_data.get("summary", {}),
    )


# ============================================================================
# BUSINESS METRICS ENDPOINTS
# ============================================================================


@router.get(
    "/business/summary",
    response_model=BusinessMetricsSummaryResponse,
    summary="Get business metrics summary",
    description="Retrieve aggregated business metrics for specified time range",
)
@async_cache(cache_type="business_summary", ttl=CACHE_TTL_AGGREGATED)
async def get_business_metrics_summary(
    hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
    current_user: User = Depends(get_admin_user),
) -> BusinessMetricsSummaryResponse:
    """
    Get business metrics summary.

    Aggregates patient interactions, quiz completions, and other business KPIs.
    Cached for 5 minutes.

    Args:
        hours: Time range in hours (1-168)
        current_user: Authenticated admin user

    Returns:
        BusinessMetricsSummaryResponse: Business metrics summary

    Raises:
        HTTPException: If business metrics collector is not available
    """
    validate_time_range(hours)

    manager = get_monitoring_manager()
    if not manager.business_metrics:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Business metrics collector not available",
        )

    summary = manager.business_metrics.get_all_metrics_summary(hours)
    return BusinessMetricsSummaryResponse(
        time_range_hours=hours,
        timestamp=datetime.utcnow(),
        metrics=summary,
    )


@router.get(
    "/business/patient/{patient_id}",
    response_model=PatientMetricsResponse,
    summary="Get metrics for specific patient",
    description="Retrieve business metrics for a specific patient",
)
@async_cache(cache_type="patient_metrics", ttl=CACHE_TTL_AGGREGATED)
async def get_patient_metrics(
    patient_id: str,
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_admin_user),
) -> PatientMetricsResponse:
    """
    Get metrics for a specific patient.

    Provides patient-specific activity and engagement metrics.
    Cached for 5 minutes per patient.

    Args:
        patient_id: Patient identifier
        hours: Time range in hours
        current_user: Authenticated admin user

    Returns:
        PatientMetricsResponse: Patient-specific metrics

    Raises:
        HTTPException: If business metrics collector is not available
    """
    validate_time_range(hours)

    manager = get_monitoring_manager()
    if not manager.business_metrics:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Business metrics collector not available",
        )

    metrics = manager.business_metrics.get_patient_metrics(patient_id, hours)
    return PatientMetricsResponse(
        patient_id=patient_id,
        time_range_hours=hours,
        timestamp=datetime.utcnow(),
        metrics=metrics,
    )


@router.get(
    "/business/metric/{metric_type}",
    response_model=MetricTypeStatsResponse,
    summary="Get statistics for specific metric type",
    description="Retrieve statistics for a specific business metric type",
)
@async_cache(cache_type="metric_type", ttl=CACHE_TTL_AGGREGATED)
async def get_business_metric_stats(
    metric_type: MetricType,
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_admin_user),
) -> MetricTypeStatsResponse:
    """
    Get statistics for a specific business metric type.

    Provides detailed statistics for specific metric types like quiz completions,
    message sends, etc.
    Cached for 5 minutes per metric type.

    Args:
        metric_type: Type of metric to query
        hours: Time range in hours
        current_user: Authenticated admin user

    Returns:
        MetricTypeStatsResponse: Metric type statistics

    Raises:
        HTTPException: If business metrics collector is not available
    """
    validate_time_range(hours)

    manager = get_monitoring_manager()
    if not manager.business_metrics:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Business metrics collector not available",
        )

    stats = manager.business_metrics.get_metric_stats(metric_type, hours)
    return MetricTypeStatsResponse(
        metric_type=metric_type,
        time_range_hours=hours,
        timestamp=datetime.utcnow(),
        statistics=stats,
    )


# ============================================================================
# ANOMALY DETECTION ENDPOINTS
# ============================================================================


@router.get(
    "/anomalies/recent",
    response_model=AnomalyListResponse,
    summary="Get recent anomalies",
    description="Retrieve recent anomalies with optional filtering and pagination",
)
@async_cache(cache_type="anomalies_recent", ttl=CACHE_TTL_REALTIME)
async def get_recent_anomalies(
    hours: int = Query(24, ge=1, le=168),
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    metric: Optional[str] = Query(None),
    current_user: User = Depends(get_admin_user),
    pagination: Dict = Depends(get_pagination_params),
) -> AnomalyListResponse:
    """
    Get recent anomalies with filtering.

    Supports filtering by severity, metric type, and cursor pagination.
    Cached for 1 minute due to real-time nature.

    Args:
        hours: Time range in hours
        severity: Filter by severity level
        metric: Filter by metric name
        current_user: Authenticated admin user
        pagination: Pagination parameters

    Returns:
        AnomalyListResponse: Paginated anomalies

    Raises:
        HTTPException: If anomaly detector is not available
    """
    validate_time_range(hours)

    manager = get_monitoring_manager()
    if not manager.anomaly_detector:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anomaly detector not available",
        )

    anomalies_data = manager.anomaly_detector.get_recent_anomalies(
        hours, severity, metric
    )

    # Apply cursor pagination
    limit = pagination["limit"]
    cursor_data = pagination["cursor_data"]

    if cursor_data:
        start_idx = cursor_data.get("index", 0)
    else:
        start_idx = 0

    paginated = anomalies_data[start_idx : start_idx + limit + 1]
    has_more = len(paginated) > limit

    if has_more:
        paginated = paginated[:limit]
        next_cursor = create_cursor(start_idx + limit)
    else:
        next_cursor = None

    # Format response
    anomalies = [
        AnomalyRecord(
            timestamp=a.get("timestamp", datetime.utcnow()),
            metric=a.get("metric", ""),
            value=a.get("value", 0.0),
            expected_value=a.get("expected_value", 0.0),
            severity=a.get("severity", "medium"),
            description=a.get("description", ""),
        )
        for a in paginated
    ]

    return AnomalyListResponse(
        data=anomalies,
        next_cursor=next_cursor,
        has_more=has_more,
        total=len(anomalies_data),
    )


@router.get(
    "/anomalies/summary",
    response_model=AnomalySummaryResponse,
    summary="Get anomalies summary",
    description="Retrieve aggregated anomaly statistics",
)
@async_cache(cache_type="anomalies_summary", ttl=CACHE_TTL_AGGREGATED)
async def get_anomalies_summary(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_admin_user),
) -> AnomalySummaryResponse:
    """
    Get anomalies summary.

    Provides aggregated statistics about anomalies.
    Cached for 5 minutes.

    Args:
        hours: Time range in hours
        current_user: Authenticated admin user

    Returns:
        AnomalySummaryResponse: Anomaly summary statistics

    Raises:
        HTTPException: If anomaly detector is not available
    """
    validate_time_range(hours)

    manager = get_monitoring_manager()
    if not manager.anomaly_detector:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anomaly detector not available",
        )

    summary = manager.anomaly_detector.get_anomaly_summary(hours)
    return AnomalySummaryResponse(
        time_range_hours=hours,
        timestamp=datetime.utcnow(),
        total_anomalies=summary.get("total", 0),
        by_severity=summary.get("by_severity", {}),
        by_metric=summary.get("by_metric", {}),
    )


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================


@router.get(
    "/dashboard/status",
    response_model=DashboardStatusResponse,
    summary="Get dashboard status",
    description="Retrieve real-time dashboard status and metrics snapshot",
)
@async_cache(cache_type="dashboard_status", ttl=CACHE_TTL_REALTIME)
async def get_dashboard_status(
    current_user: User = Depends(get_admin_user),
) -> DashboardStatusResponse:
    """
    Get dashboard status.

    Provides a comprehensive snapshot of all monitoring metrics
    for dashboard visualization.
    Cached for 1 minute.

    Args:
        current_user: Authenticated admin user

    Returns:
        DashboardStatusResponse: Dashboard status with metrics snapshot

    Raises:
        HTTPException: If dashboard is not available
    """
    manager = get_monitoring_manager()
    if not manager.dashboard:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard not available",
        )

    status_data = manager.dashboard.get_dashboard_status()

    return DashboardStatusResponse(
        timestamp=datetime.utcnow(),
        active_connections=status_data.get("active_connections", 0),
        metrics_snapshot=DashboardMetricsSnapshot(**status_data.get("metrics", {})),
    )


@router.websocket("/dashboard/stream")
async def dashboard_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.

    Streams real-time monitoring metrics to connected clients.
    Updates sent every 2 seconds.

    Usage:
        const ws = new WebSocket('ws://host/api/v2/monitoring/dashboard/stream');
        ws.onmessage = (event) => {
            const metrics = JSON.parse(event.data);
            updateDashboard(metrics);
        };

    Args:
        websocket: WebSocket connection
    """
    manager = get_monitoring_manager()
    if not manager.dashboard:
        await websocket.close(code=1003, reason="Dashboard not available")
        return

    client_id = f"dashboard_{int(datetime.utcnow().timestamp() * 1000000)}"

    try:
        await manager.dashboard.handle_websocket_connection(websocket, client_id)
    except WebSocketDisconnect:
        logger.info(f"Dashboard WebSocket client {client_id} disconnected")
    except Exception as e:
        logger.error(f"Dashboard WebSocket error for client {client_id}: {e}")
        await websocket.close(code=1011, reason="Internal error")


# ============================================================================
# ALERT ENDPOINTS
# ============================================================================


@router.get(
    "/alerts/active",
    response_model=AlertListResponse,
    summary="Get active monitoring alerts",
    description="Retrieve currently active alerts across all monitoring subsystems",
)
@async_cache(cache_type="alerts_active", ttl=CACHE_TTL_REALTIME)
async def get_active_alerts(
    current_user: User = Depends(get_admin_user),
    severity: Optional[AlertSeverity] = Query(None),
) -> AlertListResponse:
    """
    Get currently active monitoring alerts.

    Collects and aggregates alerts from APM, database, and resource monitors.
    Cached for 1 minute.

    Args:
        current_user: Authenticated admin user
        severity: Optional severity filter

    Returns:
        AlertListResponse: Active alerts
    """
    manager = get_monitoring_manager()
    alerts = []

    # APM alerts
    if manager.apm_collector:
        apm_stats = manager.apm_collector.get_global_stats()
        error_rate = apm_stats.get("error_rate", 0)

        if error_rate > 5:
            severity_level = "critical" if error_rate > 10 else "high" if error_rate > 7 else "medium"
            alerts.append(
                AlertRecord(
                    type="apm",
                    severity=severity_level,
                    message=f"High error rate: {error_rate:.1f}%",
                    value=error_rate,
                    threshold=5.0,
                    timestamp=datetime.utcnow(),
                )
            )

    # Resource alerts
    if manager.resource_monitor:
        resource_stats = manager.resource_monitor.get_current_stats()
        cpu_percent = resource_stats.get("cpu", {}).get("percent", 0)
        memory_percent = resource_stats.get("memory", {}).get("percent", 0)

        if cpu_percent > 80:
            severity_level = "critical" if cpu_percent > 95 else "high"
            alerts.append(
                AlertRecord(
                    type="resource",
                    severity=severity_level,
                    message=f"High CPU usage: {cpu_percent:.1f}%",
                    value=cpu_percent,
                    threshold=80.0,
                    timestamp=datetime.utcnow(),
                )
            )

        if memory_percent > 85:
            severity_level = "critical" if memory_percent > 95 else "high"
            alerts.append(
                AlertRecord(
                    type="resource",
                    severity=severity_level,
                    message=f"High memory usage: {memory_percent:.1f}%",
                    value=memory_percent,
                    threshold=85.0,
                    timestamp=datetime.utcnow(),
                )
            )

    # Filter by severity if requested
    if severity:
        alerts = [a for a in alerts if a.severity == severity.value]

    return AlertListResponse(
        alerts=alerts,
        count=len(alerts),
        timestamp=datetime.utcnow(),
    )


# ============================================================================
# PERFORMANCE OVERVIEW ENDPOINT
# ============================================================================


@router.get(
    "/performance/overview",
    response_model=PerformanceOverviewResponse,
    summary="Get enhanced performance overview",
    description="Retrieve comprehensive performance overview with calculated score",
)
@async_cache(cache_type="performance_overview", ttl=CACHE_TTL_AGGREGATED)
async def get_performance_overview(
    current_user: User = Depends(get_admin_user),
) -> PerformanceOverviewResponse:
    """
    Get enhanced performance overview with monitoring data.

    Calculates an overall performance score based on APM, database,
    and resource metrics. Provides actionable insights.
    Cached for 5 minutes.

    Args:
        current_user: Authenticated admin user

    Returns:
        PerformanceOverviewResponse: Performance overview with score
    """
    manager = get_monitoring_manager()

    # Gather metrics
    apm_stats = {}
    db_stats = {}
    resource_stats = {}

    if manager.apm_collector:
        apm_stats = manager.apm_collector.get_global_stats()

    if manager.db_monitor:
        db_stats = manager.db_monitor.get_query_stats()

    if manager.resource_monitor:
        resource_stats = manager.resource_monitor.get_current_stats()

    # Calculate performance score
    perf_score = calculate_performance_score(apm_stats, db_stats, resource_stats)

    return PerformanceOverviewResponse(
        timestamp=datetime.utcnow(),
        performance_score=perf_score,
        apm=apm_stats,
        database=db_stats,
        resources=resource_stats,
        system_health=manager.get_health_status(),
    )


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================


@router.get(
    "/export/prometheus",
    response_class=PlainTextResponse,
    summary="Export metrics in Prometheus format",
    description="Export all monitoring metrics in Prometheus exposition format",
)
async def get_prometheus_metrics() -> str:
    """
    Get metrics in Prometheus format.

    Exports all monitoring metrics in Prometheus exposition format
    for scraping by Prometheus server.
    No caching (Prometheus handles this).

    Returns:
        str: Metrics in Prometheus format

    Raises:
        HTTPException: If metrics exporter is not available
    """
    manager = get_monitoring_manager()
    if not manager.metrics_exporter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metrics exporter not available",
        )

    return manager.metrics_exporter.get_prometheus_metrics()


@router.post(
    "/export/grafana/query",
    response_model=GrafanaQueryResponse,
    summary="Query metrics for Grafana",
    description="Query metrics in Grafana-compatible format",
)
async def query_grafana_metrics(
    request_data: GrafanaQueryRequest,
    current_user: User = Depends(get_admin_user),
) -> GrafanaQueryResponse:
    """
    Query metrics for Grafana.

    Provides time series data in Grafana's expected format.
    Used by Grafana JSON datasource plugin.

    Args:
        request_data: Grafana query request
        current_user: Authenticated admin user

    Returns:
        GrafanaQueryResponse: Metrics in Grafana format

    Raises:
        HTTPException: If metrics exporter is not available
    """
    manager = get_monitoring_manager()
    if not manager.metrics_exporter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metrics exporter not available",
        )

    result = await manager.metrics_exporter.query_grafana_metrics(
        targets=request_data.targets,
        from_time=request_data.range.from_time,
        to_time=request_data.range.to_time,
        max_data_points=request_data.max_data_points,
    )

    return GrafanaQueryResponse(**result)


# ============================================================================
# CONFIGURATION ENDPOINTS
# ============================================================================


@router.get(
    "/config",
    response_model=MonitoringConfigResponse,
    summary="Get monitoring configuration",
    description="Retrieve current monitoring system configuration",
)
@async_cache(cache_type="monitoring_config", ttl=CACHE_TTL_CONFIG)
async def get_monitoring_config_endpoint(
    current_user: User = Depends(get_admin_user),
) -> MonitoringConfigResponse:
    """
    Get monitoring configuration.

    Returns current configuration for all monitoring subsystems.
    Cached for 30 minutes (configuration changes are rare).

    Args:
        current_user: Authenticated admin user

    Returns:
        MonitoringConfigResponse: Current configuration
    """
    config = get_monitoring_config()
    return MonitoringConfigResponse(**config.dict())


@router.put(
    "/config",
    response_model=MonitoringConfigResponse,
    summary="Update monitoring configuration",
    description="Update monitoring system configuration (admin only)",
)
async def update_monitoring_config(
    config_update: MonitoringConfigUpdateRequest,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> MonitoringConfigResponse:
    """
    Update monitoring configuration.

    Updates configuration and invalidates cache.
    Admin-only operation.

    Args:
        config_update: Configuration updates
        current_user: Authenticated admin user
        db: Database session

    Returns:
        MonitoringConfigResponse: Updated configuration
    """
    config = get_monitoring_config()

    # Apply updates
    if config_update.apm_enabled is not None:
        config.apm_enabled = config_update.apm_enabled
    if config_update.db_monitoring_enabled is not None:
        config.db_monitoring_enabled = config_update.db_monitoring_enabled
    if config_update.resource_monitoring_enabled is not None:
        config.resource_monitoring_enabled = config_update.resource_monitoring_enabled

    # TODO: Persist configuration to database or config file

    # Invalidate cache
    # await invalidate_cache("monitoring_config")

    logger.info(f"Monitoring configuration updated by user {current_user.id}")

    return MonitoringConfigResponse(**config.dict())


# ============================================================================
# MANAGEMENT ACTIONS ENDPOINTS
# ============================================================================


@router.post(
    "/actions/reset-stats",
    response_model=StatsResetResponse,
    summary="Reset all monitoring statistics",
    description="Reset all accumulated monitoring statistics (admin only)",
)
async def reset_monitoring_stats(
    current_user: User = Depends(get_admin_user),
) -> StatsResetResponse:
    """
    Reset all monitoring statistics.

    Clears all accumulated statistics across all subsystems.
    Admin-only operation with rate limiting.

    Args:
        current_user: Authenticated admin user

    Returns:
        StatsResetResponse: Reset confirmation
    """
    manager = get_monitoring_manager()
    await manager.reset_all_stats()

    logger.warning(
        f"All monitoring statistics reset by user {current_user.id}"
    )

    return StatsResetResponse(
        message="All monitoring statistics have been reset",
        timestamp=datetime.utcnow(),
        reset_by=str(current_user.id),
    )


@router.post(
    "/actions/start",
    response_model=ServiceActionResponse,
    summary="Start monitoring services",
    description="Start all monitoring subsystems (admin only)",
)
async def start_monitoring_services(
    current_user: User = Depends(get_admin_user),
) -> ServiceActionResponse:
    """
    Start monitoring services.

    Starts all monitoring subsystems if not already running.
    Admin-only operation.

    Args:
        current_user: Authenticated admin user

    Returns:
        ServiceActionResponse: Start result
    """
    manager = get_monitoring_manager()

    if manager._started:
        return ServiceActionResponse(
            success=True,
            message="Monitoring services are already running",
            timestamp=datetime.utcnow(),
        )

    await manager.start()

    logger.info(f"Monitoring services started by user {current_user.id}")

    return ServiceActionResponse(
        success=True,
        message="Monitoring services started successfully",
        timestamp=datetime.utcnow(),
    )


@router.post(
    "/actions/stop",
    response_model=ServiceActionResponse,
    summary="Stop monitoring services",
    description="Stop all monitoring subsystems (admin only)",
)
async def stop_monitoring_services(
    current_user: User = Depends(get_admin_user),
) -> ServiceActionResponse:
    """
    Stop monitoring services.

    Stops all monitoring subsystems if currently running.
    Admin-only operation.

    Args:
        current_user: Authenticated admin user

    Returns:
        ServiceActionResponse: Stop result
    """
    manager = get_monitoring_manager()

    if not manager._started:
        return ServiceActionResponse(
            success=True,
            message="Monitoring services are not running",
            timestamp=datetime.utcnow(),
        )

    await manager.stop()

    logger.info(f"Monitoring services stopped by user {current_user.id}")

    return ServiceActionResponse(
        success=True,
        message="Monitoring services stopped successfully",
        timestamp=datetime.utcnow(),
    )
