"""
Physician-specific API endpoints.

These endpoints provide aggregated views and operations for physicians,
including patient risk assessments, dashboard data, and bulk operations.

All endpoints require physician or admin authentication.
"""
import logging
from typing import Optional
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.physician import (
    RiskAssessmentsResponse,
    PatientRiskProfile
)
from app.services.risk_assessment_service import RiskAssessmentService
from app.dependencies import get_current_user, get_doctor_user

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/physician", tags=["Physician"])


# ============================================================================
# Risk Assessment Endpoints
# ============================================================================

@router.get(
    "/risk-assessments",
    response_model=RiskAssessmentsResponse,
    summary="Get aggregated risk assessments for patients",
    description="""
    Get aggregated risk assessments for all patients assigned to the physician.

    **Performance Optimization**: This endpoint replaces the N+1 query pattern
    (1 patient list query + N individual /ai/insights queries) with a single
    optimized query using JOINs.

    **Performance Target**: < 200ms for 50 patients

    **Query Parameters**:
    - `patient_id`: Optional filter for a single patient
    - `days_lookback`: Number of days to look back for alerts (default: 30)

    **Returns**:
    - Aggregated risk profiles with scores and assessments
    - Total patient count and high-risk patient count
    - Timestamp of response generation

    **Caching**: Responses are cached for 1 minute in Redis

    **Authorization**: Requires physician or admin role
    """,
    responses={
        200: {
            "description": "Risk assessments retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "patients": [
                            {
                                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                                "patient_name": "João Silva",
                                "overall_risk": "high",
                                "risk_score": 0.65,
                                "assessments": [
                                    {
                                        "category": "medication_adherence",
                                        "risk_level": "high",
                                        "severity_score": 0.75,
                                        "last_updated": "2025-10-06T14:30:00Z",
                                        "description": "Missed doses detected"
                                    }
                                ],
                                "alert_count": 3,
                                "last_assessment": "2025-10-06T14:30:00Z"
                            }
                        ],
                        "total_count": 50,
                        "high_risk_count": 8,
                        "timestamp": "2025-10-06T14:30:00Z"
                    }
                }
            }
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (requires physician or admin role)"},
        500: {"description": "Internal server error"}
    }
)
async def get_risk_assessments(
    patient_id: Optional[str] = Query(
        None,
        description="Filter by specific patient UUID"
    ),
    days_lookback: int = Query(
        30,
        ge=1,
        le=90,
        description="Number of days to look back for alerts"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_doctor_user)
):
    """
    Get aggregated risk assessments for physician's patients.

    This endpoint aggregates alerts, AI insights, and patient data into
    comprehensive risk profiles, eliminating the N+1 query problem.
    """
    try:
        # Initialize service
        service = RiskAssessmentService(db)

        # Convert patient_id string to UUID if provided
        patient_uuid = None
        if patient_id:
            try:
                patient_uuid = UUID(patient_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid patient_id format: {patient_id}"
                )

        # Get risk assessments
        profiles = service.get_patient_risk_assessments(
            physician_id=current_user.id,
            patient_id=patient_uuid,
            days_lookback=days_lookback
        )

        # Calculate summary metrics
        total_count = len(profiles)
        high_risk_count = sum(
            1 for p in profiles
            if p['overall_risk'] in ['high', 'critical']
        )

        # Build response
        response = RiskAssessmentsResponse(
            patients=profiles,
            total_count=total_count,
            high_risk_count=high_risk_count,
            timestamp=datetime.utcnow().isoformat()
        )

        logger.info(
            f"Risk assessments retrieved for physician {current_user.id}: "
            f"{total_count} patients, {high_risk_count} high-risk"
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Error retrieving risk assessments for physician {current_user.id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve risk assessments"
        )


# ============================================================================
# Patient Overview Endpoints (Future)
# ============================================================================
# Additional endpoints can be added here for:
# - Patient list with pagination
# - Patient statistics and trends
# - Bulk patient operations
# - etc.
