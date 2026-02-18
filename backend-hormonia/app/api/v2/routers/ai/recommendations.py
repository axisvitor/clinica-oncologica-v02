"""
AI Services - Recommendations Endpoints
"""

import logging

from fastapi import APIRouter, Depends
from uuid import UUID
from app.api.v2.routers.ai.dependencies import (
    ensure_real_ai_ready,
    handle_ai_failure,
    verify_physician_or_admin,
)
from app.schemas.v2.ai import AIRecommendations, RecommendationItem
from app.dependencies.business_dependencies import validate_patient_access
from app.dependencies.service_dependencies import get_patient_service
from app.models.user import User
from app.config import settings
from app.services.ai.ai_service import get_ai_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/{patient_id}",
    response_model=AIRecommendations,
    summary="Get patient recommendations",
)
async def get_patient_recommendations(
    patient_id: UUID,
    current_user: User = Depends(verify_physician_or_admin),
    patient_service=Depends(get_patient_service),
):
    """
    Get AI-generated recommendations for a patient.
    Currently returns simulated data.
    """
    # Validate access
    await validate_patient_access(patient_id, current_user, patient_service)
    
    try:
        ensure_real_ai_ready(getattr(settings, "AI_GEMINI_API_KEY", None))
        ai_service = get_ai_service()
        recs = await ai_service.generate_patient_recommendations(
            patient_id=str(patient_id),
        )
        recommendations: list[RecommendationItem] = []
        for item in recs:
            if not isinstance(item, dict):
                continue
            recommendations.append(
                RecommendationItem(
                    type=str(item.get("type", "monitoring")),
                    priority=str(item.get("priority", "medium")),
                    description=str(item.get("description", "")),
                    rationale=str(item.get("rationale", "")),
                )
            )
        if recommendations:
            return AIRecommendations(
                patient_id=patient_id,
                recommendations=recommendations,
            )
    except Exception as ai_error:
        handle_ai_failure(
            logger=logger,
            operation="recommendations",
            error=ai_error,
            allow_simulation=settings.ALLOW_AI_SIMULATION,
            disabled_detail="Recommendation generation failed and simulation fallback is disabled.",
            context={"patient_id": str(patient_id)},
        )

    return AIRecommendations(
        patient_id=patient_id,
        recommendations=[
            RecommendationItem(
                type="clinical",
                priority="high",
                description="Monitor hydration levels closely.",
                rationale="Patient reported dizziness in recent check-ins.",
            ),
            RecommendationItem(
                type="engagement",
                priority="medium",
                description="Send encouragement message.",
                rationale="Adherence score slightly dropped this week.",
            ),
            RecommendationItem(
                type="treatment",
                priority="low",
                description="Review medication schedule.",
                rationale="Approaching end of current cycle.",
            ),
        ],
    )
