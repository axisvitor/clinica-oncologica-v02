"""
Patient Analytics Module
Handles patient engagement, risk assessment and patient-related metrics.
"""

from typing import Optional, Dict
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.models.quiz import QuizSession
from app.models.patient import Patient
from app.models.user import UserRole
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.dependencies.service_dependencies import get_flow_analytics_service
from app.schemas.v2.analytics import PatientEngagement
from app.services.analytics import FlowAnalyticsService, RiskLevel
from app.utils.logging import get_logger

from .base import (
    get_role_and_user,
    serialize_patient_risk,
    get_cache_key,
    get_cached_result,
    set_cached_result,
)

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/patient-engagement",
    response_model=PatientEngagement,
    summary="Get patient engagement metrics",
    description="Get patient engagement statistics and distribution (ADMIN/DOCTOR only)",
)
async def get_patient_engagement(
    db=Depends(get_db),
    current_user=Depends(get_current_user_from_session),
):
    """
    Get patient engagement metrics.

    Returns:
    - Patients with 0 quizzes
    - Patients with 1-5 quizzes
    - Patients with 6+ quizzes
    - Average quizzes per patient
    """
    from sqlalchemy import func

    role, user_uuid = get_role_and_user(current_user)

    # Check cache first
    cache_key = get_cache_key(
        "patient-engagement",
        role=role.value,
        user=str(user_uuid) if user_uuid else None,
    )
    cached_result = await get_cached_result(cache_key)
    if cached_result:
        return cached_result

    # Get quiz counts per patient
    patient_query = db.query(
        Patient.id, func.count(QuizSession.id).label("quiz_count")
    ).outerjoin(QuizSession, Patient.id == QuizSession.patient_id)

    if role != UserRole.ADMIN and user_uuid:
        patient_query = patient_query.filter(Patient.doctor_id == user_uuid)

    patient_quiz_counts = patient_query.group_by(Patient.id).all()

    # Categorize patients
    no_quizzes = sum(1 for _, count in patient_quiz_counts if count == 0)
    low_engagement = sum(1 for _, count in patient_quiz_counts if 1 <= count <= 5)
    high_engagement = sum(1 for _, count in patient_quiz_counts if count >= 6)

    # Calculate average
    total_quizzes = sum(count for _, count in patient_quiz_counts)
    avg_quizzes = total_quizzes / len(patient_quiz_counts) if patient_quiz_counts else 0

    result = {
        "engagement_levels": {
            "no_quizzes": no_quizzes,
            "low_engagement": low_engagement,  # 1-5 quizzes
            "high_engagement": high_engagement,  # 6+ quizzes
        },
        "average_quizzes_per_patient": round(avg_quizzes, 2),
        "total_active_patients": len(patient_quiz_counts),
    }

    # Cache the result
    await set_cached_result(cache_key, result)

    return result


@router.get(
    "/risk-assessment",
    summary="Get patient risk assessment",
    description="Identify at-risk patients with recommended actions",
)
async def get_risk_assessment(
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of patients"),
    lookback_days: int = Query(
        7, ge=1, le=90, description="Days to look back for engagement data"
    ),
    current_user=Depends(get_current_user_from_session),
    analytics_service: FlowAnalyticsService = Depends(get_flow_analytics_service),
    db=Depends(get_db),
):
    """
    Analyze patient interactions to surface at-risk patients along with context.

    Args:
        risk_level: Filter by specific risk level
        limit: Maximum number of patients to return
        lookback_days: Days to analyze for engagement patterns

    Returns:
        Dict with risk assessments and recommendations
    """
    # Ensure user is authenticated (role used for auditing/logging)
    get_role_and_user(current_user)

    at_risk_patients = await analytics_service.identify_at_risk_patients(
        lookback_days=lookback_days
    )

    # Filter by requested risk level
    if risk_level:
        at_risk_patients = [
            patient for patient in at_risk_patients if patient.risk_level == risk_level
        ]

    # Apply limit
    limited_patients = at_risk_patients[:limit]

    patient_ids = [risk.patient_id for risk in limited_patients]
    patient_lookup: Dict[UUID, Patient] = {}
    if patient_ids:
        db_patients = (
            db.query(Patient.id, Patient.name).filter(Patient.id.in_(patient_ids)).all()
        )
        patient_lookup = {row.id: row for row in db_patients}

    serialized = [
        serialize_patient_risk(patient, patient_lookup) for patient in limited_patients
    ]

    return {
        "success": True,
        "risk_level_filter": risk_level.value if risk_level else "all",
        "risk_assessments": serialized,
        "total_patients": len(serialized),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
    }
