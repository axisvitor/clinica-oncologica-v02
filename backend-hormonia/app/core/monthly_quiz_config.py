"""
Monthly Quiz Configuration for Hormonia Backend System.

This module provides configuration for the monthly quiz feature,
which allows patients to access quizzes via a secure tokenized link.
"""

from __future__ import annotations

from pydantic import Field, field_validator, HttpUrl, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class MonthlyQuizConfig(BaseSettings):
    """Configuration settings for monthly quiz feature."""

    # Environment (used by link builder warnings, etc.)
    ENVIRONMENT: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENVIRONMENT", "ENVIRONMENT"),
        description="Environment name (development, staging, production)",
    )

    # Feature flags
    MONTHLY_QUIZ_VIA_LINK: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "QUIZ_ENABLE_VIA_LINK",
            "ENABLE_LINK_BASED_MONTHLY_QUIZ",
            "MONTHLY_QUIZ_VIA_LINK",
        ),
        description="Enable monthly quiz via link feature (legacy, use ENABLE_LINK_BASED_MONTHLY_QUIZ)",
    )

    @property
    def ENABLE_LINK_BASED_MONTHLY_QUIZ(self) -> bool:
        return self.MONTHLY_QUIZ_VIA_LINK

    # Gradual rollout configuration
    MONTHLY_QUIZ_LINK_PERCENTAGE: int = Field(
        default=100,
        description="Percentage of patients to receive link-based quiz (0-100 for gradual rollout)",
    )

    MONTHLY_QUIZ_LINK_ROLLOUT_BY_COHORT: bool = Field(
        default=False,
        description="Enable cohort-based rollout (uses patient_id hash for consistent assignment)",
    )

    MONTHLY_QUIZ_FALLBACK_TO_WHATSAPP: bool = Field(
        default=True,
        description="Fallback to WhatsApp conversational if link creation fails",
    )

    # Base URL for quiz links - validated as HttpUrl for security
    MONTHLY_QUIZ_BASE_URL: str = Field(
        default="http://localhost:3001",
        validation_alias=AliasChoices("QUIZ_BASE_URL", "MONTHLY_QUIZ_BASE_URL"),
        description="Base URL for monthly quiz access links (must be valid HTTP/HTTPS URL)",
    )

    @field_validator("MONTHLY_QUIZ_BASE_URL", mode="before")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """
        Validate and normalize the base URL.

        Ensures:
        - URL has valid format (scheme, host)
        - URL uses HTTP or HTTPS scheme
        - Trailing slash is removed to prevent double slashes in generated links

        Raises:
            ValueError: If URL is invalid or uses unsupported scheme
        """
        if not v or not isinstance(v, str):
            raise ValueError("MONTHLY_QUIZ_BASE_URL must be a non-empty string")

        v = v.strip()

        # Validate URL format using HttpUrl
        try:
            validated_url = HttpUrl(v)
            url_str = str(validated_url)
        except Exception as e:
            raise ValueError(
                f"MONTHLY_QUIZ_BASE_URL must be a valid URL. Got: '{v}'. Error: {e}"
            )

        # Ensure scheme is HTTP or HTTPS
        if not url_str.startswith(("http://", "https://")):
            raise ValueError(
                f"MONTHLY_QUIZ_BASE_URL must use HTTP or HTTPS scheme. Got: '{v}'"
            )

        # Remove trailing slash to prevent double slashes in generated links
        if url_str.endswith("/"):
            url_str = url_str[:-1]

        return url_str

    # Token configuration - REQUIRED, no default
    MONTHLY_QUIZ_TOKEN_SECRET: str = Field(
        ...,  # REQUIRED: Must be set via environment variable
        validation_alias=AliasChoices("QUIZ_TOKEN_SECRET", "MONTHLY_QUIZ_TOKEN_SECRET"),
        description="Secret key for generating quiz tokens (should be different from main SECRET_KEY)",
    )

    # Token expiry
    MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS: int = Field(
        default=72,
        validation_alias=AliasChoices(
            "QUIZ_TOKEN_EXPIRY_HOURS", "MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS"
        ),
        description="Token expiry time in hours (default: 72 hours = 3 days)",
    )

    # Security settings
    MONTHLY_QUIZ_MAX_ATTEMPTS: int = Field(
        default=3, description="Maximum number of quiz attempts per month"
    )

    MONTHLY_QUIZ_RATE_LIMIT_PER_HOUR: int = Field(
        default=10, description="Rate limit for quiz access per hour"
    )

    # Enhanced security settings
    MONTHLY_QUIZ_ENABLE_ENCRYPTION: bool = Field(
        default=True, description="Enable encryption for sensitive responses"
    )

    MONTHLY_QUIZ_AUDIT_ENABLED: bool = Field(
        default=True, description="Enable audit logging"
    )

    MONTHLY_QUIZ_LOCKOUT_MINUTES: int = Field(
        default=30, description="Lockout duration after max failed attempts"
    )

    MONTHLY_QUIZ_DATA_RETENTION_DAYS: int = Field(
        default=365, description="Data retention period in days"
    )

    # LGPD compliance settings
    LGPD_CONSENT_REQUIRED: bool = Field(
        default=True, description="Require explicit consent before data collection"
    )

    LGPD_ANONYMIZE_AFTER_DAYS: int = Field(
        default=730, description="Anonymize data after N days (2 years default)"
    )

    # Token rotation settings
    MONTHLY_QUIZ_ENABLE_TOKEN_ROTATION: bool = Field(
        default=True, description="Enable token rotation on each access"
    )

    MONTHLY_QUIZ_SINGLE_USE_TOKENS: bool = Field(
        default=False, description="Make tokens single-use only"
    )

    # Delivery settings
    MONTHLY_QUIZ_DEFAULT_DELIVERY: str = Field(
        default="whatsapp", description="Default delivery method (whatsapp, email, sms)"
    )

    # Template settings
    MONTHLY_QUIZ_DEFAULT_TEMPLATE: Optional[str] = Field(
        default="Quizz de Bem-Estar Mensal",
        description="Default monthly quiz template name",
    )

    # Reminder settings
    MONTHLY_QUIZ_REMINDER_1_HOURS_BEFORE: int = Field(
        default=24, description="Hours before expiry to send first reminder"
    )

    MONTHLY_QUIZ_REMINDER_2_HOURS_BEFORE: int = Field(
        default=6, description="Hours before expiry to send second reminder"
    )

    MONTHLY_QUIZ_ENABLE_REMINDERS: bool = Field(
        default=True, description="Enable automatic reminders for uncompleted quizzes"
    )

    # Analytics and monitoring
    MONTHLY_QUIZ_TRACK_LINK_METRICS: bool = Field(
        default=True,
        description="Track link access metrics (clicks, completion rate, etc.)",
    )

    MONTHLY_QUIZ_ALERT_ON_LOW_COMPLETION: bool = Field(
        default=True, description="Send alerts when completion rate is below threshold"
    )

    MONTHLY_QUIZ_LOW_COMPLETION_THRESHOLD: float = Field(
        default=0.6, description="Completion rate threshold for alerts (0.0-1.0)"
    )

    # Resilience configuration
    MAX_LINK_REGENERATIONS: int = Field(
        default=2, description="Maximum number of link regenerations before fallback"
    )

    REMINDER_MAX_RETRIES: int = Field(
        default=3, description="Maximum number of reminder retry attempts"
    )

    FALLBACK_THRESHOLD: int = Field(
        default=3, description="Number of failures before activating fallback"
    )

    REMINDER_RETRY_DELAY_HOURS: str = Field(
        default="1,2,4",
        description="Comma-separated retry delays in hours (exponential backoff)",
    )

    # Circuit breaker configuration
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(
        default=5, description="Failures within window to open circuit breaker"
    )

    CIRCUIT_BREAKER_WINDOW_MINUTES: int = Field(
        default=60, description="Time window for tracking failures (minutes)"
    )

    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = Field(
        default=300, description="Seconds before attempting recovery (half-open state)"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields from .env
    )


# Global instance
monthly_quiz_config = MonthlyQuizConfig()


def get_monthly_quiz_config() -> MonthlyQuizConfig:
    """Get monthly quiz configuration instance."""
    return monthly_quiz_config


def should_use_link_based_quiz(patient_id: str) -> bool:
    """
    Determine if patient should receive link-based quiz based on rollout configuration.

    Args:
        patient_id: Patient ID (UUID as string)

    Returns:
        bool: True if patient should receive link-based quiz
    """
    config = get_monthly_quiz_config()

    # Check if feature is enabled
    if not config.ENABLE_LINK_BASED_MONTHLY_QUIZ:
        return False

    # If 100% rollout, always use link
    if config.MONTHLY_QUIZ_LINK_PERCENTAGE >= 100:
        return True

    # If 0% rollout, never use link
    if config.MONTHLY_QUIZ_LINK_PERCENTAGE <= 0:
        return False

    # Cohort-based rollout (deterministic based on patient_id hash)
    if config.MONTHLY_QUIZ_LINK_ROLLOUT_BY_COHORT:
        import hashlib

        patient_hash = int(hashlib.md5(patient_id.encode()).hexdigest(), 16)
        cohort_assignment = (patient_hash % 100) + 1  # 1-100
        return cohort_assignment <= config.MONTHLY_QUIZ_LINK_PERCENTAGE

    # Random rollout (non-deterministic)
    import random

    return random.randint(1, 100) <= config.MONTHLY_QUIZ_LINK_PERCENTAGE
