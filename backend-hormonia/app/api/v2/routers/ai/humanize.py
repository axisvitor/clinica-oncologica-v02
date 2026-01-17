"""
AI Services - Humanize Endpoints

Security: Rate limited to prevent API abuse and manage AI costs.
"""

# Standard library imports
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Union

# Third-party imports
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

# Local application imports
from app.core.config import settings
from app.dependencies.business_dependencies import validate_patient_access
from app.dependencies.service_dependencies import get_patient_service
from app.models.user import User
from app.schemas.v2.ai import (
    AIModelType,
    BatchHumanizeRequest,
    BatchHumanizeResponse,
    CacheInfo,
    CacheStatsResponse,
    HumanizeRequest,
    HumanizeResponse,
    TokenUsage,
)
from app.utils.rate_limiter import limiter
from app.api.v2 import ai as ai_module

from .constants import CACHE_TTL_AI_RESPONSE
from .dependencies import (
    calculate_token_cost,
    generate_cache_key,
    get_cached_response,
    set_cached_response,
    track_token_usage,
    verify_physician_or_admin,
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
@limiter.limit("30/minute")
async def humanize_message(
    request: Request,  # Required for rate limiter
    humanize_request: HumanizeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    patient_service=Depends(get_patient_service),
) -> HumanizeResponse:
    """
    Humanize a message using AI with caching and cost tracking.
    """
    redis_client = None
    cache_info = None

    try:
        # Get Redis client
        redis_client = await ai_module.get_redis_cache()

        # Generate cache key with user_id to prevent cross-user cache sharing (HIPAA/Privacy)
        cache_key = generate_cache_key(
            "ai:humanize:v2",
            user_id=str(current_user.id),  # SECURITY FIX: Include user_id
            message=humanize_request.message,
            patient_id=str(humanize_request.patient_id) if humanize_request.patient_id else None,
            message_type=humanize_request.message_type,
            tone=humanize_request.tone,
        )

        # Check cache if enabled
        if humanize_request.use_cache:
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
        if humanize_request.patient_id:
            try:
                patient = await validate_patient_access(
                    humanize_request.patient_id, current_user, patient_service
                )
                patient_context = {
                    "name": patient.name,
                    "treatment_type": patient.treatment_type,
                    "current_day": patient.current_day,
                }
            except Exception as e:
                logger.warning(f"Failed to get patient context: {e}")

        # ===== AI SERVICE CALL WOULD GO HERE =====
        # Runtime guard: Prevent production use of simulation mode
        if settings.APP_ENVIRONMENT == "production" and not settings.ALLOW_AI_SIMULATION:
            logger.error(
                "[PRODUCTION ERROR] AI service not configured - simulation mode blocked",
                extra={
                    "user_id": current_user.id,
                    "endpoint": "humanize",
                    "environment": settings.APP_ENVIRONMENT,
                }
            )
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="AI service not configured. Real AI integration required for production."
            )

        # Warning: Using simulation mode
        logger.warning(
            "[SIMULATION MODE] Using mock AI response for humanization",
            extra={
                "user_id": current_user.id,
                "endpoint": "humanize",
                "environment": settings.APP_ENVIRONMENT,
                "warning": "This is simulated data - not real AI humanization"
            }
        )

        # For now, simulate AI response
        humanized = (
            f"Hi{' ' + patient_context['name'] if patient_context else ''}! "
            + humanize_request.message
        )
        if humanize_request.tone == "empathetic":
            humanized += " We're here to support you every step of the way."
        elif humanize_request.tone == "encouraging":
            humanized += " You're doing great! Keep it up!"

        # Simulate token usage
        prompt_tokens = len(humanize_request.message.split()) * 2
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
                AIModelType.GEMINI_PRO,
            ),
            model=AIModelType.GEMINI_PRO,
        )

        # Build response
        response = HumanizeResponse(
            original_message=humanize_request.message,
            humanized_message=humanized,
            personalization_notes=[
                "Added patient name" if patient_context else "Generic greeting",
                f"Applied {humanize_request.tone} tone",
            ],
            readability_score=85.0,
            tone_analysis={
                "empathy": 0.9 if humanize_request.tone == "empathetic" else 0.7,
                "professionalism": 0.8,
                "clarity": 0.85,
            },
            token_usage=token_usage,
            cache_info=CacheInfo(
                hit=False,
                key=cache_key,
                ttl_seconds=CACHE_TTL_AI_RESPONSE,
                cached_at=datetime.now(timezone.utc),
            ),
            generated_at=datetime.now(timezone.utc),
        )

        # Cache response
        response_dict = response.dict()
        await set_cached_response(
            redis_client, cache_key, response_dict, CACHE_TTL_AI_RESPONSE
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
            original_message=humanize_request.message,
            humanized_message=humanize_request.message,  # Return original as fallback
            personalization_notes=["Fallback: AI service unavailable"],
            readability_score=70.0,
            tone_analysis={},
            token_usage=None,
            cache_info=None,
            generated_at=datetime.now(timezone.utc),
        )


@router.post(
    "/batch",
    response_model=BatchHumanizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch humanize messages with TRUE parallel processing",
    description="""
    Humanize multiple messages concurrently in a single request (max 10).

    **Features:**
    - TRUE parallel processing with asyncio.gather (not sequential loop)
    - Process up to 10 messages concurrently
    - Individual caching per message
    - Aggregated token usage reporting
    - Rate limit: 10 requests/minute
    - Graceful error handling per message

    **Access:** Physicians and Admins only
    """,
)
@limiter.limit("10/minute")
async def batch_humanize_messages(
    request: Request,  # Required for rate limiter
    batch_request: BatchHumanizeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_physician_or_admin),
    patient_service=Depends(get_patient_service),
) -> BatchHumanizeResponse:
    """
    Batch humanize multiple messages with TRUE parallel processing using asyncio.gather.

    This implementation provides genuine concurrent processing, not sequential iteration.
    Each message is processed simultaneously, significantly improving performance for
    batch operations.
    """
    if not batch_request.messages:
        return BatchHumanizeResponse(
            results=[],
            total_token_usage=TokenUsage(
                total_tokens=0,
                estimated_cost_usd=0.0,
                model=AIModelType.GEMINI_PRO,
            ),
            cache_hit_rate=0.0,
            processed_at=datetime.now(timezone.utc),
        )

    # Create tasks for TRUE parallel processing
    tasks = [
        _process_single_humanize_message(
            request, msg_request, background_tasks, current_user, patient_service
        )
        for msg_request in batch_request.messages
    ]

    # Execute all tasks concurrently (TRUE parallelism)
    logger.info(f"Starting parallel batch processing of {len(tasks)} messages")
    start_time = datetime.now(timezone.utc)

    # Use asyncio.gather with return_exceptions=True for graceful error handling
    results: List[Union[HumanizeResponse, Exception]] = await asyncio.gather(
        *tasks, return_exceptions=True
    )

    # Process results and handle any exceptions
    processed_results: List[HumanizeResponse] = []
    total_tokens = 0
    total_cost = 0.0
    cache_hits = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Batch item {i} failed: {result}", exc_info=result)
            # Add fallback response for failed items
            processed_results.append(
                _create_fallback_response(batch_request.messages[i])
            )
        else:
            processed_results.append(result)

            # Aggregate metrics
            if result.token_usage:
                total_tokens += result.token_usage.total_tokens
                total_cost += result.token_usage.estimated_cost_usd

            if result.cache_info and result.cache_info.hit:
                cache_hits += 1

    processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

    total_token_usage = TokenUsage(
        total_tokens=total_tokens,
        estimated_cost_usd=total_cost,
        model=AIModelType.GEMINI_PRO,
    )

    cache_hit_rate = cache_hits / len(processed_results) if processed_results else 0.0

    logger.info(
        f"Parallel batch humanize completed: {len(processed_results)} messages, "
        f"cache hit rate: {cache_hit_rate:.1%}, "
        f"total cost: ${total_cost:.4f}, "
        f"processing time: {processing_time:.2f}s"
    )

    return BatchHumanizeResponse(
        results=processed_results,
        total_token_usage=total_token_usage,
        cache_hit_rate=cache_hit_rate,
        processed_at=datetime.now(timezone.utc),
    )


# ============================================================================
# Helper Functions for Batch Processing
# ============================================================================


async def _process_single_humanize_message(
    request_obj: Request,
    msg_request: HumanizeRequest,
    background_tasks: BackgroundTasks,
    current_user: User,
    patient_service,
) -> HumanizeResponse:
    """
    Process a single message in batch operation.

    This function is designed to be called concurrently with asyncio.gather.

    Args:
        request_obj: FastAPI request object (for rate limiter)
        msg_request: Individual humanize request
        background_tasks: FastAPI background tasks
        current_user: Authenticated user
        patient_service: Patient service for access validation

    Returns:
        HumanizeResponse for the single message

    Raises:
        Exception: Any processing error (caught by gather with return_exceptions=True)
    """
    return await humanize_message(
        request_obj, msg_request, background_tasks, current_user, patient_service
    )


def _create_fallback_response(msg_request: HumanizeRequest) -> HumanizeResponse:
    """
    Create a fallback response when message processing fails.

    Args:
        msg_request: Original humanize request

    Returns:
        Fallback HumanizeResponse with original message
    """
    return HumanizeResponse(
        original_message=msg_request.message,
        humanized_message=msg_request.message,  # Return original as fallback
        personalization_notes=["Error: Failed to process - using original message"],
        readability_score=0.0,
        tone_analysis={},
        token_usage=None,
        cache_info=None,
        generated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/cache-stats",
    response_model=CacheStatsResponse,
    summary="Get humanize cache statistics",
    description="Retrieve cache performance metrics for humanize endpoint.",
)
@limiter.limit("60/minute")
async def get_humanize_cache_stats(
    request: Request,  # Required for rate limiter
    current_user: User = Depends(verify_physician_or_admin),
) -> CacheStatsResponse:
    """Get cache statistics for humanize endpoint."""
    from fastapi import HTTPException

    redis_client = await ai_module.get_redis_cache()

    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis cache unavailable",
        )

    try:
        # Get cache keys matching pattern
        cursor = 0
        total_keys = 0
        keys = []

        while True:
            cursor, batch = await redis_client.scan(
                cursor=cursor, match="ai:humanize:v2:*", count=100
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
            generated_at=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache statistics: {str(e)}",
        )
