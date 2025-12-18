"""
System Configuration API Endpoints.

PUBLIC configuration endpoint for frontend applications.
No authentication required - exposes only safe, non-sensitive configuration.
"""

import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.schemas.v2.system import PublicConfigResponse
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger
from app.config import settings

from .helpers.config_builder import build_api_urls, get_firebase_public_config
from .helpers.redis_helper import get_redis_client

router = APIRouter()
logger = get_logger(__name__)

# Redis cache TTL for config endpoint
CACHE_TTL_CONFIG = 1800  # 30 minutes (public, rarely changes)


@router.get(
    "/config",
    response_model=PublicConfigResponse,
    summary="Get public configuration",
    description="""
    Get PUBLIC configuration for frontend applications.

    **SECURITY NOTES:**
    - This endpoint is PUBLIC and requires NO authentication
    - Only non-sensitive settings are exposed
    - Environment variables are filtered to safe whitelist (VITE_*, PUBLIC_*, RAILWAY_PUBLIC_*)
    - NEVER exposes: DATABASE_URL, SECRET_KEY, API keys, credentials

    **Caching:** 30 minutes (rarely changes)
    **Rate limit:** 100 requests/minute (generous for public endpoint)
    """,
)
@limiter.limit("100/minute")
async def get_public_config(request: Request) -> JSONResponse:
    """
    Get PUBLIC configuration for frontend applications.

    Returns ONLY safe, non-sensitive configuration values:
    - API URLs in VITE_* format
    - WebSocket URLs
    - Public feature flags
    - Environment indicators
    - Localization settings
    - Public Firebase config (web app keys only)

    This endpoint uses aggressive caching (30min) and CORS headers
    to allow frontend applications to fetch configuration at startup.
    """
    cache_key = "system:public_config"

    # Try Redis cache first
    redis = await get_redis_client()
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                logger.debug("Cache hit for public config")
                config_data = json.loads(cached)
                return JSONResponse(
                    content=config_data,
                    headers={
                        "Access-Control-Allow-Origin": "*",  # Public endpoint
                        "Access-Control-Allow-Methods": "GET, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type",
                        "Cache-Control": f"public, max-age={CACHE_TTL_CONFIG}",
                        "X-Cache-Status": "HIT",
                    },
                )
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    # Cache miss - build configuration
    try:
        urls = build_api_urls()
        firebase_config = get_firebase_public_config()

        # Build configuration response
        config = {
            # API URLs (VITE_ format for frontend)
            "VITE_API_BASE_URL": urls["API_BASE_URL"],
            "VITE_WS_BASE_URL": urls["WS_BASE_URL"],
            "VITE_API_URL": urls["API_URL"],
            # Environment
            "VITE_ENVIRONMENT": settings.APP_ENVIRONMENT,
            # Localization
            "VITE_DEFAULT_LOCALE": settings.DEFAULT_LOCALE,
            "VITE_SUPPORTED_LOCALES": settings.SUPPORTED_LOCALES,
            # Feature flags (PUBLIC ONLY)
            "features": {
                "enableRealtime": True,
                "enableAnalytics": settings.MONITORING_ENABLE_SERVICE,
                "enableEvolution": getattr(settings, "ENABLE_EVOLUTION", False),
                "enableMonthlyQuizViaLink": getattr(
                    settings, "MONTHLY_QUIZ_VIA_LINK", True
                ),
                "enableAIHumanization": getattr(
                    settings, "AI_HUMANIZATION_ENABLED", True
                ),
            },
            # CORS information
            "cors": {
                "allowedOrigins": settings.CORS_ALLOWED_ORIGINS
                if hasattr(settings, "ALLOWED_ORIGINS")
                else [],
                "credentials": True,
            },
        }

        # Add Firebase PUBLIC config if available
        config.update(firebase_config)

        # Add quiz URL if configured
        quiz_url = os.getenv("QUIZ_URL") or getattr(
            settings, "MONTHLY_QUIZ_BASE_URL", None
        )
        if quiz_url:
            config["VITE_MONTHLY_QUIZ_URL"] = quiz_url

        # Cache the result
        if redis:
            try:
                await redis.setex(
                    cache_key, CACHE_TTL_CONFIG, json.dumps(config, default=str)
                )
                logger.debug("Cached public config")
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # Log access for monitoring
        logger.info(
            f"Public config accessed from {request.client.host if request.client else 'unknown'}",
            extra={"endpoint": "/config", "environment": settings.APP_ENVIRONMENT},
        )

        return JSONResponse(
            content=config,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Cache-Control": f"public, max-age={CACHE_TTL_CONFIG}",
                "X-Cache-Status": "MISS",
            },
        )

    except Exception as e:
        logger.error(f"Error building public config: {e}", exc_info=True)

        # Return minimal fallback config
        fallback_config = {
            "VITE_API_BASE_URL": "http://localhost:8000/api/v2",
            "VITE_WS_BASE_URL": "ws://localhost:8000/ws",
            "VITE_API_URL": "http://localhost:8000",
            "VITE_ENVIRONMENT": "development",
            "VITE_DEFAULT_LOCALE": "pt-BR",
            "VITE_SUPPORTED_LOCALES": ["pt-BR", "en-US"],
            "features": {"enableRealtime": False, "enableAnalytics": False},
            "error": "Failed to build complete config",
        }

        return JSONResponse(
            content=fallback_config,
            status_code=200,  # Still 200 to not break frontend
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
        )


@router.options("/config")
async def config_options():
    """Handle CORS preflight requests for /config endpoint."""
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        },
    )
