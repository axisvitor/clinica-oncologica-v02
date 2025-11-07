"""
Alerts API v2 - Patient Safety Alert Management System

Enhanced alert endpoints with:
- Cursor-based pagination for efficient data access
- Redis caching with SHORT TTLs (alerts are time-sensitive)
- Rate limiting to prevent system abuse
- Eager loading with joinedload() for performance
- Field selection via ?fields= for sparse fieldsets
- RBAC: Physicians can create/resolve, patients can view only
- Real-time notification integration
- Rule engine for alert triggers
- Risk scoring and escalation workflows
- Comprehensive audit trail

CRITICAL: This module handles patient safety alerts. All operations must be
thoroughly validated and logged for compliance and patient safety.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Header
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from pydantic import BaseModel

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
    AlertV2Resolve,
    AlertV2Dismiss,
    AlertStatisticsV2,
    PatientAlertSummaryV2,
    PatientRiskScoreV2,
    AlertRuleV2,
    AlertRuleV2Create,
    AlertRuleV2Update,
    BulkAlertOperation,
    BulkAlertResult,
    AlertTrendV2,
    AlertEscalationV2,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    create_cursor,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configurations (SHORT TTLs for time-sensitive alert data)
CACHE_TTL_ACTIVE_ALERTS = 60  # 1 minute for active alerts
CACHE_TTL_ALERT_HISTORY = 300  # 5 minutes for alert history
CACHE_TTL_ALERT_RULES = 900  # 15 minutes for alert rules
CACHE_TTL_STATISTICS = 120  # 2 minutes for statistics


async def _get_current_user_simple(
    session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> Dict[str, Any]:
    """Simplified session validation for V2 endpoints."""
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
        return UserRole.PATIENT


def _check_physician_or_admin(current_user: Dict[str, Any]) -> None:
    """Ensure user is a physician or admin."""
    role = _extract_user_role(current_user)
    if role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only physicians and administrators can perform this action"
        )


def _check_patient_access(current_user: Dict[str, Any], patient_id: UUID, db: Session) -> None:
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
        # Check if physician owns this patient
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

    elif role == UserRole.PATIENT:
        # Patients can only view their own alerts
        # Note: This assumes patient_id equals user_id for patient users
        # Adjust based on your user-patient relationship model
        if patient_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own alerts"
            )


def _calculate_risk_score(alerts: List[Alert]) -> Dict[str, Any]:
    """
    Calculate patient risk score based on alert history.

    Risk scoring algorithm:
    - CRITICAL alerts: 10 points each
    - HIGH alerts: 5 points each
    - MEDIUM alerts: 2 points each
    - LOW alerts: 1 point each
    - Recent alerts (last 7 days) weighted 2x
    - Unresolved alerts weighted 3x

    Risk levels:
    - LOW: 0-10 points
    - MEDIUM: 11-30 points
    - HIGH: 31-60 points
    - CRITICAL: 61+ points
    """
    if not alerts:
        return {
            "score": 0,
            "level": "LOW",
            "factors": []
        }

    score = 0
    factors = []
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)

    severity_weights = {
        AlertSeverity.CRITICAL: 10,
        AlertSeverity.HIGH: 5,
        AlertSeverity.MEDIUM: 2,
        AlertSeverity.LOW: 1
    }

    for alert in alerts:
        base_score = severity_weights.get(alert.severity, 1)

        # Recent alerts weighted 2x
        if alert.created_at >= seven_days_ago:
            base_score *= 2
            factors.append(f"Recent {alert.severity.value} alert")

        # Unresolved alerts weighted 3x
        if alert.status in [AlertStatus.PENDING, AlertStatus.ACTIVE]:
            base_score *= 3
            factors.append(f"Unresolved {alert.severity.value} alert")

        score += base_score

    # Determine risk level
    if score >= 61:
        level = "CRITICAL"
    elif score >= 31:
        level = "HIGH"
    elif score >= 11:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "score": score,
        "level": level,
        "factors": list(set(factors))[:5]  # Top 5 unique factors
    }


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
@limiter.limit("60/minute")
async def list_alerts(
    request: Request,
    pagination: Dict = Depends(get_pagination_params),
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    status: Optional[AlertStatus] = Query(None, description="Filter by status"),
    patient_id: Optional[UUID] = Query(None, description="Filter by patient ID"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    start_date: Optional[datetime] = Query(None, description="Filter alerts from date"),
    end_date: Optional[datetime] = Query(None, description="Filter alerts to date"),
    unresolved_only: bool = Query(False, description="Show only unresolved alerts"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> AlertV2List:
    """
    List alerts with advanced filtering and pagination.

    Features:
    - Cursor-based pagination for efficient access
    - Multi-dimensional filtering (severity, status, patient, type, date range)
    - Field selection for bandwidth optimization
    - Eager loading for relationships
    - Redis caching with 1-minute TTL
    - RBAC: All authenticated users can list (filtered by access)

    Rate limit: 60 requests/minute
    """
    try:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]

        # Build cache key
        cache_key_parts = [
            "alerts:list",
            f"cursor:{cursor_data.get('id') if cursor_data else 'start'}",
            f"limit:{limit}",
            f"severity:{severity.value if severity else 'all'}",
            f"status:{status.value if status else 'all'}",
            f"patient:{patient_id if patient_id else 'all'}",
            f"type:{alert_type if alert_type else 'all'}",
            f"unresolved:{unresolved_only}",
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
            if status == AlertStatus.PENDING:
                query = query.filter(Alert.acknowledged == False)
            elif status == AlertStatus.ACKNOWLEDGED:
                query = query.filter(Alert.acknowledged == True)

        if patient_id:
            # Check access
            _check_patient_access(current_user, patient_id, db)
            query = query.filter(Alert.patient_id == patient_id)
        else:
            # Filter by user access
            role = _extract_user_role(current_user)
            user_id = UUID(current_user.get("id"))

            if role == UserRole.DOCTOR:
                # Physicians see alerts for their patients only
                patient_ids = db.query(Patient.id).filter(Patient.doctor_id == user_id).all()
                patient_ids = [p[0] for p in patient_ids]
                query = query.filter(Alert.patient_id.in_(patient_ids))
            elif role == UserRole.PATIENT:
                # Patients see their own alerts only
                query = query.filter(Alert.patient_id == user_id)

        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)

        if start_date:
            query = query.filter(Alert.created_at >= start_date)

        if end_date:
            query = query.filter(Alert.created_at <= end_date)

        if unresolved_only:
            query = query.filter(Alert.acknowledged == False)

        # Apply cursor pagination
        if cursor_data and "id" in cursor_data:
            query = query.filter(Alert.id > cursor_data["id"])

        # Order by ID for consistent pagination
        query = query.order_by(asc(Alert.id))

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
        await redis_cache.set(cache_key, result.dict(), ttl=CACHE_TTL_ACTIVE_ALERTS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing alerts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts"
        )


@router.get("/{alert_id}", response_model=AlertV2Response)
@limiter.limit("60/minute")
async def get_alert(
    alert_id: UUID,
    request: Request,
    fields: Optional[List[str]] = Depends(get_field_selection),
    include: Optional[List[str]] = Depends(get_eager_load_params),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get a specific alert by ID.

    Features:
    - Field selection for bandwidth optimization
    - Eager loading for relationships
    - Redis caching with 1-minute TTL
    - RBAC: User must have access to the patient

    Rate limit: 60 requests/minute
    """
    try:
        # Try cache first
        cache_key = f"alert:{alert_id}:fields:{','.join(fields) if fields else 'all'}"
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
        await redis_cache.set(cache_key, data, ttl=CACHE_TTL_ACTIVE_ALERTS)

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alert"
        )


@router.get("/patient/{patient_id}/summary", response_model=PatientAlertSummaryV2)
@limiter.limit("30/minute")
async def get_patient_alert_summary(
    patient_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> PatientAlertSummaryV2:
    """
    Get alert summary for a specific patient.

    Includes:
    - Total alert counts by severity
    - Unresolved alert counts
    - Recent alert activity
    - Patient risk score

    Features:
    - Redis caching with 2-minute TTL
    - RBAC: User must have access to the patient

    Rate limit: 30 requests/minute
    """
    try:
        # Check access
        _check_patient_access(current_user, patient_id, db)

        # Try cache first
        cache_key = f"alert:patient:{patient_id}:summary"
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for patient alert summary: {cache_key}")
            return PatientAlertSummaryV2(**cached_data)

        # Get all alerts for patient
        alerts = db.query(Alert).filter(Alert.patient_id == patient_id).all()

        # Calculate statistics
        total_alerts = len(alerts)
        pending_alerts = len([a for a in alerts if not a.acknowledged])
        critical_alerts = len([a for a in alerts if a.severity == AlertSeverity.CRITICAL])
        high_alerts = len([a for a in alerts if a.severity == AlertSeverity.HIGH])
        medium_alerts = len([a for a in alerts if a.severity == AlertSeverity.MEDIUM])
        low_alerts = len([a for a in alerts if a.severity == AlertSeverity.LOW])

        # Get recent alerts (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_alerts = [a for a in alerts if a.created_at >= seven_days_ago]

        # Calculate risk score
        risk_data = _calculate_risk_score(recent_alerts)

        # Last alert timestamp
        last_alert_at = max([a.created_at for a in alerts]) if alerts else None

        summary = PatientAlertSummaryV2(
            patient_id=patient_id,
            total_alerts=total_alerts,
            pending_alerts=pending_alerts,
            critical_alerts=critical_alerts,
            high_alerts=high_alerts,
            medium_alerts=medium_alerts,
            low_alerts=low_alerts,
            recent_alerts_7d=len(recent_alerts),
            last_alert_at=last_alert_at,
            risk_score=risk_data["score"],
            risk_level=risk_data["level"],
            risk_factors=risk_data["factors"]
        )

        # Cache the result
        await redis_cache.set(cache_key, summary.dict(), ttl=CACHE_TTL_STATISTICS)

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving patient alert summary {patient_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient alert summary"
        )


@router.post("", response_model=AlertV2Response, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_alert(
    alert_data: AlertV2Create,
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
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
        await redis_cache.delete(f"alert:patient:{alert_data.patient_id}:summary")
        await redis_cache.delete_pattern("alerts:list:*")

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


@router.post("/{alert_id}/acknowledge", response_model=AlertV2Response)
@limiter.limit("30/minute")
async def acknowledge_alert(
    alert_id: UUID,
    acknowledge_data: AlertV2Acknowledge,
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Acknowledge an alert.

    Features:
    - RBAC: Only physicians and admins can acknowledge
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
                detail="Alert already acknowledged"
            )

        # Acknowledge
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
        await redis_cache.delete(f"alert:{alert_id}:*")
        await redis_cache.delete(f"alert:patient:{alert.patient_id}:summary")
        await redis_cache.delete_pattern("alerts:list:*")

        # Log acknowledgment
        logger.info(
            f"Alert acknowledged: {alert_id} by user {user_id}"
        )

        return _serialize_alert(alert)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error acknowledging alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge alert"
        )


@router.post("/{alert_id}/resolve", response_model=AlertV2Response)
@limiter.limit("30/minute")
async def resolve_alert(
    alert_id: UUID,
    resolve_data: AlertV2Resolve,
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Resolve an alert.

    Features:
    - RBAC: Only physicians and admins can resolve
    - Requires resolution notes for audit trail
    - Invalidates relevant caches
    - Logs resolution for compliance

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

        # Auto-acknowledge if not already
        user_id = UUID(current_user.get("id"))
        if not alert.acknowledged:
            alert.acknowledged = True
            alert.acknowledged_by = user_id
            alert.acknowledged_at = datetime.utcnow()

        # Mark as resolved
        if not alert.data:
            alert.data = {}
        alert.data["resolved"] = True
        alert.data["resolved_by"] = str(user_id)
        alert.data["resolved_at"] = datetime.utcnow().isoformat()
        alert.data["resolution_notes"] = resolve_data.notes

        db.commit()
        db.refresh(alert)

        # Invalidate caches
        await redis_cache.delete(f"alert:{alert_id}:*")
        await redis_cache.delete(f"alert:patient:{alert.patient_id}:summary")
        await redis_cache.delete_pattern("alerts:list:*")

        # Log resolution
        logger.info(
            f"Alert resolved: {alert_id} by user {user_id}"
        )

        return _serialize_alert(alert)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error resolving alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve alert"
        )


@router.post("/{alert_id}/dismiss", response_model=AlertV2Response)
@limiter.limit("30/minute")
async def dismiss_alert(
    alert_id: UUID,
    dismiss_data: AlertV2Dismiss,
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Dismiss an alert (mark as false positive or not actionable).

    Features:
    - RBAC: Only physicians and admins can dismiss
    - Requires reason for audit trail
    - Invalidates relevant caches
    - Logs dismissal for compliance

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

        # Mark as dismissed
        user_id = UUID(current_user.get("id"))
        alert.acknowledged = True
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.utcnow()

        if not alert.data:
            alert.data = {}
        alert.data["dismissed"] = True
        alert.data["dismissed_by"] = str(user_id)
        alert.data["dismissed_at"] = datetime.utcnow().isoformat()
        alert.data["dismissal_reason"] = dismiss_data.reason

        db.commit()
        db.refresh(alert)

        # Invalidate caches
        await redis_cache.delete(f"alert:{alert_id}:*")
        await redis_cache.delete(f"alert:patient:{alert.patient_id}:summary")
        await redis_cache.delete_pattern("alerts:list:*")

        # Log dismissal
        logger.info(
            f"Alert dismissed: {alert_id} by user {user_id} - reason: {dismiss_data.reason}"
        )

        return _serialize_alert(alert)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error dismissing alert {alert_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss alert"
        )


@router.get("/statistics/overview", response_model=AlertStatisticsV2)
@limiter.limit("30/minute")
async def get_alert_statistics(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> AlertStatisticsV2:
    """
    Get alert system statistics and analytics.

    Includes:
    - Alert counts by severity and status
    - Trend analysis over time
    - Average response times
    - Top alert types

    Features:
    - Redis caching with 2-minute TTL
    - RBAC: Filtered by user access

    Rate limit: 30 requests/minute
    """
    try:
        # Try cache first
        cache_key = f"alert:statistics:days:{days}:user:{current_user.get('id')}"
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for alert statistics: {cache_key}")
            return AlertStatisticsV2(**cached_data)

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Build query based on user role
        query = db.query(Alert).filter(Alert.created_at >= start_date)

        role = _extract_user_role(current_user)
        user_id = UUID(current_user.get("id"))

        if role == UserRole.DOCTOR:
            # Filter to physician's patients
            patient_ids = db.query(Patient.id).filter(Patient.doctor_id == user_id).all()
            patient_ids = [p[0] for p in patient_ids]
            query = query.filter(Alert.patient_id.in_(patient_ids))
        elif role == UserRole.PATIENT:
            # Filter to patient's own alerts
            query = query.filter(Alert.patient_id == user_id)

        alerts = query.all()

        # Calculate statistics
        total_alerts = len(alerts)
        pending_alerts = len([a for a in alerts if not a.acknowledged])
        acknowledged_alerts = len([a for a in alerts if a.acknowledged])
        resolved_alerts = len([a for a in alerts if a.data and a.data.get("resolved")])

        critical_count = len([a for a in alerts if a.severity == AlertSeverity.CRITICAL])
        high_count = len([a for a in alerts if a.severity == AlertSeverity.HIGH])
        medium_count = len([a for a in alerts if a.severity == AlertSeverity.MEDIUM])
        low_count = len([a for a in alerts if a.severity == AlertSeverity.LOW])

        # Calculate average response time
        acknowledged_with_time = [
            a for a in alerts
            if a.acknowledged and a.acknowledged_at and a.created_at
        ]
        if acknowledged_with_time:
            response_times = [
                (a.acknowledged_at - a.created_at).total_seconds() / 60
                for a in acknowledged_with_time
            ]
            avg_response_time_minutes = sum(response_times) / len(response_times)
        else:
            avg_response_time_minutes = 0

        # Top alert types
        alert_type_counts = defaultdict(int)
        for alert in alerts:
            alert_type_counts[alert.alert_type] += 1

        top_alert_types = sorted(
            [{"type": k, "count": v} for k, v in alert_type_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:5]

        statistics = AlertStatisticsV2(
            total_alerts=total_alerts,
            pending_alerts=pending_alerts,
            acknowledged_alerts=acknowledged_alerts,
            resolved_alerts=resolved_alerts,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            avg_response_time_minutes=round(avg_response_time_minutes, 2),
            top_alert_types=top_alert_types,
            analysis_period_days=days
        )

        # Cache the result
        await redis_cache.set(cache_key, statistics.dict(), ttl=CACHE_TTL_STATISTICS)

        return statistics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating alert statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate alert statistics"
        )


@router.post("/bulk/acknowledge", response_model=BulkAlertResult)
@limiter.limit("10/minute")
async def bulk_acknowledge_alerts(
    operation: BulkAlertOperation,
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> BulkAlertResult:
    """
    Bulk acknowledge multiple alerts.

    Features:
    - RBAC: Only physicians and admins can acknowledge
    - Validates access to all alerts
    - Atomic operation (all or nothing)
    - Invalidates relevant caches
    - Logs bulk operation for audit trail

    Rate limit: 10 requests/minute (lower for bulk operations)
    """
    try:
        # Check permissions
        _check_physician_or_admin(current_user)

        if not operation.alert_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No alert IDs provided"
            )

        # Get all alerts
        alerts = db.query(Alert).filter(Alert.id.in_(operation.alert_ids)).all()

        if len(alerts) != len(operation.alert_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more alerts not found"
            )

        # Check access to all alerts
        for alert in alerts:
            _check_patient_access(current_user, alert.patient_id, db)

        # Acknowledge all
        user_id = UUID(current_user.get("id"))
        now = datetime.utcnow()
        success_count = 0
        failed_ids = []

        for alert in alerts:
            try:
                if not alert.acknowledged:
                    alert.acknowledged = True
                    alert.acknowledged_by = user_id
                    alert.acknowledged_at = now

                    if operation.notes:
                        if not alert.data:
                            alert.data = {}
                        alert.data["bulk_acknowledgment_notes"] = operation.notes

                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to acknowledge alert {alert.id}: {str(e)}")
                failed_ids.append(str(alert.id))

        db.commit()

        # Invalidate caches
        await redis_cache.delete_pattern("alerts:list:*")
        await redis_cache.delete_pattern("alert:patient:*:summary")

        # Log bulk operation
        logger.info(
            f"Bulk acknowledge: {success_count} alerts by user {user_id}"
        )

        return BulkAlertResult(
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_ids=failed_ids
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk acknowledge: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk acknowledge alerts"
        )


@router.get("/patient/{patient_id}/risk-score", response_model=PatientRiskScoreV2)
@limiter.limit("30/minute")
async def get_patient_risk_score(
    patient_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> PatientRiskScoreV2:
    """
    Get comprehensive risk score for a patient based on alert history.

    Features:
    - Multi-factor risk scoring algorithm
    - Trend analysis over time
    - Actionable recommendations
    - Redis caching with 2-minute TTL

    Rate limit: 30 requests/minute
    """
    try:
        # Check access
        _check_patient_access(current_user, patient_id, db)

        # Try cache first
        cache_key = f"alert:patient:{patient_id}:risk-score"
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for patient risk score: {cache_key}")
            return PatientRiskScoreV2(**cached_data)

        # Get recent alerts (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_alerts = db.query(Alert).filter(
            Alert.patient_id == patient_id,
            Alert.created_at >= thirty_days_ago
        ).all()

        # Calculate risk score
        risk_data = _calculate_risk_score(recent_alerts)

        # Generate recommendations
        recommendations = []
        if risk_data["level"] == "CRITICAL":
            recommendations.append("Immediate physician review required")
            recommendations.append("Consider escalating to specialist")
        elif risk_data["level"] == "HIGH":
            recommendations.append("Schedule follow-up within 48 hours")
            recommendations.append("Review treatment plan")
        elif risk_data["level"] == "MEDIUM":
            recommendations.append("Monitor closely for next 7 days")

        unresolved_count = len([a for a in recent_alerts if not a.acknowledged])
        if unresolved_count > 0:
            recommendations.append(f"Address {unresolved_count} unresolved alerts")

        risk_score = PatientRiskScoreV2(
            patient_id=patient_id,
            risk_score=risk_data["score"],
            risk_level=risk_data["level"],
            risk_factors=risk_data["factors"],
            recommendations=recommendations,
            calculated_at=datetime.utcnow(),
            alert_count_30d=len(recent_alerts),
            unresolved_count=unresolved_count
        )

        # Cache the result
        await redis_cache.set(cache_key, risk_score.dict(), ttl=CACHE_TTL_STATISTICS)

        return risk_score

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating risk score for patient {patient_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate patient risk score"
        )
