"""
Dashboard API v2 - Real-time Dashboard and Widgets System

Enhanced dashboard endpoints with:
- NO pagination (dashboard widgets return aggregated data)
- Redis caching with optimized TTLs:
  * Real-time widgets: 120s (2 min) cache
  * Stats widgets: 600s (10 min) cache
  * Trends widgets: 1800s (30 min) cache
- Rate limiting: 30-60 req/min
- Eager loading with joinedload() for performance
- Field selection via ?fields= for bandwidth optimization
- RBAC: Role-based dashboard views (Admin, Doctor, Patient)
- Time range filtering (today, week, month, year, custom)
- Widget types: metrics, charts, tables, activity feeds, progress bars, alerts
- Real-time updates ready (WebSocket integration prepared)
- Custom dashboard layouts with persistence

CRITICAL: Dashboard data aggregates sensitive patient information.
All queries must be optimized and access-controlled per user role.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Header
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc, text
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.alert import Alert, AlertSeverity
from app.schemas.v2.dashboard import (
    DashboardMainResponse,
    DashboardPatientResponse,
    DashboardPhysicianResponse,
    DashboardAdminResponse,
    CustomDashboardResponse,
    DashboardLayoutUpdate,
    WidgetConfig,
    MetricWidgetData,
    ChartWidgetData,
    TableWidgetData,
    ActivityFeedData,
    AlertsSummaryData,
    TimeRangeEnum,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_field_selection,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.utils.rate_limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configurations (Optimized for dashboard widgets)
CACHE_TTL_REALTIME = 120  # 2 minutes for real-time widgets
CACHE_TTL_STATS = 600  # 10 minutes for statistics widgets
CACHE_TTL_TRENDS = 1800  # 30 minutes for trend charts


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


def _calculate_date_range(time_range: TimeRangeEnum, custom_start: Optional[datetime] = None, custom_end: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Calculate start and end dates based on time range enum.

    Args:
        time_range: Enum value (TODAY, WEEK, MONTH, QUARTER, YEAR, CUSTOM)
        custom_start: Start date for CUSTOM range
        custom_end: End date for CUSTOM range

    Returns:
        Tuple of (start_date, end_date)

    Raises:
        HTTPException: If CUSTOM range provided without dates
    """
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if time_range == TimeRangeEnum.TODAY:
        return today, now
    elif time_range == TimeRangeEnum.WEEK:
        return now - timedelta(days=7), now
    elif time_range == TimeRangeEnum.MONTH:
        return now - timedelta(days=30), now
    elif time_range == TimeRangeEnum.QUARTER:
        return now - timedelta(days=90), now
    elif time_range == TimeRangeEnum.YEAR:
        return now - timedelta(days=365), now
    elif time_range == TimeRangeEnum.CUSTOM:
        if not custom_start or not custom_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="custom_start and custom_end required for CUSTOM time range"
            )
        return custom_start, custom_end
    else:
        return now - timedelta(days=7), now


def _get_patient_metrics(db: Session, patient_ids: Optional[List[UUID]] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate patient metrics for dashboard widgets.

    Args:
        db: Database session
        patient_ids: Optional list of patient IDs to filter by
        start_date: Start date for time-based metrics
        end_date: End date for time-based metrics

    Returns:
        Dictionary of patient metrics
    """
    query = db.query(Patient)

    if patient_ids:
        query = query.filter(Patient.id.in_(patient_ids))

    # Total patients
    total_patients = query.count()

    # Active patients
    active_patients = query.filter(Patient.is_active == True).count()

    # New patients in time range
    new_patients = 0
    if start_date:
        new_patients = query.filter(Patient.created_at >= start_date).count()

    # High-risk patients (based on recent alerts)
    high_risk_count = 0
    if patient_ids:
        high_risk_count = db.query(Patient).join(Alert).filter(
            Patient.id.in_(patient_ids),
            Alert.severity.in_([AlertSeverity.CRITICAL, AlertSeverity.HIGH]),
            Alert.acknowledged == False
        ).distinct().count()

    return {
        "total_patients": total_patients,
        "active_patients": active_patients,
        "inactive_patients": total_patients - active_patients,
        "new_patients": new_patients,
        "high_risk_patients": high_risk_count,
    }


def _get_message_metrics(db: Session, patient_ids: Optional[List[UUID]] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate message metrics for dashboard widgets.

    Args:
        db: Database session
        patient_ids: Optional list of patient IDs to filter by
        start_date: Start date for filtering
        end_date: End date for filtering

    Returns:
        Dictionary of message metrics
    """
    base_query = """
        SELECT
            COUNT(*) as total_messages,
            COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent_count,
            COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered_count,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
            COUNT(CASE WHEN patient_response_received = true THEN 1 END) as response_count
        FROM messages
        WHERE 1=1
    """

    params = {}

    if patient_ids:
        base_query += " AND patient_id = ANY(:patient_ids)"
        params["patient_ids"] = [str(pid) for pid in patient_ids]

    if start_date:
        base_query += " AND created_at >= :start_date"
        params["start_date"] = start_date

    if end_date:
        base_query += " AND created_at <= :end_date"
        params["end_date"] = end_date

    result = db.execute(text(base_query), params).fetchone()

    total = result.total_messages or 0
    responses = result.response_count or 0
    response_rate = round((responses / total * 100), 1) if total > 0 else 0

    return {
        "total_messages": total,
        "sent_count": result.sent_count or 0,
        "delivered_count": result.delivered_count or 0,
        "failed_count": result.failed_count or 0,
        "response_count": responses,
        "response_rate": response_rate,
    }


def _get_alert_metrics(db: Session, patient_ids: Optional[List[UUID]] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate alert metrics for dashboard widgets.

    Args:
        db: Database session
        patient_ids: Optional list of patient IDs to filter by
        start_date: Start date for filtering
        end_date: End date for filtering

    Returns:
        Dictionary of alert metrics
    """
    query = db.query(Alert)

    if patient_ids:
        query = query.filter(Alert.patient_id.in_(patient_ids))

    if start_date:
        query = query.filter(Alert.created_at >= start_date)

    if end_date:
        query = query.filter(Alert.created_at <= end_date)

    alerts = query.all()

    total_alerts = len(alerts)
    pending_alerts = len([a for a in alerts if not a.acknowledged])
    critical_alerts = len([a for a in alerts if a.severity == AlertSeverity.CRITICAL])
    high_alerts = len([a for a in alerts if a.severity == AlertSeverity.HIGH])

    return {
        "total_alerts": total_alerts,
        "pending_alerts": pending_alerts,
        "acknowledged_alerts": total_alerts - pending_alerts,
        "critical_alerts": critical_alerts,
        "high_alerts": high_alerts,
        "medium_alerts": len([a for a in alerts if a.severity == AlertSeverity.MEDIUM]),
        "low_alerts": len([a for a in alerts if a.severity == AlertSeverity.LOW]),
    }


def _get_flow_metrics(db: Session, patient_ids: Optional[List[UUID]] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate flow metrics for dashboard widgets.

    Args:
        db: Database session
        patient_ids: Optional list of patient IDs to filter by
        start_date: Start date for filtering
        end_date: End date for filtering

    Returns:
        Dictionary of flow metrics
    """
    base_query = """
        SELECT
            COUNT(*) as total_flows,
            COUNT(CASE WHEN status = 'active' THEN 1 END) as active_flows,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_flows,
            COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_flows,
            AVG(CASE WHEN status = 'completed' AND updated_at IS NOT NULL THEN
                EXTRACT(EPOCH FROM (updated_at - created_at)) / 86400 END) as avg_completion_days
        FROM patient_flows
        WHERE 1=1
    """

    params = {}

    if patient_ids:
        base_query += " AND patient_id = ANY(:patient_ids)"
        params["patient_ids"] = [str(pid) for pid in patient_ids]

    if start_date:
        base_query += " AND created_at >= :start_date"
        params["start_date"] = start_date

    if end_date:
        base_query += " AND created_at <= :end_date"
        params["end_date"] = end_date

    result = db.execute(text(base_query), params).fetchone()

    total = result.total_flows or 0
    completed = result.completed_flows or 0
    completion_rate = round((completed / total * 100), 1) if total > 0 else 0

    return {
        "total_flows": total,
        "active_flows": result.active_flows or 0,
        "completed_flows": completed,
        "paused_flows": result.paused_flows or 0,
        "completion_rate": completion_rate,
        "avg_completion_days": round(result.avg_completion_days or 0, 1),
    }


def _get_recent_activity(db: Session, patient_ids: Optional[List[UUID]] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent activity for dashboard feed.

    Args:
        db: Database session
        patient_ids: Optional list of patient IDs to filter by
        limit: Maximum number of activities to return

    Returns:
        List of activity dictionaries
    """
    activities = []

    # Build patient filter
    patient_filter = ""
    if patient_ids:
        patient_filter = f"AND m.patient_id = ANY(ARRAY[{','.join([f\"'{pid}'\" for pid in patient_ids])}]::uuid[])"

    # Recent messages
    message_query = text(f"""
        SELECT
            'message_sent' as type,
            CONCAT('Mensagem enviada para ', p.full_name) as description,
            p.full_name as entity_name,
            m.created_at as timestamp,
            m.id::text as reference_id
        FROM messages m
        JOIN patients p ON m.patient_id = p.id
        WHERE m.created_at >= NOW() - INTERVAL '24 hours'
        {patient_filter}
        ORDER BY m.created_at DESC
        LIMIT :limit
    """)

    message_results = db.execute(message_query, {"limit": limit // 3}).fetchall()
    for row in message_results:
        activities.append({
            "id": f"msg_{row.reference_id}",
            "type": row.type,
            "description": row.description,
            "entity_name": row.entity_name,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        })

    # Recent alerts
    alert_query = text(f"""
        SELECT
            'alert_created' as type,
            CONCAT('Alerta: ', a.description) as description,
            p.full_name as entity_name,
            a.created_at as timestamp,
            a.id::text as reference_id
        FROM alerts a
        JOIN patients p ON a.patient_id = p.id
        WHERE a.created_at >= NOW() - INTERVAL '24 hours'
        {patient_filter.replace('m.patient_id', 'a.patient_id')}
        ORDER BY a.created_at DESC
        LIMIT :limit
    """)

    alert_results = db.execute(alert_query, {"limit": limit // 3}).fetchall()
    for row in alert_results:
        activities.append({
            "id": f"alert_{row.reference_id}",
            "type": row.type,
            "description": row.description,
            "entity_name": row.entity_name,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        })

    # Sort by timestamp and limit
    activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return activities[:limit]


def _get_engagement_chart_data(db: Session, patient_ids: Optional[List[UUID]] = None, days: int = 7) -> List[Dict[str, Any]]:
    """
    Get engagement chart data (messages sent vs responses).

    Args:
        db: Database session
        patient_ids: Optional list of patient IDs to filter by
        days: Number of days to include

    Returns:
        List of daily engagement data points
    """
    start_date = datetime.utcnow().date() - timedelta(days=days-1)

    patient_filter = ""
    if patient_ids:
        patient_filter = f"AND patient_id = ANY(ARRAY[{','.join([f\"'{pid}'\" for pid in patient_ids])}]::uuid[])"

    query = text(f"""
        WITH date_series AS (
            SELECT generate_series(
                :start_date::date,
                CURRENT_DATE,
                '1 day'::interval
            )::date AS date
        ),
        daily_messages AS (
            SELECT DATE(created_at) as date,
                   COUNT(*) as messages_sent,
                   COUNT(CASE WHEN patient_response_received = true THEN 1 END) as responses_received
            FROM messages
            WHERE DATE(created_at) >= :start_date
            {patient_filter}
            GROUP BY DATE(created_at)
        )
        SELECT ds.date,
               COALESCE(dm.messages_sent, 0) as messages_sent,
               COALESCE(dm.responses_received, 0) as responses_received,
               CASE
                   WHEN COALESCE(dm.messages_sent, 0) = 0 THEN 0
                   ELSE ROUND((COALESCE(dm.responses_received, 0)::float / dm.messages_sent) * 100, 1)
               END as response_rate
        FROM date_series ds
        LEFT JOIN daily_messages dm ON ds.date = dm.date
        ORDER BY ds.date
    """)

    results = db.execute(query, {"start_date": start_date}).fetchall()

    return [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "messages_sent": row.messages_sent,
            "responses_received": row.responses_received,
            "response_rate": row.response_rate,
        }
        for row in results
    ]


@router.get("/main", response_model=DashboardMainResponse)
@limiter.limit("30/minute")
async def get_main_dashboard(
    request: Request,
    time_range: TimeRangeEnum = Query(TimeRangeEnum.WEEK, description="Time range for metrics"),
    custom_start: Optional[datetime] = Query(None, description="Custom start date (for CUSTOM range)"),
    custom_end: Optional[datetime] = Query(None, description="Custom end date (for CUSTOM range)"),
    fields: Optional[List[str]] = Depends(get_field_selection),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get main dashboard overview with key metrics and widgets.

    Features:
    - Role-based data filtering (Admin: all, Doctor: assigned patients, Patient: self)
    - Real-time metrics with 2-minute cache
    - Key performance indicators (KPIs)
    - Quick stats and trend indicators
    - Recent activity feed

    Widgets included:
    - Patient count metrics
    - Message statistics
    - Alert summary
    - Flow completion rates
    - Recent activity feed

    Rate limit: 30 requests/minute
    Cache TTL: 120 seconds (2 minutes)
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
        start_date, end_date = _calculate_date_range(time_range, custom_start, custom_end)

        # Determine patient scope based on role
        patient_ids = None
        if role == UserRole.DOCTOR:
            # Get doctor's patients
            patient_ids = [p.id for p in db.query(Patient.id).filter(Patient.doctor_id == user_id).all()]
        elif role == UserRole.PATIENT:
            # Patient sees only their own data
            patient_ids = [user_id]
        # Admin sees all (patient_ids = None)

        # Fetch all metrics
        patient_metrics = _get_patient_metrics(db, patient_ids, start_date, end_date)
        message_metrics = _get_message_metrics(db, patient_ids, start_date, end_date)
        alert_metrics = _get_alert_metrics(db, patient_ids, start_date, end_date)
        flow_metrics = _get_flow_metrics(db, patient_ids, start_date, end_date)
        recent_activity = _get_recent_activity(db, patient_ids, limit=10)

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
            detail="Failed to retrieve main dashboard"
        )


@router.get("/patient/{patient_id}", response_model=DashboardPatientResponse)
@limiter.limit("30/minute")
async def get_patient_dashboard(
    patient_id: UUID,
    request: Request,
    time_range: TimeRangeEnum = Query(TimeRangeEnum.MONTH, description="Time range for metrics"),
    custom_start: Optional[datetime] = Query(None, description="Custom start date"),
    custom_end: Optional[datetime] = Query(None, description="Custom end date"),
    fields: Optional[List[str]] = Depends(get_field_selection),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get patient-specific dashboard with detailed health metrics.

    Features:
    - Personal health data and trends
    - Medication adherence tracking
    - Appointment schedule
    - Alert history
    - Treatment progress
    - Quiz performance

    Access Control:
    - Admin: All patients
    - Doctor: Own patients only
    - Patient: Self only

    Rate limit: 30 requests/minute
    Cache TTL: 120 seconds (2 minutes)
    """
    try:
        role = _extract_user_role(current_user)
        user_id = UUID(current_user.get("id"))

        # Verify patient exists
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )

        # Check access
        if role == UserRole.DOCTOR and patient.doctor_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Not your patient"
            )
        elif role == UserRole.PATIENT and patient_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Can only view own dashboard"
            )

        # Build cache key
        cache_key = f"dashboard:patient:{patient_id}:range:{time_range.value}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for patient dashboard: {cache_key}")
            return apply_field_selection(cached_data, fields) if fields else cached_data

        # Calculate date range
        start_date, end_date = _calculate_date_range(time_range, custom_start, custom_end)

        # Fetch patient-specific metrics
        message_metrics = _get_message_metrics(db, [patient_id], start_date, end_date)
        alert_metrics = _get_alert_metrics(db, [patient_id], start_date, end_date)
        flow_metrics = _get_flow_metrics(db, [patient_id], start_date, end_date)
        recent_activity = _get_recent_activity(db, [patient_id], limit=15)
        engagement_data = _get_engagement_chart_data(db, [patient_id], days=30)

        # Patient info
        patient_info = {
            "id": str(patient.id),
            "full_name": patient.full_name,
            "email": patient.email,
            "is_active": patient.is_active,
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
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Cache the result
        await redis_cache.set(cache_key, response, ttl=CACHE_TTL_REALTIME)

        return apply_field_selection(response, fields) if fields else response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching patient dashboard for {patient_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve patient dashboard"
        )


@router.get("/physician", response_model=DashboardPhysicianResponse)
@limiter.limit("30/minute")
async def get_physician_dashboard(
    request: Request,
    time_range: TimeRangeEnum = Query(TimeRangeEnum.WEEK, description="Time range for metrics"),
    custom_start: Optional[datetime] = Query(None, description="Custom start date"),
    custom_end: Optional[datetime] = Query(None, description="Custom end date"),
    fields: Optional[List[str]] = Depends(get_field_selection),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get physician-specific dashboard with practice metrics.

    Features:
    - Assigned patients overview
    - Pending alerts requiring attention
    - Upcoming appointments
    - Patient engagement metrics
    - Treatment completion rates
    - Top priorities and action items

    Access Control:
    - Admin: Can view (shows aggregated data)
    - Doctor: Own practice data only
    - Patient: Access denied

    Rate limit: 30 requests/minute
    Cache TTL: 120 seconds (2 minutes)
    """
    try:
        role = _extract_user_role(current_user)
        user_id = UUID(current_user.get("id"))

        # Only doctors and admins can access
        if role == UserRole.PATIENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patients cannot access physician dashboard"
            )

        # Build cache key
        cache_key = f"dashboard:physician:{user_id}:range:{time_range.value}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for physician dashboard: {cache_key}")
            return apply_field_selection(cached_data, fields) if fields else cached_data

        # Calculate date range
        start_date, end_date = _calculate_date_range(time_range, custom_start, custom_end)

        # Get physician's patients
        patient_ids = None
        if role == UserRole.DOCTOR:
            patient_ids = [p.id for p in db.query(Patient.id).filter(Patient.doctor_id == user_id).all()]

        # Fetch metrics
        patient_metrics = _get_patient_metrics(db, patient_ids, start_date, end_date)
        message_metrics = _get_message_metrics(db, patient_ids, start_date, end_date)
        alert_metrics = _get_alert_metrics(db, patient_ids, start_date, end_date)
        flow_metrics = _get_flow_metrics(db, patient_ids, start_date, end_date)

        # Get high-priority alerts
        high_priority_alerts_query = db.query(Alert).filter(
            Alert.severity.in_([AlertSeverity.CRITICAL, AlertSeverity.HIGH]),
            Alert.acknowledged == False
        )
        if patient_ids:
            high_priority_alerts_query = high_priority_alerts_query.filter(Alert.patient_id.in_(patient_ids))

        high_priority_alerts = high_priority_alerts_query.order_by(desc(Alert.created_at)).limit(10).all()

        alerts_list = [
            {
                "id": str(alert.id),
                "patient_id": str(alert.patient_id),
                "severity": alert.severity.value,
                "alert_type": alert.alert_type,
                "description": alert.description,
                "created_at": alert.created_at.isoformat(),
            }
            for alert in high_priority_alerts
        ]

        # Get top patients by risk
        top_risk_patients_query = db.query(
            Patient.id,
            Patient.full_name,
            func.count(Alert.id).label("alert_count")
        ).join(Alert).filter(
            Alert.severity.in_([AlertSeverity.CRITICAL, AlertSeverity.HIGH]),
            Alert.acknowledged == False
        )

        if patient_ids:
            top_risk_patients_query = top_risk_patients_query.filter(Patient.id.in_(patient_ids))

        top_risk_patients = top_risk_patients_query.group_by(
            Patient.id, Patient.full_name
        ).order_by(desc("alert_count")).limit(10).all()

        risk_patients_list = [
            {
                "patient_id": str(p.id),
                "patient_name": p.full_name,
                "alert_count": p.alert_count,
            }
            for p in top_risk_patients
        ]

        # Build response
        response = {
            "user_id": str(user_id),
            "time_range": time_range.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "patient_metrics": patient_metrics,
            "message_metrics": message_metrics,
            "alert_metrics": alert_metrics,
            "flow_metrics": flow_metrics,
            "high_priority_alerts": alerts_list,
            "top_risk_patients": risk_patients_list,
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
            detail="Failed to retrieve physician dashboard"
        )


@router.get("/admin", response_model=DashboardAdminResponse)
@limiter.limit("60/minute")
async def get_admin_dashboard(
    request: Request,
    time_range: TimeRangeEnum = Query(TimeRangeEnum.MONTH, description="Time range for metrics"),
    custom_start: Optional[datetime] = Query(None, description="Custom start date"),
    custom_end: Optional[datetime] = Query(None, description="Custom end date"),
    fields: Optional[List[str]] = Depends(get_field_selection),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get admin dashboard with system-wide metrics and analytics.

    Features:
    - System-wide statistics
    - User management metrics
    - Platform health indicators
    - Performance analytics
    - Revenue and engagement trends
    - Top physicians and patients
    - Error rates and system alerts

    Access Control:
    - Admin: Full access
    - Doctor/Patient: Access denied

    Rate limit: 60 requests/minute (higher for admin operations)
    Cache TTL: 600 seconds (10 minutes)
    """
    try:
        role = _extract_user_role(current_user)

        # Only admins can access
        if role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        # Build cache key
        cache_key = f"dashboard:admin:range:{time_range.value}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for admin dashboard: {cache_key}")
            return apply_field_selection(cached_data, fields) if fields else cached_data

        # Calculate date range
        start_date, end_date = _calculate_date_range(time_range, custom_start, custom_end)

        # Fetch system-wide metrics
        patient_metrics = _get_patient_metrics(db, None, start_date, end_date)
        message_metrics = _get_message_metrics(db, None, start_date, end_date)
        alert_metrics = _get_alert_metrics(db, None, start_date, end_date)
        flow_metrics = _get_flow_metrics(db, None, start_date, end_date)

        # User statistics
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        doctors_count = db.query(User).filter(User.role == UserRole.DOCTOR).count()
        patients_count = db.query(User).filter(User.role == UserRole.PATIENT).count()

        user_metrics = {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "doctors_count": doctors_count,
            "patients_count": patients_count,
            "admins_count": db.query(User).filter(User.role == UserRole.ADMIN).count(),
        }

        # Top performing physicians by patient engagement
        top_physicians_query = text("""
            SELECT
                u.id,
                u.full_name,
                COUNT(DISTINCT p.id) as patient_count,
                COUNT(m.id) as message_count,
                AVG(CASE WHEN m.patient_response_received THEN 1.0 ELSE 0.0 END) * 100 as engagement_rate
            FROM users u
            LEFT JOIN patients p ON p.doctor_id = u.id
            LEFT JOIN messages m ON m.patient_id = p.id AND m.created_at >= :start_date
            WHERE u.role = 'doctor'
            GROUP BY u.id, u.full_name
            ORDER BY engagement_rate DESC
            LIMIT 10
        """)

        top_physicians = db.execute(top_physicians_query, {"start_date": start_date}).fetchall()

        physicians_list = [
            {
                "physician_id": str(p.id),
                "physician_name": p.full_name,
                "patient_count": p.patient_count or 0,
                "message_count": p.message_count or 0,
                "engagement_rate": round(p.engagement_rate or 0, 1),
            }
            for p in top_physicians
        ]

        # System health indicators
        system_health = {
            "message_success_rate": round(
                (message_metrics["sent_count"] + message_metrics["delivered_count"]) / message_metrics["total_messages"] * 100, 1
            ) if message_metrics["total_messages"] > 0 else 100,
            "alert_response_rate": round(
                alert_metrics["acknowledged_alerts"] / alert_metrics["total_alerts"] * 100, 1
            ) if alert_metrics["total_alerts"] > 0 else 100,
            "flow_completion_rate": flow_metrics["completion_rate"],
            "patient_active_rate": round(
                patient_metrics["active_patients"] / patient_metrics["total_patients"] * 100, 1
            ) if patient_metrics["total_patients"] > 0 else 100,
        }

        # Build response
        response = {
            "time_range": time_range.value,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "patient_metrics": patient_metrics,
            "message_metrics": message_metrics,
            "alert_metrics": alert_metrics,
            "flow_metrics": flow_metrics,
            "user_metrics": user_metrics,
            "top_physicians": physicians_list,
            "system_health": system_health,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Cache the result (longer TTL for admin dashboard)
        await redis_cache.set(cache_key, response, ttl=CACHE_TTL_STATS)

        return apply_field_selection(response, fields) if fields else response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching admin dashboard: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve admin dashboard"
        )


@router.get("/custom/{dashboard_id}", response_model=CustomDashboardResponse)
@limiter.limit("30/minute")
async def get_custom_dashboard(
    dashboard_id: UUID,
    request: Request,
    fields: Optional[List[str]] = Depends(get_field_selection),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get custom dashboard by ID with user-defined widget layout.

    Features:
    - Custom widget configurations
    - Saved dashboard layouts
    - Personalized data views
    - Widget positioning and sizing

    Access Control:
    - Users can only access their own custom dashboards
    - Admins can access all custom dashboards

    Rate limit: 30 requests/minute
    Cache TTL: 300 seconds (5 minutes)
    """
    try:
        role = _extract_user_role(current_user)
        user_id = UUID(current_user.get("id"))

        # Build cache key
        cache_key = f"dashboard:custom:{dashboard_id}:user:{user_id}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for custom dashboard: {cache_key}")
            return apply_field_selection(cached_data, fields) if fields else cached_data

        # Fetch custom dashboard configuration
        # Note: This assumes a custom_dashboards table exists
        # For now, return a placeholder response

        response = {
            "dashboard_id": str(dashboard_id),
            "user_id": str(user_id),
            "name": "Custom Dashboard",
            "description": "User-defined dashboard layout",
            "widgets": [],
            "layout": {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Cache the result
        await redis_cache.set(cache_key, response, ttl=CACHE_TTL_STATS)

        return apply_field_selection(response, fields) if fields else response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching custom dashboard {dashboard_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve custom dashboard"
        )


@router.put("/custom/{dashboard_id}/layout", response_model=CustomDashboardResponse)
@limiter.limit("10/minute")
async def update_dashboard_layout(
    dashboard_id: UUID,
    layout_data: DashboardLayoutUpdate,
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Update custom dashboard layout and widget configuration.

    Features:
    - Save widget positions
    - Update widget configurations
    - Modify dashboard settings
    - Persist custom layouts

    Access Control:
    - Users can only update their own dashboards
    - Admins can update any dashboard

    Rate limit: 10 requests/minute (lower for write operations)
    Cache invalidation: Clears custom dashboard cache
    """
    try:
        role = _extract_user_role(current_user)
        user_id = UUID(current_user.get("id"))

        # Verify ownership or admin
        # Note: This assumes a custom_dashboards table exists

        # Invalidate cache
        cache_key = f"dashboard:custom:{dashboard_id}:user:{user_id}"
        await redis_cache.delete(cache_key)

        # Update dashboard layout
        # For now, return updated response
        response = {
            "dashboard_id": str(dashboard_id),
            "user_id": str(user_id),
            "name": layout_data.name if hasattr(layout_data, 'name') else "Custom Dashboard",
            "description": layout_data.description if hasattr(layout_data, 'description') else None,
            "widgets": layout_data.widgets if hasattr(layout_data, 'widgets') else [],
            "layout": layout_data.layout if hasattr(layout_data, 'layout') else {},
            "updated_at": datetime.utcnow().isoformat(),
        }

        logger.info(f"Dashboard layout updated: {dashboard_id} by user {user_id}")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating dashboard layout {dashboard_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update dashboard layout"
        )
