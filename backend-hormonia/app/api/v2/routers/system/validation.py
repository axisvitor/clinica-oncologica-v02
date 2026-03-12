"""
Configuration Validation Module.

Provides configuration validation endpoint:
- POST /validate: Validate system configuration and security settings

Security: Admin role required.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request

from app.schemas.v2.system import (
    ConfigValidationRequest,
    ConfigValidationResponse,
)
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger
from app.config import settings
from app.utils.auth_helpers import is_admin as _is_admin
from app.utils.timezone import now_sao_paulo

router = APIRouter(tags=["system-validation"])
logger = get_logger(__name__)


# ============================================================================
# Configuration Validation Endpoint (ADMIN ONLY)
# ============================================================================


@router.post(
    "/validate",
    response_model=ConfigValidationResponse,
    summary="Validate configuration",
    description="""
    Validate system configuration and security settings.

    **Authentication:** Admin role required
    **Rate limit:** 10 requests/hour
    """,
)
@limiter.limit("10/hour")
async def validate_configuration(
    request: Request,
    validation_request: Optional[ConfigValidationRequest] = None,
    current_user=Depends(get_current_user_from_session),
):
    """
    Validate system configuration.

    Checks:
    - Critical settings (SECURITY_SECRET_KEY, DATABASE_URL)
    - Session-auth settings (cookies, CSRF, secure transport)
    - External service configurations
    - Production best practices
    """
    # Check admin privileges
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for configuration validation",
        )

    if validation_request is None:
        validation_request = ConfigValidationRequest()

    try:
        warnings = []
        errors = []
        recommendations = []

        # Validate critical settings
        if (
            not settings.SECURITY_SECRET_KEY
            or "CHANGE_THIS" in settings.SECURITY_SECRET_KEY.upper()
        ):
            errors.append("SECURITY_SECRET_KEY is not properly configured")

        if not settings.DATABASE_URL:
            errors.append("DATABASE_URL is not configured")

        if not settings.SESSION_COOKIE_NAME:
            errors.append("SESSION_COOKIE_NAME is not configured")

        # Check session-first auth diagnostics
        if not getattr(settings, "SESSION_ENABLE_COOKIE_HTTPONLY", True):
            warnings.append(
                "SESSION_ENABLE_COOKIE_HTTPONLY should remain enabled for session-based auth"
            )
            recommendations.append(
                "Enable SESSION_ENABLE_COOKIE_HTTPONLY to protect session cookies from script access"
            )

        if not getattr(settings, "SECURITY_CSRF_SECRET_KEY", None):
            warnings.append(
                "SECURITY_CSRF_SECRET_KEY is not configured for session-based auth"
            )
            recommendations.append(
                "Configure SECURITY_CSRF_SECRET_KEY so CSRF protection remains enabled for session auth"
            )

        # Check production security settings
        if settings.APP_ENVIRONMENT.lower() == "production":
            if settings.APP_ENABLE_DEBUG:
                errors.append("DEBUG should be False in production")

            if not getattr(settings, "SESSION_ENABLE_COOKIE_SECURE", False):
                warnings.append("SESSION_ENABLE_COOKIE_SECURE should be True in production")
                recommendations.append("Enable secure cookies for production")

            if not getattr(settings, "SECURITY_ENABLE_SSL_REDIRECT", False):
                warnings.append("SECURITY_ENABLE_SSL_REDIRECT should be True in production")
                recommendations.append("Enable HTTPS redirect for production")

        # Check CORS configuration
        if not getattr(settings, "CORS_ALLOWED_ORIGINS", None) and not settings.CORS_FRONTEND_URL:
            warnings.append("CORS origins not configured")
            recommendations.append("Configure allowed CORS origins")

        # Check external service configurations
        if settings.WHATSAPP_ENABLE_SERVICE and not getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None):
            warnings.append("WhatsApp service is enabled but WHATSAPP_WUZAPI_TOKEN not configured")

        if settings.AI_ENABLE_HUMANIZATION and not settings.AI_GEMINI_API_KEY:
            warnings.append(
                "AI humanization is enabled but Gemini API key not configured"
            )

        # Check rate limiting
        if (
            not settings.RATE_LIMIT_ENABLE_SERVICE
            and settings.APP_ENVIRONMENT == "production"
        ):
            warnings.append("Rate limiting is disabled in production")
            recommendations.append("Enable rate limiting for production security")

        categories_checked = validation_request.categories or [
            "security",
            "session_auth",
            "database",
            "external_services",
        ]

        return ConfigValidationResponse(
            valid=len(errors) == 0,
            warnings=warnings,
            errors=errors,
            checked_at=now_sao_paulo(),
            categories_checked=categories_checked,
            recommendations=recommendations,
        )

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration validation failed",
        )
