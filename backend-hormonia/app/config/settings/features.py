"""
Features configuration module: Application features and business logic settings.
Includes monthly quiz, flow auto-enrollment, file uploads, and localization.
"""

from pydantic import Field
from typing import List
from .base import BaseAppSettings


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
