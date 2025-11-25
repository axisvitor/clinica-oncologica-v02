"""
Integrations configuration module: External APIs and services.
Includes Evolution API (WhatsApp), Google Gemini AI, LangChain, and Celery.
"""

from pydantic import Field
from typing import List, Optional
from .base import BaseAppSettings


class IntegrationsSettings(BaseAppSettings):
    """Configuration for external API integrations and background tasks."""

    # ============================================================================
    # Evolution API (WhatsApp)
    # ============================================================================
    ENABLE_EVOLUTION: bool = Field(
        default=True, description="Enable Evolution API WhatsApp integration"
    )
    EVOLUTION_API_URL: str = Field(
        default="http://localhost:8080", description="Evolution API base URL"
    )
    EVOLUTION_INSTANCE_NAME: str = Field(
        default="clinica_oncologica", description="Evolution instance name"
    )
    EVOLUTION_API_KEY: str = Field(
        default="your-evolution-api-key-here", description="Evolution API key"
    )
    EVOLUTION_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description=(
            "Evolution webhook secret for HMAC-SHA256 signature validation. "
            "CRITICAL SECURITY: Must be set in production to prevent webhook spoofing. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    )
    EVOLUTION_WEBHOOK_URL: Optional[str] = Field(
        default=None, description="Webhook URL for receiving Evolution API events"
    )

    # WhatsApp Integration Configuration
    ENABLE_WHATSAPP_ON_REGISTRATION: bool = Field(
        default=True,
        description="Enable automatic WhatsApp welcome message on patient registration",
    )
    WHATSAPP_WELCOME_MESSAGE_ENABLED: bool = Field(
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
    CLINIC_NAME: str = Field(
        default="Neoplasias Litoral",
        description="Clinic name for WhatsApp messages",
    )
    CLINIC_SUPPORT_PHONE: Optional[str] = Field(
        default=None,
        description="Support phone number for emergencies (shown in welcome message)",
    )

    # ============================================================================
    # AI Services (Google Gemini & LangChain)
    # ============================================================================

    # LangChain Configuration
    LANGCHAIN_TRACING_V2: bool = Field(
        default=False, description="Enable LangChain tracing"
    )
    LANGCHAIN_API_KEY: Optional[str] = Field(
        default=None, description="LangChain API key"
    )

    # Google Gemini AI
    GEMINI_API_KEY: Optional[str] = Field(
        default=None, description="Google Gemini API key"
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.5-flash-latest", description="Gemini model to use"
    )
    GEMINI_TEMPERATURE: float = Field(
        default=0.7, description="Gemini generation temperature"
    )
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(
        default=500, description="Gemini max output tokens"
    )
    GEMINI_TOP_P: float = Field(default=0.8, description="Gemini top-p parameter")
    GEMINI_TOP_K: int = Field(default=40, description="Gemini top-k parameter")
    GEMINI_TIMEOUT: int = Field(default=30, description="Gemini API timeout in seconds")
    GEMINI_MAX_RETRIES: int = Field(default=3, description="Gemini API max retries")

    # AI Humanization Configuration
    AI_HUMANIZATION_ENABLED: bool = Field(
        default=True, description="Enable AI message humanization in flow engine"
    )
    AI_HUMANIZATION_SAFETY_MODE: bool = Field(
        default=True, description="Enable safety checks for critical message types"
    )
    AI_HUMANIZATION_MAX_RETRIES: int = Field(
        default=2, description="Maximum retries for AI humanization failures"
    )
    AI_HUMANIZATION_TIMEOUT: float = Field(
        default=10.0, description="Timeout for AI humanization requests in seconds"
    )
    AI_HUMANIZATION_FALLBACK_ENABLED: bool = Field(
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
            "médico",
            "consulta",
            "exame",
            "resultado",
            "tratamento",
            "quimioterapia",
            "radioterapia",
            "cirurgia",
            "efeito colateral",
            "reação adversa",
            "contraindicação",
            "suspender",
            "parar",
            "não tome",
        ],
        description="Keywords that prevent AI humanization for safety",
    )

    # ============================================================================
    # Celery Configuration (Background Tasks)
    # ============================================================================
    CELERY_BROKER_URL: str = Field(
        default="rediss://localhost:6379/0", description="Celery broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="rediss://localhost:6379/1",
        description="Celery result backend (use different DB)",
    )
    CELERY_TASK_SERIALIZER: str = Field(
        default="json", description="Celery task serializer"
    )
    CELERY_ACCEPT_CONTENT: List[str] = Field(
        default=["json"], description="Celery accepted content types"
    )
    CELERY_RESULT_SERIALIZER: str = Field(
        default="json", description="Celery result serializer"
    )
    CELERY_TIMEZONE: str = Field(default="UTC", description="Celery timezone")
    CELERY_ENABLE_UTC: bool = Field(default=True, description="Enable UTC in Celery")
    CELERY_TASK_TRACK_STARTED: bool = Field(
        default=True, description="Track task start events"
    )
    CELERY_TASK_TIME_LIMIT: int = Field(
        default=300, description="Task time limit in seconds"
    )
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(
        default=240, description="Task soft time limit in seconds"
    )
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(
        default=1000, description="Max tasks per worker child"
    )
    CELERY_WORKER_DISABLE_RATE_LIMITS: bool = Field(
        default=True, description="Disable rate limits for workers"
    )

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def is_ai_humanization_enabled(self) -> bool:
        """Check if AI humanization is enabled."""
        return self.AI_HUMANIZATION_ENABLED

    def should_humanize_message(self, content: str) -> bool:
        """Check if message content is safe for AI humanization."""
        if not self.AI_HUMANIZATION_SAFETY_MODE:
            return True

        content_lower = content.lower()
        return not any(
            keyword in content_lower
            for keyword in self.AI_HUMANIZATION_CRITICAL_KEYWORDS
        )

    def get_humanization_config(self) -> dict:
        """Get AI humanization configuration."""
        return {
            "enabled": self.AI_HUMANIZATION_ENABLED,
            "safety_mode": self.AI_HUMANIZATION_SAFETY_MODE,
            "max_retries": self.AI_HUMANIZATION_MAX_RETRIES,
            "timeout": self.AI_HUMANIZATION_TIMEOUT,
            "fallback_enabled": self.AI_HUMANIZATION_FALLBACK_ENABLED,
            "critical_keywords": self.AI_HUMANIZATION_CRITICAL_KEYWORDS,
        }
