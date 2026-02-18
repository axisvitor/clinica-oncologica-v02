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
from datetime import datetime, timezone
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import func

from app.database import get_db
from app.models.user import UserRole, User
from app.models.patient import Patient
from app.schemas.v2.dashboard import (
    DashboardMainResponse,
    DashboardPatientResponse,
    DashboardPhysicianResponse,
    DashboardAdminResponse,
    CustomDashboardResponse,
    DashboardLayoutUpdate,
    TimeRangeEnum,
)
from app.api.v2.dependencies import (
    get_field_selection_async,
)
from app.dependencies.auth_dependencies import get_generic_cache, get_current_user_from_session
from app.utils.rate_limiter import limiter
from app.services.dashboard_service import DashboardService
from app.utils.timezone import now_sao_paulo

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configurations
CACHE_TTL_REALTIME = 120  # 2 minutes for real-time widgets


async def get_dashboard_service(db=Depends(get_db)) -> DashboardService:
    """Dependency to get DashboardService instance."""
    return DashboardService(db)



def _extract_user_role(current_user: Dict[str, Any]) -> Optional[UserRole]:
    """Extract UserRole enum from user data."""
    role_str = current_user.get("role", "").lower()
    try:
        return UserRole(role_str)
    except ValueError:
        return None


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
    fields: Optional[List[str]] = Depends(get_field_selection_async),
    db=Depends(get_db),
    redis_cache=Depends(get_generic_cache),
    current_user: Dict = Depends(get_current_user_from_session),
    service: DashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """
    Get main dashboard overview with key metrics and widgets.
    """
    try:
        role = _extract_user_role(current_user)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid user role for dashboard access",
            )
        user_id = UUID(current_user.get("id"))

        # Build cache key
        cache_key = f"dashboard:main:user:{user_id}:range:{time_range.value}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for main dashboard: {cache_key}")
            return cached_data

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
        # NOTE: These are executed sequentially because the SQLAlchemy session
        # is not thread-safe and cannot be shared across asyncio.to_thread calls.
        # Future optimization: use async SQLAlchemy or separate sessions per thread.
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
            "generated_at": now_sao_paulo().isoformat(),
        }

        # Cache the result
        await redis_cache.set(cache_key, response, ttl=CACHE_TTL_REALTIME)

        return response

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
    fields: Optional[List[str]] = Depends(get_field_selection_async),
    db=Depends(get_db),
    redis_cache=Depends(get_generic_cache),
    current_user: Dict = Depends(get_current_user_from_session),
    service: DashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """
    Get patient-specific dashboard with detailed health metrics.
    """
    try:
        role = _extract_user_role(current_user)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid user role for dashboard access",
            )
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
            return cached_data

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
            "full_name": patient.name,
            "email": getattr(patient, "email", None),
            "is_active": getattr(patient, "deleted_at", None) is None,
            "created_at": patient.created_at.isoformat() if patient.created_at else None,
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
            "generated_at": now_sao_paulo().isoformat(),
        }

        # Cache the result
        await redis_cache.set(cache_key, response, ttl=CACHE_TTL_REALTIME)

        return response

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
    fields: Optional[List[str]] = Depends(get_field_selection_async),
    db=Depends(get_db),
    redis_cache=Depends(get_generic_cache),
    current_user: Dict = Depends(get_current_user_from_session),
    service: DashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """
    Get physician-specific dashboard with practice metrics.
    """
    try:
        role = _extract_user_role(current_user)
        user_id = UUID(current_user.get("id"))
        if role not in {UserRole.DOCTOR, UserRole.ADMIN}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: physician dashboard only",
            )

        # Build cache key
        cache_key = f"dashboard:physician:{user_id}:range:{time_range.value}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for physician dashboard: {cache_key}")
            return cached_data

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
            "generated_at": now_sao_paulo().isoformat(),
        }

        # Cache the result
        await redis_cache.set(cache_key, response, ttl=CACHE_TTL_REALTIME)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching physician dashboard: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve physician dashboard",
        )


@router.get("/admin", response_model=DashboardAdminResponse)
@limiter.limit("60/minute")
async def get_admin_dashboard(
    request: Request,
    time_range: TimeRangeEnum = Query(
        TimeRangeEnum.MONTH, description="Time range for metrics"
    ),
    custom_start: Optional[datetime] = Query(None, description="Custom start date"),
    custom_end: Optional[datetime] = Query(None, description="Custom end date"),
    db=Depends(get_db),
    redis_cache=Depends(get_generic_cache),
    current_user: Dict = Depends(get_current_user_from_session),
    service: DashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """Get system-wide admin dashboard."""
    role = _extract_user_role(current_user)
    if role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    start_date, end_date = service.calculate_date_range(time_range, custom_start, custom_end)
    cache_key = f"dashboard:admin:range:{time_range.value}"
    cached_data = await redis_cache.get(cache_key)
    if cached_data:
        return cached_data

    patient_metrics = service.get_patient_metrics(None, start_date, end_date)
    message_metrics = service.get_message_metrics(None, start_date, end_date)
    alert_metrics = service.get_alert_metrics(None, start_date, end_date)
    flow_metrics = service.get_flow_metrics(None, start_date, end_date)

    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active.is_(True)).count()
    doctors_count = db.query(User).filter(User.role == UserRole.DOCTOR).count()
    admins_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
    patients_count = db.query(Patient).count()

    top_physicians_rows = (
        db.query(
            User.id.label("physician_id"),
            User.full_name.label("physician_name"),
            func.count(Patient.id).label("patient_count"),
        )
        .outerjoin(Patient, Patient.doctor_id == User.id)
        .filter(User.role == UserRole.DOCTOR)
        .group_by(User.id, User.full_name)
        .order_by(func.count(Patient.id).desc())
        .limit(5)
        .all()
    )
    top_physicians = [
        {
            "physician_id": str(row.physician_id),
            "physician_name": row.physician_name or "Unknown",
            "patient_count": int(row.patient_count or 0),
            "message_count": int(message_metrics.get("total_messages", 0)),
            "engagement_rate": float(message_metrics.get("response_rate", 0)),
        }
        for row in top_physicians_rows
    ]

    system_health = {
        "message_success_rate": round(
            ((message_metrics.get("sent_count", 0) - message_metrics.get("failed_count", 0))
             / message_metrics.get("sent_count", 1))
            * 100,
            1,
        )
        if message_metrics.get("sent_count", 0) > 0
        else 0.0,
        "alert_response_rate": round(
            (alert_metrics.get("acknowledged_alerts", 0) / alert_metrics.get("total_alerts", 1))
            * 100,
            1,
        )
        if alert_metrics.get("total_alerts", 0) > 0
        else 0.0,
        "flow_completion_rate": float(flow_metrics.get("completion_rate", 0)),
        "patient_active_rate": round(
            (patient_metrics.get("active_patients", 0) / patient_metrics.get("total_patients", 1))
            * 100,
            1,
        )
        if patient_metrics.get("total_patients", 0) > 0
        else 0.0,
    }

    response = {
        "time_range": time_range.value,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "patient_metrics": patient_metrics,
        "message_metrics": message_metrics,
        "alert_metrics": alert_metrics,
        "flow_metrics": flow_metrics,
        "user_metrics": {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": max(total_users - active_users, 0),
            "doctors_count": doctors_count,
            "patients_count": patients_count,
            "admins_count": admins_count,
        },
        "top_physicians": top_physicians,
        "system_health": system_health,
        "generated_at": now_sao_paulo().isoformat(),
    }
    await redis_cache.set(cache_key, response, ttl=CACHE_TTL_REALTIME)
    return response


@router.get("/custom/{dashboard_id}", response_model=CustomDashboardResponse)
@limiter.limit("30/minute")
async def get_custom_dashboard(
    dashboard_id: UUID,
    request: Request,
    current_user: Dict = Depends(get_current_user_from_session),
) -> Dict[str, Any]:
    """Return custom dashboard layout placeholder."""
    return {
        "dashboard_id": str(dashboard_id),
        "user_id": str(current_user.get("id")),
        "name": "My Dashboard",
        "description": "Custom dashboard layout",
        "widgets": [],
        "layout": {"columns": 4, "row_height": 120},
        "created_at": now_sao_paulo().isoformat(),
        "updated_at": now_sao_paulo().isoformat(),
    }


@router.put("/custom/{dashboard_id}/layout", response_model=CustomDashboardResponse)
@limiter.limit("30/minute")
async def update_custom_dashboard_layout(
    dashboard_id: UUID,
    payload: DashboardLayoutUpdate,
    request: Request,
    current_user: Dict = Depends(get_current_user_from_session),
) -> Dict[str, Any]:
    """Update custom dashboard layout placeholder."""
    return {
        "dashboard_id": str(dashboard_id),
        "user_id": str(current_user.get("id")),
        "name": payload.name or "My Dashboard",
        "description": payload.description or "Custom dashboard layout",
        "widgets": payload.widgets or [],
        "layout": payload.layout or {"columns": 4, "row_height": 120},
        "created_at": now_sao_paulo().isoformat(),
        "updated_at": now_sao_paulo().isoformat(),
    }
