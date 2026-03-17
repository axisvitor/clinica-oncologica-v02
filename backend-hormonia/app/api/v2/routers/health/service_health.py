"""
Service Health Check Module

Provides Redis, worker, and external service health checks.
"""

import time
import logging
from typing import Any, List
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.models.user import User
from app.schemas.v2.health import (
    RedisHealth,
    WorkerHealth,
    ExternalServiceHealth,
    HealthStatus,
)
from app.config import settings
from .compat import call_health_attr, get_current_user_compat
from app.utils.timezone import now_sao_paulo
from app.core.redis_manager import get_redis_manager


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


async def check_worker_health(db: AsyncSession) -> WorkerHealth:
    """Check background worker health (Taskiq-based)."""
    active_workers = 0
    active_tasks = 0
    taskiq_status = "not_configured"

    # --- Taskiq broker health ---
    try:
        from app.taskiq_broker import check_broker_health

        taskiq_health = await check_broker_health()
        if taskiq_health.get("dragonfly_reachable", False):
            taskiq_status = "healthy"
            active_workers += 1  # Taskiq broker is reachable
        else:
            taskiq_status = "unreachable"
    except Exception as e:
        logger.warning(f"Taskiq health check failed: {e}")
        taskiq_status = f"error: {e}"

    # --- DB metrics (failed + pending tasks) ---
    failed_tasks_24h = 0
    pending_tasks = 0
    try:
        from app.models.message import Message, MessageStatus

        failed_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.status == MessageStatus.FAILED,
                Message.updated_at >= now_sao_paulo() - timedelta(hours=24),
            )
        )
        failed_tasks_24h = failed_result.scalar() or 0

        pending_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.status.in_([MessageStatus.PENDING, MessageStatus.SCHEDULED])
            )
        )
        pending_tasks = pending_result.scalar() or 0
    except Exception as e:
        logger.warning(f"Worker DB metrics check failed: {e}")

    # --- Status determination ---
    worker_status = HealthStatus.HEALTHY
    if active_workers == 0 and taskiq_status != "healthy":
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
        avg_task_duration_seconds=0.0,
    )


async def check_external_services() -> List[ExternalServiceHealth]:
    """Check external service health."""
    services = []

    return services


@router.get("/redis", response_model=RedisHealth)
async def redis_health_check(
    current_user: User = Depends(get_current_user_compat),
) -> RedisHealth:
    """
    Redis/cache health check (Authenticated).

    Returns detailed Redis health metrics.
    Cached for 1 minute.
    """
    return await call_health_attr("check_redis_health", check_redis_health)


@router.get("/workers", response_model=WorkerHealth)
async def worker_health_check(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user_compat),
) -> WorkerHealth:
    """
    Background worker health check (Authenticated).

    Returns detailed worker health metrics.
    Cached for 1 minute.
    """
    return await call_health_attr("check_worker_health", check_worker_health, db)


@router.get("/external", response_model=List[ExternalServiceHealth])
async def external_services_health_check(
    current_user: User = Depends(get_current_user_compat),
) -> List[ExternalServiceHealth]:
    """
    External services health check (Authenticated).

    Returns health status of external API dependencies.
    Cached for 2 minutes.
    """
    return await call_health_attr("check_external_services", check_external_services)
