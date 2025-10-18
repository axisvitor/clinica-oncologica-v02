"""
Rate Limiting Configuration for different endpoints and tiers.

CRITICAL FIX #4: Centralized rate limit configuration with tier-based limits.

This module provides:
1. Per-endpoint rate limit configurations
2. Tier-based limits (public, authenticated, admin)
3. Special limits for sensitive operations
4. Whitelist management
5. Priority routing configuration

Usage:
    from app.core.rate_limit_config import get_rate_limit_config, RateLimitEndpoint

    config = get_rate_limit_config(RateLimitEndpoint.API_PATIENTS)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from app.middleware.distributed_rate_limiter import RateLimitTier, RateLimitConfig


class RateLimitEndpoint(str, Enum):
    """Rate limit endpoint identifiers."""

    # Public endpoints
    HEALTH = "health"
    DOCS = "docs"

    # Authentication endpoints (more restrictive)
    AUTH_LOGIN = "auth_login"
    AUTH_REGISTER = "auth_register"
    AUTH_PASSWORD_RESET = "auth_password_reset"

    # API endpoints - General
    API_GENERAL = "api_general"

    # API endpoints - Patient management
    API_PATIENTS = "api_patients"
    API_PATIENT_CREATE = "api_patient_create"
    API_PATIENT_UPDATE = "api_patient_update"
    API_PATIENT_DELETE = "api_patient_delete"

    # API endpoints - Messages
    API_MESSAGES = "api_messages"
    API_MESSAGE_SEND = "api_message_send"

    # API endpoints - Quiz
    API_QUIZ_SUBMIT = "api_quiz_submit"
    API_QUIZ_TEMPLATES = "api_quiz_templates"

    # API endpoints - Reports
    API_REPORTS = "api_reports"
    API_REPORT_GENERATE = "api_report_generate"

    # Webhook endpoints (external integrations)
    WEBHOOK_EVOLUTION = "webhook_evolution"

    # Admin endpoints
    ADMIN_GENERAL = "admin_general"
    ADMIN_USERS = "admin_users"
    ADMIN_ANALYTICS = "admin_analytics"


@dataclass
class EndpointRateLimitConfig:
    """Complete rate limit configuration for an endpoint."""

    endpoint: RateLimitEndpoint
    public: RateLimitConfig
    authenticated: RateLimitConfig
    premium: RateLimitConfig
    admin: RateLimitConfig
    description: str = ""
    require_authentication: bool = False


# ============================================================================
# RATE LIMIT CONFIGURATIONS BY ENDPOINT
# ============================================================================

# Authentication Endpoints (Restrictive - Prevent Brute Force)
AUTH_LOGIN_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.AUTH_LOGIN,
    public=RateLimitConfig(
        requests=5,  # 5 attempts per minute
        window=60,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=10,  # Already authenticated, allow more
        window=60,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=20,
        window=60,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=100,
        window=60,
        tier=RateLimitTier.ADMIN,
    ),
    description="Login endpoint - restrictive to prevent brute force",
    require_authentication=False,
)

AUTH_REGISTER_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.AUTH_REGISTER,
    public=RateLimitConfig(
        requests=3,  # 3 registrations per hour
        window=3600,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=5,
        window=3600,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=10,
        window=3600,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=1000,  # Admin can register many users
        window=3600,
        tier=RateLimitTier.ADMIN,
    ),
    description="Registration endpoint - prevent spam accounts",
    require_authentication=False,
)

AUTH_PASSWORD_RESET_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.AUTH_PASSWORD_RESET,
    public=RateLimitConfig(
        requests=3,  # 3 resets per hour
        window=3600,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=5,
        window=3600,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=10,
        window=3600,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=100,
        window=3600,
        tier=RateLimitTier.ADMIN,
    ),
    description="Password reset endpoint - prevent abuse",
    require_authentication=False,
)

# Patient Management Endpoints
API_PATIENTS_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.API_PATIENTS,
    public=RateLimitConfig(
        requests=0,  # No public access
        window=60,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=300,  # 300 requests per minute
        window=60,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=1000,
        window=60,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=10000,
        window=60,
        tier=RateLimitTier.ADMIN,
    ),
    description="Patient list/read endpoints",
    require_authentication=True,
)

API_PATIENT_CREATE_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.API_PATIENT_CREATE,
    public=RateLimitConfig(
        requests=0,
        window=60,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=60,  # 1 per second max
        window=60,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=300,
        window=60,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=1000,
        window=60,
        tier=RateLimitTier.ADMIN,
    ),
    description="Patient creation endpoint - moderate limit",
    require_authentication=True,
)

# Message Endpoints
API_MESSAGE_SEND_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.API_MESSAGE_SEND,
    public=RateLimitConfig(
        requests=0,
        window=60,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=100,  # 100 messages per minute
        window=60,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=500,
        window=60,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=5000,
        window=60,
        tier=RateLimitTier.ADMIN,
    ),
    description="Message send endpoint - protect WhatsApp API quota",
    require_authentication=True,
)

# Quiz Endpoints
API_QUIZ_SUBMIT_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.API_QUIZ_SUBMIT,
    public=RateLimitConfig(
        requests=10,  # Allow some public submissions (with token validation)
        window=3600,  # Per hour
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=30,
        window=3600,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=100,
        window=3600,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=1000,
        window=3600,
        tier=RateLimitTier.ADMIN,
    ),
    description="Quiz submission endpoint - prevent spam",
    require_authentication=False,
)

# Report Generation Endpoints (Expensive operations)
API_REPORT_GENERATE_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.API_REPORT_GENERATE,
    public=RateLimitConfig(
        requests=0,
        window=60,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=10,  # Report generation is expensive
        window=60,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=50,
        window=60,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=500,
        window=60,
        tier=RateLimitTier.ADMIN,
    ),
    description="Report generation endpoint - expensive operation",
    require_authentication=True,
)

# Webhook Endpoints (External systems)
WEBHOOK_EVOLUTION_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.WEBHOOK_EVOLUTION,
    public=RateLimitConfig(
        requests=1000,  # Evolution API can send many webhooks
        window=60,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=1000,
        window=60,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=1000,
        window=60,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=10000,
        window=60,
        tier=RateLimitTier.ADMIN,
    ),
    description="Evolution API webhooks - high volume expected",
    require_authentication=False,  # Uses HMAC validation instead
)

# Admin Endpoints
ADMIN_GENERAL_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.ADMIN_GENERAL,
    public=RateLimitConfig(
        requests=0,
        window=60,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=0,  # Non-admin users blocked
        window=60,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=0,
        window=60,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=1000,  # Admin gets high limit
        window=60,
        tier=RateLimitTier.ADMIN,
    ),
    description="Admin endpoints - admin only",
    require_authentication=True,
)

# Default API configuration (fallback)
API_GENERAL_CONFIG = EndpointRateLimitConfig(
    endpoint=RateLimitEndpoint.API_GENERAL,
    public=RateLimitConfig(
        requests=60,  # 1 per second
        window=60,
        tier=RateLimitTier.PUBLIC,
    ),
    authenticated=RateLimitConfig(
        requests=300,  # 5 per second
        window=60,
        tier=RateLimitTier.AUTHENTICATED,
    ),
    premium=RateLimitConfig(
        requests=1000,
        window=60,
        tier=RateLimitTier.PREMIUM,
    ),
    admin=RateLimitConfig(
        requests=10000,
        window=60,
        tier=RateLimitTier.ADMIN,
    ),
    description="General API endpoints - default configuration",
    require_authentication=False,
)


# ============================================================================
# CONFIGURATION REGISTRY
# ============================================================================

RATE_LIMIT_CONFIGS: Dict[RateLimitEndpoint, EndpointRateLimitConfig] = {
    # Authentication
    RateLimitEndpoint.AUTH_LOGIN: AUTH_LOGIN_CONFIG,
    RateLimitEndpoint.AUTH_REGISTER: AUTH_REGISTER_CONFIG,
    RateLimitEndpoint.AUTH_PASSWORD_RESET: AUTH_PASSWORD_RESET_CONFIG,
    # Patients
    RateLimitEndpoint.API_PATIENTS: API_PATIENTS_CONFIG,
    RateLimitEndpoint.API_PATIENT_CREATE: API_PATIENT_CREATE_CONFIG,
    # Messages
    RateLimitEndpoint.API_MESSAGE_SEND: API_MESSAGE_SEND_CONFIG,
    # Quiz
    RateLimitEndpoint.API_QUIZ_SUBMIT: API_QUIZ_SUBMIT_CONFIG,
    # Reports
    RateLimitEndpoint.API_REPORT_GENERATE: API_REPORT_GENERATE_CONFIG,
    # Webhooks
    RateLimitEndpoint.WEBHOOK_EVOLUTION: WEBHOOK_EVOLUTION_CONFIG,
    # Admin
    RateLimitEndpoint.ADMIN_GENERAL: ADMIN_GENERAL_CONFIG,
    # General (default)
    RateLimitEndpoint.API_GENERAL: API_GENERAL_CONFIG,
}


# ============================================================================
# WHITELIST CONFIGURATION
# ============================================================================

# IPs exempt from rate limiting (monitoring, trusted services)
RATE_LIMIT_WHITELIST_IPS: List[str] = [
    "127.0.0.1",  # Localhost
    "::1",  # Localhost IPv6
    # Add trusted IPs here (e.g., monitoring services, CI/CD)
    # "192.168.1.100",
    # "10.0.0.50",
]

# Paths exempt from rate limiting
RATE_LIMIT_EXEMPT_PATHS: List[str] = [
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_rate_limit_config(
    endpoint: RateLimitEndpoint,
    tier: RateLimitTier = RateLimitTier.PUBLIC,
) -> RateLimitConfig:
    """
    Get rate limit configuration for endpoint and tier.

    Args:
        endpoint: Endpoint identifier
        tier: User tier

    Returns:
        RateLimitConfig for the specified endpoint and tier
    """
    endpoint_config = RATE_LIMIT_CONFIGS.get(
        endpoint, RATE_LIMIT_CONFIGS[RateLimitEndpoint.API_GENERAL]
    )

    if tier == RateLimitTier.ADMIN:
        return endpoint_config.admin
    elif tier == RateLimitTier.PREMIUM:
        return endpoint_config.premium
    elif tier == RateLimitTier.AUTHENTICATED:
        return endpoint_config.authenticated
    else:
        return endpoint_config.public


def get_endpoint_config(endpoint: RateLimitEndpoint) -> EndpointRateLimitConfig:
    """
    Get complete endpoint configuration.

    Args:
        endpoint: Endpoint identifier

    Returns:
        Complete EndpointRateLimitConfig
    """
    return RATE_LIMIT_CONFIGS.get(
        endpoint, RATE_LIMIT_CONFIGS[RateLimitEndpoint.API_GENERAL]
    )


def is_path_exempt(path: str) -> bool:
    """
    Check if path is exempt from rate limiting.

    Args:
        path: Request path

    Returns:
        True if exempt, False otherwise
    """
    return any(path.startswith(exempt_path) for exempt_path in RATE_LIMIT_EXEMPT_PATHS)


def is_ip_whitelisted(ip: str) -> bool:
    """
    Check if IP is whitelisted (exempt from rate limiting).

    Args:
        ip: IP address

    Returns:
        True if whitelisted, False otherwise
    """
    return ip in RATE_LIMIT_WHITELIST_IPS


def get_all_endpoint_configs() -> Dict[RateLimitEndpoint, EndpointRateLimitConfig]:
    """
    Get all rate limit configurations.

    Returns:
        Dictionary of all endpoint configurations
    """
    return RATE_LIMIT_CONFIGS.copy()


def validate_rate_limit_config(config: EndpointRateLimitConfig) -> List[str]:
    """
    Validate rate limit configuration for common issues.

    Args:
        config: Configuration to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check that limits increase with tier
    if config.authenticated.requests < config.public.requests:
        errors.append(
            f"{config.endpoint}: Authenticated limit should be >= public limit"
        )

    if config.premium.requests < config.authenticated.requests:
        errors.append(
            f"{config.endpoint}: Premium limit should be >= authenticated limit"
        )

    if config.admin.requests < config.premium.requests:
        errors.append(f"{config.endpoint}: Admin limit should be >= premium limit")

    # Check for reasonable limits
    if config.public.requests > 10000:
        errors.append(f"{config.endpoint}: Public limit seems too high (> 10000)")

    # Check window sizes
    for tier_config in [
        config.public,
        config.authenticated,
        config.premium,
        config.admin,
    ]:
        if tier_config.window < 1:
            errors.append(f"{config.endpoint}: Window must be >= 1 second")
        if tier_config.window > 3600:
            errors.append(f"{config.endpoint}: Window > 1 hour may not be practical")

    return errors


# Validate all configurations on import
def _validate_all_configs():
    """Validate all rate limit configurations."""
    all_errors = []
    for endpoint, config in RATE_LIMIT_CONFIGS.items():
        errors = validate_rate_limit_config(config)
        if errors:
            all_errors.extend(errors)

    if all_errors:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Rate limit configuration validation warnings:\n" + "\n".join(all_errors)
        )


# Run validation on module import
_validate_all_configs()


# Export public API
__all__ = [
    "RateLimitEndpoint",
    "EndpointRateLimitConfig",
    "get_rate_limit_config",
    "get_endpoint_config",
    "is_path_exempt",
    "is_ip_whitelisted",
    "get_all_endpoint_configs",
    "validate_rate_limit_config",
    "RATE_LIMIT_CONFIGS",
    "RATE_LIMIT_WHITELIST_IPS",
    "RATE_LIMIT_EXEMPT_PATHS",
]
