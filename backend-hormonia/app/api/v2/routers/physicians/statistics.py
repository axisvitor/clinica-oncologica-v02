"""
Statistics endpoints for physicians.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.async_engine import get_async_db
from app.schemas.v2.physicians import PhysicianStatistics
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter

from .base import validate_physician_access
from .services import PhysicianStatisticsService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/statistics",
    response_model=PhysicianStatistics,
    summary="Get physician statistics",
    description="""
    Get comprehensive statistics for a physician.

    **Features**:
    - Patient metrics (total, active, inactive)
    - Message statistics (sent, received, response rate)
    - Appointment statistics
    - Alert statistics
    - Patient satisfaction score
    - Average treatment duration

    **Caching**: 5 minutes Redis cache
    **Rate Limit**: 60 requests/minute
    """,
)
@limiter.limit("60/minute")
async def get_physician_statistics(
    request: Request,
    physician_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user_from_session),
    use_cache: bool = True,
):
    """Get detailed statistics for a physician."""
    try:
        physician_uuid = UUID(physician_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid physician ID format",
        )

    # Validate access
    await validate_physician_access(physician_uuid, current_user, db, allow_patient_view=True)

    # Calculate statistics
    stats_service = PhysicianStatisticsService(db)
    statistics = await stats_service.calculate_statistics(
        physician_uuid, use_cache=use_cache
    )

    return statistics
