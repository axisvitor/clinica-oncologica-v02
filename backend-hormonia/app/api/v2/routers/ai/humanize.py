"""
AI Services - Humanize Endpoints
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, BackgroundTasks, status

from app.database import get_db
from app.models.user import User
from app.dependencies import validate_patient_access, get_patient_service
from app.schemas.v2.ai import (
    HumanizeRequest,
    HumanizeResponse,
    BatchHumanizeRequest,
    BatchHumanizeResponse,
    CacheStatsResponse,
    TokenUsage,
    CacheInfo,
    AIModelType,
)
from .constants import CACHE_TTL_AI_RESPONSE
from .dependencies import (
    verify_physician_or_admin,
    get_redis_cache,
    generate_cache_key,
    get_cached_response,
    set_cached_response,
    calculate_token_cost,
    track_token_usage,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/",
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
    db = Depends(get_db),
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
    "/batch",
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
    db = Depends(get_db),
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
    "/cache-stats",
    response_model=CacheStatsResponse,
    summary="Get humanize cache statistics",
    description="Retrieve cache performance metrics for humanize endpoint.",
)
async def get_humanize_cache_stats(
    current_user: User = Depends(verify_physician_or_admin),
) -> CacheStatsResponse:
    """Get cache statistics for humanize endpoint."""
    from fastapi import HTTPException

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
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache statistics: {str(e)}"
        )
