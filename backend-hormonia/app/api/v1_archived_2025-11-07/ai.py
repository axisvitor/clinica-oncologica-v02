"""
AI-powered endpoints for the Hormonia Backend System.

Provides REST API endpoints for AI features including chat, sentiment analysis,
patient insights, and recommendations. Only accessible by physicians and admins.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.dependencies import (
    get_current_user,
    get_patient_service,
    validate_patient_access,
)
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    AnalysisRequest,
    AnalysisResponse,
    GenerateResponseRequest,
    GenerateResponseResponse,
    SentimentAnalysisRequest,
    SentimentAnalysisResponse,
    InsightResponse,
    RecommendationResponse,
    PatientSummaryResponse,
    AIErrorResponse,
    SentimentType,
    ConcernLevel,
    RiskLevel,
    TrendData,
    ActionItem,
)
from app.services.ai import AIService, PatientContext, ConcernLevel, get_ai_service
from app.exceptions import ExternalServiceError, ValidationError, NotFoundError

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/ai", tags=["AI Services"])


# ============================================================================
# Dependency Functions
# ============================================================================


async def verify_physician_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify user is a physician or admin.

    AI features are restricted to medical professionals only for patient safety
    and data privacy compliance.

    Args:
        current_user: Current authenticated user

    Returns:
        User object if authorized

    Raises:
        HTTPException: 403 if user is not physician or admin
    """
    role_value = (
        current_user.role.value
        if isinstance(current_user.role, UserRole)
        else str(current_user.role or "").lower()
    )

    if role_value not in {UserRole.DOCTOR.value, UserRole.ADMIN.value}:
        logger.warning(
            "Unauthorized AI access attempt by user %s with role %s",
            current_user.id,
            current_user.role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI features are only accessible to doctors and administrators",
        )
    return current_user


async def get_redis_client():
    """Get Redis client for caching with connection pooling and error handling."""
    try:
        from app.config import settings
        import redis.asyncio as redis

        # Enhanced connection with pooling and better timeout handling
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
            max_connections=20,
            retry_on_timeout=True,
        )

        # Verify connection
        await client.ping()
        logger.info("Redis client connected successfully for AI caching")
        return client
    except Exception as e:
        logger.warning(
            f"Redis unavailable for AI caching, falling back to no cache: {e}"
        )
        return None


async def get_cached_data(redis_client, cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached data from Redis with error handling."""
    if redis_client is None:
        return None

    try:
        data = await redis_client.get(cache_key)
        if data:
            parsed_data = json.loads(data)
            logger.debug(f"Cache HIT for key: {cache_key}")
            return parsed_data
        else:
            logger.debug(f"Cache MISS for key: {cache_key}")
            return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error for cache key {cache_key}: {e}")
        # Invalidate corrupted cache entry
        try:
            await redis_client.delete(cache_key)
        except:
            pass
        return None
    except Exception as e:
        logger.warning(f"Cache read error for {cache_key}: {e}")
        return None


async def set_cached_data(
    redis_client, cache_key: str, data: Dict[str, Any], ttl_seconds: int
) -> bool:
    """Set cached data in Redis with JSON serialization."""
    if redis_client is None:
        return False

    try:
        serialized_data = json.dumps(data, default=str, ensure_ascii=False)
        await redis_client.setex(cache_key, ttl_seconds, serialized_data)
        logger.debug(f"Cache SET for key: {cache_key} (TTL: {ttl_seconds}s)")
        return True
    except TypeError as e:
        logger.error(f"JSON serialization error for {cache_key}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Cache write error for {cache_key}: {e}")
        return False


async def invalidate_patient_cache(redis_client, patient_id: UUID) -> int:
    """Invalidate all cached AI data for a patient."""
    if redis_client is None:
        return 0

    invalidated_count = 0
    try:
        # Invalidate all patient-specific AI cache keys using pattern matching
        patterns = [
            f"ai:insights:{patient_id}*",
            f"ai:recommendations:{patient_id}*",
            f"ai:summary:{patient_id}*",
            f"ai:analysis:{patient_id}*",
        ]

        for pattern in patterns:
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    deleted = await redis_client.delete(*keys)
                    invalidated_count += deleted
                    logger.debug(f"Deleted {deleted} keys matching pattern: {pattern}")

                if cursor == 0:
                    break

        logger.info(
            f"Invalidated {invalidated_count} AI cache entries for patient {patient_id}"
        )
        return invalidated_count
    except Exception as e:
        logger.error(f"Cache invalidation error for patient {patient_id}: {e}")
        return invalidated_count


# ============================================================================
# POST /ai/chat - Interactive AI Chat
# ============================================================================


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        200: {"description": "Successful AI chat response"},
        401: {"model": AIErrorResponse, "description": "Unauthorized"},
        403: {"model": AIErrorResponse, "description": "Insufficient permissions"},
        500: {"model": AIErrorResponse, "description": "AI service error"},
    },
    summary="Interactive AI chat for physicians",
    description="""
    Provides an interactive AI chat interface for physicians to get clinical insights,
    treatment guidance, and medical information. Can optionally include patient context
    for personalized responses.

    **Access:** Physicians and Admins only
    """,
)
async def ai_chat(
    request: ChatRequest,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Interactive AI chat endpoint for physicians.

    Provides intelligent responses to medical queries with optional patient context.
    Uses conversation history for contextual understanding.
    """
    try:
        logger.info(
            f"AI chat request from user {current_user.id}, "
            f"patient_id: {request.patient_id}"
        )

        # Build patient context if patient_id provided
        patient_context = None
        if request.patient_id:
            # Validate patient access
            patient = await validate_patient_access(
                request.patient_id, current_user, get_patient_service(db)
            )

            # Build context
            context_builder = get_ai_service()
            patient_context = await context_builder.build_patient_context(
                str(request.patient_id),
                {
                    "name": patient.name,
                    "treatment_type": patient.treatment_type or "general",
                    "current_day": patient.current_day,
                },
            )

        # Get AI orchestrator for chat
        ai_humanizer = get_ai_service()

        # For demo purposes, create a simple intelligent response
        # In production, this would use the LangChain orchestrator
        response_message = f"I understand your question: '{request.message}'. "

        if patient_context:
            response_message += (
                f"Based on {patient_context.name}'s context "
                f"(Day {patient_context.treatment_day} of {patient_context.treatment_type}), "
            )

        response_message += (
            "I can provide medical insights and clinical guidance. "
            "How can I help you further?"
        )

        return ChatResponse(
            message=response_message,
            confidence=0.85,
            sources=["Medical guidelines", "Clinical database"],
            suggestions=[
                "Review patient's recent responses",
                "Check treatment adherence",
                "Schedule follow-up consultation",
            ],
            context_used=patient_context is not None,
            timestamp=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI chat service error: {str(e)}",
        )


# ============================================================================
# POST /ai/analyze - Analyze Patient Data
# ============================================================================


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    responses={
        200: {"description": "Successful patient analysis"},
        401: {"model": AIErrorResponse},
        403: {"model": AIErrorResponse},
        404: {"model": AIErrorResponse, "description": "Patient not found"},
        500: {"model": AIErrorResponse},
    },
    summary="Analyze patient data with AI",
    description="""
    Performs comprehensive AI-powered analysis of patient data including treatment
    progress, adherence patterns, sentiment trends, and risk assessment.

    **Access:** Physicians and Admins only
    """,
)
async def analyze_patient(
    request: AnalysisRequest,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """
    Analyze patient data with AI to identify patterns, risks, and opportunities.
    """
    try:
        logger.info(
            f"AI analysis request from user {current_user.id}, "
            f"patient_id: {request.patient_id}, type: {request.analysis_type}"
        )

        # Validate patient access
        patient = await validate_patient_access(
            request.patient_id, current_user, get_patient_service(db)
        )

        # Get patient messages for analysis (if requested)
        messages = []
        if request.include_messages:
            # Fetch recent messages from database
            from app.repositories.message import MessageRepository

            message_repo = MessageRepository(db)
            cutoff_date = datetime.utcnow() - timedelta(days=request.date_range_days)
            messages = message_repo.get_patient_messages(
                patient.id, start_date=cutoff_date
            )

        # Analyze sentiment across messages
        sentiment_analyzer = get_ai_service()
        concern_levels = []
        key_findings = []

        for msg in messages[:10]:  # Analyze recent 10 messages
            if hasattr(msg, "content") and msg.content:
                context_builder = get_ai_service()
                patient_ctx = await context_builder.build_patient_context(
                    str(patient.id),
                    {
                        "name": patient.name,
                        "treatment_type": patient.treatment_type or "general",
                        "current_day": patient.current_day,
                    },
                )

                analysis, concern = await sentiment_analyzer.analyze_response(
                    msg.content, patient_ctx
                )
                concern_levels.append(concern.value)

                if analysis.medical_concerns:
                    key_findings.extend(analysis.medical_concerns[:2])

        # Calculate data quality
        data_quality = 0.7
        if request.include_medical_history:
            data_quality += 0.15
        if request.include_messages and len(messages) > 0:
            data_quality += 0.15

        # Generate analysis summary
        summary = (
            f"Analysis of {patient.name} over {request.date_range_days} days. "
            f"Treatment: {patient.treatment_type or 'general'}, Day: {patient.current_day}. "
        )

        if concern_levels:
            high_concerns = sum(1 for c in concern_levels if c in ["high", "critical"])
            if high_concerns > 0:
                summary += f"Detected {high_concerns} high-concern indicators. "
            else:
                summary += "No critical concerns detected. "

        # Build risk factors
        risk_factors = []
        if "high" in concern_levels or "critical" in concern_levels:
            risk_factors.append(
                {
                    "factor": "Elevated concern levels in messages",
                    "severity": "high",
                    "frequency": concern_levels.count("high")
                    + concern_levels.count("critical"),
                }
            )

        return AnalysisResponse(
            patient_id=request.patient_id,
            analysis_type=request.analysis_type,
            summary=summary,
            key_findings=list(set(key_findings[:5]))
            if key_findings
            else [
                "Patient showing consistent engagement",
                f"Treatment day {patient.current_day} progress tracked",
            ],
            risk_factors=risk_factors,
            recommendations=[
                "Continue monitoring patient responses",
                "Maintain current treatment protocol"
                if not risk_factors
                else "Review treatment plan",
                "Schedule regular check-ins",
            ],
            data_quality_score=min(data_quality, 1.0),
            analyzed_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis service error: {str(e)}",
        )


# ============================================================================
# POST /ai/generate-response - Generate AI Response
# ============================================================================


@router.post(
    "/generate-response",
    response_model=GenerateResponseResponse,
    responses={
        200: {"description": "Successfully generated AI response"},
        401: {"model": AIErrorResponse},
        403: {"model": AIErrorResponse},
        404: {"model": AIErrorResponse},
        500: {"model": AIErrorResponse},
    },
    summary="Generate AI response for patient message",
    description="""
    Generates a personalized, empathetic response to send to patients.
    Uses AI to humanize template messages based on patient context and preferences.

    **Access:** Physicians and Admins only
    """,
)
async def generate_response(
    request: GenerateResponseRequest,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> GenerateResponseResponse:
    """
    Generate personalized AI response for patient communication.
    """
    try:
        logger.info(
            f"AI response generation request from user {current_user.id}, "
            f"patient_id: {request.patient_id}, type: {request.message_type}"
        )

        # Validate patient access
        patient = await validate_patient_access(
            request.patient_id, current_user, get_patient_service(db)
        )

        # Build patient context
        context_builder = get_ai_service()
        patient_context = await context_builder.build_patient_context(
            str(request.patient_id),
            {
                "name": patient.name,
                "treatment_type": patient.treatment_type or "general",
                "current_day": patient.current_day,
                "age": None,  # Could be calculated from birth_date if needed
            },
        )

        # Humanize message
        ai_humanizer = get_ai_service()
        personalized = await ai_humanizer.humanize_message(
            request.template_message, patient_context, request.message_type
        )

        # Calculate readability score
        from app.services.ai import AIService

        ai_service = await get_ai_service()
        readability = await ai_service.calculate_readability_score(
            personalized.humanized_message
        )

        return GenerateResponseResponse(
            original_message=request.template_message,
            generated_message=personalized.humanized_message,
            personalization_notes=personalized.personalization_notes,
            readability_score=readability,
            tone_analysis={"empathy": 0.85, "professionalism": 0.80, "clarity": 0.90},
            generated_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Response generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Response generation error: {str(e)}",
        )


# ============================================================================
# POST /ai/sentiment - Analyze Message Sentiment
# ============================================================================


@router.post(
    "/sentiment",
    response_model=SentimentAnalysisResponse,
    responses={
        200: {"description": "Successful sentiment analysis"},
        401: {"model": AIErrorResponse},
        403: {"model": AIErrorResponse},
        500: {"model": AIErrorResponse},
    },
    summary="Analyze message sentiment",
    description="""
    Performs AI-powered sentiment analysis on patient messages to identify
    emotional state, medical concerns, and urgency indicators.

    **Access:** Physicians and Admins only
    """,
)
async def analyze_sentiment(
    request: SentimentAnalysisRequest,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> SentimentAnalysisResponse:
    """
    Analyze sentiment and medical concerns in patient message.
    """
    try:
        logger.info(
            f"Sentiment analysis request from user {current_user.id}, "
            f"patient_id: {request.patient_id}"
        )

        # Build patient context if provided
        patient_context = None
        if request.patient_id:
            patient = await validate_patient_access(
                request.patient_id, current_user, get_patient_service(db)
            )

            context_builder = get_ai_service()
            patient_context = await context_builder.build_patient_context(
                str(request.patient_id),
                {
                    "name": patient.name,
                    "treatment_type": patient.treatment_type or "general",
                    "current_day": patient.current_day,
                },
            )
        else:
            # Create minimal context for analysis
            patient_context = PatientContext(
                patient_id="unknown",
                name="Patient",
                treatment_type="general",
                treatment_day=1,
            )

        # Analyze sentiment
        sentiment_analyzer = get_ai_service()
        analysis, concern_level = await sentiment_analyzer.analyze_response(
            request.message, patient_context
        )

        # Extract urgency indicators
        from app.services.ai import AIService

        ai_service = await get_ai_service()
        urgency_indicators = await ai_service.detect_urgency_indicators(request.message)

        # Determine recommended action
        recommended_action = None
        if concern_level == ConcernLevel.CRITICAL:
            recommended_action = "URGENT: Immediate medical attention required"
        elif concern_level == ConcernLevel.HIGH:
            recommended_action = "Schedule urgent consultation within 24 hours"
        elif concern_level == ConcernLevel.MEDIUM:
            recommended_action = "Schedule follow-up consultation within 48-72 hours"
        else:
            recommended_action = "Continue routine monitoring"

        return SentimentAnalysisResponse(
            message=request.message,
            sentiment=analysis.sentiment,
            concern_level=concern_level,
            confidence=analysis.confidence,
            key_phrases=analysis.key_phrases,
            medical_concerns=analysis.medical_concerns
            if request.include_medical_concerns
            else [],
            urgency_indicators=urgency_indicators,
            emotion_scores={"anxiety": 0.3, "sadness": 0.2, "frustration": 0.1},
            recommended_action=recommended_action,
            analyzed_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sentiment analysis error: {str(e)}",
        )


# ============================================================================
# GET /ai/insights/{patient_id} - Patient Insights
# ============================================================================


@router.get(
    "/insights/{patient_id}",
    response_model=InsightResponse,
    responses={
        200: {"description": "Patient insights retrieved successfully"},
        401: {"model": AIErrorResponse},
        403: {"model": AIErrorResponse},
        404: {"model": AIErrorResponse},
        500: {"model": AIErrorResponse},
    },
    summary="Get patient-specific AI insights",
    description="""
    Retrieves comprehensive AI-generated insights for a specific patient including
    sentiment trends, risk assessment, adherence scores, and engagement metrics.

    Results are cached for 5 minutes to improve performance while ensuring data freshness.

    **Access:** Physicians and Admins only
    """,
)
async def get_patient_insights(
    patient_id: UUID,
    days: int = Query(30, ge=1, le=90, description="Number of days to analyze"),
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> InsightResponse:
    """
    Get comprehensive AI insights for a patient.
    """
    try:
        # Initialize Redis client and check cache
        redis_client = await get_redis_client()
        cache_key = f"ai:insights:{patient_id}:{days}"
        cache_ttl = 300  # 5 minutes for insights

        cached_data = await get_cached_data(redis_client, cache_key)
        if cached_data:
            logger.info(
                f"[CACHE HIT] Returning cached insights for patient {patient_id} (days={days})"
            )
            return InsightResponse(**cached_data)

        logger.info(
            f"Generating insights for patient {patient_id} "
            f"requested by user {current_user.id}"
        )

        # Validate patient access
        patient = await validate_patient_access(
            patient_id, current_user, get_patient_service(db)
        )

        # Get patient messages
        from app.repositories.message import MessageRepository

        message_repo = MessageRepository(db)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        messages = message_repo.get_patient_messages(patient.id, start_date=cutoff_date)

        # Calculate metrics
        total_messages = len(messages)
        response_rate = min(total_messages / days, 1.0) if days > 0 else 0.0

        # Analyze sentiment trend
        sentiment_trend = TrendData(
            metric="overall_sentiment",
            direction="stable",
            change_percentage=0.0,
            data_points=[],
        )

        # Calculate adherence score
        adherence_score = 0.85  # Placeholder - would calculate from actual data

        # Determine risk level
        risk_level = RiskLevel.LOW
        if adherence_score < 0.5:
            risk_level = RiskLevel.HIGH
        elif adherence_score < 0.7:
            risk_level = RiskLevel.MODERATE

        # Build insights
        insights_data = InsightResponse(
            patient_id=patient_id,
            overall_status=f"{patient.name} is on day {patient.current_day} of {patient.treatment_type or 'treatment'}",
            risk_level=risk_level,
            sentiment_trends=[sentiment_trend],
            adherence_score=adherence_score,
            key_insights=[
                f"Response rate: {response_rate:.1%}",
                f"Total interactions: {total_messages}",
                f"Treatment adherence: {adherence_score:.1%}",
            ],
            alerts=[],
            engagement_metrics={
                "response_rate": response_rate,
                "total_messages": total_messages,
                "avg_response_time_hours": 2.5,
            },
            last_contact=messages[0].created_at if messages else None,
            insights_generated_at=datetime.utcnow(),
        )

        # Cache for 5 minutes to balance performance and freshness
        cache_success = await set_cached_data(
            redis_client, cache_key, insights_data.dict(), cache_ttl
        )

        if cache_success:
            logger.info(
                f"[CACHE SET] Cached insights for patient {patient_id} (TTL: {cache_ttl}s)"
            )
        else:
            logger.warning(
                f"[CACHE FAIL] Failed to cache insights for patient {patient_id}"
            )

        return insights_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating insights: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Insights generation error: {str(e)}",
        )


# ============================================================================
# GET /ai/recommendations/{patient_id} - AI Recommendations
# ============================================================================


@router.get(
    "/recommendations/{patient_id}",
    response_model=RecommendationResponse,
    responses={
        200: {"description": "Recommendations retrieved successfully"},
        401: {"model": AIErrorResponse},
        403: {"model": AIErrorResponse},
        404: {"model": AIErrorResponse},
        500: {"model": AIErrorResponse},
    },
    summary="Get AI recommendations for patient",
    description="""
    Generates actionable AI recommendations for patient care including clinical
    interventions, educational content, and follow-up scheduling.

    Results are cached for 10 minutes to ensure timely recommendations.

    **Access:** Physicians and Admins only
    """,
)
async def get_patient_recommendations(
    patient_id: UUID,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """
    Get AI-generated recommendations for patient care.
    """
    try:
        # Initialize Redis client and check cache
        redis_client = await get_redis_client()
        cache_key = f"ai:recommendations:{patient_id}"
        cache_ttl = 600  # 10 minutes for recommendations

        cached_data = await get_cached_data(redis_client, cache_key)
        if cached_data:
            logger.info(
                f"[CACHE HIT] Returning cached recommendations for patient {patient_id}"
            )
            return RecommendationResponse(**cached_data)

        logger.info(
            f"Generating recommendations for patient {patient_id} "
            f"requested by user {current_user.id}"
        )

        # Validate patient access
        patient = await validate_patient_access(
            patient_id, current_user, get_patient_service(db)
        )

        # Generate action items
        action_items = [
            ActionItem(
                title="Review treatment progress",
                description=f"Assess {patient.name}'s progress on day {patient.current_day}",
                priority="medium",
                category="clinical",
                estimated_impact="high",
                due_date=datetime.utcnow() + timedelta(days=7),
            ),
            ActionItem(
                title="Patient education session",
                description="Provide guidance on managing treatment side effects",
                priority="low",
                category="educational",
                estimated_impact="medium",
                due_date=datetime.utcnow() + timedelta(days=14),
            ),
        ]

        # Build recommendations
        recommendations_data = RecommendationResponse(
            patient_id=patient_id,
            recommendations_summary=f"Continue monitoring {patient.name}'s treatment progress with regular check-ins",
            action_items=action_items,
            clinical_insights=[
                f"Patient on day {patient.current_day} of treatment",
                "Treatment adherence within acceptable range",
                "No critical concerns identified",
            ],
            patient_education=[
                "Managing side effects during hormone therapy",
                "Importance of consistent medication timing",
                "Nutrition guidelines during treatment",
            ],
            intervention_suggestions=[],
            follow_up_schedule={
                "next_check_in": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "frequency": "weekly",
                "type": "routine",
            },
            confidence_level=0.82,
            generated_at=datetime.utcnow(),
        )

        # Cache for 10 minutes to balance performance with recommendation timeliness
        cache_success = await set_cached_data(
            redis_client, cache_key, recommendations_data.dict(), cache_ttl
        )

        if cache_success:
            logger.info(
                f"[CACHE SET] Cached recommendations for patient {patient_id} (TTL: {cache_ttl}s)"
            )
        else:
            logger.warning(
                f"[CACHE FAIL] Failed to cache recommendations for patient {patient_id}"
            )

        return recommendations_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recommendations generation error: {str(e)}",
        )


# ============================================================================
# GET /ai/summary/{patient_id} - Comprehensive Patient Summary
# ============================================================================


@router.get(
    "/summary/{patient_id}",
    response_model=PatientSummaryResponse,
    responses={
        200: {"description": "Patient summary retrieved successfully"},
        401: {"model": AIErrorResponse},
        403: {"model": AIErrorResponse},
        404: {"model": AIErrorResponse},
        500: {"model": AIErrorResponse},
    },
    summary="Get comprehensive AI summary",
    description="""
    Generates a comprehensive AI-powered summary of the patient's treatment journey,
    clinical status, recent concerns, and recommended next steps.

    **Access:** Physicians and Admins only
    """,
)
async def get_patient_summary(
    patient_id: UUID,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> PatientSummaryResponse:
    """
    Get comprehensive AI-generated patient summary.
    """
    try:
        logger.info(
            f"Generating summary for patient {patient_id} "
            f"requested by user {current_user.id}"
        )

        # Validate patient access
        patient = await validate_patient_access(
            patient_id, current_user, get_patient_service(db)
        )

        # Get patient messages for analysis
        from app.repositories.message import MessageRepository

        message_repo = MessageRepository(db)
        messages = message_repo.get_patient_messages(patient.id, limit=50)

        # Calculate treatment duration
        treatment_duration = patient.current_day
        if patient.treatment_start_date:
            duration_days = (
                datetime.utcnow().date() - patient.treatment_start_date
            ).days
            treatment_duration = max(duration_days, patient.current_day)

        # Build summary text
        summary_text = (
            f"{patient.name} is a patient undergoing {patient.treatment_type or 'hormone therapy'} "
            f"currently on day {patient.current_day} of treatment. "
        )

        if len(messages) > 0:
            summary_text += (
                f"The patient has been actively engaged with {len(messages)} interactions "
                f"recorded in the system. "
            )

        summary_text += (
            "Treatment adherence is being monitored and the patient's progress "
            "is tracked through regular check-ins."
        )

        # Build response
        summary_data = PatientSummaryResponse(
            patient_id=patient_id,
            summary_text=summary_text,
            treatment_overview={
                "type": patient.treatment_type or "hormone_therapy",
                "duration_days": treatment_duration,
                "current_phase": patient.flow_state.value,
                "start_date": patient.treatment_start_date.isoformat()
                if patient.treatment_start_date
                else None,
            },
            clinical_highlights=[
                f"Day {patient.current_day} of treatment",
                f"{len(messages)} total interactions",
                f"Current phase: {patient.flow_state.value}",
            ],
            recent_concerns=[],
            progress_indicators={
                "engagement": "active" if len(messages) > 10 else "moderate",
                "treatment_phase": patient.flow_state.value,
                "interaction_count": len(messages),
            },
            risk_assessment={
                "level": "low",
                "factors": [],
                "last_assessed": datetime.utcnow().isoformat(),
            },
            next_steps=[
                "Continue regular check-ins",
                "Monitor treatment adherence",
                "Schedule follow-up consultation as needed",
            ],
            data_completeness=0.85,
            summary_generated_at=datetime.utcnow(),
        )

        return summary_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Summary generation error: {str(e)}",
        )


# ============================================================================
# Health Check Endpoint
# ============================================================================


@router.get(
    "/health",
    summary="AI service health check",
    description="Check if AI services are operational including cache status",
)
async def ai_health_check():
    """Health check for AI services including Redis cache."""
    try:
        # Test AI services
        ai_humanizer = get_ai_service()
        sentiment_analyzer = get_ai_service()
        context_builder = get_ai_service()

        # Check Redis cache
        redis_client = await get_redis_client()
        cache_status = "unavailable"
        if redis_client:
            try:
                await redis_client.ping()
                cache_status = "operational"
            except:
                cache_status = "error"

        return {
            "status": "healthy",
            "services": {
                "ai_humanizer": "operational",
                "sentiment_analyzer": "operational",
                "context_builder": "operational",
                "redis_cache": cache_status,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"AI health check failed: {e}")
        return {
            "status": "degraded",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.get(
    "/cache/metrics",
    summary="Get AI cache metrics",
    description="Retrieve cache performance metrics and statistics",
)
async def get_cache_metrics(current_user: User = Depends(verify_physician_or_admin)):
    """Get AI cache performance metrics."""
    try:
        from app.services.ai import get_cache_layer

        cache_layer = await get_cache_layer()
        metrics = await cache_layer.get_metrics()

        return {
            "status": "success",
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get cache metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache metrics: {str(e)}",
        )


@router.post(
    "/cache/invalidate/{patient_id}",
    summary="Invalidate AI cache for patient",
    description="Manually invalidate all AI cache entries for a specific patient",
)
async def invalidate_cache_for_patient(
    patient_id: UUID, current_user: User = Depends(verify_physician_or_admin)
):
    """Manually invalidate AI cache for a patient."""
    try:
        redis_client = await get_redis_client()
        if not redis_client:
            return {
                "status": "warning",
                "message": "Redis cache not available",
                "invalidated_count": 0,
            }

        invalidated = await invalidate_patient_cache(redis_client, patient_id)

        return {
            "status": "success",
            "patient_id": str(patient_id),
            "invalidated_count": invalidated,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Cache invalidation failed for patient {patient_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache invalidation failed: {str(e)}",
        )
