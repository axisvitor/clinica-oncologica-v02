"""
Integrations configuration module: External APIs and services.
Includes WhatsApp provider settings, Google Gemini AI, LangChain, and Celery.
ENV Variable Naming Convention: {CATEGORY}_{SUBCATEGORY}_{ATTRIBUTE}_{UNIT}
"""

from pydantic import Field, model_validator
from typing import List, Optional
from .base import BaseAppSettings


class IntegrationsSettings(BaseAppSettings):
    """Configuration for external API integrations and background tasks."""

    # ============================================================================
    # Notification / auth recovery delivery
    # ============================================================================
    SMTP_HOST: str = Field(
        default="localhost",
        description="SMTP server host for email delivery",
    )
    SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port for email delivery",
    )
    SMTP_USERNAME: Optional[str] = Field(
        default=None,
        description="Optional SMTP username for authenticated relays",
    )
    SMTP_PASSWORD: Optional[str] = Field(
        default=None,
        description="Optional SMTP password for authenticated relays",
    )
    SMTP_FROM_EMAIL: str = Field(
        default="noreply@example.com",
        description="From address used for outbound email notifications",
    )
    SMTP_USE_TLS: bool = Field(
        default=True,
        description="Enable STARTTLS for SMTP delivery",
    )
    SMTP_REQUIRE_AUTH: bool = Field(
        default=False,
        description="Require SMTP username/password before attempting email delivery",
    )
    SMTP_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        description="SMTP connection timeout in seconds",
    )
    SLACK_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Slack incoming webhook URL for alerts",
    )
    SLACK_DEFAULT_CHANNEL: str = Field(
        default="#alerts",
        description="Default Slack channel for notifications",
    )
    PAGERDUTY_API_KEY: Optional[str] = Field(
        default=None,
        description="PagerDuty REST API key",
    )
    PAGERDUTY_SERVICE_KEY: Optional[str] = Field(
        default=None,
        description="PagerDuty Events API routing key",
    )
    NOTIFICATION_RETRY_ATTEMPTS: int = Field(
        default=3,
        description="Maximum retry attempts for notification delivery",
    )
    NOTIFICATION_RETRY_DELAY: int = Field(
        default=5,
        description="Base retry delay in seconds for notification delivery",
    )
    AUTH_RESET_BASE_URL: str = Field(
        default="http://localhost:5173",
        description="Frontend base URL used to build password reset links",
    )
    AUTH_RESET_PATH: str = Field(
        default="/reset-password",
        description="Frontend path used for regular password reset flows",
    )
    AUTH_FIRST_ACCESS_PATH: str = Field(
        default="/primeiro-acesso",
        description="Frontend path used for first-access activation flows",
    )
    AUTH_RESET_TOKEN_EXPIRE_HOURS: int = Field(
        default=24,
        description="Password reset token lifetime in hours",
    )

    # ============================================================================
    # WhatsApp provider - Direct ENV names
    # ============================================================================
    WHATSAPP_ENABLE_SERVICE: bool = Field(
        default=True, description="Enable WhatsApp integration"
    )
    WHATSAPP_WEBHOOK_HMAC_ENABLED: bool = Field(
        default=True,
        description="Enable HMAC signature validation for WhatsApp webhooks",
    )
    WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED: bool = Field(
        default=False,
        description="Require webhook timestamp header for replay protection",
    )
    WHATSAPP_WEBHOOK_MAX_TIMESTAMP_AGE_SECONDS: int = Field(
        default=300,
        description="Maximum webhook timestamp age in seconds",
    )
    WHATSAPP_WEBHOOK_IP_WHITELIST: List[str] = Field(
        default_factory=list,
        description=(
            "Optional list of allowed webhook source IPs. "
            "Leave empty to disable IP filtering."
        ),
    )
    WHATSAPP_WEBHOOK_TRUST_PROXY_HEADERS: bool = Field(
        default=False,
        description=(
            "Trust X-Forwarded-For/X-Real-IP headers for webhook client IP resolution. "
            "Keep disabled unless requests always come from a trusted reverse proxy."
        ),
    )
    WHATSAPP_WEBHOOK_TRUSTED_PROXIES: List[str] = Field(
        default_factory=list,
        description="Explicit reverse proxy IPs/CIDRs allowed to supply webhook client IP headers.",
    )
    WHATSAPP_WUZAPI_BASE_URL: str = Field(
        default="http://localhost:8080",
        description="WuzAPI base URL (e.g. http://wuzapi:8080)",
    )
    WHATSAPP_WUZAPI_TOKEN: Optional[str] = Field(
        default=None,
        description=(
            "WuzAPI API token. REQUIRED in non-test environments. "
            "Application refuses to start if absent. "
            "Set via Authorization header on every WuzAPI request."
        ),
    )
    WHATSAPP_WUZAPI_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description=(
            "HMAC-SHA256 secret for WuzAPI webhook signature validation. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        ),
    )
    WHATSAPP_WUZAPI_USE_MOCK: bool = Field(
        default=False,
        description=(
            "Use MockWuzAPIClient instead of real WuzAPI HTTP calls. "
            "Set true only for local development/testing without WuzAPI."
        ),
    )

    @model_validator(mode="after")
    def validate_wuzapi_token(self) -> "IntegrationsSettings":
        """Hard-fail at startup if WHATSAPP_WUZAPI_TOKEN is missing (CFG-02).

        Application must refuse to start without the token in non-test environments.
        Silent fallback is explicitly prohibited.
        """
        import os

        is_test = bool(
            os.getenv("PYTEST_CURRENT_TEST")
            or os.getenv("TESTING") == "1"
            or self.APP_ENVIRONMENT.lower() in ("test", "testing")
        )
        if is_test:
            return self

        token = self.WHATSAPP_WUZAPI_TOKEN
        if not token or not token.strip():
            raise ValueError(
                "\n" + "=" * 70 + "\n"
                "STARTUP VALIDATION FAILED: WHATSAPP_WUZAPI_TOKEN is required.\n"
                "=" * 70 + "\n"
                "Set WHATSAPP_WUZAPI_TOKEN in your .env file or environment.\n"
                "This token authenticates all WuzAPI API calls.\n"
                "Obtain it from your WuzAPI instance configuration.\n"
                "=" * 70
            )
        return self

    # WhatsApp Integration Configuration - Direct ENV names
    WHATSAPP_ENABLE_ON_REGISTRATION: bool = Field(
        default=True,
        description="Enable automatic WhatsApp welcome message on patient registration",
    )
    WHATSAPP_ENABLE_WELCOME_MESSAGE: bool = Field(
        default=True,
        description="Enable welcome message feature (can be disabled for testing)",
    )
    WHATSAPP_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retry attempts for failed WhatsApp messages",
    )
    WHATSAPP_RETRY_DELAY_SECONDS: int = Field(
        default=60,
        description="Initial delay in seconds before retrying failed messages (uses exponential backoff)",
    )
    WHATSAPP_FLOW_RESPONSE_TIMEOUT_SECONDS: int = Field(
        default=180,
        description="Timeout for processing patient responses via webhook background flow",
    )
    WHATSAPP_FLOW_SCHEDULE_TIMEOUT_SECONDS: int = Field(
        default=60,
        description="Timeout for scheduling follow-up messages after webhook processing",
    )
    WHATSAPP_FLOW_CONTINUE_TIMEOUT_SECONDS: int = Field(
        default=120,
        description="Timeout for continuing sequential flow after webhook response",
    )
    WHATSAPP_CLINIC_NAME: str = Field(
        default="Neoplasias Litoral",
        description="Clinic name for WhatsApp messages",
    )
    WHATSAPP_CLINIC_SUPPORT_PHONE: Optional[str] = Field(
        default=None,
        description="Support phone number for emergencies (shown in welcome message)",
    )

    # ============================================================================
    # AI Services - Direct ENV names
    # ============================================================================

    # LangChain Configuration - Direct ENV names
    AI_LANGCHAIN_ENABLE_TRACING_V2: bool = Field(
        default=False, description="Enable LangChain tracing"
    )
    AI_LANGCHAIN_API_KEY: Optional[str] = Field(
        default=None, description="LangChain API key"
    )

    # Google Gemini AI - Direct ENV names
    AI_GEMINI_API_KEY: Optional[str] = Field(
        default=None, description="Google Gemini API key"
    )
    AI_GEMINI_MODEL: str = Field(
        default="gemini-3-flash-preview", description="Gemini model to use"
    )
    AI_GEMINI_TEMPERATURE: float = Field(
        default=0.7, description="Gemini generation temperature"
    )
    AI_GEMINI_MAX_OUTPUT_TOKENS: int = Field(
        default=500, description="Gemini max output tokens"
    )
    AI_GEMINI_TOP_P: float = Field(default=0.8, description="Gemini top-p parameter")
    AI_GEMINI_TOP_K: int = Field(default=40, description="Gemini top-k parameter")
    AI_GEMINI_TIMEOUT_SECONDS: int = Field(
        default=30, description="Gemini API timeout in seconds"
    )
    AI_GEMINI_MAX_RETRIES: int = Field(default=3, description="Gemini API max retries")

    # AI Humanization Configuration - Direct ENV names
    AI_ENABLE_HUMANIZATION: bool = Field(
        default=True, description="Enable AI message humanization in flow engine"
    )
    AI_HUMANIZATION_ENABLE_SAFETY_MODE: bool = Field(
        default=True, description="Enable safety checks for critical message types"
    )
    AI_HUMANIZATION_MAX_RETRIES: int = Field(
        default=2, description="Maximum retries for AI humanization failures"
    )
    AI_HUMANIZATION_TIMEOUT_SECONDS: float = Field(
        default=10.0, description="Timeout for AI humanization requests in seconds"
    )
    AI_HUMANIZATION_ENABLE_FALLBACK: bool = Field(
        default=True, description="Enable fallback to original message on AI failure"
    )
    AI_HUMANIZATION_CRITICAL_KEYWORDS: List[str] = Field(
        default=[
            "medicação",
            "remédio",
            "dosagem",
            "mg",
            "ml",
            "emergência",
            "urgente",
            "hospital",
        ],
        description="Keywords that prevent AI humanization for safety",
    )

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def is_ai_humanization_enabled(self) -> bool:
        """Check if AI humanization is enabled."""
        return self.AI_ENABLE_HUMANIZATION

    def should_humanize_message(self, content: str) -> bool:
        """Check if message content is safe for AI humanization."""
        if not self.AI_HUMANIZATION_ENABLE_SAFETY_MODE:
            return True

        content_lower = content.lower()
        return not any(
            keyword in content_lower
            for keyword in self.AI_HUMANIZATION_CRITICAL_KEYWORDS
        )

    def get_humanization_config(self) -> dict:
        """Get AI humanization configuration."""
        return {
            "enabled": self.AI_ENABLE_HUMANIZATION,
            "safety_mode": self.AI_HUMANIZATION_ENABLE_SAFETY_MODE,
            "max_retries": self.AI_HUMANIZATION_MAX_RETRIES,
            "timeout": self.AI_HUMANIZATION_TIMEOUT_SECONDS,
            "fallback_enabled": self.AI_HUMANIZATION_ENABLE_FALLBACK,
            "critical_keywords": self.AI_HUMANIZATION_CRITICAL_KEYWORDS,
        }
