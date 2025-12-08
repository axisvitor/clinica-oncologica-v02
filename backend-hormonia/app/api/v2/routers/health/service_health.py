"""
Service Health Check Module

Provides Redis, worker, and external service health checks.
"""

import time
import logging
from typing import Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user
from app.models.user import User
from app.schemas.v2.health import (
    RedisHealth,
    WorkerHealth,
    ExternalServiceHealth,
    HealthStatus,
)
from app.config import settings


logger = logging.getLogger(__name__)
router = APIRouter()


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
    if hasattr(settings, 'ENABLE_EVOLUTION') and settings.WHATSAPP_ENABLE_SERVICE:
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
    db: Session = Depends(get_db),
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
