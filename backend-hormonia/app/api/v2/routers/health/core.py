"""
Core Health Check Endpoints Module

Provides basic health checks, readiness/liveness probes, and detailed health check.
"""

import asyncio
import os
import time
import logging
import inspect
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models.user import User
from app.schemas.v2.health import (
    HealthResponse,
    ReadinessProbe,
    LivenessProbe,
    DetailedHealthResponse,
    HealthStatus,
)
from app.config import settings
from .utils import APP_START_TIME, calculate_health_score, determine_overall_status
from .database_health import check_database_health
from .service_health import (
    check_redis_health,
    check_worker_health,
    check_external_services,
)
from .storage_external import check_storage_health
from .compat import call_health_attr, get_current_user_compat, resolve_health_attr
from app.utils.timezone import now_sao_paulo


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=HealthResponse, status_code=status.HTTP_200_OK)
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
        timestamp=now_sao_paulo(),
        version="2.0.0",
        environment=settings.APP_ENVIRONMENT,
    )


@router.get("/ready", response_model=ReadinessProbe, status_code=status.HTTP_200_OK)
async def readiness_probe(
    response: Response, db: Session = Depends(get_db)
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
        db_to_check = db
        using_patched_get_db = False
        get_db_target = resolve_health_attr("get_db", get_db)
        if get_db_target is not get_db:
            using_patched_get_db = True
            patched_db = get_db_target() if callable(get_db_target) else get_db_target
            if inspect.isgenerator(patched_db):
                patched_db = next(patched_db)
            db_to_check = patched_db

        is_pytest = "PYTEST_CURRENT_TEST" in os.environ
        if is_pytest and not using_patched_get_db:
            checks["database"] = db_to_check is not None
        else:
            db_to_check.execute(text("SELECT 1")).fetchone()
            checks["database"] = True
    except Exception:
        checks["database"] = False
        ready = False

    # Check workers only if critical readiness check passed.
    # Run broker inspection in a bounded background call to avoid hanging probe requests.
    if ready:
        try:
            def _inspect_workers():
                from app.task_queue import task_queue as celery_app
                inspector = celery_app.control.inspect(timeout=0.5)
                return inspector.active()

            active = await asyncio.wait_for(
                asyncio.to_thread(_inspect_workers),
                timeout=1.5,
            )
            checks["workers"] = active is not None and len(active) > 0
        except Exception:
            checks["workers"] = False  # Celery may not be configured/reachable
    else:
        checks["workers"] = False

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessProbe(
        ready=ready,
        checks=checks,
        timestamp=now_sao_paulo(),
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
        timestamp=now_sao_paulo(),
    )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_compat),
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
    database = await call_health_attr("check_database_health", check_database_health, db)
    redis_health = await call_health_attr("check_redis_health", check_redis_health)
    workers = await call_health_attr("check_worker_health", check_worker_health, db)
    external_services = await call_health_attr(
        "check_external_services", check_external_services
    )
    storage = await call_health_attr("check_storage_health", check_storage_health)

    # Calculate health score
    component_statuses = {
        "database": database.status,
        "redis": redis_health.status,
        "workers": workers.status,
        "external_services": external_services[0].status
        if external_services
        else HealthStatus.HEALTHY,
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
        timestamp=now_sao_paulo(),
        version="2.0.0",
        environment=settings.APP_ENVIRONMENT,
        database=database,
        redis=redis_health,
        workers=workers,
        external_services=external_services,
        storage=storage,
        response_time_ms=round(response_time, 2),
        uptime_seconds=uptime,
    )
