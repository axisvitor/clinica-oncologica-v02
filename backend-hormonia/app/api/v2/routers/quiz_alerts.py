"""
Quiz Alerts API v2 - Quiz Alert Management System

Alert management endpoints with:
- Alert listing with cursor pagination and filtering
- Alert detail retrieval
- Alert acknowledgement workflow
- Alert statistics and analytics
- Alert rule creation and configuration

Features:
- Automated alert triggers based on quiz responses
- Severity-based alert prioritization (CRITICAL, HIGH, MEDIUM, LOW)
- Alert status workflow (PENDING -> ACKNOWLEDGED -> RESOLVED/DISMISSED)
- Alert acknowledgement tracking with timestamps
- Alert statistics with response time metrics
- Alert rule engine with flexible trigger conditions
- Redis caching with 1-2 minute TTLs (time-sensitive data)
- Rate limiting to prevent abuse
- RBAC: Doctors (assigned patients), Admin (full access)

This module was extracted from quiz_extensions.py as part of the backend refactoring.
Total: 5 alert endpoints
"""

from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
# from sqlalchemy.orm import Session,
from sqlalchemy import desc, asc

from app.database import get_db
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.schemas.v2.quiz_extensions import (
    QuizAlertV2Detail,
    QuizAlertV2List,
    AlertAcknowledgementV2,
    AlertStatisticsV2,
    AlertRuleV2Create,
    AlertRuleV2Detail,
)
from app.api.v2.dependencies import (
    get_pagination_params,
    create_cursor,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.utils.rate_limiter import limiter

# Import shared helpers and cache TTLs
from app.api.v2._quiz_shared import (
    _get_current_user_simple,
    _check_patient_access,
    CACHE_TTL_ALERTS,
    CACHE_TTL_STATISTICS,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Quiz Alert Endpoints (5 endpoints)
# ============================================================================

@router.get(
    "/alerts",
    response_model=QuizAlertV2List,
    summary="List quiz alerts",
    description="List quiz-triggered alerts with cursor pagination"
)
@limiter.limit("50/minute")  # Doctor/Admin limit
async def list_quiz_alerts(
    request: Request,
    patient_id: Optional[UUID] = Query(None, description="Filter by patient"),
    session_id: Optional[UUID] = Query(None, description="Filter by quiz session"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    status: Optional[AlertStatus] = Query(None, description="Filter by status"),
    pagination: dict = Depends(get_pagination_params),
    db = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """
    List quiz-related alerts.

    **RBAC:**
    - Doctors: View assigned patients' alerts
    - Admin: View all alerts

    **Cache:** 1 minute TTL (time-sensitive)
    """
    # Only doctors and admins can view alerts
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz alerts"
        )

    # Build query for quiz-related alerts
    query = db.query(Alert).filter(Alert.alert_type == "quiz_response")

    # Apply RBAC
    if current_user.role == UserRole.DOCTOR:
        patient_ids = db.query(Patient.id).filter(Patient.doctor_id == current_user.id).all()
        patient_ids = [p[0] for p in patient_ids]
        query = query.filter(Alert.patient_id.in_(patient_ids))

    # Apply filters
    if patient_id:
        _check_patient_access(db, current_user, patient_id)
        query = query.filter(Alert.patient_id == patient_id)

    if session_id:
        # Filter by session_id in data field
        query = query.filter(Alert.data["quiz_session_id"].astext == str(session_id))

    if severity:
        query = query.filter(Alert.severity == severity)

    if status:
        query = query.filter(Alert.status == status)

    # Apply cursor pagination
    cursor_data = pagination.get("cursor_data")
    limit = pagination.get("limit", 20)

    if cursor_data:
        query = query.filter(Alert.id > cursor_data.get("id"))

    # Order by ID
    query = query.order_by(desc(Alert.created_at), asc(Alert.id))

    # Fetch limit + 1
    alerts = query.limit(limit + 1).all()

    # Check if there are more
    has_more = len(alerts) > limit
    if has_more:
        alerts = alerts[:limit]

    # Enrich alerts with patient names
    enriched_alerts = []
    for alert in alerts:
        patient = db.query(Patient).filter(Patient.id == alert.patient_id).first()

        enriched = QuizAlertV2Detail(
            id=alert.id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            description=alert.description,
            trigger_data=alert.data,
            patient_id=alert.patient_id,
            quiz_session_id=alert.data.get("quiz_session_id") if alert.data else None,
            response_id=alert.data.get("response_id") if alert.data else None,
            status=alert.status,
            created_at=alert.created_at,
            acknowledged_at=alert.acknowledged_at,
            acknowledged_by=alert.acknowledged_by,
            resolved_at=alert.resolved_at,
            patient_name=patient.name if patient else None
        )
        enriched_alerts.append(enriched)

    # Generate next cursor
    next_cursor = None
    if has_more and alerts:
        last_item = alerts[-1]
        next_cursor = create_cursor(last_item.id, last_item.created_at)

    total = query.count()

    return QuizAlertV2List(
        data=enriched_alerts,
        next_cursor=next_cursor,
        has_more=has_more,
        total=total
    )


@router.get(
    "/alerts/{alert_id}",
    response_model=QuizAlertV2Detail,
    summary="Get quiz alert details",
    description="Get detailed information about a quiz alert"
)
@limiter.limit("50/minute")
async def get_quiz_alert_detail(
    request: Request,
    alert_id: UUID,
    db = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """Get detailed quiz alert information."""
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz alerts"
        )

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Check access
    if current_user.role == UserRole.DOCTOR:
        _check_patient_access(db, current_user, alert.patient_id)

    patient = db.query(Patient).filter(Patient.id == alert.patient_id).first()

    return QuizAlertV2Detail(
        id=alert.id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        description=alert.description,
        trigger_data=alert.data,
        patient_id=alert.patient_id,
        quiz_session_id=alert.data.get("quiz_session_id") if alert.data else None,
        response_id=alert.data.get("response_id") if alert.data else None,
        status=alert.status,
        created_at=alert.created_at,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        resolved_at=alert.resolved_at,
        patient_name=patient.name if patient else None
    )


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=QuizAlertV2Detail,
    summary="Acknowledge quiz alert",
    description="Mark a quiz alert as acknowledged"
)
@limiter.limit("50/minute")
async def acknowledge_quiz_alert(
    request: Request,
    alert_id: UUID,
    acknowledgement: AlertAcknowledgementV2,
    db = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """
    Acknowledge a quiz alert.

    **RBAC:**
    - Doctors: Acknowledge alerts for assigned patients
    - Admin: Acknowledge all alerts
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can acknowledge alerts"
        )

    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Check access
    if current_user.role == UserRole.DOCTOR:
        _check_patient_access(db, current_user, alert.patient_id)

    # Update alert
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = current_user.id

    # Add notes to data field if provided
    if acknowledgement.notes:
        if not alert.data:
            alert.data = {}
        alert.data["acknowledgement_notes"] = acknowledgement.notes

    db.commit()
    db.refresh(alert)

    logger.info(f"Alert {alert_id} acknowledged by user {current_user.id}")

    patient = db.query(Patient).filter(Patient.id == alert.patient_id).first()

    return QuizAlertV2Detail(
        id=alert.id,
        alert_type=alert.alert_type,
        severity=alert.severity,
        description=alert.description,
        trigger_data=alert.data,
        patient_id=alert.patient_id,
        quiz_session_id=alert.data.get("quiz_session_id") if alert.data else None,
        response_id=alert.data.get("response_id") if alert.data else None,
        status=alert.status,
        created_at=alert.created_at,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        resolved_at=alert.resolved_at,
        patient_name=patient.name if patient else None
    )


@router.get(
    "/alerts/statistics",
    response_model=AlertStatisticsV2,
    summary="Get alert statistics",
    description="Get aggregate statistics for quiz alerts"
)
@limiter.limit("30/minute")
async def get_alert_statistics(
    request: Request,
    patient_id: Optional[UUID] = Query(None, description="Filter by patient"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    db = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple),
    redis_cache = Depends(get_redis_cache)
):
    """
    Get quiz alert statistics.

    **RBAC:**
    - Doctors: View stats for assigned patients
    - Admin: View all stats

    **Cache:** 2 minutes TTL
    """
    if current_user.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view alert statistics"
        )

    # Build query
    query = db.query(Alert).filter(Alert.alert_type == "quiz_response")

    # Apply RBAC
    if current_user.role == UserRole.DOCTOR:
        patient_ids = db.query(Patient.id).filter(Patient.doctor_id == current_user.id).all()
        patient_ids = [p[0] for p in patient_ids]
        query = query.filter(Alert.patient_id.in_(patient_ids))

    # Apply filters
    if patient_id:
        _check_patient_access(db, current_user, patient_id)
        query = query.filter(Alert.patient_id == patient_id)

    if start_date:
        query = query.filter(Alert.created_at >= start_date)

    if end_date:
        query = query.filter(Alert.created_at <= end_date)

    # Get alerts
    alerts = query.all()
    total_alerts = len(alerts)

    # Count by severity
    by_severity = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0
    }
    for alert in alerts:
        by_severity[alert.severity.value] += 1

    # Count by status
    by_status = {
        "PENDING": 0,
        "ACKNOWLEDGED": 0,
        "RESOLVED": 0,
        "DISMISSED": 0
    }
    for alert in alerts:
        by_status[alert.status.value] += 1

    # Calculate acknowledgement rate
    acknowledged_count = by_status.get("ACKNOWLEDGED", 0) + by_status.get("RESOLVED", 0)
    acknowledgement_rate = (acknowledged_count / total_alerts * 100) if total_alerts > 0 else 0.0

    # Calculate average response time
    response_times = []
    for alert in alerts:
        if alert.acknowledged_at:
            time_diff = (alert.acknowledged_at - alert.created_at).total_seconds() / 3600
            response_times.append(time_diff)

    avg_response_time = sum(response_times) / len(response_times) if response_times else None

    # Get triggered rules
    rule_counts = defaultdict(int)
    for alert in alerts:
        if alert.data and "rule_name" in alert.data:
            rule_counts[alert.data["rule_name"]] += 1

    triggered_rules = [
        {"rule_name": rule, "count": count}
        for rule, count in sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    return AlertStatisticsV2(
        total_alerts=total_alerts,
        by_severity=by_severity,
        by_status=by_status,
        acknowledgement_rate=round(acknowledgement_rate, 2),
        avg_response_time_hours=round(avg_response_time, 2) if avg_response_time else None,
        triggered_rules=triggered_rules
    )


@router.post(
    "/alerts/rules",
    response_model=AlertRuleV2Detail,
    summary="Create alert rule",
    description="Create a new quiz alert rule",
    status_code=status.HTTP_201_CREATED
)
@limiter.limit("20/minute")
async def create_alert_rule(
    request: Request,
    rule: AlertRuleV2Create,
    db = Depends(get_db),
    current_user: User = Depends(_get_current_user_simple)
):
    """
    Create a new quiz alert rule.

    **RBAC:** Admin only

    Alert rules automatically trigger alerts based on quiz responses:
    - Score thresholds
    - Answer patterns
    - Missing responses
    - Trend detection
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create alert rules"
        )

    # For now, we'll store rules in a JSONB field in the Alert model
    # In a production system, you'd have a dedicated AlertRule model
    # This is a simplified implementation for the migration

    # Create a placeholder alert rule record
    # In production, use a proper AlertRule model
    rule_record = Alert(
        alert_type="alert_rule_definition",
        severity=rule.severity,
        description=f"Alert rule: {rule.rule_name}",
        data={
            "rule_name": rule.rule_name,
            "trigger_type": rule.trigger_type.value,
            "trigger_condition": rule.trigger_condition,
            "notification_type": rule.notification_type,
            "enabled": rule.enabled,
            "is_rule_definition": True,
            "created_by": str(current_user.id),
            "triggered_count": 0
        },
        patient_id=None,  # Rules don't belong to specific patients
        status=AlertStatus.PENDING
    )

    db.add(rule_record)
    db.commit()
    db.refresh(rule_record)

    logger.info(f"Alert rule '{rule.rule_name}' created by user {current_user.id}")

    return AlertRuleV2Detail(
        id=rule_record.id,
        rule_name=rule.rule_name,
        trigger_type=rule.trigger_type,
        trigger_condition=rule.trigger_condition,
        severity=rule.severity,
        notification_type=rule.notification_type,
        enabled=rule.enabled,
        created_by=current_user.id,
        created_at=rule_record.created_at,
        updated_at=rule_record.updated_at,
        triggered_count=0,
        last_triggered_at=None
    )
