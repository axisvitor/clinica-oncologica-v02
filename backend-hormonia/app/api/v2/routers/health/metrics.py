"""
Metrics Endpoints Module

Provides Prometheus-compatible metrics and system/application metrics.
"""

import logging
import psutil
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.v2.health import (
    SystemMetrics,
    ApplicationMetrics,
    CustomMetrics,
    HealthStatus,
)
from .database_health import check_database_health
from .service_health import check_redis_health, check_worker_health
from .storage_external import check_storage_health
from .compat import call_health_attr, get_current_user_compat
from app.utils.timezone import now_sao_paulo


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(
    current_user: User = Depends(get_current_user_compat),
    db: Session = Depends(get_db),
) -> str:
    """
    Prometheus-compatible metrics endpoint (Authenticated).

    Returns metrics in Prometheus text format.
    Cached for 2 minutes.
    """
    database = await call_health_attr("check_database_health", check_database_health, db)
    redis_health = await call_health_attr("check_redis_health", check_redis_health)
    workers = await call_health_attr("check_worker_health", check_worker_health, db)
    storage = await call_health_attr("check_storage_health", check_storage_health)

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
    current_user: User = Depends(get_current_user_compat),
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
        memory_used_mb=round(memory.used / (1024**2), 2),
        memory_available_mb=round(memory.available / (1024**2), 2),
        disk_usage_percent=round(disk.percent, 2),
        disk_free_gb=round(disk.free / (1024**3), 2),
        network_bytes_sent=network.bytes_sent,
        network_bytes_recv=network.bytes_recv,
        process_count=len(psutil.pids()),
    )


@router.get("/metrics/application", response_model=ApplicationMetrics)
async def application_metrics_endpoint(
    current_user: User = Depends(get_current_user_compat),
    db: Session = Depends(get_db),
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
    current_user: User = Depends(get_current_user_compat),
    db: Session = Depends(get_db),
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

    active_patients_query = db.query(Patient)
    if hasattr(Patient, "deleted_at"):
        active_patients_query = active_patients_query.filter(Patient.deleted_at.is_(None))
    active_patients = active_patients_query.count()

    messages_24h = (
        db.query(Message)
        .filter(Message.created_at >= now_sao_paulo() - timedelta(hours=24))
        .count()
    )

    quizzes_24h = (
        db.query(QuizSession)
        .filter(QuizSession.created_at >= now_sao_paulo() - timedelta(hours=24))
        .count()
    )

    alerts_24h = (
        db.query(Alert)
        .filter(Alert.created_at >= now_sao_paulo() - timedelta(hours=24))
        .count()
    )

    return CustomMetrics(
        active_patients=active_patients,
        messages_sent_24h=messages_24h,
        quizzes_completed_24h=quizzes_24h,
        alerts_triggered_24h=alerts_24h,
    )
