"""
Platform-Specific Health Check Module

Provides Railway, production, and environment health checks.
"""

import os
import logging
from datetime import datetime

from fastapi import APIRouter, Depends

from app.dependencies.auth_dependencies import get_current_user
from app.models.user import User
from app.schemas.v2.health import (
    RailwayHealth,
    ProductionHealth,
    EnvironmentHealth,
    HealthStatus,
)
from app.config import settings


logger = logging.getLogger(__name__)
router = APIRouter()


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
