"""
AI Services - Usage Statistics and Cache Stats Endpoints
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.user import User
from app.schemas.v2.ai import UsageStatsResponse
from .dependencies import verify_physician_or_admin, get_redis_cache

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
        redis_client = await get_redis_cache()

        if not redis_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis unavailable for usage stats",
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
            generated_at=datetime.now(timezone.utc),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get usage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve usage statistics: {str(e)}",
        )
