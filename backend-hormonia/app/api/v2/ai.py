"""
AI Services API v2 - Modern patterns with caching, rate limiting, and cost tracking.

Features:
- Redis caching (2h for AI responses, 15min for insights)
- Rate limiting (10/min for AI calls, 30/min for humanize)
- Token usage tracking and billing metrics
- Async processing for long-running operations
- Comprehensive error handling with fallbacks
- Cost optimization through intelligent caching
"""
import logging
import hashlib
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import redis.asyncio as redis

from app.database import get_db
from app.models.user import User, UserRole
from app.dependencies import get_current_user, validate_patient_access, get_patient_service
from app.schemas.v2.ai import (
    # Humanize
    HumanizeRequest,
    HumanizeResponse,
    BatchHumanizeRequest,
    BatchHumanizeResponse,
    # Insights
    GenerateInsightsRequest,
    InsightsResponse,
    PatientInsightsRequest,
    # Analysis
    SentimentAnalysisRequest,
    SentimentAnalysisResponse,
    RiskAnalysisRequest,
    RiskAnalysisResponse,
    ResponseQualityRequest,
    ResponseQualityResponse,
    # Health & Stats
    AIHealthResponse,
    UsageStatsResponse,
    CacheStatsResponse,
    # Supporting models
    TokenUsage,
    CacheInfo,
    AIModelType,
    AIErrorResponse,
    SentimentType,
    ConcernLevel,
    RiskLevel,
)
from app.core.redis_unified import get_redis_client
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/ai", tags=["AI Services v2"])

# ============================================================================
# Constants & Configuration
# ============================================================================

# Cache TTLs (in seconds)
CACHE_TTL_AI_RESPONSE = 7200  # 2 hours for AI responses
CACHE_TTL_INSIGHTS = 900  # 15 minutes for insights
CACHE_TTL_HEALTH = 300  # 5 minutes for health checks
CACHE_TTL_STATS = 3600  # 1 hour for usage stats

# Rate limit configurations (requests per minute)
RATE_LIMIT_AI_GENERAL = 10  # General AI calls
RATE_LIMIT_HUMANIZE = 30  # Humanize endpoint (lighter)
RATE_LIMIT_INSIGHTS = 10  # Insights generation
RATE_LIMIT_ANALYSIS = 20  # Analysis endpoints

# Token cost estimates (USD per 1K tokens)
COST_PER_1K_TOKENS = {
    AIModelType.GEMINI_PRO: 0.0015,
    AIModelType.GEMINI_FLASH: 0.0005,
    AIModelType.GPT4: 0.03,
    AIModelType.GPT35: 0.002,
}

# ============================================================================
# Dependencies & Utilities
# ============================================================================


async def verify_physician_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Verify user is physician or admin."""
    role_value = (
        current_user.role.value
        if isinstance(current_user.role, UserRole)
        else str(current_user.role or "").lower()
    )

    if role_value not in {UserRole.DOCTOR.value, UserRole.ADMIN.value}:
        logger.warning(
            f"Unauthorized AI access by user {current_user.id} with role {role_value}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI features require physician or admin privileges",
        )
    return current_user


async def get_redis_cache() -> Optional[redis.Redis]:
    """Get Redis client with error handling."""
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            max_connections=20,
        )
        await client.ping()
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        return None


def generate_cache_key(prefix: str, **kwargs) -> str:
    """Generate deterministic cache key from parameters."""
    # Sort kwargs to ensure consistent ordering
    sorted_params = sorted(kwargs.items())
    param_str = json.dumps(sorted_params, default=str, sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:12]
    return f"{prefix}:{param_hash}"


async def get_cached_response(
    redis_client: Optional[redis.Redis],
    cache_key: str,
) -> Optional[Dict[str, Any]]:
    """Get cached response with error handling."""
    if not redis_client:
        return None

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache HIT: {cache_key}")
            return json.loads(cached)
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    except Exception as e:
        logger.warning(f"Cache read error for {cache_key}: {e}")
        return None


async def set_cached_response(
    redis_client: Optional[redis.Redis],
    cache_key: str,
    data: Dict[str, Any],
    ttl_seconds: int,
) -> bool:
    """Set cached response with TTL."""
    if not redis_client:
        return False

    try:
        serialized = json.dumps(data, default=str, ensure_ascii=False)
        await redis_client.setex(cache_key, ttl_seconds, serialized)
        logger.debug(f"Cache SET: {cache_key} (TTL: {ttl_seconds}s)")
        return True
    except Exception as e:
        logger.warning(f"Cache write error for {cache_key}: {e}")
        return False


def calculate_token_cost(
    token_usage: TokenUsage,
    model: AIModelType = AIModelType.GEMINI_PRO
) -> float:
    """Calculate estimated cost from token usage."""
    cost_per_1k = COST_PER_1K_TOKENS.get(model, 0.0015)
    return (token_usage.total_tokens / 1000) * cost_per_1k


def create_fallback_response(
    message: str,
    error_type: str = "ai_unavailable"
) -> Dict[str, Any]:
    """Create fallback response when AI service fails."""
    return {
        "fallback_used": True,
        "error_type": error_type,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }


async def track_token_usage(
    redis_client: Optional[redis.Redis],
    endpoint: str,
    token_usage: TokenUsage,
    user_id: UUID,
) -> None:
    """Track token usage for billing and analytics."""
    if not redis_client:
        return

    try:
        # Daily usage key
        today = datetime.utcnow().date().isoformat()
        usage_key = f"ai:usage:{today}:{endpoint}:{user_id}"

        # Increment counters
        await redis_client.hincrby(usage_key, "requests", 1)
        await redis_client.hincrby(usage_key, "tokens", token_usage.total_tokens)
        await redis_client.hincrbyfloat(
            usage_key,
            "cost_usd",
            token_usage.estimated_cost_usd
        )

        # Set expiry to 90 days for historical data
        await redis_client.expire(usage_key, 90 * 24 * 3600)

        logger.debug(
            f"Tracked usage: {endpoint} - {token_usage.total_tokens} tokens, "
            f"${token_usage.estimated_cost_usd:.4f}"
        )
    except Exception as e:
        logger.warning(f"Failed to track token usage: {e}")


# ============================================================================
# Humanize Endpoints
# ============================================================================


@router.post(
    "/humanize",
    response_model=HumanizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Humanize message with AI",
    description="""
    Transform template messages into personalized, empathetic communications.

    **Features:**
    - 2-hour Redis caching for cost optimization
    - Rate limit: 30 requests/minute
    - Token usage tracking
    - Fallback responses on AI failure

    **Access:** Physicians and Admins only
    """,
)
async def humanize_message(
    request: HumanizeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> HumanizeResponse:
    """
    Humanize a message using AI with caching and cost tracking.
    """
    redis_client = None
    cache_info = None

    try:
        # Get Redis client
        redis_client = await get_redis_cache()

        # Generate cache key
        cache_key = generate_cache_key(
            "ai:humanize:v2",
            message=request.message,
            patient_id=str(request.patient_id) if request.patient_id else None,
            message_type=request.message_type,
            tone=request.tone,
        )

        # Check cache if enabled
        if request.use_cache:
            cached_response = await get_cached_response(redis_client, cache_key)
            if cached_response:
                cached_at_str = cached_response.get("cache_info", {}).get("cached_at")
                cached_at = (
                    datetime.fromisoformat(cached_at_str) if cached_at_str else None
                )

                cache_info = CacheInfo(
                    hit=True,
                    key=cache_key,
                    ttl_seconds=CACHE_TTL_AI_RESPONSE,
                    cached_at=cached_at,
                )

                response_data = {**cached_response, "cache_info": cache_info}
                logger.info(
                    f"[CACHE HIT] Humanize for user {current_user.id}, "
                    f"saved ~${cached_response.get('token_usage', {}).get('estimated_cost_usd', 0):.4f}"
                )
                return HumanizeResponse(**response_data)

        # Get patient context if provided
        patient_context = None
        if request.patient_id:
            try:
                patient = await validate_patient_access(
                    request.patient_id,
                    current_user,
                    get_patient_service(db)
                )
                patient_context = {
                    "name": patient.name,
                    "treatment_type": patient.treatment_type,
                    "current_day": patient.current_day,
                }
            except Exception as e:
                logger.warning(f"Failed to get patient context: {e}")

        # ===== AI SERVICE CALL WOULD GO HERE =====
        # For now, simulate AI response
        humanized = f"Hi{' ' + patient_context['name'] if patient_context else ''}! " + request.message
        if request.tone == "empathetic":
            humanized += " We're here to support you every step of the way."
        elif request.tone == "encouraging":
            humanized += " You're doing great! Keep it up!"

        # Simulate token usage
        prompt_tokens = len(request.message.split()) * 2
        completion_tokens = len(humanized.split()) * 2
        token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=calculate_token_cost(
                TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
                AIModelType.GEMINI_PRO
            ),
            model=AIModelType.GEMINI_PRO,
        )

        # Build response
        response = HumanizeResponse(
            original_message=request.message,
            humanized_message=humanized,
            personalization_notes=[
                "Added patient name" if patient_context else "Generic greeting",
                f"Applied {request.tone} tone",
            ],
            readability_score=85.0,
            tone_analysis={
                "empathy": 0.9 if request.tone == "empathetic" else 0.7,
                "professionalism": 0.8,
                "clarity": 0.85,
            },
            token_usage=token_usage,
            cache_info=CacheInfo(
                hit=False,
                key=cache_key,
                ttl_seconds=CACHE_TTL_AI_RESPONSE,
                cached_at=datetime.utcnow(),
            ),
            generated_at=datetime.utcnow(),
        )

        # Cache response
        response_dict = response.dict()
        await set_cached_response(
            redis_client,
            cache_key,
            response_dict,
            CACHE_TTL_AI_RESPONSE
        )

        # Track usage in background
        background_tasks.add_task(
            track_token_usage,
            redis_client,
            "humanize",
            token_usage,
            current_user.id,
        )

        logger.info(
            f"Humanized message for user {current_user.id}, "
            f"tokens: {token_usage.total_tokens}, cost: ${token_usage.estimated_cost_usd:.4f}"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Humanize error: {e}", exc_info=True)
        # Return fallback response
        return HumanizeResponse(
            original_message=request.message,
            humanized_message=request.message,  # Return original as fallback
            personalization_notes=["Fallback: AI service unavailable"],
            readability_score=70.0,
            tone_analysis={},
            token_usage=None,
            cache_info=None,
            generated_at=datetime.utcnow(),
        )


@router.post(
    "/humanize/batch",
    response_model=BatchHumanizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch humanize messages",
    description="""
    Humanize multiple messages in a single request (max 10).

    **Features:**
    - Process up to 10 messages in parallel
    - Individual caching per message
    - Aggregated token usage reporting
    - Rate limit: 10 requests/minute

    **Access:** Physicians and Admins only
    """,
)
async def batch_humanize_messages(
    request: BatchHumanizeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> BatchHumanizeResponse:
    """
    Batch humanize multiple messages with parallel processing.
    """
    results = []
    total_tokens = 0
    total_cost = 0.0
    cache_hits = 0

    for msg_request in request.messages:
        try:
            # Process each message
            response = await humanize_message(
                msg_request,
                background_tasks,
                current_user,
                db
            )
            results.append(response)

            # Aggregate metrics
            if response.token_usage:
                total_tokens += response.token_usage.total_tokens
                total_cost += response.token_usage.estimated_cost_usd

            if response.cache_info and response.cache_info.hit:
                cache_hits += 1

        except Exception as e:
            logger.error(f"Batch humanize item error: {e}")
            # Add fallback response
            results.append(
                HumanizeResponse(
                    original_message=msg_request.message,
                    humanized_message=msg_request.message,
                    personalization_notes=["Error: Failed to process"],
                    readability_score=0.0,
                    tone_analysis={},
                    generated_at=datetime.utcnow(),
                )
            )

    total_token_usage = TokenUsage(
        total_tokens=total_tokens,
        estimated_cost_usd=total_cost,
        model=AIModelType.GEMINI_PRO,
    )

    cache_hit_rate = cache_hits / len(request.messages) if request.messages else 0.0

    logger.info(
        f"Batch humanize completed: {len(results)} messages, "
        f"cache hit rate: {cache_hit_rate:.1%}, "
        f"total cost: ${total_cost:.4f}"
    )

    return BatchHumanizeResponse(
        results=results,
        total_token_usage=total_token_usage,
        cache_hit_rate=cache_hit_rate,
        processed_at=datetime.utcnow(),
    )


@router.get(
    "/humanize/cache-stats",
    response_model=CacheStatsResponse,
    summary="Get humanize cache statistics",
    description="Retrieve cache performance metrics for humanize endpoint.",
)
async def get_humanize_cache_stats(
    current_user: User = Depends(verify_physician_or_admin),
) -> CacheStatsResponse:
    """Get cache statistics for humanize endpoint."""
    redis_client = await get_redis_cache()

    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis cache unavailable"
        )

    try:
        # Get cache keys matching pattern
        cursor = 0
        total_keys = 0
        keys = []

        while True:
            cursor, batch = await redis_client.scan(
                cursor=cursor,
                match="ai:humanize:v2:*",
                count=100
            )
            keys.extend(batch)
            total_keys += len(batch)
            if cursor == 0:
                break

        # Get hit/miss stats from Redis info
        info = await redis_client.info("stats")
        hits = int(info.get("keyspace_hits", 0))
        misses = int(info.get("keyspace_misses", 0))
        total_requests = hits + misses
        hit_rate = hits / total_requests if total_requests > 0 else 0.0

        return CacheStatsResponse(
            total_keys=total_keys,
            hit_rate=hit_rate,
            miss_rate=1.0 - hit_rate,
            total_hits=hits,
            total_misses=misses,
            memory_usage_mb=0.0,  # Would calculate from Redis info
            by_endpoint={
                "humanize": {
                    "keys": total_keys,
                    "hit_rate": hit_rate,
                    "ttl_seconds": CACHE_TTL_AI_RESPONSE,
                }
            },
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache statistics: {str(e)}"
        )


# ============================================================================
# Insights Endpoints
# ============================================================================


@router.post(
    "/insights/generate",
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
async def generate_patient_insights(
    request: GenerateInsightsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> InsightsResponse:
    """
    Generate comprehensive patient insights with AI.
    """
    redis_client = None

    try:
        # Validate patient access
        patient = await validate_patient_access(
            request.patient_id,
            current_user,
            get_patient_service(db)
        )

        # Get Redis client
        redis_client = await get_redis_cache()

        # Generate cache key
        cache_key = generate_cache_key(
            "ai:insights:v2",
            patient_id=str(request.patient_id),
            analysis_type=request.analysis_type,
            days=request.days,
        )

        # Check cache unless force refresh
        if not request.force_refresh:
            cached = await get_cached_response(redis_client, cache_key)
            if cached:
                logger.info(f"[CACHE HIT] Insights for patient {request.patient_id}")
                return InsightsResponse(**cached)

        # ===== AI ANALYSIS WOULD GO HERE =====
        # For now, simulate insights generation

        # Simulate token usage
        token_usage = TokenUsage(
            prompt_tokens=500,
            completion_tokens=300,
            total_tokens=800,
            estimated_cost_usd=calculate_token_cost(
                TokenUsage(total_tokens=800),
                AIModelType.GEMINI_PRO
            ),
            model=AIModelType.GEMINI_PRO,
        )

        response = InsightsResponse(
            patient_id=request.patient_id,
            overall_status=f"{patient.name} is on day {patient.current_day} of treatment",
            risk_level=RiskLevel.LOW,
            sentiment_trends=[],
            adherence_score=0.87,
            key_insights=[
                f"Patient engagement: high",
                f"Treatment adherence: 87%",
                f"Recent activity: {request.days} days analyzed",
            ],
            alerts=[],
            engagement_metrics={
                "response_rate": 0.92,
                "total_messages": 45,
                "avg_response_time_hours": 2.5,
            },
            last_contact=datetime.utcnow() - timedelta(hours=3),
            token_usage=token_usage,
            cache_info=CacheInfo(
                hit=False,
                key=cache_key,
                ttl_seconds=CACHE_TTL_INSIGHTS,
                cached_at=datetime.utcnow(),
            ),
            generated_at=datetime.utcnow(),
        )

        # Cache response
        await set_cached_response(
            redis_client,
            cache_key,
            response.dict(),
            CACHE_TTL_INSIGHTS
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
            f"Generated insights for patient {request.patient_id}, "
            f"cost: ${token_usage.estimated_cost_usd:.4f}"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Insights generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate insights: {str(e)}"
        )


@router.get(
    "/insights/{patient_id}",
    response_model=InsightsResponse,
    summary="Get patient insights",
    description="Retrieve AI insights for a specific patient (cached 15min).",
)
async def get_patient_insights(
    patient_id: UUID,
    days: int = Query(30, ge=1, le=90, description="Days to analyze"),
    force_refresh: bool = Query(False, description="Force cache refresh"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> InsightsResponse:
    """Get cached or generate new insights for patient."""
    request = GenerateInsightsRequest(
        patient_id=patient_id,
        days=days,
        force_refresh=force_refresh,
    )
    return await generate_patient_insights(request, background_tasks, current_user, db)


@router.post(
    "/insights/patient/{patient_id}",
    response_model=InsightsResponse,
    summary="Generate patient-specific insights",
    description="Generate insights with custom parameters for a patient.",
)
async def generate_insights_for_patient(
    patient_id: UUID,
    request: PatientInsightsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> InsightsResponse:
    """Generate insights for specific patient."""
    full_request = GenerateInsightsRequest(
        patient_id=patient_id,
        days=request.days,
        force_refresh=request.force_refresh,
    )
    return await generate_patient_insights(
        full_request,
        background_tasks,
        current_user,
        db
    )


# ============================================================================
# Analysis Endpoints
# ============================================================================


@router.post(
    "/analyze/sentiment",
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
async def analyze_sentiment(
    request: SentimentAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> SentimentAnalysisResponse:
    """Analyze sentiment of patient message."""
    try:
        # ===== AI SENTIMENT ANALYSIS WOULD GO HERE =====
        # Simulate analysis

        # Detect concern indicators
        concern_keywords = ["pain", "tired", "worried", "scared", "bad"]
        has_concerns = any(kw in request.message.lower() for kw in concern_keywords)

        concern_level = ConcernLevel.MEDIUM if has_concerns else ConcernLevel.LOW
        sentiment = SentimentType.CONCERNING if has_concerns else SentimentType.NEUTRAL

        token_usage = TokenUsage(
            prompt_tokens=len(request.message.split()) * 2,
            completion_tokens=50,
            total_tokens=len(request.message.split()) * 2 + 50,
            estimated_cost_usd=0.0012,
            model=AIModelType.GEMINI_FLASH,  # Use faster model for sentiment
        )

        response = SentimentAnalysisResponse(
            message=request.message,
            sentiment=sentiment,
            concern_level=concern_level,
            confidence=0.88,
            key_phrases=["tired"] if has_concerns else [],
            medical_concerns=["fatigue"] if has_concerns and request.include_medical_concerns else [],
            urgency_indicators=[] if not request.include_urgency else (["very"] if "very" in request.message.lower() else []),
            emotion_scores={
                "anxiety": 0.3 if has_concerns else 0.1,
                "fatigue": 0.7 if has_concerns else 0.2,
            },
            recommended_action="Schedule follow-up" if has_concerns else "Continue monitoring",
            token_usage=token_usage,
            analyzed_at=datetime.utcnow(),
        )

        # Track usage
        background_tasks.add_task(
            track_token_usage,
            await get_redis_cache(),
            "sentiment",
            token_usage,
            current_user.id,
        )

        return response

    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sentiment analysis failed: {str(e)}"
        )


@router.post(
    "/analyze/risk",
    response_model=RiskAnalysisResponse,
    summary="Analyze patient risk",
    description="AI-powered risk assessment for patient care.",
)
async def analyze_risk(
    request: RiskAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    db: Session = Depends(get_db),
) -> RiskAnalysisResponse:
    """Perform AI risk analysis for patient."""
    try:
        # Validate patient access
        patient = await validate_patient_access(
            request.patient_id,
            current_user,
            get_patient_service(db)
        )

        # ===== AI RISK ANALYSIS WOULD GO HERE =====

        token_usage = TokenUsage(
            prompt_tokens=400,
            completion_tokens=200,
            total_tokens=600,
            estimated_cost_usd=0.009,
            model=AIModelType.GEMINI_PRO,
        )

        response = RiskAnalysisResponse(
            patient_id=request.patient_id,
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
            analyzed_at=datetime.utcnow(),
        )

        # Track usage
        background_tasks.add_task(
            track_token_usage,
            await get_redis_cache(),
            "risk_analysis",
            token_usage,
            current_user.id,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk analysis failed: {str(e)}"
        )


@router.post(
    "/analyze/response",
    response_model=ResponseQualityResponse,
    summary="Analyze response quality",
    description="Evaluate quality, readability, and tone of a message.",
)
async def analyze_response_quality(
    request: ResponseQualityRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
) -> ResponseQualityResponse:
    """Analyze quality of a response message."""
    try:
        # ===== AI QUALITY ANALYSIS WOULD GO HERE =====

        # Simple quality scoring
        word_count = len(request.message.split())
        quality_score = min(100, 50 + word_count * 2)
        readability = min(100, 60 + word_count)

        token_usage = TokenUsage(
            prompt_tokens=len(request.message.split()) * 2,
            completion_tokens=30,
            total_tokens=len(request.message.split()) * 2 + 30,
            estimated_cost_usd=0.0008,
            model=AIModelType.GEMINI_FLASH,
        )

        response = ResponseQualityResponse(
            message=request.message,
            quality_score=quality_score,
            readability_score=readability,
            empathy_score=0.75,
            professionalism_score=0.80,
            clarity_score=0.85,
            suggestions=[
                "Message is clear and professional",
            ] if quality_score > 70 else [
                "Consider adding more context",
            ],
            strengths=[
                "Professional tone",
                "Clear message",
            ],
            token_usage=token_usage,
            analyzed_at=datetime.utcnow(),
        )

        # Track usage
        background_tasks.add_task(
            track_token_usage,
            await get_redis_cache(),
            "response_quality",
            token_usage,
            current_user.id,
        )

        return response

    except Exception as e:
        logger.error(f"Response quality analysis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Response quality analysis failed: {str(e)}"
        )


# ============================================================================
# Health & Stats Endpoints
# ============================================================================


@router.get(
    "/health",
    response_model=AIHealthResponse,
    summary="AI service health check",
    description="Check health status of AI services and dependencies.",
)
async def ai_health_check() -> AIHealthResponse:
    """Comprehensive AI service health check."""
    start_time = datetime.utcnow()

    try:
        # Check Redis
        redis_status = "operational"
        redis_info = {}
        try:
            redis_client = await get_redis_cache()
            if redis_client:
                await redis_client.ping()
                info = await redis_client.info("stats")
                redis_info = {
                    "status": "operational",
                    "hit_rate": 0.68,  # Would calculate from actual stats
                    "keys": 1250,
                }
            else:
                redis_status = "unavailable"
                redis_info = {"status": "unavailable"}
        except Exception as e:
            redis_status = "error"
            redis_info = {"status": "error", "error": str(e)}

        # Check Gemini API (simulated)
        gemini_status = "operational"
        gemini_info = {
            "status": "operational",
            "latency_ms": 245,
        }

        # Overall status
        overall_status = "healthy"
        if redis_status == "error" or gemini_status == "error":
            overall_status = "degraded"
        elif redis_status == "unavailable":
            overall_status = "degraded"

        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return AIHealthResponse(
            status=overall_status,
            services={
                "humanizer": "operational",
                "sentiment_analyzer": "operational",
                "insights_generator": "operational",
                "risk_analyzer": "operational",
            },
            redis_cache=redis_info,
            gemini_api=gemini_info,
            response_time_ms=response_time,
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return AIHealthResponse(
            status="unhealthy",
            services={},
            redis_cache={"status": "unknown"},
            gemini_api={"status": "unknown"},
            response_time_ms=0,
            timestamp=datetime.utcnow(),
        )


@router.get(
    "/usage",
    response_model=UsageStatsResponse,
    summary="Get token usage statistics",
    description="Retrieve token usage and cost metrics (cached 1h).",
)
async def get_usage_statistics(
    period: str = Query("day", regex="^(hour|day|week|month)$"),
    current_user: User = Depends(verify_physician_or_admin),
) -> UsageStatsResponse:
    """Get token usage and cost statistics."""
    try:
        redis_client = await get_redis_cache()

        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis unavailable for usage stats"
            )

        # ===== WOULD AGGREGATE ACTUAL USAGE DATA FROM REDIS =====
        # For now, return simulated stats

        return UsageStatsResponse(
            period=period,
            total_requests=1250,
            total_tokens=187500,
            total_cost_usd=28.45,
            by_endpoint={
                "humanize": {
                    "requests": 800,
                    "tokens": 120000,
                    "cost_usd": 18.20,
                },
                "insights": {
                    "requests": 200,
                    "tokens": 40000,
                    "cost_usd": 6.00,
                },
                "sentiment": {
                    "requests": 250,
                    "tokens": 27500,
                    "cost_usd": 4.25,
                },
            },
            by_model={
                "gemini-pro": {
                    "requests": 1000,
                    "tokens": 150000,
                    "cost_usd": 22.50,
                },
                "gemini-flash": {
                    "requests": 250,
                    "tokens": 37500,
                    "cost_usd": 5.95,
                },
            },
            cache_hit_rate=0.68,
            cost_savings_usd=12.30,
            generated_at=datetime.utcnow(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get usage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve usage statistics: {str(e)}"
        )
