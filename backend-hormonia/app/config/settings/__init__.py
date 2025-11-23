"""
Main Settings module that combines all configuration modules.
This provides backward compatibility with the monolithic config.py while using modular architecture.
"""

from typing import Any, List
from pydantic import model_validator
import json

from .base import BaseAppSettings
from .database import DatabaseSettings
from .security import SecuritySettings
from .integrations import IntegrationsSettings
from .features import FeaturesSettings
from .monitoring import MonitoringSettings


class Settings(
    DatabaseSettings,
    SecuritySettings,
    IntegrationsSettings,
    FeaturesSettings,
    MonitoringSettings,
):
    """
    Main application settings combining all configuration modules.

    This class inherits from all specialized settings modules:
    - DatabaseSettings: PostgreSQL and Redis configuration
    - SecuritySettings: JWT, Firebase, CSRF, CORS, rate limiting
    - IntegrationsSettings: Evolution API, Gemini AI, Celery
    - FeaturesSettings: Monthly quiz, flows, file uploads, localization
    - MonitoringSettings: Sentry, logging, APM, error tracking

    Multiple inheritance is used to combine all settings into a single class
    while maintaining modular organization.
    """

    @model_validator(mode="before")
    @classmethod
    def parse_env_values(cls, data: Any) -> Any:
        """
        Parse all environment variable values before model validation (Pydantic v2 compatible).
        This consolidates parsing logic from all parent classes.
        """
        # Parse boolean fields from string
        boolean_fields = [
            "DEBUG",
            "SESSION_COOKIE_SECURE",
            "SECURE_SSL_REDIRECT",
            "FIREBASE_REQUIRE_CUSTOM_CLAIMS",
            "FIREBASE_ENABLE_AUDIT_LOGGING",
            "FIREBASE_BLOCK_PUBLIC_DOMAINS",
            "RATE_LIMIT_ENABLED",
            "ENABLE_EVOLUTION",
            "ENABLE_WHATSAPP_ON_REGISTRATION",
            "WHATSAPP_WELCOME_MESSAGE_ENABLED",
            "LANGCHAIN_TRACING_V2",
            "AI_HUMANIZATION_ENABLED",
            "AI_HUMANIZATION_SAFETY_MODE",
            "AI_HUMANIZATION_FALLBACK_ENABLED",
            "CELERY_ENABLE_UTC",
            "CELERY_TASK_TRACK_STARTED",
            "CELERY_WORKER_DISABLE_RATE_LIMITS",
            "MONTHLY_QUIZ_VIA_LINK",
            "ENABLE_AUTO_FLOW_ENROLLMENT",
            "AUTO_FLOW_ENROLLMENT_FALLBACK",
            "ENABLE_REQUEST_LOGGING",
            "LOG_STACK_TRACES",
            "ENABLE_ERROR_TRACKING",
            "CRITICAL_ERROR_NOTIFICATION",
            "MONITORING_ENABLED",
            "MONITORING_DEBUG",
            "REDIS_SSL",
            "REDIS_RETRY_ON_TIMEOUT",
            "REDIS_DECODE_RESPONSES",
            "REDIS_ENABLE_DB_ISOLATION",
        ]

        for field in boolean_fields:
            if field in data:
                v = data[field]
                if isinstance(v, bool):
                    data[field] = v
                elif isinstance(v, str):
                    data[field] = v.lower() not in ("false", "0", "no", "off", "")
                else:
                    data[field] = bool(v)

        # Parse FIREBASE_ALLOWED_DOMAINS from JSON string
        if "FIREBASE_ALLOWED_DOMAINS" in data:
            v = data["FIREBASE_ALLOWED_DOMAINS"]
            if v is None or v == "":
                data["FIREBASE_ALLOWED_DOMAINS"] = []
            elif isinstance(v, str):
                try:
                    data["FIREBASE_ALLOWED_DOMAINS"] = json.loads(v)
                except json.JSONDecodeError:
                    data["FIREBASE_ALLOWED_DOMAINS"] = []

        # Parse ALLOWED_ORIGINS
        if "ALLOWED_ORIGINS" in data:
            v = data["ALLOWED_ORIGINS"]
            if isinstance(v, list) and len(v) > 0:
                pass  # Already a list
            elif isinstance(v, str) and v.strip():
                s = v.strip()
                if s.startswith("["):
                    try:
                        data["ALLOWED_ORIGINS"] = json.loads(s)
                    except:
                        data["ALLOWED_ORIGINS"] = [
                            item.strip() for item in s.split(",") if item.strip()
                        ]
                else:
                    data["ALLOWED_ORIGINS"] = [
                        item.strip() for item in s.split(",") if item.strip()
                    ]
            else:
                data["ALLOWED_ORIGINS"] = []

        # Parse AI_HUMANIZATION_CRITICAL_KEYWORDS
        if "AI_HUMANIZATION_CRITICAL_KEYWORDS" in data:
            v = data["AI_HUMANIZATION_CRITICAL_KEYWORDS"]
            if isinstance(v, list):
                pass  # Already a list
            elif isinstance(v, str):
                s = v.strip()
                if s.startswith("["):
                    try:
                        arr = json.loads(s)
                        if isinstance(arr, list):
                            data["AI_HUMANIZATION_CRITICAL_KEYWORDS"] = arr
                        else:
                            data["AI_HUMANIZATION_CRITICAL_KEYWORDS"] = [
                                item.strip() for item in s.split(",") if item.strip()
                            ]
                    except Exception:
                        data["AI_HUMANIZATION_CRITICAL_KEYWORDS"] = [
                            item.strip() for item in s.split(",") if item.strip()
                        ]
                else:
                    data["AI_HUMANIZATION_CRITICAL_KEYWORDS"] = [
                        item.strip() for item in s.split(",") if item.strip()
                    ]

        # Validate security keys are not placeholders
        for field in ["SECRET_KEY", "JWT_SECRET_KEY", "ENCRYPTION_KEY"]:
            if field in data:
                v = data[field]
                if v and ("CHANGE_THIS" in v.upper() or "YOUR_" in v.upper()):
                    raise ValueError(
                        f"{field} must be changed from placeholder value. "
                        f"Never use default/example values in production."
                    )

        return data

    def __init__(self, **kwargs):
        """Initialize settings with validation."""
        super().__init__(**kwargs)
        self.validate_firebase_config()
        self.validate_cors_config()
        self.validate_production_config()
        self.validate_csrf_config()

    def validate_production_config(self):
        """Validate production environment has secure configurations."""
        if self.ENVIRONMENT.lower() == "production":
            errors = []

            # DEBUG must be False in production
            if self.DEBUG:
                errors.append("DEBUG must be False in production environment")

            # Redis SSL validation (optional - some Redis Cloud instances don't use SSL)
            # Note: Redis Cloud port 14149 does NOT use SSL/TLS
            # Validate URL scheme matches SSL setting
            if self.REDIS_SSL and not self.REDIS_URL.startswith("rediss://"):
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    "Redis SSL configuration mismatch",
                    extra={
                        "redis_ssl": self.REDIS_SSL,
                        "redis_url_scheme": self.REDIS_URL.split("://")[0] if "://" in self.REDIS_URL else "unknown",
                        "warning": "REDIS_SSL=True but URL doesn't use rediss:// scheme"
                    }
                )
            elif not self.REDIS_SSL and self.REDIS_URL.startswith("rediss://"):
                errors.append(
                    "REDIS_SSL=False but URL uses rediss:// scheme - configuration mismatch"
                )

            # Session cookies must be secure in production
            if not self.SESSION_COOKIE_SECURE:
                errors.append(
                    "SESSION_COOKIE_SECURE must be True in production environment"
                )

            # SSL redirect should be enabled in production
            if not self.SECURE_SSL_REDIRECT:
                errors.append(
                    "SECURE_SSL_REDIRECT must be True in production environment"
                )

            if errors:
                raise ValueError(
                    f"Production environment security validation failed:\n"
                    + "\n".join(f"  - {error}" for error in errors)
                )


# Global settings instance
settings = Settings()


# ============================================================================
# Backward Compatibility Helper Functions
# ============================================================================


def is_ai_humanization_enabled() -> bool:
    """Check if AI humanization is enabled."""
    return settings.AI_HUMANIZATION_ENABLED


def should_humanize_message(content: str) -> bool:
    """Check if message content is safe for AI humanization."""
    if not settings.AI_HUMANIZATION_SAFETY_MODE:
        return True

    content_lower = content.lower()
    return not any(
        keyword in content_lower
        for keyword in settings.AI_HUMANIZATION_CRITICAL_KEYWORDS
    )


def get_humanization_config() -> dict:
    """Get AI humanization configuration."""
    return {
        "enabled": settings.AI_HUMANIZATION_ENABLED,
        "safety_mode": settings.AI_HUMANIZATION_SAFETY_MODE,
        "max_retries": settings.AI_HUMANIZATION_MAX_RETRIES,
        "timeout": settings.AI_HUMANIZATION_TIMEOUT,
        "fallback_enabled": settings.AI_HUMANIZATION_FALLBACK_ENABLED,
        "critical_keywords": settings.AI_HUMANIZATION_CRITICAL_KEYWORDS,
    }


def get_settings():
    """Get settings instance."""
    return settings


def get_firebase_security_config():
    """Get Firebase security configuration for user provisioning."""
    return {
        "allowed_domains": settings.FIREBASE_ALLOWED_DOMAINS,
        "require_custom_claims": settings.FIREBASE_REQUIRE_CUSTOM_CLAIMS,
        "allowed_roles": settings.FIREBASE_ALLOWED_ROLES,
        "enable_audit_logging": settings.FIREBASE_ENABLE_AUDIT_LOGGING,
        "block_public_domains": settings.FIREBASE_BLOCK_PUBLIC_DOMAINS,
        "public_domains_blocklist": settings.FIREBASE_PUBLIC_DOMAINS_BLOCKLIST,
    }


# Export all for convenience
__all__ = [
    "Settings",
    "settings",
    "is_ai_humanization_enabled",
    "should_humanize_message",
    "get_humanization_config",
    "get_settings",
    "get_firebase_security_config",
]
