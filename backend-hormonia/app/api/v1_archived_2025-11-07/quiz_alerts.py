"""
Quiz Alert Endpoints for Hormonia Backend System.

Sprint 2 - Week 1, Task 3: Automatic Alert Evaluation API
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.auth_dependencies import get_current_user
from app.database import get_db
from app.models.user import User, UserRole
from app.models.alert import AlertSeverity, AlertStatus
from app.repositories.alert import AlertRepository
from app.services.quiz_response_evaluator import QuizResponseEvaluator
from app.schemas.alert import AlertResponse, AlertsResponse
from app.exceptions import NotFoundError
from app.core.rate_limiting import rate_limit


router = APIRouter(prefix="/quiz-alerts", tags=["Quiz Alerts"])


@router.get(
    "/patient/{patient_id}",
    response_model=AlertsResponse,
    summary="Get quiz-generated alerts for patient",
    description="Retrieve all alerts generated from quiz responses for a specific patient"
)
@rate_limit(max_requests=100, window_seconds=60)
async def get_patient_quiz_alerts(
    patient_id: UUID,
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    status: Optional[AlertStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get quiz-generated alerts for a specific patient.

    **Permissions:**
    - Médico: Can view alerts for their patients
    - Admin: Can view all alerts

    **Filters:**
    - severity: CRITICAL, HIGH, MEDIUM, LOW
    - status: PENDING, ACKNOWLEDGED, RESOLVED, DISMISSED

    **Returns:**
    - List of alerts with pagination metadata
    """
    # Authorization check
    if current_user.role not in {UserRole.DOCTOR, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view patient alerts"
        )

    # Get alerts
    alert_repository = AlertRepository(db)

    # Get quiz-response type alerts
    query_filters = {"alert_type": "quiz_response"}

    if severity:
        alerts = alert_repository.get_by_severity(severity, skip=skip, limit=limit)
        # Filter by patient_id
        alerts = [a for a in alerts if a.patient_id == patient_id]
    elif status:
        alerts = alert_repository.get_alerts_by_patient_and_status(
            patient_id, status, skip=skip, limit=limit
        )
        # Filter by type
        alerts = [a for a in alerts if a.alert_type == "quiz_response"]
    else:
        alerts = alert_repository.get_by_patient(patient_id, skip=skip, limit=limit)
        # Filter by type
        alerts = [a for a in alerts if a.alert_type == "quiz_response"]

    total = len(alerts)

    return AlertsResponse(
        alerts=[AlertResponse.from_orm(alert) for alert in alerts],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get(
    "/session/{session_id}",
    response_model=AlertsResponse,
    summary="Get alerts for quiz session",
    description="Retrieve all alerts generated from a specific quiz session"
)
@rate_limit(max_requests=100, window_seconds=60)
async def get_quiz_session_alerts(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all alerts generated from a specific quiz session.

    **Permissions:**
    - Médico: Can view alerts for their patients' sessions
    - Admin: Can view all alerts

    **Returns:**
    - List of alerts for the session
    """
    # Authorization check
    if current_user.role not in {UserRole.DOCTOR, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view quiz alerts"
        )

    # Get alerts for session
    alert_repository = AlertRepository(db)

    # Query alerts by session_id (stored in data field)
    all_alerts = alert_repository.get_by_patient(
        patient_id=current_user.id,  # Will be filtered later
        limit=1000
    )

    session_alerts = [
        alert for alert in all_alerts
        if alert.quiz_session_id == session_id
    ]

    return AlertsResponse(
        alerts=[AlertResponse.from_orm(alert) for alert in session_alerts],
        total=len(session_alerts),
        skip=0,
        limit=len(session_alerts)
    )


@router.get(
    "/summary/{patient_id}",
    summary="Get alert evaluation summary for patient",
    description="Get statistics and summary of quiz alert evaluations"
)
@rate_limit(max_requests=50, window_seconds=60)
async def get_patient_alert_summary(
    patient_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive alert evaluation summary for a patient.

    **Returns:**
    - Total quiz alerts
    - Breakdown by severity
    - Most common triggered rules
    - Acknowledgement rate
    """
    # Authorization check
    if current_user.role not in {UserRole.DOCTOR, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view alert summaries"
        )

    # Get summary
    evaluator = QuizResponseEvaluator(db)

    try:
        summary = evaluator.get_evaluation_summary(patient_id, days=days)
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate alert summary: {str(e)}"
        )


@router.post(
    "/acknowledge/{alert_id}",
    response_model=AlertResponse,
    summary="Acknowledge a quiz alert",
    description="Mark a quiz alert as acknowledged by medical staff"
)
@rate_limit(max_requests=100, window_seconds=60)
async def acknowledge_quiz_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Acknowledge a quiz alert.

    **Permissions:**
    - Médico: Can acknowledge alerts for their patients
    - Admin: Can acknowledge all alerts

    **Returns:**
    - Updated alert with acknowledgment details
    """
    # Authorization check
    if current_user.role not in {UserRole.DOCTOR, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can acknowledge alerts"
        )

    # Get alert
    alert_repository = AlertRepository(db)
    alert = alert_repository.get(alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )

    # Update status
    result = alert_repository.bulk_update_status(
        alert_ids=[alert_id],
        new_status=AlertStatus.ACKNOWLEDGED,
        acknowledged_by=current_user.id
    )

    if result == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge alert"
        )

    # Refresh and return
    db.refresh(alert)
    return AlertResponse.from_orm(alert)


@router.get(
    "/critical",
    response_model=AlertsResponse,
    summary="Get all critical quiz alerts",
    description="Retrieve all unacknowledged CRITICAL alerts from quiz evaluations"
)
@rate_limit(max_requests=50, window_seconds=60)
async def get_critical_quiz_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all critical unacknowledged quiz alerts.

    **Permissions:**
    - Médico: Can view critical alerts for their patients
    - Admin: Can view all critical alerts

    **Returns:**
    - List of CRITICAL alerts that are PENDING
    """
    # Authorization check
    if current_user.role not in {UserRole.DOCTOR, UserRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only medical staff can view critical alerts"
        )

    # Get critical alerts
    alert_repository = AlertRepository(db)
    critical_alerts = alert_repository.get_critical_unacknowledged(
        skip=skip,
        limit=limit
    )

    # Filter quiz-response type
    quiz_critical_alerts = [
        a for a in critical_alerts
        if a.alert_type == "quiz_response"
    ]

    return AlertsResponse(
        alerts=[AlertResponse.from_orm(alert) for alert in quiz_critical_alerts],
        total=len(quiz_critical_alerts),
        skip=skip,
        limit=limit
    )
