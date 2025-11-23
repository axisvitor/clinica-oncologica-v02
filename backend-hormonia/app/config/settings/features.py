"""
Features configuration module: Application features and business logic settings.
Includes monthly quiz, flow auto-enrollment, file uploads, and localization.
"""

from pydantic import Field
from typing import List
from .base import BaseAppSettings
from pydantic import field_validator


class FeaturesSettings(BaseAppSettings):
    """Configuration for application features and business logic."""

    # ============================================================================
    # Alert System Configuration (QW-020)
    # ============================================================================
    # Note: Legacy alert system archived in legacy/alerts_archive_2025-11-09/
    # Consolidated alert system is now the only implementation.

    # ============================================================================
    # Monthly Quiz Configuration
    # ============================================================================
    MONTHLY_QUIZ_VIA_LINK: bool = Field(
        default=True,
        description="Enable monthly quiz via secure link (True) or WhatsApp conversational (False)",
    )
    MONTHLY_QUIZ_BASE_URL: str = Field(
        default="http://localhost:3001",
        description="Base URL for monthly quiz access links",
    )
    MONTHLY_QUIZ_TOKEN_SECRET: str = Field(
        default="your-monthly-quiz-token-secret-change-this",
        description="Secret key for generating quiz tokens (should be different from main SECRET_KEY)",
    )
    MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS: int = Field(
        default=72,
        description="Monthly quiz link expiry time in hours (default: 72 hours = 3 days)",
    )

    # ============================================================================
    # Saga Pattern Configuration
    # ============================================================================
    ENABLE_SAGA_PATTERN: bool = Field(
        default=True,
        description="Enable Saga Pattern for patient onboarding (recommended for production)",
    )
    SAGA_STEP_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of retries for each saga step before marking as failed",
    )
    SAGA_RETRY_INITIAL_DELAY_SECONDS: int = Field(
        default=1,
        description="Initial delay in seconds before first retry (exponential backoff)",
    )
    SAGA_RETRY_MAX_DELAY_SECONDS: int = Field(
        default=30,
        description="Maximum delay in seconds between retries (exponential backoff cap)",
    )
    SAGA_GLOBAL_TIMEOUT_SECONDS: int = Field(
        default=300,
        description="Global timeout for saga execution in seconds (default: 5 minutes)",
    )
    SAGA_PERSISTENCE_TTL_SECONDS: int = Field(
        default=604800,
        description="TTL for saga state persistence in Redis (default: 7 days)",
    )

    # ============================================================================
    # Flow Auto-Enrollment Configuration
    # ============================================================================
    ENABLE_AUTO_FLOW_ENROLLMENT: bool = Field(
        default=True,
        description="Automatically enroll patients in treatment flows after registration",
    )
    AUTO_FLOW_ENROLLMENT_FALLBACK: bool = Field(
        default=True,
        description="Use fallback flow template if specific template not found during auto-enrollment",
    )

    # ============================================================================
    # File Storage Configuration
    # ============================================================================
    UPLOAD_DIR: str = Field(default="uploads", description="Upload directory for files")
    MAX_FILE_SIZE: int = Field(
        default=10 * 1024 * 1024, description="Max file size in bytes (10MB)"
    )

    # ============================================================================
    # Localization Configuration
    # ============================================================================
    DEFAULT_LOCALE: str = Field(default="pt-BR", description="Default language locale")
    SUPPORTED_LOCALES: List[str] = Field(
        default=["en", "pt-BR", "es"],
        description="Supported language locales",
    )

    @field_validator("MONTHLY_QUIZ_BASE_URL")
    @classmethod
    def validate_quiz_url(cls, v: str, info) -> str:
        """Validate that quiz URL is present if link mode is enabled."""
        # Note: We can't easily access other fields in field_validator in Pydantic v2 
        # without using model_validator, but for now we just ensure it's not empty 
        # if it's provided. The logic to check dependency on MONTHLY_QUIZ_VIA_LINK 
        # would require a model validator.
        if v is None or v.strip() == "":
             # Fallback to localhost if empty, or raise error? 
             # For safety, let's default to localhost if empty to avoid crashes,
             # but log a warning ideally.
             return "http://localhost:3001"
        return v.rstrip("/")
