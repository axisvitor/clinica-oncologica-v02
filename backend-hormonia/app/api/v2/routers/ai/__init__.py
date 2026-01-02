"""
AI Services API v2 - Modular Router Package

Modern patterns with caching, rate limiting, and cost tracking.

Features:
- Redis caching (2h for AI responses, 15min for insights)
- Rate limiting (10/min for AI calls, 30/min for humanize)
- Token usage tracking and billing metrics
- Async processing for long-running operations
- Comprehensive error handling with fallbacks
- Cost optimization through intelligent caching
"""

from fastapi import APIRouter

from . import humanize, insights, analysis, health, stats, summary, recommendations

# Initialize main router with prefix and tags
router = APIRouter(tags=["AI Services v2"])

# Include all sub-routers
router.include_router(humanize.router, prefix="/humanize", tags=["AI - Humanize"])
router.include_router(insights.router, prefix="/insights", tags=["AI - Insights"])
router.include_router(analysis.router, prefix="/analyze", tags=["AI - Analysis"])
router.include_router(health.router, prefix="/health", tags=["AI - Health"])
router.include_router(stats.router, prefix="/usage", tags=["AI - Usage Stats"])
router.include_router(summary.router, prefix="/summary", tags=["AI - Patient Summary"])
router.include_router(recommendations.router, prefix="/recommendations", tags=["AI - Recommendations"])

__all__ = ["router"]
