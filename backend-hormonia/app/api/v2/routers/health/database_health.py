"""
Database Health Check Module

Provides database-specific health checks and metrics.
"""

import time
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine  # KEEP: sync engine for pool stats
from app.core.database.async_engine import get_async_db
from app.models.user import User
from app.schemas.v2.health import DatabaseHealth, HealthStatus
from .compat import call_health_attr, get_current_user_compat


logger = logging.getLogger(__name__)
router = APIRouter()


async def check_database_health(db: AsyncSession) -> DatabaseHealth:
    """Check database health with detailed metrics."""
    try:
        start_time = time.time()
        ping_result_obj = await db.execute(text("SELECT 1 as health_check"))
        result = ping_result_obj.fetchone()
        latency_ms = (time.time() - start_time) * 1000

        # Get pool metrics (sync engine pool — no session needed)
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
            version_result_obj = await db.execute(
                text("SELECT version_num FROM alembic_version")
            )
            version_result = version_result_obj.fetchone()
            migrations_current = version_result is not None
        except Exception:
            migrations_current = False  # Table may not exist yet

        # Check RLS
        rls_enabled = False
        try:
            rls_result_obj = await db.execute(
                text(
                    "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true"
                )
            )
            rls_result = rls_result_obj.fetchone()
            rls_enabled = rls_result[0] > 0 if rls_result else False
        except Exception as e:
            logger.warning(f"RLS check failed: {e}")

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


@router.get("/database", response_model=DatabaseHealth)
async def database_health_check(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user_compat),
) -> DatabaseHealth:
    """
    Database health check (Authenticated).

    Returns detailed database health metrics.
    Cached for 1 minute.
    """
    try:
        return await call_health_attr("check_database_health", check_database_health, db)
    except Exception as e:
        logger.warning(f"Database health endpoint fallback after check failure: {e}")
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
