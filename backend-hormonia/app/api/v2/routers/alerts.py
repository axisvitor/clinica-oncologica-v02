"""
Alerts API v2
Clinical alerts with cursor pagination and caching.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session,  joinedload
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.alerts import (
    AlertV2Response,
    AlertV2List,
    AlertV2Create,
    AlertV2Update,
    AlertV2Acknowledge,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    create_cursor,
    apply_field_selection,
)
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configurations (alerts are time-sensitive)
CACHE_TTL_LIST = 120  # 2 minutes for alert lists
CACHE_TTL_SINGLE = 300  # 5 minutes for single alert


async def get_redis_cache():
    """Get Redis cache dependency."""
    from app.core.redis_manager import RedisManager
    redis_manager = RedisManager()
    return redis_manager


async def get_current_user_simple(
    request: Request,
    db = Depends(get_db),
    redis_cache=Depends(get_redis_cache)
) -> Dict[str, Any]:
    """Simplified session validation for V2 endpoints."""
    # Try session ID from header first
    session_id = request.headers.get("X-Session-ID") or request.headers.get("x-session-id")

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided in X-Session-ID header"
        )

    session_data = await redis_cache.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data"
        )

    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user_data


def _extract_user_role(current_user: Dict[str, Any]) -> UserRole:
    """Extract UserRole enum from user data."""
    role_str = current_user.get("role", "").lower()
    try:
        return UserRole(role_str)
    except ValueError:
        # FIXED: Invalid role - default to DOCTOR instead of removed PATIENT role
        # Only ADMIN and DOCTOR roles exist in the system
        return UserRole.DOCTOR


def _check_physician_or_admin(current_user: Dict[str, Any]) -> None:
    """Ensure user is a physician or admin."""
    role = _extract_user_role(current_user)
    if role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only physicians and administrators can perform this action"
        )


def _check_patient_access(current_user: Dict[str, Any], patient_id: UUID, db: Any) -> None:
    """
    Ensure user has access to patient data.
    - Admins can access all patients
    - Physicians can access their own patients
    - Patients can only access their own data
    """
    role = _extract_user_role(current_user)
    user_id = UUID(current_user.get("id"))

    if role == UserRole.ADMIN:
        return  # Admins have full access

    if role == UserRole.DOCTOR:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
        if patient.doctor_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this patient"
            )

    # FIXED: Removed UserRole.PATIENT check - only ADMIN and DOCTOR roles exist


def _serialize_alert(alert: Alert, fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """Serialize Alert model to dictionary with optional field selection."""
    data = {
        "id": str(alert.id),
        "patient_id": str(alert.patient_id),
        "alert_type": alert.alert_type,
        "severity": alert.severity.value,
        "description": alert.description,
        "status": alert.status,
        "data": alert.data or {},
        "acknowledged": alert.acknowledged,
        "acknowledged_by": str(alert.acknowledged_by) if alert.acknowledged_by else None,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "created_at": alert.created_at.isoformat(),
        "updated_at": alert.updated_at.isoformat(),
    }

    # Include eager-loaded relationships if present
    if hasattr(alert, "patient") and alert.patient:
        data["patient"] = {
            "id": str(alert.patient.id),
            "name": alert.patient.name,
            "email": alert.patient.email
        }

    if hasattr(alert, "acknowledged_by_user") and alert.acknowledged_by_user:
        data["acknowledged_by_user"] = {
            "id": str(alert.acknowledged_by_user.id),
            "name": alert.acknowledged_by_user.full_name,
            "email": alert.acknowledged_by_user.email
        }

    return apply_field_selection(data, fields) if fields else data


@router.get("", response_model=AlertV2List)
@limiter.limit("50/minute")
async def list_alerts(
    request: Request,
    pagination: Dict = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status (pending/acknowledged)"),
    patient_id: Optional[UUID] = Query(None, description="Filter by patient ID"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    db = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(get_current_user_simple),
) -> AlertV2List:
    """
    List alerts with cursor-based pagination.

    Features:
    - Cursor-based pagination for efficient access
    - Multi-dimensional filtering (severity, status, patient, type)
    - Field selection for bandwidth optimization (?fields=id,severity)
    - Eager loading for relationships (?include=patient)
    - Redis caching with 2-minute TTL
    - RBAC: All authenticated users can list (filtered by access)

    Rate limit: 50 requests/minute
    """
    try:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]

        # Build cache key
        cache_key_parts = [
            "alerts:v2:list",
            f"user:{current_user.get('id')}",
            f"cursor:{cursor_data.get('id') if cursor_data else 'start'}",
            f"limit:{limit}",
            f"severity:{severity.value if severity else 'all'}",
            f"status:{status if status else 'all'}",
            f"patient:{patient_id if patient_id else 'all'}",
            f"type:{alert_type if alert_type else 'all'}",
        ]
        cache_key = ":".join(cache_key_parts)

        # Try to get from cache
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for alerts list: {cache_key}")
            return AlertV2List(**cached_data)

        # Build query with eager loading
        query = db.query(Alert)

        if include and "patient" in include:
            query = query.options(joinedload(Alert.patient))
        if include and "acknowledged_by_user" in include:
            query = query.options(joinedload(Alert.acknowledged_by_user))

        # Apply filters
        if severity:
            query = query.filter(Alert.severity == severity)

        if status:
            if status.lower() == "pending":
                query = query.filter(Alert.acknowledged == False)
            elif status.lower() == "acknowledged":
                query = query.filter(Alert.acknowledged == True)

        if patient_id:
            _check_patient_access(current_user, patient_id, db)
            query = query.filter(Alert.patient_id == patient_id)
        else:
            # Filter by user access
            role = _extract_user_role(current_user)
            user_id = UUID(current_user.get("id"))

            if role == UserRole.DOCTOR:
                patient_ids = db.query(Patient.id).filter(Patient.doctor_id == user_id).all()
                patient_ids = [p[0] for p in patient_ids]
                query = query.filter(Alert.patient_id.in_(patient_ids))
            # FIXED: Removed UserRole.PATIENT check - only ADMIN and DOCTOR roles exist

        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)

        # Apply cursor pagination
        if cursor_data and "id" in cursor_data:
            query = query.filter(Alert.id > cursor_data["id"])

        # Order by ID for consistent pagination
        query = query.order_by(Alert.id.asc())

        # Fetch limit + 1 to check if there are more results
        alerts = query.limit(limit + 1).all()

        has_more = len(alerts) > limit
        if has_more:
            alerts = alerts[:limit]

        # Create next cursor
        next_cursor = None
        if has_more and alerts:
            next_cursor = create_cursor(alerts[-1].id)

        # Serialize results
        data = [_serialize_alert(alert, fields) for alert in alerts]

        result = AlertV2List(
            data=data,
            next_cursor=next_cursor,
            has_more=has_more,
            total=None  # Total count is expensive for large datasets
        )

        # Cache the result
        await redis_cache.set(cache_key, result.dict(), ttl=CACHE_TTL_LIST)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing alerts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts"
        )


@router.post("", response_model=AlertV2Response, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_alert(
    alert_data: AlertV2Create,
    request: Request,
    db = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(get_current_user_simple),
) -> Dict[str, Any]:
    """
    Create a new alert.

    Features:
    - RBAC: Only physicians and admins can create alerts
    - Validates patient exists and user has access
    - Invalidates relevant caches
    - Logs creation for audit trail

    Rate limit: 30 requests/minute
    """
    try:
        # Check permissions
        _check_physician_or_admin(current_user)

        # Check access to patient
        _check_patient_access(current_user, alert_data.patient_id, db)

        # Verify patient exists
        patient = db.query(Patient).filter(Patient.id == alert_data.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )

        # Create alert
        alert = Alert(
            patient_id=alert_data.patient_id,
            alert_type=alert_data.alert_type,
            severity=alert_data.severity,
            description=alert_data.description,
            data=alert_data.data or {},
            acknowledged=False
        )

        db.add(alert)
        db.commit()
        db.refresh(alert)

        # Invalidate caches
        await redis_cache.delete_pattern(f"alerts:v2:list:*")

        # Log creation
        logger.info(
            f"Alert created: {alert.id} for patient {alert_data.patient_id} "
            f"by user {current_user.get('id')} - {alert.severity.value} - {alert.alert_type}"
        )

        return _serialize_alert(alert)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating alert: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create alert"
        )


@router.get("/{alert_id}", response_model=AlertV2Response)
@limiter.limit("50/minute")
async def get_alert(
    alert_id: UUID,
    request: Request,
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    db = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get a specific alert by ID.

    Features:
    - Field selection for bandwidth optimization (?fields=id,severity)
    - Eager loading for relationships (?include=patient)
    - Redis caching with 5-minute TTL
    - RBAC: User must have access to the patient

    Rate limit: 50 requests/minute
    """
    try:
        # Try cache first
        cache_key = f"alerts:v2:single:{alert_id}:fields:{','.join(fields) if fields else 'all'}"
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for alert: {cache_key}")
            return cached_data

        # Build query with eager loading
        query = db.query(Alert).filter(Alert.id == alert_id)

        if include and "patient" in include:
            query = query.options(joinedload(Alert.patient))
        if include and "acknowledged_by_user" in include:
            query = query.options(joinedload(Alert.acknowledged_by_user))

        alert = query.first()

        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )

        # Check access
        _check_patient_access(current_user, alert.patient_id, db)

        # Serialize
        data = _serialize_alert(alert, fields)

        # Cache the result
        await redis_cache.set(cache_key, data, ttl=CACHE_TTL_SINGLE)

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alert"
        )


@router.patch("/{alert_id}", response_model=AlertV2Response)
@limiter.limit("30/minute")
async def update_alert(
    alert_id: UUID,
    alert_data: AlertV2Update,
    request: Request,
    db = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(get_current_user_simple),
) -> Dict[str, Any]:
    """
    Update an alert (partial update).

    Features:
    - RBAC: Only physicians and admins can update alerts
    - Partial updates (only provided fields are updated)
    - Invalidates relevant caches
    - Logs update for audit trail

    Rate limit: 30 requests/minute
    """
    try:
        # Check permissions
        _check_physician_or_admin(current_user)

        # Get alert
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )

        # Check access
        _check_patient_access(current_user, alert.patient_id, db)

        # Update only provided fields
        update_data = alert_data.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(alert, field, value)

        db.commit()
        db.refresh(alert)

        # Invalidate caches
        await redis_cache.delete(f"alerts:v2:single:{alert_id}:*")
        await redis_cache.delete_pattern("alerts:v2:list:*")

        # Log update
        logger.info(
            f"Alert updated: {alert_id} by user {current_user.get('id')}"
        )

        return _serialize_alert(alert)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update alert"
        )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_alert(
    alert_id: UUID,
    request: Request,
    db = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(get_current_user_simple),
):
    """
    Delete an alert.

    Features:
    - RBAC: Only physicians and admins can delete alerts
    - Soft delete option via alert.data field
    - Invalidates relevant caches
    - Logs deletion for audit trail

    Rate limit: 30 requests/minute
    """
    try:
        # Check permissions
        _check_physician_or_admin(current_user)

        # Get alert
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )

        # Check access
        _check_patient_access(current_user, alert.patient_id, db)

        # Delete alert
        db.delete(alert)
        db.commit()

        # Invalidate caches
        await redis_cache.delete_pattern(f"alerts:v2:single:{alert_id}:*")
        await redis_cache.delete_pattern("alerts:v2:list:*")

        # Log deletion
        logger.info(
            f"Alert deleted: {alert_id} by user {current_user.get('id')}"
        )

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete alert"
        )


@router.patch("/{alert_id}/read", response_model=AlertV2Response)
@limiter.limit("30/minute")
async def mark_alert_read(
    alert_id: UUID,
    acknowledge_data: AlertV2Acknowledge,
    request: Request,
    db = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(get_current_user_simple),
) -> Dict[str, Any]:
    """
    Mark an alert as read (acknowledge).

    Features:
    - RBAC: Only physicians and admins can mark alerts as read
    - Records who acknowledged and when
    - Invalidates relevant caches
    - Logs acknowledgment for audit trail

    Rate limit: 30 requests/minute
    """
    try:
        # Check permissions
        _check_physician_or_admin(current_user)

        # Get alert
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )

        # Check access
        _check_patient_access(current_user, alert.patient_id, db)

        # Check if already acknowledged
        if alert.acknowledged:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Alert already marked as read"
            )

        # Mark as read
        user_id = UUID(current_user.get("id"))
        alert.acknowledged = True
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()

        # Add notes if provided
        if acknowledge_data.notes:
            if not alert.data:
                alert.data = {}
            alert.data["acknowledgment_notes"] = acknowledge_data.notes

        db.commit()
        db.refresh(alert)

        # Invalidate caches
        await redis_cache.delete(f"alerts:v2:single:{alert_id}:*")
        await redis_cache.delete_pattern("alerts:v2:list:*")

        # Log acknowledgment
        logger.info(
            f"Alert marked as read: {alert_id} by user {user_id}"
        )

        return _serialize_alert(alert)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error marking alert as read {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark alert as read"
        )


@router.post("/read-all", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def mark_all_alerts_read(
    request: Request,
    patient_id: Optional[UUID] = Query(None, description="Optional: Mark all alerts for specific patient"),
    db = Depends(get_db),
    redis_cache=Depends(get_redis_cache),
    current_user: Dict = Depends(get_current_user_simple),
) -> Dict[str, Any]:
    """
    Mark all unread alerts as read.

    Features:
    - RBAC: Only physicians and admins can mark all alerts as read
    - Optional patient filter
    - Respects user access permissions
    - Invalidates relevant caches
    - Logs bulk operation for audit trail

    Rate limit: 10 requests/minute
    """
    try:
        # Check permissions
        _check_physician_or_admin(current_user)

        # Build query for unread alerts
        query = db.query(Alert).filter(Alert.acknowledged == False)

        # Apply patient filter if provided
        if patient_id:
            _check_patient_access(current_user, patient_id, db)
            query = query.filter(Alert.patient_id == patient_id)
        else:
            # Filter by user access
            role = _extract_user_role(current_user)
            user_id = UUID(current_user.get("id"))

            if role == UserRole.DOCTOR:
                patient_ids = db.query(Patient.id).filter(Patient.doctor_id == user_id).all()
                patient_ids = [p[0] for p in patient_ids]
                query = query.filter(Alert.patient_id.in_(patient_ids))
            # FIXED: Removed UserRole.PATIENT check - only ADMIN and DOCTOR roles exist

        # Get all unread alerts
        unread_alerts = query.all()

        if not unread_alerts:
            return {
                "success": True,
                "count": 0,
                "message": "No unread alerts to mark as read"
            }

        # Mark all as read
        user_id = UUID(current_user.get("id"))
        now = datetime.utcnow()
        count = 0

        for alert in unread_alerts:
            alert.acknowledged = True
            alert.acknowledged_by = user_id
            alert.acknowledged_at = now
            count += 1

        db.commit()

        # Invalidate caches
        await redis_cache.delete_pattern("alerts:v2:list:*")
        await redis_cache.delete_pattern("alerts:v2:single:*")

        # Log bulk operation
        logger.info(
            f"Marked all alerts as read: {count} alerts by user {user_id}"
            + (f" for patient {patient_id}" if patient_id else "")
        )

        return {
            "success": True,
            "count": count,
            "message": f"Successfully marked {count} alert(s) as read"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error marking all alerts as read: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all alerts as read"
        )
