"""
Main Settings module that combines all configuration modules.
This provides backward compatibility with the monolithic config.py while using modular architecture.
"""

from typing import Any
from pydantic import model_validator
import json
import os

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
        def _strip_wrapping_quotes(value: str) -> str:
            s = value.strip()
            while len(s) >= 2 and s[0] == s[-1] and s[0] in ("\"", "'"):
                s = s[1:-1].strip()
            return s

        if isinstance(data, dict):
            for k, v in list(data.items()):
                if isinstance(v, str):
                    data[k] = _strip_wrapping_quotes(v)

        # Parse boolean fields from string - Using NEW direct field names
        boolean_fields = [
            # Base
            "APP_ENABLE_DEBUG",
            # Security
            "SESSION_ENABLE_COOKIE_SECURE",
            "SESSION_ENABLE_COOKIE_HTTPONLY",
            "SECURITY_ENABLE_SSL_REDIRECT",
            "SECURITY_ENABLE_CONTENT_TYPE_NOSNIFF",
            "SECURITY_ENABLE_BROWSER_XSS_FILTER",
            "SECURITY_ENABLE_FIELD_ENCRYPTION",
            # Firebase
            "FIREBASE_ENABLE_REQUIRE_CUSTOM_CLAIMS",
            "FIREBASE_ENABLE_AUDIT_LOGGING",
            "FIREBASE_ENABLE_BLOCK_PUBLIC_DOMAINS",
            # Rate Limiting
            "RATE_LIMIT_ENABLE_SERVICE",
            # WhatsApp/Evolution
            "WHATSAPP_ENABLE_SERVICE",
            "WHATSAPP_ENABLE_ON_REGISTRATION",
            "WHATSAPP_ENABLE_WELCOME_MESSAGE",
            # AI
            "AI_LANGCHAIN_ENABLE_TRACING_V2",
            "AI_ENABLE_HUMANIZATION",
            "AI_HUMANIZATION_ENABLE_SAFETY_MODE",
            "AI_HUMANIZATION_ENABLE_FALLBACK",
            # Celery
            "CELERY_ENABLE_UTC",
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

        # Parse CORS_ALLOWED_ORIGINS
        if "CORS_ALLOWED_ORIGINS" in data:
            v = data["CORS_ALLOWED_ORIGINS"]
            if isinstance(v, list) and len(v) > 0:
                pass  # Already a list
            elif isinstance(v, str) and v.strip():
                s = v.strip()

                # Handle case where entire JSON array is wrapped in quotes
                if (s.startswith('"') and s.endswith('"')) or (
                    s.startswith("'") and s.endswith("'")
                ):
                    s = s[1:-1].strip()

                if s.startswith("["):
                    try:
                        data["CORS_ALLOWED_ORIGINS"] = json.loads(s)
                    except (json.JSONDecodeError, ValueError):
                        # Fallback: remove brackets and split
                        s_clean = s.replace("[", "").replace("]", "")
                        data["CORS_ALLOWED_ORIGINS"] = [
                            item.strip() for item in s_clean.split(",") if item.strip()
                        ]
                else:
                    # Remove brackets if present in comma-separated string (just in case)
                    s_clean = s.replace("[", "").replace("]", "")
                    data["CORS_ALLOWED_ORIGINS"] = [
                        item.strip() for item in s_clean.split(",") if item.strip()
                    ]
            else:
                data["CORS_ALLOWED_ORIGINS"] = []

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
        import os

        is_production = (
            os.environ.get("APP_ENVIRONMENT", "development").lower() == "production"
        )

        if is_production:
            security_fields = ["SECURITY_SECRET_KEY", "SECURITY_ENCRYPTION_KEY"]
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
        self.validate_csrf_config()

    def validate_production_config(self):
        """Validate production environment has secure configurations."""
        if self.APP_ENVIRONMENT.lower() == "production":
            errors = []

            # DEBUG must be False in production
            if self.APP_ENABLE_DEBUG:
                errors.append(
                    "APP_ENABLE_DEBUG must be False in production environment"
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
