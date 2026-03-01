"""
AI Services - Insights Generation Endpoints

Security: Rate limited to prevent API abuse and manage AI costs.
"""

# Standard library imports
import json
import logging
from datetime import timedelta
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Local application imports
from app.config import settings
from app.core.database.async_engine import get_async_db
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
from app.services.ai.ai_service import get_ai_service
from app.utils.rate_limiter import limiter
from app.api.v2.routers import ai as ai_module

from .constants import CACHE_TTL_INSIGHTS
from .dependencies import (
    calculate_token_cost,
    ensure_real_ai_ready,
    generate_cache_key,
    get_cached_response,
    handle_ai_failure,
    set_cached_response,
    track_token_usage,
    verify_physician_or_admin,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

router = APIRouter()


def _estimate_token_usage(prompt_text: str, output_text: str) -> TokenUsage:
    prompt_tokens = max(1, len((prompt_text or "").split()) * 2)
    completion_tokens = max(1, len((output_text or "").split()) * 2)
    total_tokens = prompt_tokens + completion_tokens
    usage_base = TokenUsage(total_tokens=total_tokens)
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=calculate_token_cost(usage_base, AIModelType.GEMINI_PRO),
        model=AIModelType.GEMINI_PRO,
    )


def _simulation_insights(
    patient,
    insights_request: GenerateInsightsRequest,
    cache_key: str,
) -> InsightsResponse:
    token_usage = TokenUsage(
        prompt_tokens=500,
        completion_tokens=300,
        total_tokens=800,
        estimated_cost_usd=calculate_token_cost(
            TokenUsage(total_tokens=800), AIModelType.GEMINI_PRO
        ),
        model=AIModelType.GEMINI_PRO,
    )

    return InsightsResponse(
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
        last_contact=now_sao_paulo() - timedelta(hours=3),
        token_usage=token_usage,
        cache_info=CacheInfo(
            hit=False,
            key=cache_key,
            ttl_seconds=CACHE_TTL_INSIGHTS,
            cached_at=now_sao_paulo(),
        ),
        generated_at=now_sao_paulo(),
    )


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
    db: AsyncSession = Depends(get_async_db),
) -> InsightsResponse:
    """
    Generate comprehensive patient insights with AI.
    """
    from app.models.patient import Patient
    from app.models.user import UserRole
    from app.utils.auth_helpers import ensure_uuid, extract_user_context
    
    redis_client = None

    try:
        # Validate patient access - inline query instead of broken dependency call
        patient_result = await db.execute(
            select(Patient).where(Patient.id == insights_request.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found"
            )
        

        role_enum, user_id = extract_user_context(current_user)
        user_uuid = ensure_uuid(user_id)
        user_id_str = user_id or (str(user_uuid) if user_uuid else "unknown")

        if role_enum == UserRole.DOCTOR:
            if not user_uuid or patient.doctor_id != user_uuid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Patient not assigned to current doctor"
                )

        # Get Redis client
        redis_client = await ai_module.get_redis_cache()

        # Generate cache key with user_id to prevent cross-user cache sharing (HIPAA/Privacy)
        cache_key = generate_cache_key(
            "ai:insights:v2",
            user_id=user_id_str, 
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

        try:
            ensure_real_ai_ready(getattr(settings, "AI_GEMINI_API_KEY", None))
            ai_service = get_ai_service()
            parsed = await ai_service.generate_patient_insights(
                patient_id=str(insights_request.patient_id),
                patient_name=patient.name,
                treatment_type=getattr(patient, "treatment_type", None),
                current_day=getattr(patient, "current_day", None),
                analysis_type=insights_request.analysis_type,
                days_window=insights_request.days,
            )
            output_text = json.dumps(parsed, ensure_ascii=False)
            risk_level_raw = str(parsed.get("risk_level", "low")).lower()
            risk_level = (
                RiskLevel(risk_level_raw)
                if risk_level_raw in RiskLevel._value2member_map_
                else RiskLevel.LOW
            )
            token_usage = _estimate_token_usage(
                f"insights patient={insights_request.patient_id} type={insights_request.analysis_type} days={insights_request.days}",
                output_text,
            )

            response = InsightsResponse(
                patient_id=insights_request.patient_id,
                overall_status=str(parsed.get("overall_status") or "").strip()
                or f"{patient.name} is under active follow-up",
                risk_level=risk_level,
                sentiment_trends=parsed.get("sentiment_trends", []) or [],
                adherence_score=max(
                    0.0, min(1.0, float(parsed.get("adherence_score", 0.5)))
                ),
                key_insights=parsed.get("key_insights", []) or [],
                alerts=parsed.get("alerts", []) or [],
                engagement_metrics=parsed.get("engagement_metrics", {}) or {},
                last_contact=now_sao_paulo() - timedelta(hours=3),
                token_usage=token_usage,
                cache_info=CacheInfo(
                    hit=False,
                    key=cache_key,
                    ttl_seconds=CACHE_TTL_INSIGHTS,
                    cached_at=now_sao_paulo(),
                ),
                generated_at=now_sao_paulo(),
            )
        except Exception as ai_error:
            handle_ai_failure(
                logger=logger,
                operation="insights",
                error=ai_error,
                allow_simulation=settings.ALLOW_AI_SIMULATION,
                disabled_detail="Insights generation failed and simulation fallback is disabled.",
                context={
                    "patient_id": str(insights_request.patient_id),
                    "user_id": user_id_str,
                },
            )
            response = _simulation_insights(patient, insights_request, cache_key)
            token_usage = response.token_usage or TokenUsage(
                total_tokens=0,
                estimated_cost_usd=0.0,
                model=AIModelType.GEMINI_PRO,
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
            user_uuid if user_uuid else user_id_str,
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
    db: AsyncSession = Depends(get_async_db),
) -> InsightsResponse:
    """Get cached or generate new insights for patient."""
    insights_request = GenerateInsightsRequest(
        patient_id=patient_id,
        days=days,
        force_refresh=force_refresh,
    )
    return await generate_patient_insights(request, insights_request, background_tasks, current_user, db)


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
    db: AsyncSession = Depends(get_async_db),
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
