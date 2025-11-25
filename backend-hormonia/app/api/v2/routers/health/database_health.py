"""
Database Health Check Module

Provides database-specific health checks and metrics.
"""

import time
import logging
from typing import Any
from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db, engine
from app.dependencies.auth_dependencies import get_current_user
from app.models.user import User
from app.schemas.v2.health import DatabaseHealth, HealthStatus


logger = logging.getLogger(__name__)
router = APIRouter()


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


@router.get("/database", response_model=DatabaseHealth)
async def database_health_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DatabaseHealth:
    """
    Database health check (Authenticated).

    Returns detailed database health metrics.
    Cached for 1 minute.
    """
    return await check_database_health(db)
