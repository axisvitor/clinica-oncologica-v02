"""
AI Services - Health Check and Status Endpoints
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.v2.ai import AIHealthResponse
from .dependencies import get_redis_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/",
    response_model=AIHealthResponse,
    summary="AI service health check",
    description="Check health status of AI services and dependencies.",
)
async def ai_health_check() -> AIHealthResponse:
    """Comprehensive AI service health check."""
    start_time = datetime.now(timezone.utc)

    try:
        # Check Redis
        redis_status = "operational"
        redis_info = {}
        try:
            redis_client = await get_redis_cache()
            if redis_client:
                await redis_client.ping()
                stats_info = await redis_client.info("stats")
                keyspace_info = await redis_client.info("keyspace")

                # Calculate actual hit rate
                hits = stats_info.get("keyspace_hits", 0)
                misses = stats_info.get("keyspace_misses", 0)
                total = hits + misses
                hit_rate = round(hits / total, 2) if total > 0 else 0.0

                # Get actual key count from keyspace (db0 typically)
                keys = 0
                for db_name, db_info in keyspace_info.items():
                    if db_name.startswith("db") and isinstance(db_info, dict):
                        keys += db_info.get("keys", 0)

                redis_info = {
                    "status": "operational",
                    "hit_rate": hit_rate,
                    "keys": keys,
                }
            else:
                redis_status = "unavailable"
                redis_info = {"status": "unavailable"}
        except Exception as e:
            redis_status = "error"
            redis_info = {"status": "error", "error": str(e)}

        # Check Gemini API availability
        gemini_status = "unknown"
        gemini_info = {"status": "unknown", "reason": "not_tested"}
        try:
            from app.config import settings

            if settings.AI_GEMINI_API_KEY:
                gemini_status = "configured"
                gemini_info = {"status": "configured", "enabled": True}
            else:
                gemini_info = {"status": "not_configured", "enabled": False}
        except Exception as e:
            gemini_info = {"status": "error", "error": str(e)}

        # Overall status
        overall_status = "healthy"
        if redis_status == "error" or gemini_status == "error":
            overall_status = "degraded"
        elif redis_status == "unavailable":
            overall_status = "degraded"

        response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Check actual AI service configurations
        from app.config import settings

        services = {
            "humanizer": "operational"
            if getattr(settings, "AI_ENABLE_HUMANIZATION", True)
            else "disabled",
            "sentiment_analyzer": "operational"
            if getattr(settings, "AI_ENABLE_SENTIMENT", True)
            else "disabled",
            "insights_generator": "operational"
            if getattr(settings, "AI_ENABLE_INSIGHTS", True)
            else "disabled",
            "risk_analyzer": "operational"
            if getattr(settings, "AI_ENABLE_RISK_ANALYSIS", True)
            else "disabled",
        }

        return AIHealthResponse(
            status=overall_status,
            services=services,
            redis_cache=redis_info,
            gemini_api=gemini_info,
            response_time_ms=response_time,
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return AIHealthResponse(
            status="unhealthy",
            services={},
            redis_cache={"status": "unknown"},
            gemini_api={"status": "unknown"},
            response_time_ms=0,
            timestamp=datetime.now(timezone.utc),
        )
