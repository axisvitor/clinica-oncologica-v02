"""
Features configuration module: Application features and business logic settings.
Includes monthly quiz, flow auto-enrollment, file uploads, and localization.
ENV Variable Naming Convention: {CATEGORY}_{SUBCATEGORY}_{ATTRIBUTE}_{UNIT}
"""

from pydantic import Field
from typing import List
from .base import BaseAppSettings
from pydantic import field_validator


class FeaturesSettings(BaseAppSettings):
    """Configuration for application features and business logic."""

    # ============================================================================
    # Monthly Quiz Configuration - Direct ENV names
    # ============================================================================
    QUIZ_ENABLE_VIA_LINK: bool = Field(
        default=True,
        description="Enable monthly quiz via secure link (True) or WhatsApp conversational (False)",
    )
    QUIZ_BASE_URL: str = Field(
        default="http://localhost:3001",
        description="Base URL for monthly quiz access links",
    )
    QUIZ_SHORT_BASE_URL: str = Field(
        default="",
        description="Base URL for short quiz links (optional, e.g., https://api.example.com/q)",
    )
    QUIZ_TOKEN_SECRET: str = Field(
        default="your-monthly-quiz-token-secret-change-this",
        description="Secret key for generating quiz tokens (should be different from main SECURITY_SECRET_KEY)",
    )
    QUIZ_TOKEN_EXPIRY_HOURS: int = Field(
        default=72,
        description="Monthly quiz link expiry time in hours (default: 72 hours = 3 days)",
    )

    # ============================================================================
    # Saga Pattern Configuration - Direct ENV names
    # ============================================================================
    TASK_SAGA_ENABLE_PATTERN: bool = Field(
        default=True,
        description="Enable Saga Pattern for patient onboarding (recommended for production)",
    )
    TASK_SAGA_STEP_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of retries for each saga step before marking as failed",
    )
    TASK_SAGA_RETRY_INITIAL_DELAY_SECONDS: int = Field(
        default=1,
        description="Initial delay in seconds before first retry (exponential backoff)",
    )
    TASK_SAGA_RETRY_MAX_DELAY_SECONDS: int = Field(
        default=30,
        description="Maximum delay in seconds between retries (exponential backoff cap)",
    )
    TASK_SAGA_GLOBAL_TIMEOUT_SECONDS: int = Field(
        default=300,
        description="Global timeout for saga execution in seconds (default: 5 minutes)",
    )
    TASK_SAGA_PERSISTENCE_TTL_SECONDS: int = Field(
        default=604800,
        description="TTL for saga state persistence in Redis (default: 7 days)",
    )
    TASK_SAGA_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retries for saga operations",
    )
    TASK_SAGA_RETRY_DELAY_SECONDS: int = Field(
        default=60,
        description="Base delay for saga retries in seconds",
    )

    # ============================================================================
    # Flow Auto-Enrollment Configuration - Direct ENV names
    # ============================================================================
    FLOW_ENABLE_AUTO_ENROLLMENT: bool = Field(
        default=True,
        description="Automatically enroll patients in treatment flows after registration",
    )
    FLOW_ENABLE_AUTO_ENROLLMENT_FALLBACK: bool = Field(
        default=True,
        description="Use fallback flow template if specific template not found during auto-enrollment",
    )

    # ============================================================================
    # File Storage Configuration - Direct ENV names
    # ============================================================================
    UPLOAD_DIRECTORY: str = Field(
        default="uploads", description="Upload directory for files"
    )
    UPLOAD_MAX_SIZE_BYTES: int = Field(
        default=10 * 1024 * 1024, description="Max file size in bytes (10MB)"
    )

    # ============================================================================
    # Data Retention Configuration - Direct ENV names
    # ============================================================================
    RETENTION_DATA_DAYS: int = Field(
        default=730, description="Data retention period in days (default: 2 years)"
    )
    RETENTION_AUDIT_LOG_DAYS: int = Field(
        default=365, description="Audit log retention period in days"
    )

    # ============================================================================
    # Localization Configuration
    # ============================================================================
    DEFAULT_LOCALE: str = Field(default="pt-BR", description="Default language locale")
    SUPPORTED_LOCALES: List[str] = Field(
        default=["en", "pt-BR", "es"],
        description="Supported language locales",
    )

    @field_validator("QUIZ_BASE_URL", mode="before")
    @classmethod
    def validate_quiz_url(cls, v: str) -> str:
        """Validate that quiz URL is present if link mode is enabled."""
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return "http://localhost:3001"
        return v.rstrip("/") if isinstance(v, str) else v

    @field_validator("QUIZ_SHORT_BASE_URL", mode="before")
    @classmethod
    def validate_quiz_short_url(cls, v: str) -> str:
        if v is None:
            return ""
        return v.rstrip("/") if isinstance(v, str) else v
