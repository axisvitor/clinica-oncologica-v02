"""
Physicians API v2
Enhanced physician endpoints with statistics, workload tracking, and patient assignments.

This module provides:
- List physicians with filtering (specialty, status, workload)
- Get physician profile with comprehensive statistics
- Update physician information (Admin only)

Features:
- Cursor-based pagination
- Redis caching (list: 30min, profile: 15min, stats: 10min)
- Rate limiting (60 req/min)
- Field selection (?fields=id,name,email)
- Eager loading (?include=statistics,patients)
- RBAC enforcement (Admin, Physician, Patient roles)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, date, time
from uuid import UUID
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, case, or_

from app.database import get_db
from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState
from app.models.message import Message, MessageDirection, MessageStatus
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.schemas.v2.physicians import (
    PhysicianResponse,
    PhysicianList,
    PhysicianUpdate,
    PhysicianStatistics,
    PhysicianStatus,
    WorkloadLevel,
    Specialty,
    MessageStats,
    AppointmentStats,
    AlertStats,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter
from app.core.redis_unified import get_sync_redis

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def _extract_user_context(current_user) -> tuple[Optional[UserRole], Optional[str]]:
    """Extract role and user_id from current_user (dict or model)."""
    role = None
    user_id = None

    if isinstance(current_user, dict):
        role = current_user.get("role")
        user_id = current_user.get("id")
    else:
        user_id = getattr(current_user, "id", None)
        role = getattr(current_user, "role", None)

    if isinstance(role, UserRole):
        role_enum = role
    elif isinstance(role, str):
        try:
            role_enum = UserRole(role.lower())
        except ValueError:
            role_enum = None
    else:
        role_enum = None

    if user_id is not None:
        user_id = str(user_id)

    return role_enum, user_id


def _is_admin(current_user) -> bool:
    """Check if current user is admin."""
    role_enum, _ = _extract_user_context(current_user)
    return role_enum == UserRole.ADMIN


def _calculate_workload_level(patient_count: int) -> WorkloadLevel:
    """
    Calculate workload level based on patient count.

    Args:
        patient_count: Number of assigned patients

    Returns:
        WorkloadLevel enum value
    """
    if patient_count == 0:
        return WorkloadLevel.LOW
    elif patient_count <= 20:
        return WorkloadLevel.LOW
    elif patient_count <= 50:
        return WorkloadLevel.MEDIUM
    elif patient_count <= 100:
        return WorkloadLevel.HIGH
    else:
        return WorkloadLevel.OVERLOADED


def _calculate_physician_statistics(
    db: Session,
    physician_id: UUID,
    cache_ttl: int = 600
) -> PhysicianStatistics:
    """
    Calculate comprehensive statistics for a physician.

    Args:
        db: Database session
        physician_id: Physician UUID
        cache_ttl: Cache TTL in seconds (default 10 minutes)

    Returns:
        PhysicianStatistics model with all metrics
    """
    # Check Redis cache first
    cache_key = f"physician:stats:{physician_id}"
    try:
        redis_client = get_sync_redis()
        if redis_client:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache HIT for physician {physician_id} statistics")
                stats_dict = json.loads(cached_data)
                return PhysicianStatistics(**stats_dict)
    except Exception as e:
        logger.warning(f"Redis cache error: {e}")

    logger.info(f"Calculating statistics for physician {physician_id}")

    # Patient metrics
    total_patients = db.query(Patient).filter(
        Patient.doctor_id == physician_id,
        Patient.deleted_at.is_(None)
    ).count()

    active_patients = db.query(Patient).filter(
        Patient.doctor_id == physician_id,
        Patient.flow_state == FlowState.ACTIVE,
        Patient.deleted_at.is_(None)
    ).count()

    inactive_patients = db.query(Patient).filter(
        Patient.doctor_id == physician_id,
        Patient.flow_state == FlowState.CANCELLED,
        Patient.deleted_at.is_(None)
    ).count()

    # New patients this month
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_patients_this_month = db.query(Patient).filter(
        Patient.doctor_id == physician_id,
        Patient.created_at >= start_of_month,
        Patient.deleted_at.is_(None)
    ).count()

    # Workload level
    workload_level = _calculate_workload_level(total_patients)

    # Message statistics
    today_start = datetime.combine(date.today(), time.min)
    today_end = datetime.combine(date.today(), time.max)
    week_ago = datetime.utcnow() - timedelta(days=7)

    patient_ids = db.query(Patient.id).filter(
        Patient.doctor_id == physician_id,
        Patient.deleted_at.is_(None)
    ).subquery()

    # Messages sent (outbound)
    total_sent = db.query(Message).filter(
        Message.patient_id.in_(patient_ids),
        Message.direction == MessageDirection.OUTBOUND
    ).count()

    # Messages received (inbound)
    total_received = db.query(Message).filter(
        Message.patient_id.in_(patient_ids),
        Message.direction == MessageDirection.INBOUND
    ).count()

    # Unread messages
    unread_count = db.query(Message).filter(
        Message.patient_id.in_(patient_ids),
        Message.direction == MessageDirection.INBOUND,
        Message.status.notin_([MessageStatus.READ])
    ).count()

    # Response rate (last 7 days)
    inbound_count = db.query(Message).filter(
        Message.patient_id.in_(patient_ids),
        Message.direction == MessageDirection.INBOUND,
        Message.created_at >= week_ago
    ).count()

    read_count = db.query(Message).filter(
        Message.patient_id.in_(patient_ids),
        Message.direction == MessageDirection.INBOUND,
        Message.status == MessageStatus.READ,
        Message.created_at >= week_ago
    ).count()

    response_rate = (read_count / inbound_count) if inbound_count > 0 else 0.0

    message_stats = MessageStats(
        total_sent=total_sent,
        total_received=total_received,
        unread_count=unread_count,
        response_rate=round(response_rate, 2),
        avg_response_time_minutes=None  # TODO: Implement with message threading
    )

    # Appointment statistics (placeholder - TODO: implement when appointments table available)
    appointment_stats = AppointmentStats(
        total_scheduled=0,
        completed=0,
        cancelled=0,
        upcoming=0,
        today=0
    )

    # Alert statistics
    alert_counts = db.query(
        func.count(Alert.id).label('total'),
        func.sum(case((Alert.severity == AlertSeverity.CRITICAL, 1), else_=0)).label('critical'),
        func.sum(case((Alert.severity == AlertSeverity.HIGH, 1), else_=0)).label('high'),
        func.sum(case((Alert.severity == AlertSeverity.MEDIUM, 1), else_=0)).label('medium'),
        func.sum(case((Alert.severity == AlertSeverity.LOW, 1), else_=0)).label('low')
    ).filter(
        Alert.patient_id.in_(patient_ids),
        Alert.status.in_([AlertStatus.PENDING, AlertStatus.ACTIVE])
    ).first()

    alert_stats = AlertStats(
        total=alert_counts.total or 0,
        critical=alert_counts.critical or 0,
        high=alert_counts.high or 0,
        medium=alert_counts.medium or 0,
        low=alert_counts.low or 0
    )

    # Build statistics object
    statistics = PhysicianStatistics(
        total_patients=total_patients,
        active_patients=active_patients,
        inactive_patients=inactive_patients,
        new_patients_this_month=new_patients_this_month,
        workload_level=workload_level,
        messages=message_stats,
        appointments=appointment_stats,
        alerts=alert_stats,
        patient_satisfaction_score=None,  # TODO: Implement patient satisfaction
        avg_treatment_duration_days=None,  # TODO: Calculate from treatment data
        calculated_at=datetime.utcnow()
    )

    # Cache in Redis
    try:
        redis_client = get_sync_redis()
        if redis_client:
            redis_client.setex(
                cache_key,
                cache_ttl,
                statistics.model_dump_json()
            )
            logger.info(f"Cached statistics for physician {physician_id} (TTL: {cache_ttl}s)")
    except Exception as e:
        logger.warning(f"Failed to cache statistics: {e}")

    return statistics


def _serialize_physician(
    physician: User,
    db: Session,
    include_statistics: bool = False
) -> Dict[str, Any]:
    """
    Serialize physician User model to API response dict.

    Args:
        physician: User model instance
        db: Database session
        include_statistics: Whether to include detailed statistics

    Returns:
        Dictionary with physician data
    """
    # Count assigned patients
    total_patients = db.query(Patient).filter(
        Patient.doctor_id == physician.id,
        Patient.deleted_at.is_(None)
    ).count()

    active_patients = db.query(Patient).filter(
        Patient.doctor_id == physician.id,
        Patient.flow_state == FlowState.ACTIVE,
        Patient.deleted_at.is_(None)
    ).count()

    workload_level = _calculate_workload_level(total_patients)

    # Get specialties from Firebase custom claims or metadata
    specialties = []
    if physician.firebase_custom_claims and isinstance(physician.firebase_custom_claims, dict):
        specialties = physician.firebase_custom_claims.get("specialties", [])

    # Get status (default to active if user is active)
    status = PhysicianStatus.ACTIVE if physician.is_active else PhysicianStatus.INACTIVE

    # Base response
    response = {
        "id": str(physician.id),
        "email": physician.email,
        "full_name": physician.full_name or physician.firebase_display_name,
        "role": physician.role.value if hasattr(physician.role, 'value') else str(physician.role),
        "is_active": physician.is_active,
        "firebase_uid": physician.firebase_uid,
        "firebase_email_verified": physician.firebase_email_verified,
        "firebase_display_name": physician.firebase_display_name,
        "firebase_photo_url": physician.firebase_photo_url,
        "specialties": specialties,
        "status": status.value,
        "license_number": physician.firebase_custom_claims.get("license_number") if physician.firebase_custom_claims else None,
        "phone": physician.firebase_custom_claims.get("phone") if physician.firebase_custom_claims else None,
        "bio": physician.firebase_custom_claims.get("bio") if physician.firebase_custom_claims else None,
        "assigned_patients_count": total_patients,
        "active_patients_count": active_patients,
        "workload_level": workload_level.value,
        "created_at": physician.created_at,
        "updated_at": physician.updated_at,
        "last_login": physician.firebase_last_sign_in,
    }

    # Add statistics if requested
    if include_statistics:
        statistics = _calculate_physician_statistics(db, physician.id)
        response["statistics"] = statistics.model_dump()

    return response


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "",
    response_model=PhysicianList,
    summary="List physicians with filtering",
    description="""
    Get paginated list of physicians with optional filtering and statistics.

    **Features**:
    - Cursor-based pagination for efficient large datasets
    - Filter by specialty, status, workload level
    - Search by name or email
    - Field selection (?fields=id,email,full_name)
    - Eager loading statistics (?include=statistics)

    **RBAC**:
    - Admin: View all physicians
    - Physician: View self and colleagues
    - Patient: View assigned physician

    **Caching**: 30 minutes Redis cache
    **Rate Limit**: 60 requests/minute
    """
)
@limiter.limit("60/minute")
async def list_physicians(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    pagination = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    # Filters
    specialty: Optional[Specialty] = Query(None, description="Filter by specialty"),
    status: Optional[PhysicianStatus] = Query(None, description="Filter by status"),
    workload: Optional[WorkloadLevel] = Query(None, description="Filter by workload level"),
    min_patients: Optional[int] = Query(None, ge=0, description="Minimum patient count"),
    max_patients: Optional[int] = Query(None, ge=0, description="Maximum patient count"),
    search: Optional[str] = Query(None, description="Search by name or email"),
):
    """List physicians with cursor pagination and filtering."""
    cursor_data = pagination["cursor_data"]
    limit = pagination["limit"]

    # Check cache for list (without statistics)
    cache_key = f"physicians:list:{specialty}:{status}:{workload}:{min_patients}:{max_patients}:{search}:{limit}:{cursor_data}"
    try:
        redis_client = get_sync_redis()
        if redis_client and not include:  # Only cache simple lists
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info("Cache HIT for physicians list")
                return json.loads(cached_data)
    except Exception as e:
        logger.warning(f"Redis cache error: {e}")

    # Build query
    query = db.query(User).filter(User.role == UserRole.DOCTOR)

    # Apply RBAC
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        # Non-admin users can only see active physicians
        query = query.filter(User.is_active == True)

    # Apply cursor pagination
    if cursor_data and "id" in cursor_data:
        cursor_id = UUID(cursor_data["id"]) if isinstance(cursor_data["id"], str) else cursor_data["id"]
        cursor_created_at = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))

        query = query.filter(
            (User.created_at < cursor_created_at) |
            ((User.created_at == cursor_created_at) & (User.id > cursor_id))
        )

    # Apply search filter
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_filter),
                User.email.ilike(search_filter),
                User.firebase_display_name.ilike(search_filter)
            )
        )

    # Apply is_active filter for status
    if status == PhysicianStatus.INACTIVE:
        query = query.filter(User.is_active == False)
    elif status == PhysicianStatus.ACTIVE:
        query = query.filter(User.is_active == True)

    # Get total count (only on first page)
    total = None
    if not cursor_data:
        total = query.count()

    # Order and fetch
    query = query.order_by(User.created_at.desc(), User.id)
    physicians = query.limit(limit + 1).all()

    # Check for more results
    has_more = len(physicians) > limit
    if has_more:
        physicians = physicians[:limit]

    # Create next cursor
    next_cursor = None
    if has_more and physicians:
        import base64
        cursor_data = {
            "id": str(physicians[-1].id),
            "created_at": physicians[-1].created_at.isoformat()
        }
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    # Serialize physicians
    include_statistics = include and "statistics" in include
    physician_responses = []

    for physician in physicians:
        physician_dict = _serialize_physician(physician, db, include_statistics)

        # Apply field selection
        if fields:
            physician_dict = apply_field_selection(physician_dict, fields)

        physician_responses.append(physician_dict)

    # Apply post-query filters (specialty, workload, patient counts)
    if specialty or workload or min_patients is not None or max_patients is not None:
        filtered_responses = []
        for p in physician_responses:
            # Filter by specialty
            if specialty and specialty.value not in p.get("specialties", []):
                continue

            # Filter by workload
            if workload and p.get("workload_level") != workload.value:
                continue

            # Filter by patient count
            patient_count = p.get("assigned_patients_count", 0)
            if min_patients is not None and patient_count < min_patients:
                continue
            if max_patients is not None and patient_count > max_patients:
                continue

            filtered_responses.append(p)

        physician_responses = filtered_responses

    response = {
        "data": physician_responses,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }

    # Cache the response (30 minutes)
    try:
        redis_client = get_sync_redis()
        if redis_client and not include:
            redis_client.setex(
                cache_key,
                1800,  # 30 minutes
                json.dumps(response, default=str)
            )
            logger.info("Cached physicians list (TTL: 30min)")
    except Exception as e:
        logger.warning(f"Failed to cache list: {e}")

    return response


@router.get(
    "/{physician_id}",
    response_model=PhysicianResponse,
    summary="Get physician profile by ID",
    description="""
    Get detailed physician profile with optional statistics.

    **Features**:
    - Complete physician information
    - Patient assignment counts
    - Optional detailed statistics (?include=statistics)
    - Field selection support

    **RBAC**:
    - Admin: View any physician
    - Physician: View self
    - Patient: View assigned physician

    **Caching**: 15 minutes Redis cache
    **Rate Limit**: 60 requests/minute
    """
)
@limiter.limit("60/minute")
async def get_physician(
    request: Request,
    physician_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
):
    """Get physician by ID with optional statistics."""
    try:
        physician_uuid = UUID(physician_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid physician ID format"
        )

    # Check cache
    cache_key = f"physician:profile:{physician_id}:{include}"
    try:
        redis_client = get_sync_redis()
        if redis_client:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache HIT for physician {physician_id}")
                return json.loads(cached_data)
    except Exception as e:
        logger.warning(f"Redis cache error: {e}")

    # Fetch physician
    physician = db.query(User).filter(
        User.id == physician_uuid,
        User.role == UserRole.DOCTOR
    ).first()

    if not physician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physician with id {physician_id} not found"
        )

    # RBAC: Check access
    role_enum, user_id = _extract_user_context(current_user)
    if role_enum != UserRole.ADMIN:
        # Physicians can view themselves
        if str(physician.id) != user_id:
            # Patients can view their assigned physician
            # TODO: Implement patient-physician relationship check
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this physician"
            )

    # Serialize physician
    include_statistics = include and "statistics" in include
    physician_dict = _serialize_physician(physician, db, include_statistics)

    # Apply field selection
    if fields:
        physician_dict = apply_field_selection(physician_dict, fields)

    # Cache the response (15 minutes)
    try:
        redis_client = get_sync_redis()
        if redis_client:
            redis_client.setex(
                cache_key,
                900,  # 15 minutes
                json.dumps(physician_dict, default=str)
            )
            logger.info(f"Cached physician {physician_id} (TTL: 15min)")
    except Exception as e:
        logger.warning(f"Failed to cache profile: {e}")

    return physician_dict


@router.patch(
    "/{physician_id}",
    response_model=PhysicianResponse,
    summary="Update physician information",
    description="""
    Update physician profile information (Admin only).

    **Features**:
    - Partial updates (only provided fields)
    - Update specialties, status, contact info
    - Automatic cache invalidation

    **RBAC**: Admin only

    **Rate Limit**: 60 requests/minute
    """
)
@limiter.limit("60/minute")
async def update_physician(
    request: Request,
    physician_id: str,
    update_data: PhysicianUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """Update physician information (Admin only)."""
    # RBAC: Admin only
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update physician information"
        )

    try:
        physician_uuid = UUID(physician_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid physician ID format"
        )

    # Fetch physician
    physician = db.query(User).filter(
        User.id == physician_uuid,
        User.role == UserRole.DOCTOR
    ).first()

    if not physician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physician with id {physician_id} not found"
        )

    # Apply updates
    update_dict = update_data.model_dump(exclude_unset=True)

    # Update direct User fields
    if "full_name" in update_dict:
        physician.full_name = update_dict["full_name"]

    if "is_active" in update_dict:
        physician.is_active = update_dict["is_active"]

    # Update Firebase custom claims for other fields
    if not physician.firebase_custom_claims:
        physician.firebase_custom_claims = {}

    if "specialties" in update_dict:
        physician.firebase_custom_claims["specialties"] = [
            s.value if isinstance(s, Specialty) else s
            for s in update_dict["specialties"]
        ]

    if "status" in update_dict:
        status_value = update_dict["status"]
        if isinstance(status_value, PhysicianStatus):
            status_value = status_value.value
        physician.firebase_custom_claims["status"] = status_value

        # Sync is_active with status
        physician.is_active = (status_value == PhysicianStatus.ACTIVE.value)

    if "license_number" in update_dict:
        physician.firebase_custom_claims["license_number"] = update_dict["license_number"]

    if "phone" in update_dict:
        physician.firebase_custom_claims["phone"] = update_dict["phone"]

    if "bio" in update_dict:
        physician.firebase_custom_claims["bio"] = update_dict["bio"]

    # Commit changes
    db.commit()
    db.refresh(physician)

    # Invalidate cache
    try:
        redis_client = get_sync_redis()
        if redis_client:
            # Invalidate profile cache
            cache_pattern = f"physician:profile:{physician_id}:*"
            redis_client.delete(cache_pattern)
            # Invalidate statistics cache
            stats_cache = f"physician:stats:{physician_id}"
            redis_client.delete(stats_cache)
            # Invalidate list cache (simple invalidation)
            list_pattern = "physicians:list:*"
            redis_client.delete(list_pattern)
            logger.info(f"Invalidated caches for physician {physician_id}")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

    # Return updated physician
    physician_dict = _serialize_physician(physician, db, include_statistics=False)
    return physician_dict
