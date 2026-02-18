"""
Main Settings module that combines all configuration modules.
This provides backward compatibility with the monolithic config.py while using modular architecture.
"""

from typing import Any
from pydantic import model_validator
import json
import os

from .parsing import parse_boolean_env_values, parse_list_field, strip_wrapping_quotes

# =============================================================================
# CRITICAL: Preprocess env vars BEFORE any pydantic-settings class is imported
# =============================================================================
# pydantic-settings captures env vars when EnvSettingsSource is created.
# For List[str] fields, it calls json.loads() which fails on empty strings.
# We MUST fix the env vars BEFORE importing Settings classes.
# =============================================================================

_LIST_FIELDS_WITH_EMPTY_DEFAULT = [
    "CORS_ALLOWED_ORIGINS",
    "FIREBASE_ALLOWED_DOMAINS",
    "SECURITY_ALLOWED_HOSTS",
    "AI_HUMANIZATION_CRITICAL_KEYWORDS",
    "SUPPORTED_LOCALES",
]


def _preprocess_list_env_vars():
    """
    Preprocess List[str] env vars to prevent pydantic-settings JSON parse errors.

    Must be called BEFORE any Settings class is instantiated.
    Converts:
    - Empty string "" -> "[]" (valid empty JSON array)
    - Comma-separated "a,b,c" -> '["a","b","c"]' (JSON array)
    """
    for field_name in _LIST_FIELDS_WITH_EMPTY_DEFAULT:
        env_value = os.environ.get(field_name, None)
        if env_value is not None:
            stripped = env_value.strip()
            # Empty string or whitespace -> empty JSON array
            if not stripped:
                os.environ[field_name] = "[]"
            # Already valid JSON array -> leave as-is
            elif stripped.startswith("["):
                pass
            # Comma-separated without brackets -> convert to JSON array
            elif "," in stripped:
                items = [item.strip() for item in stripped.split(",") if item.strip()]
                os.environ[field_name] = json.dumps(items)
            # Single value without brackets -> wrap in array
            else:
                os.environ[field_name] = json.dumps([stripped])


# Execute preprocessing IMMEDIATELY at module load time
_preprocess_list_env_vars()


from .base import BaseAppSettings  # noqa: F401 - exported for use by other modules
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

        NOTE: Field names here are the DIRECT env variable names (no more aliases).
        """
        if isinstance(data, dict):
            for k, v in list(data.items()):
                if isinstance(v, str):
                    data[k] = strip_wrapping_quotes(v)

        if "ALLOW_AI_SIMULATION" not in data:
            app_env = data.get("APP_ENVIRONMENT") or os.environ.get(
                "APP_ENVIRONMENT", "development"
            )
            if isinstance(app_env, str) and app_env.lower() == "production":
                data["ALLOW_AI_SIMULATION"] = False

        # Parse boolean fields from string - Using NEW direct field names
        boolean_fields = [
            # Base
            "APP_ENABLE_DEBUG",
            "ALLOW_AI_SIMULATION",
            # Security
            "SESSION_ENABLE_COOKIE_SECURE",
            "SESSION_ENABLE_COOKIE_HTTPONLY",
            "ENABLE_COOKIE_PRIORITY",
            "SECURITY_ENABLE_SSL_REDIRECT",
            "SECURITY_ENABLE_CONTENT_TYPE_NOSNIFF",
            "SECURITY_ENABLE_BROWSER_XSS_FILTER",
            "SECURITY_ENABLE_FIELD_ENCRYPTION",
            "SECURITY_ALLOW_WEAK_KEYS",
            # Firebase
            "FIREBASE_ENABLE_REQUIRE_CUSTOM_CLAIMS",
            "FIREBASE_ENABLE_AUDIT_LOGGING",
            "FIREBASE_ENABLE_BLOCK_PUBLIC_DOMAINS",
            # Rate Limiting
            "RATE_LIMIT_ENABLE_SERVICE",
            # WhatsApp/Evolution
            "WHATSAPP_ENABLE_SERVICE",
            "WHATSAPP_EVOLUTION_USE_MOCK",
            "WHATSAPP_ENABLE_ON_REGISTRATION",
            "WHATSAPP_ENABLE_WELCOME_MESSAGE",
            "WHATSAPP_WEBHOOK_HMAC_ENABLED",
            "WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED",
            "WHATSAPP_WEBHOOK_TRUST_PROXY_HEADERS",
            # AI
            "AI_LANGCHAIN_ENABLE_TRACING_V2",
            "AI_ENABLE_HUMANIZATION",
            "AI_HUMANIZATION_ENABLE_SAFETY_MODE",
            "AI_HUMANIZATION_ENABLE_FALLBACK",
            # Celery
            "CELERY_ENABLE_TZ_NORMALIZATION",
            "CELERY_ENABLE_TRACK_STARTED",
            "CELERY_ENABLE_DISABLE_RATE_LIMITS",
            # Quiz
            "QUIZ_ENABLE_VIA_LINK",
            # Flow
            "FLOW_ENABLE_AUTO_ENROLLMENT",
            "FLOW_ENABLE_AUTO_ENROLLMENT_FALLBACK",
            "TASK_SAGA_ENABLE_PATTERN",
            # Logging/Monitoring
            "LOGGING_ENABLE_REQUEST_LOGGING",
            "LOGGING_ENABLE_STACK_TRACES",
            "ERROR_ENABLE_TRACKING",
            "ERROR_ENABLE_CRITICAL_NOTIFICATION",
            "MONITORING_ENABLE_SERVICE",
            "MONITORING_ENABLE_DEBUG",
            # Redis
            "REDIS_ENABLE_SERVICE",
            "REDIS_ENABLE_SSL",
            "REDIS_ENABLE_RETRY_ON_TIMEOUT",
            "REDIS_ENABLE_DECODE_RESPONSES",
            "REDIS_ENABLE_DB_ISOLATION",
            "REDIS_ENABLE_CLUSTER_MODE",
        ]

        parse_boolean_env_values(data, boolean_fields)
        parse_list_field(data, "FIREBASE_ALLOWED_DOMAINS")
        parse_list_field(data, "CORS_ALLOWED_ORIGINS", allow_quoted_json=True)
        parse_list_field(data, "SUPPORTED_LOCALES", allow_quoted_json=True)

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

        # Validate security keys are not placeholders (only in production)
        # In development, default insecure keys are allowed for local testing
        is_production = (
            os.environ.get("APP_ENVIRONMENT", "development").lower() == "production"
        )

        if is_production:
            security_fields = [
                "SECURITY_SECRET_KEY",
                "SECURITY_CSRF_SECRET_KEY",
                "ENCRYPTION_KEY_CURRENT",
                "PHI_ENCRYPTION_KEY",
                "HASH_SALT",
                "SECURITY_ENCRYPTION_KEY",
            ]
            placeholder_patterns = [
                "CHANGE_THIS",
                "YOUR_",
                "INSECURE",
                "DEV-",
                "MUST-BE-CHANGED",
            ]
            for field in security_fields:
                if field in data:
                    v = data[field]
                    if v and any(
                        pattern in v.upper() for pattern in placeholder_patterns
                    ):
                        raise ValueError(
                            f"{field} must be changed from placeholder/default value in production. "
                            f"Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
                        )

        return data

    def __init__(self, **kwargs):
        """Initialize settings with validation."""
        super().__init__(**kwargs)
        self.validate_production_config()
        self.validate_ai_config()
        self.validate_csrf_config()

    def validate_production_config(self):
        """Validate production environment has secure configurations."""
        # Run SecuritySettings validation (entropy checks)
        SecuritySettings.validate_production_config(self)

        if self.APP_ENVIRONMENT.lower() == "production":
            errors = []

            # DEBUG must be False in production
            if self.APP_ENABLE_DEBUG:
                errors.append(
                    "APP_ENABLE_DEBUG must be False in production environment"
                )

            # AI simulation is not allowed in production.
            if self.ALLOW_AI_SIMULATION:
                errors.append(
                    "ALLOW_AI_SIMULATION must be False in production environment"
                )

            # Redis SSL validation (optional - some Redis Cloud instances don't use SSL)
            # Note: Redis Cloud port 14149 does NOT use SSL/TLS
            # Validate URL scheme matches SSL setting
            if self.REDIS_ENABLE_SSL and not self.REDIS_URL.startswith("rediss://"):
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    "Redis SSL configuration mismatch",
                    extra={
                        "redis_ssl": self.REDIS_ENABLE_SSL,
                        "redis_url_scheme": self.REDIS_URL.split("://")[0]
                        if "://" in self.REDIS_URL
                        else "unknown",
                        "warning": "REDIS_ENABLE_SSL=True but URL doesn't use rediss:// scheme",
                    },
                )
            elif not self.REDIS_ENABLE_SSL and self.REDIS_URL.startswith("rediss://"):
                errors.append(
                    "REDIS_ENABLE_SSL=False but URL uses rediss:// scheme - configuration mismatch"
                )

            # Session cookies must be secure in production
            if not self.SESSION_ENABLE_COOKIE_SECURE:
                errors.append(
                    "SESSION_ENABLE_COOKIE_SECURE must be True in production environment"
                )

            # SSL redirect should be enabled in production
            if not self.SECURITY_ENABLE_SSL_REDIRECT:
                errors.append(
                    "SECURITY_ENABLE_SSL_REDIRECT must be True in production environment"
                )

            if errors:
                raise ValueError(
                    "Production environment security validation failed:\n"
                    + "\n".join(f"  - {error}" for error in errors)
                )

    def validate_ai_config(self):
        """Validate AI configuration when simulation is disabled."""
        if not self.ALLOW_AI_SIMULATION:
            if not self.AI_GEMINI_API_KEY or not self.AI_GEMINI_API_KEY.strip():
                raise ValueError(
                    "AI_GEMINI_API_KEY must be set when ALLOW_AI_SIMULATION is False."
                )


# Global settings instance
settings = Settings()


# ============================================================================
# Backward Compatibility Helper Functions
# ============================================================================


def is_ai_humanization_enabled() -> bool:
    """Check if AI humanization is enabled."""
    return settings.AI_ENABLE_HUMANIZATION


def should_humanize_message(content: str) -> bool:
    """Check if message content is safe for AI humanization."""
    if not settings.AI_HUMANIZATION_ENABLE_SAFETY_MODE:
        return True

    content_lower = content.lower()
    return not any(
        keyword in content_lower
        for keyword in settings.AI_HUMANIZATION_CRITICAL_KEYWORDS
    )


def get_humanization_config() -> dict:
    """Get AI humanization configuration."""
    return {
        "enabled": settings.AI_ENABLE_HUMANIZATION,
        "safety_mode": settings.AI_HUMANIZATION_ENABLE_SAFETY_MODE,
        "max_retries": settings.AI_HUMANIZATION_MAX_RETRIES,
        "timeout": settings.AI_HUMANIZATION_TIMEOUT_SECONDS,
        "fallback_enabled": settings.AI_HUMANIZATION_ENABLE_FALLBACK,
        "critical_keywords": settings.AI_HUMANIZATION_CRITICAL_KEYWORDS,
    }


def get_settings():
    """Get settings instance."""
    return settings


def get_firebase_security_config():
    """Get Firebase security configuration for user provisioning."""
    return {
        "allowed_domains": settings.FIREBASE_ALLOWED_DOMAINS,
        "require_custom_claims": settings.FIREBASE_ENABLE_REQUIRE_CUSTOM_CLAIMS,
        "allowed_roles": settings.FIREBASE_ALLOWED_ROLES,
        "enable_audit_logging": settings.FIREBASE_ENABLE_AUDIT_LOGGING,
        "block_public_domains": settings.FIREBASE_ENABLE_BLOCK_PUBLIC_DOMAINS,
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
