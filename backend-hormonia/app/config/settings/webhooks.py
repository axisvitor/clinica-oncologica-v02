"""
Webhook Configuration Settings

MEDIUM-009: Configuration for webhook retry logic with exponential backoff.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class WebhookSettings(BaseSettings):
    """
    Webhook retry and processing configuration.

    Retry Logic:
        Exponential backoff with configurable parameters
        Example with defaults:
            Attempt 1: Immediate
            Attempt 2: +2s  (total: 2s)
            Attempt 3: +4s  (total: 6s)
            Attempt 4: +8s  (total: 14s)
            Attempt 5: +16s (total: 30s)
    """

    # Retry Configuration
    WEBHOOK_MAX_RETRIES: int = 5
    """Maximum number of retry attempts before sending to DLQ"""

    WEBHOOK_RETRY_MIN_WAIT: int = 2
    """Minimum wait time between retries (seconds)"""

    WEBHOOK_RETRY_MAX_WAIT: int = 60
    """Maximum wait time between retries (seconds)"""

    WEBHOOK_RETRY_MULTIPLIER: int = 1
    """Exponential backoff multiplier"""

    # Processing Configuration
    WEBHOOK_TIMEOUT: int = 30
    """Timeout for webhook processing (seconds)"""

    WEBHOOK_BATCH_SIZE: int = 50
    """Number of webhooks to process in parallel"""

    # Security
    WEBHOOK_SIGNATURE_REQUIRED: bool = True
    """Whether webhook signature validation is required"""

    WEBHOOK_SIGNATURE_HEADER: str = "X-Webhook-Signature"
    """Header name for webhook signature"""

    model_config = SettingsConfigDict(
        env_prefix="WEBHOOK_",
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # CRITICAL: Ignore extra environment variables not defined in model
    )


# Singleton instance
webhook_settings = WebhookSettings()
