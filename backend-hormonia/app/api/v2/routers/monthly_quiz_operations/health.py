"""
Health check endpoint for quiz operations.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    summary="Quiz extensions health check",
    description="Check if quiz extensions API is operational",
)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "quiz-extensions-v2",
        "version": "2.0.0",
        "endpoints": {
            "quiz_responses": 3,
            "quiz_alerts": 5,
            "monthly_quiz": 13,
            "public_quiz": 3,
        },
        "features": {
            "cursor_pagination": True,
            "redis_caching": True,
            "rate_limiting": True,
            "rbac": True,
            "alert_rules": True,
            "public_access": True,
        },
    }
