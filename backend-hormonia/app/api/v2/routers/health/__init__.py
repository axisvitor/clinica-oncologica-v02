"""
Health Check API V2 Package

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

Module Structure:
- core: Basic health checks, readiness/liveness probes
- database_health: Database-specific health checks
- service_health: Redis, worker, and external service checks
- storage_external: Storage health checks
- metrics: Prometheus metrics and system/application metrics
- platform: Railway, production, environment health checks
- monitoring: Health history, incidents, and alerts
- test: Admin-only manual health testing
- utils: Helper functions and health scoring
"""

from fastapi import APIRouter

from .core import router as core_router
from .database_health import router as database_router
from .service_health import router as service_router
from .storage_external import router as storage_router
from .metrics import router as metrics_router
from .platform import router as platform_router
from .monitoring import router as monitoring_router
from .test import router as test_router

# Import health check functions for backward compatibility
from .database_health import check_database_health
from .service_health import check_redis_health, check_worker_health, check_external_services
from .storage_external import check_storage_health
from .utils import calculate_health_score, determine_overall_status, APP_START_TIME


# Main router combining all sub-routers
router = APIRouter(prefix="/health", tags=["health-v2"])

# Include all sub-routers
router.include_router(core_router)
router.include_router(database_router)
router.include_router(service_router)
router.include_router(storage_router)
router.include_router(metrics_router)
router.include_router(platform_router)
router.include_router(monitoring_router)
router.include_router(test_router)


# Export commonly used functions for backward compatibility
__all__ = [
    "router",
    "check_database_health",
    "check_redis_health",
    "check_worker_health",
    "check_external_services",
    "check_storage_health",
    "calculate_health_score",
    "determine_overall_status",
    "APP_START_TIME",
]
