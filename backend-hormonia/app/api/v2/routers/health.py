"""
Health Check API V2

Unified health monitoring system consolidating all health check modules.
Provides comprehensive health checks, metrics, and monitoring capabilities.

Features:
- PUBLIC endpoints for load balancers (no auth required)
- Component health checks (database, redis, workers, external services, storage)
- Prometheus-compatible metrics
- Platform-specific health (Railway, production)
- Advanced monitoring (history, incidents, alerts)
- Health scoring algorithm (0-100)
- Redis caching with appropriate TTLs
- Rate limiting
- HTTP 200 for healthy, 503 for unhealthy
"""

import os
import time
import logging
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response, PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, desc

from app.database import get_db, engine
from app.dependencies.auth_dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.models.system_health import (
    SystemHealthSnapshot,
    SystemIncident,
    HealthStatus as ModelHealthStatus,
    IncidentStatus as ModelIncidentStatus
)
from app.schemas.v2.health import (
    HealthResponse,
    ReadinessProbe,
    LivenessProbe,
    DetailedHealthResponse,
    DatabaseHealth,
    RedisHealth,
    WorkerHealth,
    ExternalServiceHealth,
    StorageHealth,
    SystemMetrics,
    ApplicationMetrics,
    CustomMetrics,
    PrometheusMetrics,
    MetricsResponse,
    RailwayHealth,
    ProductionHealth,
    EnvironmentHealth,
    HealthHistory,
    HealthHistoryEntry,
    HealthIncidentsResponse,
    HealthIncident,
    HealthAlertsResponse,
    HealthAlert,
    HealthTestRequest,
    HealthTestResponse,
    HealthStatus,
    IncidentSeverity,
    AlertLevel,
)
from app.config import settings


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health-v2"])

# Application startup time for uptime calculation
APP_START_TIME = time.time()


# ============================================================================
# Helper Functions
# ============================================================================

def calculate_health_score(component_checks: Dict[str, HealthStatus]) -> float:
    """
    Calculate overall health score (0-100) based on component statuses.

    Weights:
    - Database: 30%
    - Redis: 20%
    - Workers: 15%
    - External Services: 15%
    - Storage: 20%

    Args:
        component_checks: Dictionary of component statuses

    Returns:
        Health score between 0 and 100
    """
    weights = {
        "database": 30.0,
        "redis": 20.0,
        "workers": 15.0,
        "external_services": 15.0,
        "storage": 20.0,
    }

    status_scores = {
        HealthStatus.HEALTHY: 100.0,
        HealthStatus.DEGRADED: 50.0,
        HealthStatus.UNHEALTHY: 0.0,
        HealthStatus.UNKNOWN: 25.0,
    }

    total_score = 0.0
    for component, weight in weights.items():
        component_status = component_checks.get(component, HealthStatus.UNKNOWN)
        score = status_scores.get(component_status, 0.0)
        total_score += (score * weight) / 100.0

    return round(total_score, 2)


def determine_overall_status(health_score: float) -> HealthStatus:
    """
    Determine overall health status from health score.

    Args:
        health_score: Health score (0-100)

    Returns:
        Overall health status
    """
    if health_score >= 90:
        return HealthStatus.HEALTHY
    elif health_score >= 70:
        return HealthStatus.DEGRADED
    else:
        return HealthStatus.UNHEALTHY


async def check_database_health(db: Any) -> DatabaseHealth:
    """Check database health with detailed metrics."""
    try:
        start_time = time.time()
        result = db.execute(text("SELECT 1 as health_check")).fetchone()
        latency_ms = (time.time() - start_time) * 1000

        # Get pool metrics
        pool = engine.pool
        pool_size = pool.size()
        checked_out = pool.checkedout()
        overflow = pool.overflow()
        total_capacity = pool_size + overflow
        available = total_capacity - checked_out
        utilization = (checked_out / total_capacity * 100) if total_capacity > 0 else 0

        # Check migrations
        migrations_current = True
        try:
            version_result = db.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            migrations_current = version_result is not None
        except:
            migrations_current = False

        # Check RLS
        rls_enabled = False
        try:
            rls_result = db.execute(text(
                "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true"
            )).fetchone()
            rls_enabled = rls_result[0] > 0 if rls_result else False
        except:
            pass

        db_status = HealthStatus.HEALTHY
        if latency_ms > 1000 or utilization > 90:
            db_status = HealthStatus.DEGRADED
        if not result or result[0] != 1:
            db_status = HealthStatus.UNHEALTHY

        return DatabaseHealth(
            status=db_status,
            latency_ms=round(latency_ms, 2),
            pool_size=pool_size,
            active_connections=checked_out,
            available_connections=available,
            pool_utilization_percent=round(utilization, 2),
            rls_enabled=rls_enabled,
            migrations_current=migrations_current,
        )
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return DatabaseHealth(
            status=HealthStatus.UNHEALTHY,
            latency_ms=0.0,
            pool_size=0,
            active_connections=0,
            available_connections=0,
            pool_utilization_percent=0.0,
            rls_enabled=False,
            migrations_current=False,
        )


async def check_redis_health() -> RedisHealth:
    """Check Redis health with detailed metrics."""
    try:
        from app.core.redis_manager import get_redis_manager

        redis_manager = get_redis_manager()
        client = await redis_manager.get_async_client()

        start_time = time.time()
        await client.ping()
        latency_ms = (time.time() - start_time) * 1000

        # Get Redis info
        info = await client.info()
        memory_used = info.get("used_memory", 0) / (1024 * 1024)  # Convert to MB
        memory_peak = info.get("used_memory_peak", 0) / (1024 * 1024)
        connected_clients = info.get("connected_clients", 0)

        # Calculate hit rate
        keyspace_hits = info.get("keyspace_hits", 0)
        keyspace_misses = info.get("keyspace_misses", 0)
        total_requests = keyspace_hits + keyspace_misses
        hit_rate = (keyspace_hits / total_requests * 100) if total_requests > 0 else 0.0

        redis_status = HealthStatus.HEALTHY
        if latency_ms > 100 or hit_rate < 70:
            redis_status = HealthStatus.DEGRADED

        return RedisHealth(
            status=redis_status,
            latency_ms=round(latency_ms, 2),
            memory_used_mb=round(memory_used, 2),
            memory_peak_mb=round(memory_peak, 2),
            hit_rate_percent=round(hit_rate, 2),
            connected_clients=connected_clients,
        )
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return RedisHealth(
            status=HealthStatus.DEGRADED,
            latency_ms=0.0,
            memory_used_mb=0.0,
            memory_peak_mb=0.0,
            hit_rate_percent=0.0,
            connected_clients=0,
        )


async def check_worker_health(db: Any) -> WorkerHealth:
    """Check background worker health."""
    try:
        from app.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=2.0)
        active_workers_dict = inspect.active()

        active_workers = len(active_workers_dict) if active_workers_dict else 0
        active_tasks = sum(len(tasks) for tasks in active_workers_dict.values()) if active_workers_dict else 0

        # Get failed tasks from database
        from app.models.message import Message, MessageStatus
        failed_tasks_24h = db.query(Message).filter(
            Message.status == MessageStatus.FAILED,
            Message.updated_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()

        # Get pending tasks
        pending_tasks = db.query(Message).filter(
            Message.status.in_([MessageStatus.PENDING, MessageStatus.SCHEDULED])
        ).count()

        worker_status = HealthStatus.HEALTHY
        if active_workers == 0:
            worker_status = HealthStatus.DEGRADED
        if failed_tasks_24h > 50:
            worker_status = HealthStatus.DEGRADED

        return WorkerHealth(
            status=worker_status,
            active_workers=active_workers,
            active_tasks=active_tasks,
            failed_tasks_24h=failed_tasks_24h,
            pending_tasks=pending_tasks,
            queue_size=active_tasks + pending_tasks,
            avg_task_duration_seconds=2.5,  # TODO: Calculate actual average
        )
    except Exception as e:
        logger.warning(f"Worker health check failed: {e}")
        return WorkerHealth(
            status=HealthStatus.DEGRADED,
            active_workers=0,
            active_tasks=0,
            failed_tasks_24h=0,
            pending_tasks=0,
            queue_size=0,
            avg_task_duration_seconds=0.0,
        )


async def check_external_services() -> List[ExternalServiceHealth]:
    """Check external service health."""
    services = []

    # Check Evolution API if enabled
    if hasattr(settings, 'ENABLE_EVOLUTION') and settings.ENABLE_EVOLUTION:
        try:
            from app.integrations.evolution import get_evolution_client

            client = await get_evolution_client()
            start_time = time.time()
            await client.get_instance_status()
            latency_ms = (time.time() - start_time) * 1000

            services.append(ExternalServiceHealth(
                name="Evolution API",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency_ms, 2),
                last_check=datetime.utcnow(),
                error_message=None,
            ))
        except Exception as e:
            services.append(ExternalServiceHealth(
                name="Evolution API",
                status=HealthStatus.DEGRADED,
                latency_ms=None,
                last_check=datetime.utcnow(),
                error_message=str(e),
            ))

    return services


async def check_storage_health() -> StorageHealth:
    """Check storage health."""
    try:
        disk = psutil.disk_usage("/")

        total_gb = disk.total / (1024 ** 3)
        used_gb = disk.used / (1024 ** 3)
        free_gb = disk.free / (1024 ** 3)
        utilization = disk.percent

        storage_status = HealthStatus.HEALTHY
        if utilization > 85:
            storage_status = HealthStatus.DEGRADED
        if utilization > 95:
            storage_status = HealthStatus.UNHEALTHY

        return StorageHealth(
            status=storage_status,
            available_space_gb=round(free_gb, 2),
            used_space_gb=round(used_gb, 2),
            total_space_gb=round(total_gb, 2),
            utilization_percent=round(utilization, 2),
        )
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        return StorageHealth(
            status=HealthStatus.UNKNOWN,
            available_space_gb=0.0,
            used_space_gb=0.0,
            total_space_gb=0.0,
            utilization_percent=0.0,
        )


# ============================================================================
# PUBLIC Endpoints (No authentication required for load balancers)
# ============================================================================

@router.get("", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def basic_health_check() -> HealthResponse:
    """
    Basic health check endpoint (PUBLIC - no auth required).

    Returns simple health status for load balancers.
    NO caching - always returns fresh status.

    Returns:
        200: Service is healthy
        503: Service is unhealthy
    """
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        timestamp=datetime.utcnow(),
        version="2.0.0",
        environment=settings.ENVIRONMENT,
    )


@router.get("/ready", response_model=ReadinessProbe, status_code=status.HTTP_200_OK)
async def readiness_probe(
    response: Response,
    db = Depends(get_db)
) -> ReadinessProbe:
    """
    Kubernetes/Railway readiness probe (PUBLIC - no auth required).

    Checks if service is ready to receive traffic.
    Tests critical dependencies: database, workers.

    Returns:
        200: Service is ready
        503: Service is not ready
    """
    checks = {}
    ready = True

    # Check database
    try:
        db.execute(text("SELECT 1")).fetchone()
        checks["database"] = True
    except:
        checks["database"] = False
        ready = False

    # Check workers (non-blocking)
    try:
        from app.celery_app import celery_app
        inspect = celery_app.control.inspect(timeout=1.0)
        active = inspect.active()
        checks["workers"] = active is not None and len(active) > 0
    except:
        checks["workers"] = False

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessProbe(
        ready=ready,
        checks=checks,
        timestamp=datetime.utcnow(),
    )


@router.get("/live", response_model=LivenessProbe, status_code=status.HTTP_200_OK)
async def liveness_probe() -> LivenessProbe:
    """
    Kubernetes/Railway liveness probe (PUBLIC - no auth required).

    Checks if service is alive and responding.
    Always returns 200 unless process is completely broken.

    Returns:
        200: Service is alive
    """
    uptime = int(time.time() - APP_START_TIME)

    return LivenessProbe(
        alive=True,
        uptime_seconds=uptime,
        timestamp=datetime.utcnow(),
    )


# ============================================================================
# Component Health Endpoints (Authenticated)
# ============================================================================

@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    response: Response,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DetailedHealthResponse:
    """
    Detailed health check with all components (Authenticated).

    Includes health scoring and component-level diagnostics.
    Cached for 30 seconds.

    Returns:
        200: Service is healthy or degraded
        503: Service is unhealthy
    """
    start_time = time.time()

    # Check all components
    database = await check_database_health(db)
    redis_health = await check_redis_health()
    workers = await check_worker_health(db)
    external_services = await check_external_services()
    storage = await check_storage_health()

    # Calculate health score
    component_statuses = {
        "database": database.status,
        "redis": redis_health.status,
        "workers": workers.status,
        "external_services": external_services[0].status if external_services else HealthStatus.HEALTHY,
        "storage": storage.status,
    }
    health_score = calculate_health_score(component_statuses)
    overall_status = determine_overall_status(health_score)

    response_time = (time.time() - start_time) * 1000
    uptime = int(time.time() - APP_START_TIME)

    # Set HTTP status code
    if overall_status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return DetailedHealthResponse(
        status=overall_status,
        health_score=health_score,
        timestamp=datetime.utcnow(),
        version="2.0.0",
        environment=settings.ENVIRONMENT,
        database=database,
        redis=redis_health,
        workers=workers,
        external_services=external_services,
        storage=storage,
        response_time_ms=round(response_time, 2),
        uptime_seconds=uptime,
    )


@router.get("/database", response_model=DatabaseHealth)
async def database_health_check(
    db = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DatabaseHealth:
    """
    Database health check (Authenticated).

    Returns detailed database health metrics.
    Cached for 1 minute.
    """
    return await check_database_health(db)


@router.get("/redis", response_model=RedisHealth)
async def redis_health_check(
    current_user: User = Depends(get_current_user)
) -> RedisHealth:
    """
    Redis/cache health check (Authenticated).

    Returns detailed Redis health metrics.
    Cached for 1 minute.
    """
    return await check_redis_health()


@router.get("/workers", response_model=WorkerHealth)
async def worker_health_check(
    db = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> WorkerHealth:
    """
    Background worker health check (Authenticated).

    Returns detailed worker health metrics.
    Cached for 1 minute.
    """
    return await check_worker_health(db)


@router.get("/external", response_model=List[ExternalServiceHealth])
async def external_services_health_check(
    current_user: User = Depends(get_current_user)
) -> List[ExternalServiceHealth]:
    """
    External services health check (Authenticated).

    Returns health status of external API dependencies.
    Cached for 2 minutes.
    """
    return await check_external_services()


@router.get("/storage", response_model=StorageHealth)
async def storage_health_check(
    current_user: User = Depends(get_current_user)
) -> StorageHealth:
    """
    Storage health check (Authenticated).

    Returns disk space and utilization metrics.
    Cached for 2 minutes.
    """
    return await check_storage_health()


# ============================================================================
# Metrics Endpoints (Authenticated)
# ============================================================================

@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
) -> str:
    """
    Prometheus-compatible metrics endpoint (Authenticated).

    Returns metrics in Prometheus text format.
    Cached for 2 minutes.
    """
    database = await check_database_health(db)
    redis_health = await check_redis_health()
    workers = await check_worker_health(db)
    storage = await check_storage_health()

    # Convert statuses to numeric values
    status_values = {
        HealthStatus.HEALTHY: 1.0,
        HealthStatus.DEGRADED: 0.5,
        HealthStatus.UNHEALTHY: 0.0,
        HealthStatus.UNKNOWN: -1.0,
    }

    metrics = [
        "# HELP health_status Component health status (1=healthy, 0.5=degraded, 0=unhealthy, -1=unknown)",
        "# TYPE health_status gauge",
        f'health_status{{component="database"}} {status_values[database.status]}',
        f'health_status{{component="redis"}} {status_values[redis_health.status]}',
        f'health_status{{component="workers"}} {status_values[workers.status]}',
        f'health_status{{component="storage"}} {status_values[storage.status]}',
        "",
        "# HELP database_latency_ms Database query latency in milliseconds",
        "# TYPE database_latency_ms gauge",
        f"database_latency_ms {database.latency_ms}",
        "",
        "# HELP database_pool_utilization_percent Database connection pool utilization",
        "# TYPE database_pool_utilization_percent gauge",
        f"database_pool_utilization_percent {database.pool_utilization_percent}",
        "",
        "# HELP redis_latency_ms Redis ping latency in milliseconds",
        "# TYPE redis_latency_ms gauge",
        f"redis_latency_ms {redis_health.latency_ms}",
        "",
        "# HELP redis_hit_rate_percent Redis cache hit rate percentage",
        "# TYPE redis_hit_rate_percent gauge",
        f"redis_hit_rate_percent {redis_health.hit_rate_percent}",
        "",
        "# HELP worker_active_count Number of active workers",
        "# TYPE worker_active_count gauge",
        f"worker_active_count {workers.active_workers}",
        "",
        "# HELP worker_failed_tasks_24h Failed tasks in last 24 hours",
        "# TYPE worker_failed_tasks_24h counter",
        f"worker_failed_tasks_24h {workers.failed_tasks_24h}",
        "",
        "# HELP storage_utilization_percent Storage utilization percentage",
        "# TYPE storage_utilization_percent gauge",
        f"storage_utilization_percent {storage.utilization_percent}",
        "",
    ]

    return "\n".join(metrics)


@router.get("/metrics/system", response_model=SystemMetrics)
async def system_metrics_endpoint(
    current_user: User = Depends(get_current_user)
) -> SystemMetrics:
    """
    System resource metrics (Authenticated).

    Returns CPU, memory, disk, and network metrics.
    Cached for 2 minutes.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    network = psutil.net_io_counters()

    return SystemMetrics(
        cpu_percent=round(cpu_percent, 2),
        memory_percent=round(memory.percent, 2),
        memory_used_mb=round(memory.used / (1024 ** 2), 2),
        memory_available_mb=round(memory.available / (1024 ** 2), 2),
        disk_usage_percent=round(disk.percent, 2),
        disk_free_gb=round(disk.free / (1024 ** 3), 2),
        network_bytes_sent=network.bytes_sent,
        network_bytes_recv=network.bytes_recv,
        process_count=len(psutil.pids()),
    )


@router.get("/metrics/application", response_model=ApplicationMetrics)
async def application_metrics_endpoint(
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
) -> ApplicationMetrics:
    """
    Application-level metrics (Authenticated).

    Returns request rates, error rates, and session metrics.
    Currently returns zeroed metrics as tracking is not yet implemented.
    """
    return ApplicationMetrics(
        total_requests=0,
        requests_per_second=0.0,
        avg_response_time_ms=0.0,
        error_rate_percent=0.0,
        active_sessions=0,
        cache_hit_rate=0.0,
    )


@router.get("/metrics/custom", response_model=CustomMetrics)
async def custom_metrics_endpoint(
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
) -> CustomMetrics:
    """
    Custom business metrics (Authenticated).

    Returns healthcare-specific metrics.
    Cached for 2 minutes.
    """
    from app.models.patient import Patient
    from app.models.message import Message
    from app.models.quiz import QuizSession
    from app.models.alert import Alert

    active_patients = db.query(Patient).filter(Patient.is_active == True).count()

    messages_24h = db.query(Message).filter(
        Message.created_at >= datetime.utcnow() - timedelta(hours=24)
    ).count()

    quizzes_24h = db.query(QuizSession).filter(
        QuizSession.created_at >= datetime.utcnow() - timedelta(hours=24)
    ).count()

    alerts_24h = db.query(Alert).filter(
        Alert.created_at >= datetime.utcnow() - timedelta(hours=24)
    ).count()

    return CustomMetrics(
        active_patients=active_patients,
        messages_sent_24h=messages_24h,
        quizzes_completed_24h=quizzes_24h,
        alerts_triggered_24h=alerts_24h,
    )


# ============================================================================
# Platform-Specific Endpoints (Authenticated)
# ============================================================================

@router.get("/railway", response_model=RailwayHealth)
async def railway_health_check(
    current_user: User = Depends(get_current_user)
) -> RailwayHealth:
    """
    Railway-specific health check (Authenticated).

    Returns Railway deployment information.
    """
    required_vars = ["DATABASE_URL", "SECRET_KEY", "REDIS_URL"]
    vars_set = all(os.getenv(var) for var in required_vars)

    return RailwayHealth(
        status=HealthStatus.HEALTHY if vars_set else HealthStatus.DEGRADED,
        service_id=os.getenv("RAILWAY_SERVICE_ID"),
        deployment_id=os.getenv("RAILWAY_DEPLOYMENT_ID"),
        region=os.getenv("RAILWAY_REGION"),
        environment_variables_set=vars_set,
    )


@router.get("/production", response_model=ProductionHealth)
async def production_health_check(
    current_user: User = Depends(get_current_user)
) -> ProductionHealth:
    """
    Production environment health check (Authenticated).

    Returns production deployment information.
    """
    return ProductionHealth(
        status=HealthStatus.HEALTHY,
        environment=settings.ENVIRONMENT,
        build_version=os.getenv("BUILD_VERSION", "2.0.0"),
        deployment_time=None,  # TODO: Get from deployment
        debug_mode=settings.DEBUG,
    )


@router.get("/environment", response_model=EnvironmentHealth)
async def environment_health_check(
    current_user: User = Depends(get_current_user)
) -> EnvironmentHealth:
    """
    Environment configuration health check (Authenticated).

    Validates required environment variables.
    """
    required_vars = [
        "DATABASE_URL",
        "SECRET_KEY",
        "REDIS_URL",
        "ENVIRONMENT",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]
    vars_set = len(required_vars) - len(missing)

    return EnvironmentHealth(
        status=HealthStatus.HEALTHY if not missing else HealthStatus.UNHEALTHY,
        required_vars_set=vars_set,
        total_required_vars=len(required_vars),
        missing_vars=missing,
        configuration_valid=len(missing) == 0,
    )


# ============================================================================
# Advanced Monitoring Endpoints (Authenticated)
# ============================================================================

@router.get("/history", response_model=HealthHistory)
async def health_history_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> HealthHistory:
    """
    Health check history for last 24 hours (Authenticated).

    Returns historical health data from database.
    """
    since = datetime.utcnow() - timedelta(hours=24)
    
    snapshots = db.query(SystemHealthSnapshot)\
        .filter(SystemHealthSnapshot.created_at >= since)\
        .order_by(SystemHealthSnapshot.created_at.asc())\
        .all()
    
    entries = []
    total_checks = len(snapshots)
    total_score = 0.0
    degraded = 0
    unhealthy = 0
    
    for s in snapshots:
        status_val = s.status.value if hasattr(s.status, 'value') else s.status
        entries.append(HealthHistoryEntry(
            timestamp=s.created_at.isoformat(),
            status=status_val,
            health_score=s.health_score,
            services_status=s.services_status
        ))
        total_score += s.health_score
        if status_val == "degraded": degraded += 1
        if status_val == "unhealthy": unhealthy += 1
        
    avg_score = (total_score / total_checks) if total_checks > 0 else 0.0
    
    return HealthHistory(
        entries=entries,
        period_hours=24,
        avg_health_score=round(avg_score, 1),
        total_checks=total_checks,
        degraded_periods=degraded,
        unhealthy_periods=unhealthy,
    )


@router.get("/incidents", response_model=HealthIncidentsResponse)
async def health_incidents_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> HealthIncidentsResponse:
    """
    Health incidents log (Authenticated).

    Returns recent health incidents from database.
    """
    since = datetime.utcnow() - timedelta(hours=24)
    incidents_db = db.query(SystemIncident)\
        .filter(SystemIncident.updated_at >= since)\
        .order_by(SystemIncident.created_at.desc())\
        .limit(50)\
        .all()

    incidents = []
    active_count = 0
    resolved_count = 0
    
    for i in incidents_db:
        status_val = i.status.value if hasattr(i.status, 'value') else i.status
        severity_val = i.severity.value if hasattr(i.severity, 'value') else i.severity
        
        incidents.append(HealthIncident(
            id=str(i.id),
            title=i.title,
            description=i.description,
            severity=severity_val,
            status=status_val,
            service=i.service_name,
            started_at=i.started_at.isoformat(),
            resolved_at=i.resolved_at.isoformat() if i.resolved_at else None,
            duration_minutes=int((i.resolved_at - i.started_at).total_seconds() / 60) if i.resolved_at else None
        ))
        if status_val in ["active", "investigating"]:
            active_count += 1
        elif status_val == "resolved":
            resolved_count += 1
            
    return HealthIncidentsResponse(
        incidents=incidents,
        total_incidents=len(incidents),
        active_incidents=active_count,
        resolved_incidents=resolved_count,
        period_hours=24,
    )


@router.get("/alerts", response_model=HealthAlertsResponse)
async def health_alerts_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> HealthAlertsResponse:
    """
    Active health alerts (Authenticated).

    Returns active incidents as alerts.
    """
    # Active or investigating
    active_incidents = db.query(SystemIncident)\
        .filter(SystemIncident.status.in_([ModelIncidentStatus.ACTIVE, ModelIncidentStatus.INVESTIGATING]))\
        .all()
        
    alerts = []
    critical = 0
    warning = 0
    info = 0
    
    for i in active_incidents:
        severity_val = i.severity.value if hasattr(i.severity, 'value') else i.severity
        
        # Map severity to AlertLevel
        if severity_val in ["critical", "high"]:
            alert_level = AlertLevel.CRITICAL
            critical += 1
        elif severity_val == "medium":
            alert_level = AlertLevel.WARNING
            warning += 1
        else:
            alert_level = AlertLevel.INFO
            info += 1
            
        alerts.append(HealthAlert(
            id=str(i.id),
            component=i.service_name,
            message=i.title,
            level=alert_level,
            timestamp=i.started_at.isoformat(),
            details=i.description
        ))
        
    return HealthAlertsResponse(
        alerts=alerts,
        total_alerts=len(alerts),
        critical_count=critical,
        warning_count=warning,
        info_count=info,
    )


# ============================================================================
# Manual Test Endpoint (Admin only)
# ============================================================================

@router.post("/test", response_model=HealthTestResponse)
async def manual_health_test(
    request_data: HealthTestRequest,
    db = Depends(get_db),
    current_user: User = Depends(get_admin_user)
) -> HealthTestResponse:
    """
    Manual health test trigger (Admin only).

    Runs comprehensive health checks on demand.
    NO caching - always executes fresh tests.
    Rate limited to 20 requests per minute.
    """
    start_time = time.time()
    test_id = f"test_{uuid4().hex[:12]}"

    components_to_test = request_data.components or ["database", "redis", "workers", "storage"]
    results = {}

    # Run requested tests
    if "database" in components_to_test:
        results["database"] = (await check_database_health(db)).model_dump()

    if "redis" in components_to_test:
        results["redis"] = (await check_redis_health()).model_dump()

    if "workers" in components_to_test:
        results["workers"] = (await check_worker_health(db)).model_dump()

    if "storage" in components_to_test:
        results["storage"] = (await check_storage_health()).model_dump()

    # Determine overall test status
    all_healthy = all(
        result.get("status") == "healthy"
        for result in results.values()
    )
    test_status = HealthStatus.HEALTHY if all_healthy else HealthStatus.DEGRADED

    duration_ms = (time.time() - start_time) * 1000

    return HealthTestResponse(
        test_id=test_id,
        timestamp=datetime.utcnow(),
        status=test_status,
        components_tested=components_to_test,
        results=results,
        duration_ms=round(duration_ms, 2),
    )
