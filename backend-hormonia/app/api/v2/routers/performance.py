"""
Performance Monitoring API v2
Unified performance monitoring system consolidating cache, database health, and optimization.
Delegates logic to PerformanceService.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
# from sqlalchemy.orm import Session,

from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.models.user import User, UserRole
from app.schemas.v2.performance import (
    CacheMetrics,
    PerformanceOverview,
    DatabaseHealth,
    VacuumRequest,
    VacuumResponse
)
from app.services.performance_service import PerformanceService
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

def get_performance_service(db = Depends(get_db)) -> PerformanceService:
    return PerformanceService(db)

def _check_admin_role(current_user: User) -> None:
    """Check if user has admin role."""
    if isinstance(current_user, dict):
        role = current_user.get("role", "").upper()
    else:
        role = getattr(current_user, "role", "").upper() if hasattr(current_user, "role") else ""

    if role != "ADMIN" and role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

@router.get(
    "/cache/metrics",
    response_model=CacheMetrics,
    summary="Get cache performance metrics"
)
async def get_cache_metrics(
    current_user: User = Depends(get_current_user_from_session),
    service: PerformanceService = Depends(get_performance_service)
) -> CacheMetrics:
    return await service.get_cache_metrics(getattr(current_user, 'id', 'unknown'))

@router.get(
    "/overview",
    response_model=PerformanceOverview,
    summary="Get overall performance overview"
)
async def get_performance_overview(
    current_user: User = Depends(get_current_user_from_session),
    service: PerformanceService = Depends(get_performance_service)
) -> PerformanceOverview:
    return await service.get_performance_overview()

@router.get(
    "/database/health",
    response_model=DatabaseHealth,
    summary="Get database health status"
)
async def get_database_health(
    current_user: User = Depends(get_current_user_from_session),
    service: PerformanceService = Depends(get_performance_service)
) -> DatabaseHealth:
    return await service.get_database_health()

@router.post(
    "/database/vacuum",
    response_model=VacuumResponse,
    summary="Run VACUUM operation"
)
async def run_vacuum(
    request: VacuumRequest,
    current_user: User = Depends(get_current_user_from_session),
    service: PerformanceService = Depends(get_performance_service)
) -> VacuumResponse:
    _check_admin_role(current_user)
    return await service.run_vacuum(request, getattr(current_user, 'id', 'unknown'))
