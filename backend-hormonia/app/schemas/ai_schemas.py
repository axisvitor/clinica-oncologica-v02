"""
Pydantic models for AI response validation.

Provides structured validation for AI-generated responses to ensure
schema compliance and graceful fallback on parsing failures.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class SentimentAnalysisResult(BaseModel):
    """Structured sentiment analysis result from AI."""

    sentiment: str = Field(
        default="neutral",
        description="Detected sentiment: positive, neutral, negative, or concerning",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1",
    )
    emotional_indicators: List[str] = Field(
        default_factory=list,
        description="Detected emotional indicators",
    )
    medical_concerns: bool = Field(
        default=False,
        description="Whether medical concerns were detected",
    )
    requires_attention: bool = Field(
        default=False,
        description="Whether the response requires human attention",
    )
    key_themes: List[str] = Field(
        default_factory=list,
        description="Key themes identified in the response",
    )
    suggested_follow_up: str = Field(
        default="standard",
        description="Type of follow-up recommended",
    )

    @validator("sentiment", pre=True, always=True)
    def normalize_sentiment(cls, v: Any) -> str:
        """Normalize sentiment to allowed values."""
        if not isinstance(v, str):
            return "neutral"
        normalized = v.strip().lower()
        allowed = {"positive", "neutral", "negative", "concerning"}
        return normalized if normalized in allowed else "neutral"

    @classmethod
    def fallback(cls) -> "SentimentAnalysisResult":
        """Return default fallback result."""
        return cls()


class ReminderIntentResult(BaseModel):
    """Structured reminder intent extraction result."""

    is_request: bool = Field(
        default=False,
        description="Whether this is a reminder request",
    )
    declined: bool = Field(
        default=False,
        description="Whether the user declined",
    )
    reminder_text: Optional[str] = Field(
        default=None,
        description="Extracted reminder text",
    )
    time_local: Optional[str] = Field(
        default=None,
        description="Extracted time in HH:MM format",
    )
    date_local: Optional[str] = Field(
        default=None,
        description="Extracted date in YYYY-MM-DD format",
    )
    recurrence: Optional[str] = Field(
        default=None,
        description="Recurrence pattern: none, daily, weekly, interval",
    )
    interval_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Interval in days for recurrence",
    )
    weekday: Optional[int] = Field(
        default=None,
        ge=0,
        le=6,
        description="Weekday (0=Monday, 6=Sunday)",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Extraction confidence",
    )

    @classmethod
    def fallback(cls) -> "ReminderIntentResult":
        """Return default fallback result."""
        return cls()


class EntityExtractionResult(BaseModel):
    """Structured entity extraction result."""

    entities: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of extracted entities",
    )
    symptoms: List[str] = Field(
        default_factory=list,
        description="Detected symptoms",
    )
    medications: List[str] = Field(
        default_factory=list,
        description="Mentioned medications",
    )
    concerns: List[str] = Field(
        default_factory=list,
        description="Medical concerns",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall extraction confidence",
    )

    @classmethod
    def fallback(cls) -> "EntityExtractionResult":
        """Return default fallback result."""
        return cls()


class AIResponseValidation:
    """Utility for validating AI responses with Pydantic models."""

    @staticmethod
    def validate_sentiment(data: Dict[str, Any]) -> SentimentAnalysisResult:
        """Validate sentiment analysis data."""
        try:
            return SentimentAnalysisResult(**data)
        except Exception:
            return SentimentAnalysisResult.fallback()

    @staticmethod
    def validate_reminder_intent(data: Dict[str, Any]) -> ReminderIntentResult:
        """Validate reminder intent data."""
        try:
            return ReminderIntentResult(**data)
        except Exception:
            return ReminderIntentResult.fallback()

    @staticmethod
    def validate_entities(data: Dict[str, Any]) -> EntityExtractionResult:
        """Validate entity extraction data."""
        try:
            return EntityExtractionResult(**data)
        except Exception:
            return EntityExtractionResult.fallback()
