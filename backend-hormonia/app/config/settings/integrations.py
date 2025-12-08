"""
Integrations configuration module: External APIs and services.
Includes Evolution API (WhatsApp), Google Gemini AI, LangChain, and Celery.
ENV Variable Naming Convention: {CATEGORY}_{SUBCATEGORY}_{ATTRIBUTE}_{UNIT}
"""

from pydantic import Field
from typing import List, Optional
from .base import BaseAppSettings


class IntegrationsSettings(BaseAppSettings):
    """Configuration for external API integrations and background tasks."""

    # ============================================================================
    # WhatsApp / Evolution API - Direct ENV names
    # ============================================================================
    WHATSAPP_ENABLE_SERVICE: bool = Field(
        default=True,
        description="Enable Evolution API WhatsApp integration"
    )
    WHATSAPP_EVOLUTION_API_URL: str = Field(
        default="http://localhost:8080",
        description="Evolution API base URL"
    )
    WHATSAPP_EVOLUTION_INSTANCE_NAME: str = Field(
        default="clinica_oncologica",
        description="Evolution instance name"
    )
    WHATSAPP_EVOLUTION_API_KEY: str = Field(
        default="your-evolution-api-key-here",
        description="Evolution API key"
    )
    WHATSAPP_EVOLUTION_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description=(
            "Evolution webhook secret for HMAC-SHA256 signature validation. "
            "CRITICAL SECURITY: Must be set in production to prevent webhook spoofing. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    )
    WHATSAPP_EVOLUTION_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Webhook URL for receiving Evolution API events"
    )

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
        default=False,
        description="Enable LangChain tracing"
    )
    AI_LANGCHAIN_API_KEY: Optional[str] = Field(
        default=None,
        description="LangChain API key"
    )

    # Google Gemini AI - Direct ENV names
    AI_GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key"
    )
    AI_GEMINI_MODEL: str = Field(
        default="gemini-2.0-flash-exp",
        description="Gemini model to use"
    )
    AI_GEMINI_TEMPERATURE: float = Field(
        default=0.7,
        description="Gemini generation temperature"
    )
    AI_GEMINI_MAX_OUTPUT_TOKENS: int = Field(
        default=500,
        description="Gemini max output tokens"
    )
    AI_GEMINI_TOP_P: float = Field(
        default=0.8,
        description="Gemini top-p parameter"
    )
    AI_GEMINI_TOP_K: int = Field(
        default=40,
        description="Gemini top-k parameter"
    )
    AI_GEMINI_TIMEOUT_SECONDS: int = Field(
        default=30,
        description="Gemini API timeout in seconds"
    )
    AI_GEMINI_MAX_RETRIES: int = Field(
        default=3,
        description="Gemini API max retries"
    )

    # AI Humanization Configuration - Direct ENV names
    AI_ENABLE_HUMANIZATION: bool = Field(
        default=True,
        description="Enable AI message humanization in flow engine"
    )
    AI_HUMANIZATION_ENABLE_SAFETY_MODE: bool = Field(
        default=True,
        description="Enable safety checks for critical message types"
    )
    AI_HUMANIZATION_MAX_RETRIES: int = Field(
        default=2,
        description="Maximum retries for AI humanization failures"
    )
    AI_HUMANIZATION_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        description="Timeout for AI humanization requests in seconds"
    )
    AI_HUMANIZATION_ENABLE_FALLBACK: bool = Field(
        default=True,
        description="Enable fallback to original message on AI failure"
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
    # Celery Configuration (Background Tasks) - Direct ENV names
    # ============================================================================
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0", description="Celery broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
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
    CELERY_ENABLE_TRACK_STARTED: bool = Field(
        default=True,
        description="Track task start events"
    )
    CELERY_WORKER_TIME_LIMIT_SECONDS: int = Field(
        default=300,
        description="Task time limit in seconds"
    )
    CELERY_WORKER_SOFT_TIME_LIMIT_SECONDS: int = Field(
        default=240,
        description="Task soft time limit in seconds"
    )
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(
        default=1000, description="Max tasks per worker child"
    )
    CELERY_ENABLE_DISABLE_RATE_LIMITS: bool = Field(
        default=True,
        description="Disable rate limits for workers"
    )
    CELERY_WORKER_CONCURRENCY: int = Field(
        default=4, description="Number of Celery worker processes"
    )
    CELERY_QUEUES: str = Field(
        default="celery,flows,quiz,maintenance,monitoring",
        description="Comma-separated list of Celery queues"
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
