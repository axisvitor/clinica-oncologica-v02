"""
CORS Configuration Module - Network Barrier with Fail-Fast Validation

Modern security implementation with strict validation at application startup.
All CORS origins MUST come from environment variables via settings.get_cors_origins().

Security Principles:
1. Fail fast: Validate configuration on startup, not at runtime
2. Zero runtime overhead: No in-memory structures or rate limiting
3. Clear error messages: Help developers fix issues immediately
4. Environment-driven: All configuration from settings, never hardcoded

Architecture:
- settings/security.py: Single source of truth for CORS origins (parses env vars)
- core/cors.py: Startup validation and middleware configuration

Production Security Rules:
1. NO regex patterns in production
2. NO wildcard (*) origins in production
3. All origins must be HTTPS in production
4. Origins validated at startup (fail fast)
"""

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from typing import List, Optional
import logging

from app.config.settings import settings

logger = logging.getLogger(__name__)


def is_production() -> bool:
    """
    Check if running in production environment.

    Returns:
        bool: True if production mode
    """
    return settings.APP_ENVIRONMENT.lower() in ["production", "prod"]


def validate_cors_configuration(
    allow_origins: List[str],
    allow_origin_regex: Optional[str] = None
) -> None:
    """
    Validate CORS configuration for production safety at application startup.

    This function implements the "fail fast" strategy: it validates the CORS
    configuration when the application starts, not at request time. This ensures
    that misconfigurations are caught immediately with clear error messages.

    Security Rules (Production Only):
    1. NO regex patterns (too permissive, hard to audit)
    2. NO wildcard (*) origins (allows any origin)
    3. All origins must be HTTPS (prevent MITM attacks)
    4. At least one origin must be configured

    Development Mode:
    - All validation is skipped to allow flexible local development
    - Localhost HTTP origins are permitted

    Args:
        allow_origins: List of allowed origin URLs
        allow_origin_regex: Optional regex pattern for origins

    Raises:
        ValueError: If configuration violates production security rules
            with detailed error message explaining how to fix
    """
    if not is_production():
        # Development mode - skip all validation for flexibility
        logger.info(
            "CORS validation skipped in development mode",
            extra={
                "environment": settings.APP_ENVIRONMENT,
                "origins_count": len(allow_origins),
            }
        )
        return

    # Production validation starts here
    errors = []

    # Rule 1: No regex in production (too permissive, hard to audit)
    if allow_origin_regex:
        errors.append(
            "CORS origin regex patterns are not allowed in production.\n"
            "  Reason: Regex patterns are difficult to audit and can be too permissive.\n"
            "  Fix: Use explicit origin URLs in CORS_ALLOWED_ORIGINS environment variable.\n"
            "  Example: CORS_ALLOWED_ORIGINS=['https://app.example.com','https://admin.example.com']"
        )

    # Rule 2: No wildcard origins in production (allows any origin)
    if "*" in allow_origins:
        errors.append(
            "CORS wildcard origin (*) is not allowed in production.\n"
            "  Reason: Wildcard allows ANY origin to access your API, defeating CORS security.\n"
            "  Fix: Specify explicit origin URLs in CORS_ALLOWED_ORIGINS.\n"
            "  Example: CORS_ALLOWED_ORIGINS=['https://app.example.com']"
        )

    # Rule 3: At least one origin must be configured in production
    if not allow_origins:
        errors.append(
            "No CORS origins configured for production.\n"
            "  Reason: Production requires explicit CORS configuration for security.\n"
            "  Fix: Set one or more of these environment variables:\n"
            "    - CORS_ALLOWED_ORIGINS: List of allowed origins (JSON array or comma-separated)\n"
            "    - CORS_FRONTEND_URL: Primary frontend application URL\n"
            "    - CORS_QUIZ_URL: Quiz interface URL\n"
            "  Example: CORS_FRONTEND_URL='https://app.example.com'"
        )

    # Rule 4: All origins must be HTTPS in production (prevent MITM)
    non_https_origins = [
        origin for origin in allow_origins
        if not origin.startswith("https://")
    ]

    if non_https_origins:
        errors.append(
            f"CORS origins must use HTTPS in production (found {len(non_https_origins)} HTTP origins):\n"
            + "\n".join(f"  - {origin}" for origin in non_https_origins) + "\n"
            "  Reason: HTTP is vulnerable to man-in-the-middle attacks.\n"
            "  Fix: Update environment variables to use https:// protocol.\n"
            "  Example: CORS_FRONTEND_URL='https://app.example.com' (not http://)"
        )

    # If any validation errors, raise with detailed message
    if errors:
        error_message = (
            "\n" + "=" * 80 + "\n"
            "❌ CORS CONFIGURATION VALIDATION FAILED\n"
            "=" * 80 + "\n\n"
            "The following CORS security issues must be fixed before starting in production:\n\n"
            + "\n\n".join(f"{i}. {error}" for i, error in enumerate(errors, 1)) + "\n\n"
            + "=" * 80 + "\n"
            f"Environment: {settings.APP_ENVIRONMENT}\n"
            f"Configured Origins: {allow_origins}\n"
            "=" * 80 + "\n"
        )

        logger.error(
            "CORS validation failed",
            extra={
                "environment": settings.APP_ENVIRONMENT,
                "errors": errors,
                "origins": allow_origins,
                "regex": allow_origin_regex,
            }
        )

        raise ValueError(error_message)

    # Validation passed - log success
    logger.info(
        "✅ CORS configuration validated successfully",
        extra={
            "environment": settings.APP_ENVIRONMENT,
            "origins_count": len(allow_origins),
            "all_https": all(o.startswith("https://") for o in allow_origins),
        }
    )


def configure_cors(
    app: FastAPI,
    allowed_origin_regex: Optional[str] = None,
    allow_credentials: bool = True,
    allow_methods: Optional[List[str]] = None,
    allow_headers: Optional[List[str]] = None,
) -> None:
    """
    Configure CORS middleware with fail-fast production security validation.

    This function follows the "fail fast" principle: configuration errors are
    detected at application startup, not at runtime. This ensures that production
    deployments with invalid CORS settings never reach the running state.

    Configuration Source:
    - ALL origins come from settings.get_cors_origins() (environment variables)
    - NEVER pass origins manually - configure via environment instead
    - Settings module handles all parsing, normalization, and protocol addition

    Production Security:
    - Origins must be explicit HTTPS URLs (validated at startup)
    - No wildcards, no regex patterns (validated at startup)
    - Credentials enabled for httpOnly cookies
    - Explicit header whitelist (NEVER "*" with credentials)

    Development Defaults:
    - Origins from environment or localhost fallbacks
    - More permissive configuration for local testing
    - HTTP allowed for localhost

    Security Note:
    Using allow_headers=["*"] with allow_credentials=True is a critical
    vulnerability that exposes all request headers (Authorization, cookies)
    to cross-origin requests. Always use explicit header whitelists.

    Args:
        app: FastAPI application instance
        allowed_origin_regex: Regex pattern for origins (forbidden in production)
        allow_credentials: Allow credentials (cookies, authorization headers)
        allow_methods: Allowed HTTP methods (defaults to common REST methods)
        allow_headers: Allowed request headers (explicit list required for security)

    Raises:
        ValueError: If production security rules violated (fail fast on startup)

    Example:
        # In main.py startup
        configure_cors(app)  # Origins auto-loaded from environment
    """
    # Get origins from settings (single source of truth)
    # Settings module handles:
    # - Parsing env vars (CORS_ALLOWED_ORIGINS, CORS_FRONTEND_URL, CORS_QUIZ_URL)
    # - Removing quotes and whitespace
    # - Auto-adding https:// prefix in production
    # - Normalizing URLs (removing trailing slashes)
    allowed_origins = settings.get_cors_origins()

    # Development fallback: Use localhost if no origins configured
    # This allows local development without environment configuration
    if not allowed_origins and not is_production():
        allowed_origins = [
            "http://localhost:3000",   # Legacy frontend port
            "http://localhost:3001",   # Quiz Interface
            "http://localhost:5173",   # Frontend Hormonia Vite (current)
            "http://127.0.0.1:3000",   # IPv4 loopback variants
            "http://127.0.0.1:3001",
            "http://127.0.0.1:5173",
        ]
        logger.warning(
            "Using default localhost origins for development",
            extra={"origins": allowed_origins}
        )

    # FAIL FAST: Validate configuration at startup
    # This prevents production deployments with invalid CORS settings
    validate_cors_configuration(allowed_origins, allowed_origin_regex)

    # Default methods for RESTful APIs
    if allow_methods is None:
        allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]

    # Default headers - Explicit whitelist for security
    # CRITICAL SECURITY: Never use ["*"] with allow_credentials=True
    #
    # Why? The combination of allow_headers=["*"] and allow_credentials=True
    # creates a serious security vulnerability:
    # - Allows cross-origin requests to include ALL headers
    # - Exposes Authorization tokens, session cookies, API keys
    # - Violates principle of least privilege
    # - Makes CORS protection essentially useless
    #
    # Solution: Explicit whitelist of required headers only
    if allow_headers is None:
        allow_headers = [
            "Content-Type",        # Standard content negotiation
            "Authorization",       # Bearer tokens and basic auth
            "X-Requested-With",    # AJAX request detection
            "X-CSRF-Token",        # CSRF protection tokens
            "X-CSRFToken",         # Alternative CSRF header
            "X-XSRF-Token",        # Angular/Axios CSRF header
            "Accept",              # Content type acceptance
            "Origin",              # Request origin (required for CORS)
        ]

    # Add CORS middleware with validated configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=allowed_origin_regex,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
        expose_headers=[
            "content-type",     # Allow reading response content type
            "x-csrf-token",     # Expose CSRF tokens to JavaScript
            "x-total-count",    # Pagination metadata
            "x-page",           # Current page number
            "x-per-page",       # Items per page
        ],
        max_age=3600,  # Cache preflight requests for 1 hour (reduces OPTIONS requests)
    )

    # Log configuration for debugging and monitoring
    log_context = {
        "origins_count": len(allowed_origins),
        "environment": settings.APP_ENVIRONMENT,
        "allow_credentials": allow_credentials,
        "allowed_origins": allowed_origins,  # Full list for debugging
    }

    if is_production():
        # Production logging with extra detail for security monitoring
        logger.info("CORS configured for PRODUCTION", extra=log_context)

        # Also print to stdout for easier debugging in production logs
        # (Some deployment platforms don't capture structured logs well)
        print(f"[CORS] Production environment - {len(allowed_origins)} origins configured")
        print(f"[CORS] Origins: {allowed_origins}")
        print(f"[CORS] All HTTPS: {all(o.startswith('https://') for o in allowed_origins)}")
        print(f"[CORS] Credentials: {allow_credentials}")
    else:
        # Development logging - warning level to make it visible
        logger.warning("CORS configured for DEVELOPMENT", extra=log_context)
        print(f"[CORS] Development environment - {len(allowed_origins)} origins")
        print(f"[CORS] Origins: {allowed_origins}")
