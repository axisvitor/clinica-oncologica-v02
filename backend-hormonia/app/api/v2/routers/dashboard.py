"""
Dashboard API v2 - Real-time Dashboard and Widgets System

Enhanced dashboard endpoints with:
- NO pagination (dashboard widgets return aggregated data)
- Redis caching with optimized TTLs
- Rate limiting
- RBAC
- Separated Service Logic
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Header

from app.database import get_db
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.dashboard import (
    DashboardMainResponse,
    DashboardPatientResponse,
    DashboardPhysicianResponse,
    TimeRangeEnum,
)
from app.api.v2.dependencies import (
    get_field_selection,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter
from app.services.dashboard_service import DashboardService

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configurations
CACHE_TTL_REALTIME = 120  # 2 minutes for real-time widgets


def get_dashboard_service(db=Depends(get_db)) -> DashboardService:
    """Dependency to get DashboardService instance."""
    return DashboardService(db)


async def _get_current_user_simple(
    session_id: str = Header(None, alias="X-Session-ID"),
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
) -> Dict[str, Any]:
    """Simplified session validation for V2 endpoints."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided in X-Session-ID header",
        )

    session_data = await redis_cache.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session data"
        )

    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "is_active": user.is_active,
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )

    return user_data


def _extract_user_role(current_user: Dict[str, Any]) -> UserRole:
    """Extract UserRole enum from user data."""
    role_str = current_user.get("role", "").lower()
    try:
        return UserRole(role_str)
    except ValueError:
        return UserRole.DOCTOR


@router.get("/main", response_model=DashboardMainResponse)
@limiter.limit("30/minute")
async def get_main_dashboard(
    request: Request,
    time_range: TimeRangeEnum = Query(
        TimeRangeEnum.WEEK, description="Time range for metrics"
    ),
    custom_start: Optional[datetime] = Query(
        None, description="Custom start date (for CUSTOM range)"
    ),
    custom_end: Optional[datetime] = Query(
        None, description="Custom end date (for CUSTOM range)"
    ),
    fields: Optional[List[str]] = Depends(get_field_selection),
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
    service: DashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """
    Get main dashboard overview with key metrics and widgets.
    """
    try:
        role = _extract_user_role(current_user)
        user_id = UUID(current_user.get("id"))

        # Build cache key
        cache_key = f"dashboard:main:user:{user_id}:range:{time_range.value}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for main dashboard: {cache_key}")
            return apply_field_selection(cached_data, fields) if fields else cached_data

        # Calculate date range
        start_date, end_date = service.calculate_date_range(
            time_range, custom_start, custom_end
        )

        # Determine patient scope based on role
        patient_ids = None
        if role == UserRole.DOCTOR:
            # Get doctor's patients
            patient_ids = [
                p.id
                for p in db.query(Patient.id).filter(Patient.doctor_id == user_id).all()
            ]

        # Fetch all metrics using service
        patient_metrics = service.get_patient_metrics(patient_ids, start_date, end_date)
        message_metrics = service.get_message_metrics(patient_ids, start_date, end_date)
        alert_metrics = service.get_alert_metrics(patient_ids, start_date, end_date)
        flow_metrics = service.get_flow_metrics(patient_ids, start_date, end_date)
        recent_activity = service.get_recent_activity(patient_ids, limit=10)

        # Build response
        response = {
            "user_role": role.value,
            "time_range": time_range.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "patient_metrics": patient_metrics,
            "message_metrics": message_metrics,
            "alert_metrics": alert_metrics,
            "flow_metrics": flow_metrics,
            "recent_activity": recent_activity,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Cache the result
        await redis_cache.set(cache_key, response, ttl=CACHE_TTL_REALTIME)

        return apply_field_selection(response, fields) if fields else response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching main dashboard: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve main dashboard",
        )


@router.get("/patient/{patient_id}", response_model=DashboardPatientResponse)
@limiter.limit("30/minute")
async def get_patient_dashboard(
    patient_id: UUID,
    request: Request,
    time_range: TimeRangeEnum = Query(
        TimeRangeEnum.MONTH, description="Time range for metrics"
    ),
    custom_start: Optional[datetime] = Query(None, description="Custom start date"),
    custom_end: Optional[datetime] = Query(None, description="Custom end date"),
    fields: Optional[List[str]] = Depends(get_field_selection),
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
    service: DashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """
    Get patient-specific dashboard with detailed health metrics.
    """
    try:
        role = _extract_user_role(current_user)
        user_id = UUID(current_user.get("id"))

        # Verify patient exists
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
            )

        # Check access
        if role == UserRole.DOCTOR and patient.doctor_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Not your patient",
            )

        # Build cache key
        cache_key = f"dashboard:patient:{patient_id}:range:{time_range.value}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for patient dashboard: {cache_key}")
            return apply_field_selection(cached_data, fields) if fields else cached_data

        # Calculate date range
        start_date, end_date = service.calculate_date_range(
            time_range, custom_start, custom_end
        )

        # Fetch patient-specific metrics
        message_metrics = service.get_message_metrics(
            [patient_id], start_date, end_date
        )
        alert_metrics = service.get_alert_metrics([patient_id], start_date, end_date)
        flow_metrics = service.get_flow_metrics([patient_id], start_date, end_date)
        recent_activity = service.get_recent_activity([patient_id], limit=15)
        engagement_data = service.get_engagement_chart_data([patient_id], days=30)

        # Patient info
        patient_info = {
            "id": str(patient.id),
            "full_name": patient.full_name,
            "email": patient.email,
            "is_active": patient.is_active,
            "created_at": patient.created_at.isoformat()
            if patient.created_at
            else None,
        }

        # Build response
        response = {
            "patient": patient_info,
            "time_range": time_range.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "message_metrics": message_metrics,
            "alert_metrics": alert_metrics,
            "flow_metrics": flow_metrics,
            "recent_activity": recent_activity,
            "engagement_chart": engagement_data,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Cache the result
        await redis_cache.set(cache_key, response, ttl=CACHE_TTL_REALTIME)

        return apply_field_selection(response, fields) if fields else response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching patient dashboard for {patient_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient dashboard",
        )


@router.get("/physician", response_model=DashboardPhysicianResponse)
@limiter.limit("30/minute")
async def get_physician_dashboard(
    request: Request,
    time_range: TimeRangeEnum = Query(
        TimeRangeEnum.WEEK, description="Time range for metrics"
    ),
    custom_start: Optional[datetime] = Query(None, description="Custom start date"),
    custom_end: Optional[datetime] = Query(None, description="Custom end date"),
    fields: Optional[List[str]] = Depends(get_field_selection),
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
    service: DashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """
    Get physician-specific dashboard with practice metrics.
    """
    try:
        role = _extract_user_role(current_user)
        user_id = UUID(current_user.get("id"))

        # Build cache key
        cache_key = f"dashboard:physician:{user_id}:range:{time_range.value}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for physician dashboard: {cache_key}")
            return apply_field_selection(cached_data, fields) if fields else cached_data

        # Calculate date range
        start_date, end_date = service.calculate_date_range(
            time_range, custom_start, custom_end
        )

        # Get physician's patients
        patient_ids = None
        if role == UserRole.DOCTOR:
            patient_ids = [
                p.id
                for p in db.query(Patient.id).filter(Patient.doctor_id == user_id).all()
            ]

        # Fetch metrics
        patient_metrics = service.get_patient_metrics(patient_ids, start_date, end_date)
        message_metrics = service.get_message_metrics(patient_ids, start_date, end_date)
        alert_metrics = service.get_alert_metrics(patient_ids, start_date, end_date)
        flow_metrics = service.get_flow_metrics(patient_ids, start_date, end_date)

        # Stub data for now as they weren't fully implemented in original file
        high_priority_alerts = []
        top_risk_patients = []

        response = {
            "user_id": str(user_id),
            "time_range": time_range.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "patient_metrics": patient_metrics,
            "message_metrics": message_metrics,
            "alert_metrics": alert_metrics,
            "flow_metrics": flow_metrics,
            "high_priority_alerts": high_priority_alerts,
            "top_risk_patients": top_risk_patients,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Cache the result
        await redis_cache.set(cache_key, response, ttl=CACHE_TTL_REALTIME)

        return apply_field_selection(response, fields) if fields else response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching physician dashboard: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve physician dashboard",
        )
