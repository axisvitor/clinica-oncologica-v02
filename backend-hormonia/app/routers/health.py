"""
Health check endpoints for monitoring and orchestration.

Provides liveness, readiness, and metrics endpoints for comprehensive
application health monitoring and dependency validation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any
import time
from datetime import datetime, timezone
import psutil
import sys

from app.database import get_db
from app.core.redis_unified import get_async_redis
from app.utils.structured_logger import StructuredLogger
from app.middleware.metrics import get_metrics as get_performance_metrics

logger = StructuredLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

# Track application start time
START_TIME = time.time()


@router.get("", status_code=status.HTTP_200_OK)
@router.get("/", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """
    Simple health check endpoint for Railway and load balancers.

    Returns basic health status without checking dependencies.
    Use /health/ready for comprehensive dependency checks.

    Returns:
        dict: Basic health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "version": "2.0.0",
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }


@router.get("/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with middleware status.

    Returns comprehensive health information including:
    - Overall application status
    - Critical middleware loading status
    - Timestamp and uptime

    This endpoint is used by Railway for health checks to ensure
    all critical security middlewares are properly loaded.

    Returns:
        dict: Detailed health status including middleware status

    Raises:
        HTTPException: 503 if any critical middleware failed to load
    """
    from app.core.middleware_setup import get_middleware_status

    middlewares = get_middleware_status()
    all_healthy = all(middlewares.values())

    response = {
        "status": "healthy" if all_healthy else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "middlewares": {
            "csrf": {
                "loaded": middlewares.get("csrf", False),
                "description": "CSRF protection (Double Submit Cookie)"
            },
            "security_headers": {
                "loaded": middlewares.get("security_headers", False),
                "description": "Security headers (HSTS, CSP, X-Frame-Options)"
            },
            "rate_limiting": {
                "loaded": middlewares.get("rate_limiting", False),
                "description": "Distributed rate limiting (Redis-backed)"
            }
        }
    }

    if not all_healthy:
        logger.error(
            "Detailed health check failed - middlewares not loaded",
            middlewares=middlewares
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response
        )

    return response


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_check() -> Dict[str, Any]:
    """
    Basic liveness check - returns 200 if application is running.

    This endpoint should be used by container orchestrators (Kubernetes, Docker)
    to determine if the application process is alive.

    Returns:
        dict: Liveness status with timestamp
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Readiness check - validates all critical dependencies.

    Checks:
    - Database connectivity
    - Redis connectivity (optional)
    - Firebase connectivity (via environment validation)

    Returns 200 only if all critical dependencies are healthy.
    This endpoint should be used by load balancers to determine
    if the application can serve traffic.

    Args:
        db: Database session

    Returns:
        dict: Readiness status with dependency details

    Raises:
        HTTPException: If any dependency is unhealthy
    """
    start_time = time.perf_counter()
    dependencies = {}
    all_healthy = True

    # Check database connection
    try:
        db_start = time.perf_counter()
        result = db.execute(text("SELECT 1"))
        result.scalar()
        db_duration = (time.perf_counter() - db_start) * 1000

        dependencies["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_duration, 2),
        }
        logger.info(
            "Database health check passed", response_time_ms=round(db_duration, 2)
        )
    except Exception as e:
        all_healthy = False
        dependencies["database"] = {"status": "unhealthy", "error": str(e)}
        logger.error("Database health check failed", exc_info=e, error=str(e))

    # Check Redis connection (non-critical)
    try:
        redis_client = await get_async_redis()
        redis_start = time.perf_counter()
        await redis_client.ping()
        redis_duration = (time.perf_counter() - redis_start) * 1000

        dependencies["redis"] = {
            "status": "healthy",
            "response_time_ms": round(redis_duration, 2),
        }
        logger.info(
            "Redis health check passed", response_time_ms=round(redis_duration, 2)
        )
    except Exception as e:
        # Redis is optional, don't fail readiness check
        dependencies["redis"] = {
            "status": "degraded",
            "error": str(e),
            "note": "Non-critical - caching disabled",
        }
        logger.warning("Redis health check failed (non-critical)", error=str(e))

    # Check Firebase configuration (environment variables)
    try:
        from app.config import settings

        firebase_healthy = bool(
            getattr(settings, "FIREBASE_ADMIN_PROJECT_ID", None)
            and getattr(settings, "FIREBASE_ADMIN_PRIVATE_KEY", None)
            and getattr(settings, "FIREBASE_ADMIN_CLIENT_EMAIL", None)
        )

        dependencies["firebase"] = {
            "status": "healthy" if firebase_healthy else "unhealthy",
            "note": "Configuration validated",
        }

        if not firebase_healthy:
            all_healthy = False
            logger.error("Firebase configuration incomplete")
    except Exception as e:
        all_healthy = False
        dependencies["firebase"] = {"status": "unhealthy", "error": str(e)}
        logger.error("Firebase configuration check failed", exc_info=e, error=str(e))

    total_duration = (time.perf_counter() - start_time) * 1000

    response = {
        "status": "ready" if all_healthy else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "dependencies": dependencies,
        "total_check_time_ms": round(total_duration, 2),
    }

    if not all_healthy:
        logger.error("Readiness check failed", dependencies=dependencies)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response
        )

    logger.info("Readiness check passed", total_check_time_ms=round(total_duration, 2))
    return response


@router.get("/metrics", status_code=status.HTTP_200_OK)
async def metrics_endpoint() -> Dict[str, Any]:
    """
    Performance metrics endpoint in JSON format.

    Provides comprehensive application metrics including:
    - System resource usage (CPU, memory)
    - Application uptime
    - Python runtime information
    - Process statistics

    Returns:
        dict: Performance metrics in Prometheus-compatible format
    """
    try:
        # Process info
        process = psutil.Process()

        # CPU metrics
        cpu_percent = process.cpu_percent(interval=0.1)
        cpu_times = process.cpu_times()

        # Memory metrics
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()

        # System metrics
        system_cpu = psutil.cpu_percent(interval=0.1)
        system_memory = psutil.virtual_memory()

        # Uptime
        uptime_seconds = time.time() - START_TIME

        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "application": {
                "uptime_seconds": round(uptime_seconds, 2),
                "python_version": sys.version,
                "process_id": process.pid,
            },
            "process": {
                "cpu": {
                    "percent": round(cpu_percent, 2),
                    "user_time_seconds": round(cpu_times.user, 2),
                    "system_time_seconds": round(cpu_times.system, 2),
                },
                "memory": {
                    "rss_bytes": memory_info.rss,
                    "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                    "vms_bytes": memory_info.vms,
                    "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
                    "percent": round(memory_percent, 2),
                },
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
            },
            "system": {
                "cpu": {
                    "percent": round(system_cpu, 2),
                    "count": psutil.cpu_count(),
                },
                "memory": {
                    "total_bytes": system_memory.total,
                    "total_mb": round(system_memory.total / 1024 / 1024, 2),
                    "available_bytes": system_memory.available,
                    "available_mb": round(system_memory.available / 1024 / 1024, 2),
                    "percent_used": round(system_memory.percent, 2),
                },
            },
        }

        logger.log_performance(
            operation="metrics_collection",
            duration_ms=0,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
        )

        return metrics

    except Exception as e:
        logger.error("Failed to collect metrics", exc_info=e, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to collect metrics", "message": str(e)},
        )


@router.get("/startup", status_code=status.HTTP_200_OK)
async def startup_validation(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Comprehensive startup validation check.

    Performs deep validation of all application components:
    - Database schema validation
    - Critical tables existence
    - Configuration completeness
    - Dependency health

    This endpoint should be called during application initialization
    to ensure the application is properly configured.

    Args:
        db: Database session

    Returns:
        dict: Validation results with detailed status
    """
    validation_results = {}
    all_valid = True

    # Validate database schema
    try:
        # Check critical tables exist
        critical_tables = [
            "users",
            "patients",
            "flows",
            "messages",
            "quiz_submissions",
            "alerts",
        ]

        for table in critical_tables:
            # Use parameterized query to prevent SQL injection
            result = db.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :table_name)"
                ),
                {"table_name": table}
            )
            exists = result.scalar()

            if not exists:
                all_valid = False
                logger.error(f"Critical table missing: {table}")

            validation_results[f"table_{table}"] = "present" if exists else "missing"

    except Exception as e:
        all_valid = False
        validation_results["database_schema"] = {"status": "error", "error": str(e)}
        logger.error("Database schema validation failed", exc_info=e, error=str(e))

    # Validate configuration
    try:
        from app.config import settings

        required_settings = ["FIREBASE_PROJECT_ID", "DATABASE_URL", "SECRET_KEY"]

        for setting in required_settings:
            value = getattr(settings, setting, None)
            is_set = bool(value)

            if not is_set:
                all_valid = False
                logger.error(f"Required setting missing: {setting}")

            validation_results[f"config_{setting.lower()}"] = (
                "set" if is_set else "missing"
            )

    except Exception as e:
        all_valid = False
        validation_results["configuration"] = {"status": "error", "error": str(e)}
        logger.error("Configuration validation failed", exc_info=e, error=str(e))

    response = {
        "status": "valid" if all_valid else "invalid",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "validation_results": validation_results,
    }

    if not all_valid:
        logger.error("Startup validation failed", validation_results=validation_results)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response
        )

    logger.info("Startup validation passed")
    return response


@router.get("/performance", status_code=status.HTTP_200_OK)
async def performance_metrics() -> Dict[str, Any]:
    """
    Get application performance metrics.

    Returns comprehensive performance metrics collected by the
    PerformanceMetricsMiddleware including:
    - Request statistics (count, avg duration, by status)
    - Endpoint-specific metrics (per-endpoint performance)
    - Database query statistics
    - Cache performance (hit/miss rates)
    - Memory usage

    This endpoint provides real-time performance data for monitoring
    and optimization purposes.

    Returns:
        dict: Performance metrics snapshot
    """
    try:
        metrics = get_performance_metrics()

        logger.info(
            "Performance metrics retrieved",
            total_requests=metrics.get("requests", {}).get("total", 0),
            cache_hit_rate=metrics.get("cache", {}).get("hit_rate_percent", 0),
        )

        return metrics

    except Exception as e:
        logger.error("Failed to retrieve performance metrics", exc_info=e, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to retrieve metrics", "message": str(e)},
        )
