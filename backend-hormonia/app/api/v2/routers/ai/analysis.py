"""
AI Services - Analysis Endpoints (sentiment, risk, quality)

Security: Rate limited to prevent API abuse and manage AI costs.
"""

# Standard library imports
import json
import logging

# Third-party imports
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)

# Local application imports
from app.config import settings
from app.dependencies.business_dependencies import validate_patient_access
from app.dependencies.service_dependencies import get_patient_service
from app.models.user import User
from app.schemas.v2.ai import (
    AIModelType,
    ConcernLevel,
    ResponseQualityRequest,
    ResponseQualityResponse,
    RiskAnalysisRequest,
    RiskAnalysisResponse,
    RiskLevel,
    SentimentAnalysisRequest,
    SentimentAnalysisResponse,
    SentimentType,
    TokenUsage,
)
from app.utils.rate_limiter import limiter
from app.services.ai.ai_service import SentimentType as ServiceSentimentType
from app.services.ai.ai_service import get_ai_service
from .dependencies import (
    calculate_token_cost,
    ensure_real_ai_ready,
    get_redis_cache as _router_get_redis_cache,
    handle_ai_failure,
    track_token_usage,
    verify_physician_or_admin,
)
from app.utils.auth_helpers import extract_user_context
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_redis_cache():
    """Compatibility wrapper for tests that patch module-local get_redis_cache."""
    return await _router_get_redis_cache()


def _estimate_token_usage(
    prompt_text: str,
    output_text: str,
    model: AIModelType,
) -> TokenUsage:
    prompt_tokens = max(1, len((prompt_text or "").split()) * 2)
    completion_tokens = max(1, len((output_text or "").split()) * 2)
    total_tokens = prompt_tokens + completion_tokens
    usage_base = TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=calculate_token_cost(usage_base, model),
        model=model,
    )


def _coerce_sentiment(value: ServiceSentimentType | str) -> SentimentType:
    raw = value.value if isinstance(value, ServiceSentimentType) else str(value)
    try:
        return SentimentType(raw)
    except ValueError:
        return SentimentType.NEUTRAL


def _coerce_concern_level(value: str | None) -> ConcernLevel:
    if not value:
        return ConcernLevel.LOW
    normalized = value.strip().lower()
    if normalized == ConcernLevel.CRITICAL.value:
        return ConcernLevel.CRITICAL
    if normalized == ConcernLevel.HIGH.value:
        return ConcernLevel.HIGH
    if normalized == ConcernLevel.MEDIUM.value:
        return ConcernLevel.MEDIUM
    return ConcernLevel.LOW


def _simulation_sentiment(sentiment_request: SentimentAnalysisRequest) -> SentimentAnalysisResponse:
    concern_keywords = ["pain", "tired", "worried", "scared", "bad"]
    has_concerns = any(
        kw in sentiment_request.message.lower() for kw in concern_keywords
    )
    concern_level = ConcernLevel.MEDIUM if has_concerns else ConcernLevel.LOW
    sentiment = SentimentType.CONCERNING if has_concerns else SentimentType.NEUTRAL

    token_usage = TokenUsage(
        prompt_tokens=len(sentiment_request.message.split()) * 2,
        completion_tokens=50,
        total_tokens=len(sentiment_request.message.split()) * 2 + 50,
        estimated_cost_usd=0.0012,
        model=AIModelType.GEMINI_FLASH,
    )

    return SentimentAnalysisResponse(
        message=sentiment_request.message,
        sentiment=sentiment,
        concern_level=concern_level,
        confidence=0.88,
        key_phrases=["tired"] if has_concerns else [],
        medical_concerns=["fatigue"]
        if has_concerns and sentiment_request.include_medical_concerns
        else [],
        urgency_indicators=[]
        if not sentiment_request.include_urgency
        else (["very"] if "very" in sentiment_request.message.lower() else []),
        emotion_scores={
            "anxiety": 0.3 if has_concerns else 0.1,
            "fatigue": 0.7 if has_concerns else 0.2,
        },
        recommended_action="Schedule follow-up"
        if has_concerns
        else "Continue monitoring",
        token_usage=token_usage,
        analyzed_at=now_sao_paulo(),
    )


@router.post(
    "/sentiment",
    response_model=SentimentAnalysisResponse,
    summary="Analyze message sentiment",
    description="""
    Perform AI-powered sentiment analysis on patient messages.

    **Features:**
    - Medical concern detection
    - Urgency indicators
    - Emotion scoring
    - Rate limit: 20 requests/minute
    """,
)
@limiter.limit("20/minute")
async def analyze_sentiment(
    request: Request,  # Required for rate limiter
    sentiment_request: SentimentAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    patient_service=Depends(get_patient_service),
) -> SentimentAnalysisResponse:
    """Analyze sentiment of patient message."""
    try:
        _, user_id = extract_user_context(current_user)
        user_id_str = user_id or "unknown"

        patient_context: dict[str, object] = {}
        if sentiment_request.patient_id:
            patient = await validate_patient_access(
                sentiment_request.patient_id, current_user, patient_service
            )
            patient_context = {
                "patient_id": str(patient.id),
                "name": patient.name,
                "treatment_type": getattr(patient, "treatment_type", None),
                "current_day": getattr(patient, "current_day", None),
            }

        try:
            ensure_real_ai_ready(getattr(settings, "AI_GEMINI_API_KEY", None))
            ai_service = get_ai_service()
            sentiment_result, concern_result = await ai_service.analyze_sentiment(
                sentiment_request.message, patient_context
            )

            concern_level = _coerce_concern_level(getattr(concern_result, "value", None))
            medical_concerns = (
                sentiment_result.medical_concerns
                if sentiment_request.include_medical_concerns
                else []
            )
            urgency_indicators = []
            if sentiment_request.include_urgency and concern_level in {
                ConcernLevel.HIGH,
                ConcernLevel.CRITICAL,
            }:
                urgency_indicators.append("high_concern_level")

            emotion_scores: dict[str, float] = {}
            for indicator in sentiment_result.emotional_indicators:
                emotion_scores[str(indicator)] = 0.7

            response = SentimentAnalysisResponse(
                message=sentiment_request.message,
                sentiment=_coerce_sentiment(sentiment_result.sentiment),
                concern_level=concern_level,
                confidence=sentiment_result.confidence,
                key_phrases=sentiment_result.key_phrases or [],
                medical_concerns=medical_concerns,
                urgency_indicators=urgency_indicators,
                emotion_scores=emotion_scores,
                recommended_action=(
                    "Immediate clinical review"
                    if concern_level in {ConcernLevel.HIGH, ConcernLevel.CRITICAL}
                    else "Continue monitoring"
                ),
                token_usage=_estimate_token_usage(
                    sentiment_request.message,
                    json.dumps(
                        {
                            "sentiment": _coerce_sentiment(sentiment_result.sentiment).value,
                            "confidence": sentiment_result.confidence,
                            "medical_concerns": medical_concerns,
                        },
                        ensure_ascii=False,
                    ),
                    AIModelType.GEMINI_FLASH,
                ),
                analyzed_at=now_sao_paulo(),
            )
        except Exception as ai_error:
            handle_ai_failure(
                logger=logger,
                operation="sentiment_analysis",
                error=ai_error,
                allow_simulation=settings.ALLOW_AI_SIMULATION,
                disabled_detail="Sentiment analysis failed and simulation fallback is disabled.",
                context={"user_id": user_id_str},
            )
            response = _simulation_sentiment(sentiment_request)

        token_usage = response.token_usage or TokenUsage(total_tokens=0, estimated_cost_usd=0.0)
        # Track usage
        background_tasks.add_task(
            track_token_usage,
            await get_redis_cache(),
            "sentiment",
            token_usage,
            user_id_str,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sentiment analysis failed: {str(e)}",
        )


@router.post(
    "/risk",
    response_model=RiskAnalysisResponse,
    summary="Analyze patient risk",
    description="AI-powered risk assessment for patient care.",
)
@limiter.limit("15/minute")
async def analyze_risk(
    request: Request,  # Required for rate limiter
    risk_request: RiskAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    patient_service=Depends(get_patient_service),
) -> RiskAnalysisResponse:
    """Perform AI risk analysis for patient."""
    try:
        _, user_id = extract_user_context(current_user)
        user_id_str = user_id or "unknown"

        # Validate patient access
        patient = await validate_patient_access(
            risk_request.patient_id, current_user, patient_service
        )

        try:
            ensure_real_ai_ready(getattr(settings, "AI_GEMINI_API_KEY", None))
            ai_service = get_ai_service()
            parsed = await ai_service.generate_risk_analysis(
                patient_id=str(risk_request.patient_id),
                patient_name=patient.name,
                treatment_type=getattr(patient, "treatment_type", None),
                current_day=getattr(patient, "current_day", None),
                analysis_days=risk_request.days,
            )
            output_text = json.dumps(parsed, ensure_ascii=False)

            risk_level_raw = str(parsed.get("risk_level", "low")).lower()
            risk_level = (
                RiskLevel(risk_level_raw)
                if risk_level_raw in RiskLevel._value2member_map_
                else RiskLevel.LOW
            )
            risk_score = float(parsed.get("risk_score", 0.25))
            confidence = float(parsed.get("confidence", 0.75))
            token_usage = _estimate_token_usage(
                f"risk_analysis patient={risk_request.patient_id} days={risk_request.days}",
                output_text,
                AIModelType.GEMINI_PRO,
            )

            response = RiskAnalysisResponse(
                patient_id=risk_request.patient_id,
                risk_level=risk_level,
                risk_score=max(0.0, min(1.0, risk_score)),
                risk_factors=parsed.get("risk_factors", []) or [],
                protective_factors=parsed.get("protective_factors", []) or [],
                recommendations=parsed.get("recommendations", []) or [],
                trend=str(parsed.get("trend", "stable")),
                confidence=max(0.0, min(1.0, confidence)),
                token_usage=token_usage,
                analyzed_at=now_sao_paulo(),
            )
        except Exception as ai_error:
            handle_ai_failure(
                logger=logger,
                operation="risk_analysis",
                error=ai_error,
                allow_simulation=settings.ALLOW_AI_SIMULATION,
                disabled_detail="Risk analysis failed and simulation fallback is disabled.",
                context={
                    "patient_id": str(risk_request.patient_id),
                    "user_id": user_id_str,
                },
            )
            token_usage = TokenUsage(
                prompt_tokens=400,
                completion_tokens=200,
                total_tokens=600,
                estimated_cost_usd=0.009,
                model=AIModelType.GEMINI_PRO,
            )
            response = RiskAnalysisResponse(
                patient_id=risk_request.patient_id,
                risk_level=RiskLevel.LOW,
                risk_score=0.25,
                risk_factors=[],
                protective_factors=[
                    "Regular engagement",
                    "Good treatment adherence",
                ],
                recommendations=[
                    "Continue current care plan",
                    "Monitor for changes",
                ],
                trend="stable",
                confidence=0.82,
                token_usage=token_usage,
                analyzed_at=now_sao_paulo(),
            )

        # Track usage
        background_tasks.add_task(
            track_token_usage,
            await get_redis_cache(),
            "risk_analysis",
            token_usage,
            user_id_str,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk analysis failed: {str(e)}",
        )


@router.post(
    "/response",
    response_model=ResponseQualityResponse,
    summary="Analyze response quality",
    description="Evaluate quality, readability, and tone of a message.",
)
@limiter.limit("30/minute")
async def analyze_response_quality(
    request: Request,  # Required for rate limiter
    quality_request: ResponseQualityRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
) -> ResponseQualityResponse:
    """Analyze quality of a response message."""
    try:
        _, user_id = extract_user_context(current_user)
        user_id_str = user_id or "unknown"

        try:
            ensure_real_ai_ready(getattr(settings, "AI_GEMINI_API_KEY", None))
            ai_service = get_ai_service()
            parsed = await ai_service.analyze_message_quality(
                message=quality_request.message,
                context=quality_request.context,
            )
            output_text = json.dumps(parsed, ensure_ascii=False)
            response = ResponseQualityResponse(
                message=quality_request.message,
                quality_score=max(0.0, min(100.0, float(parsed.get("quality_score", 75.0)))),
                readability_score=max(
                    0.0, min(100.0, float(parsed.get("readability_score", 75.0)))
                ),
                empathy_score=max(0.0, min(1.0, float(parsed.get("empathy_score", 0.75)))),
                professionalism_score=max(
                    0.0, min(1.0, float(parsed.get("professionalism_score", 0.8)))
                ),
                clarity_score=max(0.0, min(1.0, float(parsed.get("clarity_score", 0.85)))),
                suggestions=parsed.get("suggestions", []) or [],
                strengths=parsed.get("strengths", []) or [],
                token_usage=_estimate_token_usage(
                    f"response_quality length={len(quality_request.message)}",
                    output_text,
                    AIModelType.GEMINI_FLASH,
                ),
                analyzed_at=now_sao_paulo(),
            )
        except Exception as ai_error:
            handle_ai_failure(
                logger=logger,
                operation="response_quality",
                error=ai_error,
                allow_simulation=settings.ALLOW_AI_SIMULATION,
                disabled_detail="Response quality analysis failed and simulation fallback is disabled.",
                context={"user_id": user_id_str},
            )
            word_count = len(quality_request.message.split())
            quality_score = min(100, 50 + word_count * 2)
            readability = min(100, 60 + word_count)
            response = ResponseQualityResponse(
                message=quality_request.message,
                quality_score=quality_score,
                readability_score=readability,
                empathy_score=0.75,
                professionalism_score=0.80,
                clarity_score=0.85,
                suggestions=[
                    "Message is clear and professional",
                ]
                if quality_score > 70
                else [
                    "Consider adding more context",
                ],
                strengths=[
                    "Professional tone",
                    "Clear message",
                ],
                token_usage=TokenUsage(
                    prompt_tokens=len(quality_request.message.split()) * 2,
                    completion_tokens=30,
                    total_tokens=len(quality_request.message.split()) * 2 + 30,
                    estimated_cost_usd=0.0008,
                    model=AIModelType.GEMINI_FLASH,
                ),
                analyzed_at=now_sao_paulo(),
            )

        token_usage = response.token_usage or TokenUsage(total_tokens=0, estimated_cost_usd=0.0)
        # Track usage
        background_tasks.add_task(
            track_token_usage,
            await get_redis_cache(),
            "response_quality",
            token_usage,
            user_id_str,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Response quality analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Response quality analysis failed: {str(e)}",
        )
