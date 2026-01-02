"""
AI Services - Recommendations Endpoints
"""

from fastapi import APIRouter, Depends
from uuid import UUID
from app.api.v2.routers.ai.dependencies import verify_physician_or_admin
from app.schemas.v2.ai import AIRecommendations, RecommendationItem
from app.database import get_db
from app.dependencies import get_patient_service, validate_patient_access
from app.models.user import User

router = APIRouter()

@router.get(
    "/{patient_id}",
    response_model=AIRecommendations,
    summary="Get patient recommendations",
)
async def get_patient_recommendations(
    patient_id: UUID,
    current_user: User = Depends(verify_physician_or_admin),
    db=Depends(get_db)
):
    """
    Get AI-generated recommendations for a patient.
    Currently returns simulated data.
    """
    # Validate access
    await validate_patient_access(patient_id, current_user, get_patient_service(db))
    
    # Mock response (simulation)
    return AIRecommendations(
        patient_id=patient_id,
        recommendations=[
            RecommendationItem(
                type="clinical",
                priority="high",
                description="Monitor hydration levels closely.",
                rationale="Patient reported dizziness in recent check-ins."
            ),
             RecommendationItem(
                type="engagement",
                priority="medium",
                description="Send encouragement message.",
                rationale="Adherence score slightly dropped this week."
            ),
             RecommendationItem(
                type="treatment",
                priority="low",
                description="Review medication schedule.",
                rationale="Approaching end of current cycle."
            )
        ]
    )
