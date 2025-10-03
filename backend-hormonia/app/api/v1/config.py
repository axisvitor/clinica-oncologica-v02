"""
Configuration endpoint for public frontend runtime settings.

Provides PUBLIC configuration values that frontend applications need
without exposing sensitive secrets. Uses VITE_* naming convention
for frontend environment variable compatibility.

SECURITY:
- This endpoint is PUBLIC and requires NO authentication
- Only safe, non-sensitive values are exposed
- ALL sensitive keys (SUPABASE_ANON_KEY, API keys, etc.) are EXCLUDED
- CORS headers are configured to allow frontend domains
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from app.config import settings
from app.utils.logging import get_logger
import os
import json

router = APIRouter()
logger = get_logger(__name__)


def get_railway_url(service_type: str = "backend") -> Optional[str]:
    """
    Get Railway public URL for a service.

    Args:
        service_type: Type of service (backend, frontend, quiz)

    Returns:
        Public URL or None if not in Railway environment
    """
    # Check for Railway-specific environment variables
    railway_public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    railway_static_url = os.getenv("RAILWAY_STATIC_URL")

    if railway_public_domain:
        # Use public domain if available
        url = railway_public_domain
        if not url.startswith("http"):
            url = f"https://{url}"
        return url
    elif railway_static_url:
        # Use static URL as fallback
        return railway_static_url

    return None


def build_api_urls() -> Dict[str, str]:
    """
    Build API URLs based on environment.

    Returns:
        Dictionary with API_URL, API_BASE_URL, and WS_BASE_URL
    """
    # Priority 1: Explicit FRONTEND_API_URL from environment
    api_url = os.getenv("FRONTEND_API_URL")

    if not api_url:
        # Priority 2: Railway environment
        railway_url = get_railway_url("backend")
        if railway_url:
            api_url = railway_url
        else:
            # Priority 3: Build based on environment setting
            if settings.ENVIRONMENT == "production":
                # Production: Use Railway domain or fallback
                api_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://backend-production.railway.app")
                if not api_url.startswith("http"):
                    api_url = f"https://{api_url}"
            else:
                # Development: Use localhost
                port = os.getenv("PORT", "8000")
                api_url = f"http://localhost:{port}"

    # Build derivative URLs
    api_base_url = f"{api_url}/api/v1"
    ws_base_url = api_url.replace("https://", "wss://").replace("http://", "ws://") + "/ws"

    return {
        "API_URL": api_url,
        "API_BASE_URL": api_base_url,
        "WS_BASE_URL": ws_base_url
    }


def get_allowed_origins() -> list:
    """
    Get allowed CORS origins dynamically.

    Returns:
        List of allowed origin URLs
    """
    # Start with configured origins
    configured_origins = settings.ALLOWED_ORIGINS
    if isinstance(configured_origins, str):
        try:
            configured_origins = json.loads(configured_origins)
        except json.JSONDecodeError:
            configured_origins = [origin.strip() for origin in configured_origins.split(",")]

    # Add Railway-specific origins if in Railway environment
    railway_origins = []

    # Add frontend Railway URLs
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url and frontend_url not in configured_origins:
        railway_origins.append(frontend_url)

    # Add quiz Railway URLs
    quiz_url = os.getenv("QUIZ_URL")
    if quiz_url and quiz_url not in configured_origins:
        railway_origins.append(quiz_url)

    # Combine all origins
    all_origins = list(configured_origins) + railway_origins

    return all_origins


def get_firebase_public_config() -> Dict[str, Any]:
    """
    Get Firebase public configuration (if needed by frontend).

    Returns:
        Dictionary with public Firebase settings
    """
    # Only return PUBLIC Firebase settings
    # NEVER return private keys or service account credentials
    firebase_config = {}

    # Check for Firebase web app config (public)
    firebase_api_key = os.getenv("FIREBASE_WEB_API_KEY")  # Public web API key
    firebase_project_id = os.getenv("FIREBASE_WEB_PROJECT_ID")
    firebase_app_id = os.getenv("FIREBASE_WEB_APP_ID")

    if firebase_api_key:
        firebase_config["VITE_FIREBASE_API_KEY"] = firebase_api_key
    if firebase_project_id:
        firebase_config["VITE_FIREBASE_PROJECT_ID"] = firebase_project_id
    if firebase_app_id:
        firebase_config["VITE_FIREBASE_APP_ID"] = firebase_app_id

    # Add other public Firebase settings
    firebase_auth_domain = os.getenv("FIREBASE_AUTH_DOMAIN")
    if firebase_auth_domain:
        firebase_config["VITE_FIREBASE_AUTH_DOMAIN"] = firebase_auth_domain

    return firebase_config


@router.get("/config", response_model=Dict[str, Any])
async def get_public_config(request: Request) -> JSONResponse:
    """
    Get PUBLIC configuration for frontend applications.

    Returns configuration values that are SAFE to expose publicly:
    - API URLs in VITE_* format for frontend compatibility
    - WebSocket URLs
    - Public feature flags
    - Environment indicators
    - Localization settings
    - Public Firebase config (if configured)

    SECURITY NOTES:
    - This endpoint is PUBLIC and requires NO authentication
    - Only non-sensitive settings are exposed
    - Sensitive keys are NEVER included:
      - SUPABASE_ANON_KEY (removed for security)
      - SUPABASE_SERVICE_ROLE_KEY (server-only)
      - API keys and secrets
      - Database credentials
      - Private Firebase keys

    Returns:
        JSONResponse: Public configuration with CORS headers
    """
    try:
        # Build API URLs
        urls = build_api_urls()

        # Get Firebase config (if available)
        firebase_config = get_firebase_public_config()

        # Get allowed origins for CORS info
        allowed_origins = get_allowed_origins()

        # Build public configuration response
        config = {
            # API URLs (VITE_ format for frontend env variables)
            "VITE_API_BASE_URL": urls["API_BASE_URL"],
            "VITE_WS_BASE_URL": urls["WS_BASE_URL"],
            "VITE_API_URL": urls["API_URL"],

            # Legacy format for backward compatibility (during transition)
            "API_URL": urls["API_URL"],
            "API_BASE_URL": urls["API_BASE_URL"],
            "WS_BASE_URL": urls["WS_BASE_URL"],

            # Environment information (safe to expose)
            "VITE_ENVIRONMENT": settings.ENVIRONMENT,
            "ENVIRONMENT": settings.ENVIRONMENT,  # Legacy

            # Localization settings (public)
            "VITE_DEFAULT_LOCALE": settings.DEFAULT_LOCALE,
            "VITE_SUPPORTED_LOCALES": settings.SUPPORTED_LOCALES,
            "DEFAULT_LOCALE": settings.DEFAULT_LOCALE,  # Legacy
            "SUPPORTED_LOCALES": settings.SUPPORTED_LOCALES,  # Legacy

            # Feature flags (public, safe to expose)
            "features": {
                "enableRealtime": True,  # WebSocket support enabled
                "enableAnalytics": settings.MONITORING_ENABLED,
                "enableEvolution": getattr(settings, "ENABLE_EVOLUTION", False),
                "enableMonthlyQuizViaLink": getattr(settings, "MONTHLY_QUIZ_VIA_LINK", True),
                "enableAIHumanization": getattr(settings, "AI_HUMANIZATION_ENABLED", True),
            },

            # CORS information (helpful for debugging)
            "cors": {
                "allowedOrigins": allowed_origins,
                "credentials": True
            }
        }

        # Add Firebase config if available
        if firebase_config:
            config.update(firebase_config)

        # Add monthly quiz URL if configured
        if hasattr(settings, "MONTHLY_QUIZ_BASE_URL"):
            monthly_quiz_url = os.getenv("QUIZ_URL") or settings.MONTHLY_QUIZ_BASE_URL
            config["VITE_MONTHLY_QUIZ_URL"] = monthly_quiz_url
            config["MONTHLY_QUIZ_BASE_URL"] = monthly_quiz_url  # Legacy

        # Log configuration request for monitoring
        logger.info(
            f"Public config requested from {request.client.host if request.client else 'unknown'}",
            extra={
                "endpoint": "/config",
                "environment": settings.ENVIRONMENT,
                "origin": request.headers.get("origin", "none")
            }
        )

        # Return with CORS headers for frontend access
        return JSONResponse(
            content=config,
            headers={
                "Access-Control-Allow-Origin": "*",  # Public endpoint
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
            }
        )

    except Exception as e:
        logger.error(f"Error building public config: {e}", exc_info=True)

        # Return minimal fallback config
        fallback_config = {
            "VITE_API_BASE_URL": "http://localhost:8000/api/v1",
            "VITE_WS_BASE_URL": "ws://localhost:8000/ws",
            "VITE_API_URL": "http://localhost:8000",
            "VITE_ENVIRONMENT": "development",
            "error": "Failed to build complete config, using fallback",
            "features": {
                "enableRealtime": False,
                "enableAnalytics": False
            }
        }

        return JSONResponse(
            content=fallback_config,
            status_code=200,  # Still return 200 to not break frontend
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )


@router.options("/config")
async def config_options():
    """
    Handle CORS preflight requests for /config endpoint.

    Returns:
        Response with CORS headers
    """
    return JSONResponse(
        content={"status": "ok"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",  # Cache preflight for 1 hour
        }
    )
