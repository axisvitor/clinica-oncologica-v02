"""
AI Services - Insights Generation Endpoints

Security: Rate limited to prevent API abuse and manage AI costs.
"""

# Standard library imports
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

# Third-party imports
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)

# Local application imports
from app.core.config import settings
from app.database import get_db
from app.dependencies import get_patient_service, validate_patient_access
from app.models.user import User
from app.schemas.v2.ai import (
    AIModelType,
    CacheInfo,
    GenerateInsightsRequest,
    InsightsResponse,
    PatientInsightsRequest,
    RiskLevel,
    TokenUsage,
)
from app.utils.rate_limiter import limiter

from .constants import CACHE_TTL_INSIGHTS
from .dependencies import (
    calculate_token_cost,
    generate_cache_key,
    get_cached_response,
    get_redis_cache,
    set_cached_response,
    track_token_usage,
    verify_physician_or_admin,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/generate",
    response_model=InsightsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI insights for patient",
    description="""
    Generate comprehensive AI-powered insights for patient care.

    **Features:**
    - 15-minute Redis caching
    - Rate limit: 10 requests/minute
    - Multi-dimensional analysis
    - Risk assessment and trends

    **Access:** Physicians and Admins only
    """,
)
@limiter.limit("10/minute")
async def generate_patient_insights(
    request: Request,  # Required for rate limiter
    insights_request: GenerateInsightsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    db=Depends(get_db),
) -> InsightsResponse:
    """
    Generate comprehensive patient insights with AI.
    """
    redis_client = None

    try:
        # Validate patient access
        patient = await validate_patient_access(
            insights_request.patient_id, current_user, get_patient_service(db)
        )

        # Get Redis client
        redis_client = await get_redis_cache()

        # Generate cache key with user_id to prevent cross-user cache sharing (HIPAA/Privacy)
        cache_key = generate_cache_key(
            "ai:insights:v2",
            user_id=str(current_user.id),  # SECURITY FIX: Include user_id
            patient_id=str(insights_request.patient_id),
            analysis_type=insights_request.analysis_type,
            days=insights_request.days,
        )

        # Check cache unless force refresh
        if not insights_request.force_refresh:
            cached = await get_cached_response(redis_client, cache_key)
            if cached:
                logger.info(f"[CACHE HIT] Insights for patient {insights_request.patient_id}")
                return InsightsResponse(**cached)

        # ===== AI ANALYSIS WOULD GO HERE =====
        # Runtime guard: Prevent production use of simulation mode
        if settings.APP_ENVIRONMENT == "production" and not settings.ALLOW_AI_SIMULATION:
            logger.error(
                "[PRODUCTION ERROR] AI service not configured - simulation mode blocked",
                extra={
                    "patient_id": str(insights_request.patient_id),
                    "endpoint": "insights",
                    "environment": settings.APP_ENVIRONMENT,
                }
            )
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="AI service not configured. Real AI integration required for production."
            )

        # Warning: Using simulation mode
        logger.warning(
            "[SIMULATION MODE] Using mock AI response for insights generation",
            extra={
                "patient_id": str(insights_request.patient_id),
                "endpoint": "insights",
                "environment": settings.APP_ENVIRONMENT,
                "warning": "This is simulated data - not real AI analysis"
            }
        )

        # For now, simulate insights generation
        # Simulate token usage
        token_usage = TokenUsage(
            prompt_tokens=500,
            completion_tokens=300,
            total_tokens=800,
            estimated_cost_usd=calculate_token_cost(
                TokenUsage(total_tokens=800), AIModelType.GEMINI_PRO
            ),
            model=AIModelType.GEMINI_PRO,
        )

        response = InsightsResponse(
            patient_id=insights_request.patient_id,
            overall_status=f"{patient.name} is on day {patient.current_day} of treatment",
            risk_level=RiskLevel.LOW,
            sentiment_trends=[],
            adherence_score=0.87,
            key_insights=[
                "Patient engagement: high",
                "Treatment adherence: 87%",
                f"Recent activity: {insights_request.days} days analyzed",
            ],
            alerts=[],
            engagement_metrics={
                "response_rate": 0.92,
                "total_messages": 45,
                "avg_response_time_hours": 2.5,
            },
            last_contact=datetime.now(timezone.utc) - timedelta(hours=3),
            token_usage=token_usage,
            cache_info=CacheInfo(
                hit=False,
                key=cache_key,
                ttl_seconds=CACHE_TTL_INSIGHTS,
                cached_at=datetime.now(timezone.utc),
            ),
            generated_at=datetime.now(timezone.utc),
        )

        # Cache response
        await set_cached_response(
            redis_client, cache_key, response.dict(), CACHE_TTL_INSIGHTS
        )

        # Track usage
        background_tasks.add_task(
            track_token_usage,
            redis_client,
            "insights",
            token_usage,
            current_user.id,
        )

        logger.info(
            f"Generated insights for patient {insights_request.patient_id}, "
            f"cost: ${token_usage.estimated_cost_usd:.4f}"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Insights generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate insights: {str(e)}",
        )


@router.get(
    "/{patient_id}",
    response_model=InsightsResponse,
    summary="Get patient insights",
    description="Retrieve AI insights for a specific patient (cached 15min).",
)
@limiter.limit("20/minute")
async def get_patient_insights(
    request: Request,  # Required for rate limiter
    patient_id: UUID,
    days: int = Query(30, ge=1, le=90, description="Days to analyze"),
    force_refresh: bool = Query(False, description="Force cache refresh"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(verify_physician_or_admin),
    db=Depends(get_db),
) -> InsightsResponse:
    """Get cached or generate new insights for patient."""
    request = GenerateInsightsRequest(
        patient_id=patient_id,
        days=days,
        force_refresh=force_refresh,
    )
    return await generate_patient_insights(request_obj, request, background_tasks, current_user, db)


@router.post(
    "/patient/{patient_id}",
    response_model=InsightsResponse,
    summary="Generate patient-specific insights",
    description="Generate insights with custom parameters for a patient.",
)
@limiter.limit("10/minute")
async def generate_insights_for_patient(
    request: Request,  # Required for rate limiter
    patient_id: UUID,
    patient_insights_request: PatientInsightsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    db=Depends(get_db),
) -> InsightsResponse:
    """Generate insights for specific patient."""
    full_request = GenerateInsightsRequest(
        patient_id=patient_id,
        days=patient_insights_request.days,
        force_refresh=patient_insights_request.force_refresh,
    )
    return await generate_patient_insights(
        request, full_request, background_tasks, current_user, db
    )
