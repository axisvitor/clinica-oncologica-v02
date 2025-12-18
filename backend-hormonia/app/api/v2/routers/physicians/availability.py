"""
Availability and schedule endpoints for physicians.
"""

import logging
from uuid import UUID
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter

from .base import validate_physician_access
from .services import PhysicianAvailabilityService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/schedule",
    summary="Get physician schedule",
    description="""
    Get physician's schedule for a date range.

    **Features**:
    - List all appointments in date range
    - Filter by appointment status
    - View appointment details

    **Rate Limit**: 60 requests/minute
    """,
)
@limiter.limit("60/minute")
async def get_physician_schedule(
    request: Request,
    physician_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    start_date: date = Query(..., description="Schedule start date"),
    end_date: date = Query(..., description="Schedule end date"),
):
    """Get physician's schedule for a date range."""
    try:
        physician_uuid = UUID(physician_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid physician ID format",
        )

    # Validate access
    validate_physician_access(
        physician_uuid, current_user, db, allow_patient_view=False
    )

    # Get schedule
    availability_service = PhysicianAvailabilityService(db)
    schedule = availability_service.get_schedule(physician_uuid, start_date, end_date)

    return schedule


@router.get(
    "/availability",
    summary="Check physician availability",
    description="""
    Check if physician is available at a specific datetime.

    **Rate Limit**: 60 requests/minute
    """,
)
@limiter.limit("60/minute")
async def check_physician_availability(
    request: Request,
    physician_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    requested_datetime: datetime = Query(
        ..., description="Requested appointment datetime"
    ),
    duration_minutes: int = Query(
        30, ge=15, le=120, description="Appointment duration"
    ),
):
    """Check if physician is available at a specific datetime."""
    try:
        physician_uuid = UUID(physician_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid physician ID format",
        )

    # Validate access
    validate_physician_access(physician_uuid, current_user, db, allow_patient_view=True)

    # Check availability
    availability_service = PhysicianAvailabilityService(db)
    is_available = availability_service.is_available(
        physician_uuid, requested_datetime, duration_minutes
    )

    return {
        "physician_id": str(physician_uuid),
        "requested_datetime": requested_datetime.isoformat(),
        "duration_minutes": duration_minutes,
        "is_available": is_available,
    }


@router.get(
    "/next-available",
    summary="Get next available slot",
    description="""
    Find the next available appointment slot for a physician.

    **Rate Limit**: 60 requests/minute
    """,
)
@limiter.limit("60/minute")
async def get_next_available_slot(
    request: Request,
    physician_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_session),
    after_datetime: datetime = Query(None, description="Search after this datetime"),
    duration_minutes: int = Query(30, ge=15, le=120, description="Required duration"),
    max_days_ahead: int = Query(30, ge=1, le=90, description="Maximum days to search"),
):
    """Find the next available appointment slot."""
    try:
        physician_uuid = UUID(physician_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid physician ID format",
        )

    # Validate access
    validate_physician_access(physician_uuid, current_user, db, allow_patient_view=True)

    # Find next available slot
    availability_service = PhysicianAvailabilityService(db)
    next_slot = availability_service.get_next_available_slot(
        physician_uuid, after_datetime, duration_minutes, max_days_ahead
    )

    if next_slot is None:
        return {
            "physician_id": str(physician_uuid),
            "next_available": None,
            "message": f"No available slots found within {max_days_ahead} days",
        }

    return {
        "physician_id": str(physician_uuid),
        "next_available": next_slot.isoformat(),
        "duration_minutes": duration_minutes,
    }
