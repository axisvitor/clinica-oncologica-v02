"""
AI Services - Usage Statistics and Cache Stats Endpoints
"""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.user import User
from app.schemas.v2.ai import AIModelType
from app.schemas.v2.ai import UsageStatsResponse
from app.api.v2.routers import ai as ai_module
from .dependencies import verify_physician_or_admin
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/",
    response_model=UsageStatsResponse,
    summary="Get token usage statistics",
    description="Retrieve token usage and cost metrics (cached 1h).",
)
async def get_usage_statistics(
    period: str = Query("day", pattern="^(hour|day|week|month)$"),
    current_user: User = Depends(verify_physician_or_admin),
) -> UsageStatsResponse:
    """Get token usage and cost statistics."""
    try:
        redis_client = await ai_module.get_redis_cache()

        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis unavailable for usage stats",
            )

        lookback_days = {
            "hour": 1,
            "day": 1,
            "week": 7,
            "month": 30,
        }.get(period, 1)
        cutoff = now_sao_paulo().date() - timedelta(days=lookback_days - 1)

        cursor = 0
        usage_keys: list[str] = []
        while True:
            cursor, batch = await redis_client.scan(
                cursor=cursor,
                match="ai:usage:*",
                count=500,
            )
            if batch:
                usage_keys.extend(batch)
            if cursor == 0:
                break

        total_requests = 0
        total_tokens = 0
        total_cost = 0.0
        by_endpoint: dict[str, dict[str, float | int]] = {}
        by_model: dict[str, dict[str, float | int]] = {}

        def infer_model(endpoint: str) -> str:
            if endpoint in {"sentiment", "response_quality"}:
                return AIModelType.GEMINI_FLASH.value
            return AIModelType.GEMINI_PRO.value

        for key in usage_keys:
            parts = str(key).split(":")
            if len(parts) < 5:
                continue

            try:
                key_date = date.fromisoformat(parts[2])
            except ValueError:
                continue
            if key_date < cutoff:
                continue

            endpoint = parts[3]
            payload = await redis_client.hgetall(key)
            requests_count = int(float(payload.get("requests", 0)))
            tokens_count = int(float(payload.get("tokens", 0)))
            cost_usd = float(payload.get("cost_usd", 0.0))

            total_requests += requests_count
            total_tokens += tokens_count
            total_cost += cost_usd

            endpoint_stats = by_endpoint.setdefault(
                endpoint,
                {"requests": 0, "tokens": 0, "cost_usd": 0.0},
            )
            endpoint_stats["requests"] += requests_count
            endpoint_stats["tokens"] += tokens_count
            endpoint_stats["cost_usd"] += cost_usd

            model_key = infer_model(endpoint)
            model_stats = by_model.setdefault(
                model_key,
                {"requests": 0, "tokens": 0, "cost_usd": 0.0},
            )
            model_stats["requests"] += requests_count
            model_stats["tokens"] += tokens_count
            model_stats["cost_usd"] += cost_usd

        cache_hit_rate = 0.0
        cost_savings = 0.0
        try:
            stats_info = await redis_client.info("stats")
            hits = int(stats_info.get("keyspace_hits", 0))
            misses = int(stats_info.get("keyspace_misses", 0))
            total_cache_ops = hits + misses
            cache_hit_rate = hits / total_cache_ops if total_cache_ops else 0.0
            cost_savings = total_cost * cache_hit_rate
        except Exception as redis_stats_error:
            logger.warning("Could not compute cache hit rate: %s", redis_stats_error)

        return UsageStatsResponse(
            period=period,
            total_requests=total_requests,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 6),
            by_endpoint=by_endpoint,
            by_model=by_model,
            cache_hit_rate=cache_hit_rate,
            cost_savings_usd=round(cost_savings, 6),
            generated_at=now_sao_paulo(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get usage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve usage statistics: {str(e)}",
        )
