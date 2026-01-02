"""
AI Service Schemas for API v2
Enhanced schemas with modern patterns, validation, and cost tracking.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict, constr, conint
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ============================================================================
# Enums
# ============================================================================


class SentimentType(str, Enum):
    """Sentiment classification types."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    CONCERNING = "concerning"


class ConcernLevel(str, Enum):
    """Medical concern severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    """Patient risk assessment levels."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class AIModelType(str, Enum):
    """AI model types for tracking."""

    GEMINI_PRO = "gemini-pro"
    GEMINI_FLASH = "gemini-flash"
    GPT4 = "gpt-4"
    GPT35 = "gpt-3.5-turbo"


# ============================================================================
# Token Usage Tracking
# ============================================================================


class TokenUsage(BaseModel):
    """Token usage for billing and monitoring."""

    prompt_tokens: int = Field(0, ge=0, description="Tokens in prompt")
    completion_tokens: int = Field(0, ge=0, description="Tokens in completion")
    total_tokens: int = Field(0, ge=0, description="Total tokens used")
    estimated_cost_usd: float = Field(0.0, ge=0.0, description="Estimated cost in USD")
    model: Optional[AIModelType] = Field(None, description="AI model used")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompt_tokens": 150,
                "completion_tokens": 75,
                "total_tokens": 225,
                "estimated_cost_usd": 0.0034,
                "model": "gemini-pro",
            }
        }
    )


class CacheInfo(BaseModel):
    """Cache hit/miss information."""

    hit: bool = Field(description="Whether response was from cache")
    key: Optional[str] = Field(None, description="Cache key used")
    ttl_seconds: Optional[int] = Field(None, description="TTL in seconds")
    cached_at: Optional[datetime] = Field(None, description="When data was cached")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hit": True,
                "key": "ai:humanize:abc123",
                "ttl_seconds": 7200,
                "cached_at": "2025-01-17T10:00:00Z",
            }
        }
    )


# ============================================================================
# Humanize Endpoints
# ============================================================================


class HumanizeRequest(BaseModel):
    """Request to humanize a message."""

    message: constr(min_length=1, max_length=2000) = Field(
        ..., description="Message to humanize"
    )
    patient_id: Optional[UUID] = Field(None, description="Patient context ID")
    message_type: str = Field(
        "general",
        description="Message type: welcome, check_in, reminder, support, education, general",
    )
    tone: str = Field(
        "empathetic",
        description="Desired tone: empathetic, professional, encouraging, caring, neutral",
    )
    max_length: conint(ge=50, le=2000) = Field(
        500, description="Maximum response length"
    )
    use_cache: bool = Field(True, description="Whether to use cached responses")

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, v):
        valid = ["welcome", "check_in", "reminder", "support", "education", "general"]
        if v not in valid:
            raise ValueError(f"message_type must be one of: {', '.join(valid)}")
        return v

    @field_validator("tone")
    @classmethod
    def validate_tone(cls, v):
        valid = ["empathetic", "professional", "encouraging", "caring", "neutral"]
        if v not in valid:
            raise ValueError(f"tone must be one of: {', '.join(valid)}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Time to take your medication",
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "message_type": "reminder",
                "tone": "empathetic",
                "max_length": 300,
                "use_cache": True,
            }
        }
    )


class HumanizeResponse(BaseModel):
    """Response from humanize endpoint."""

    original_message: str = Field(description="Original message")
    humanized_message: str = Field(description="AI-humanized message")
    personalization_notes: List[str] = Field(
        default_factory=list, description="Notes on personalization applied"
    )
    readability_score: float = Field(
        ge=0.0, le=100.0, description="Readability score (0-100)"
    )
    tone_analysis: Dict[str, float] = Field(
        default_factory=dict, description="Tone metrics (0-1)"
    )
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage stats")
    cache_info: Optional[CacheInfo] = Field(None, description="Cache information")
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "original_message": "Time to take your medication",
                "humanized_message": "Hi Maria! Just a gentle reminder about your medication. Keep up the great work! 💊",
                "personalization_notes": [
                    "Added patient name",
                    "Used encouraging tone",
                ],
                "readability_score": 87.5,
                "tone_analysis": {"empathy": 0.9, "professionalism": 0.8},
                "token_usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 45,
                    "total_tokens": 165,
                    "estimated_cost_usd": 0.0025,
                    "model": "gemini-pro",
                },
                "cache_info": {
                    "hit": False,
                    "key": "ai:humanize:xyz",
                    "ttl_seconds": 7200,
                },
                "generated_at": "2025-01-17T10:00:00Z",
            }
        }
    )


class BatchHumanizeRequest(BaseModel):
    """Batch humanize request."""

    messages: List[HumanizeRequest] = Field(
        ..., min_length=1, max_length=10, description="Messages to humanize (max 10)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "messages": [
                    {
                        "message": "Time for medication",
                        "message_type": "reminder",
                        "tone": "empathetic",
                    },
                    {
                        "message": "How are you feeling?",
                        "message_type": "check_in",
                        "tone": "caring",
                    },
                ]
            }
        }
    )


class BatchHumanizeResponse(BaseModel):
    """Batch humanize response."""

    results: List[HumanizeResponse] = Field(description="Humanized messages")
    total_token_usage: TokenUsage = Field(description="Total token usage")
    cache_hit_rate: float = Field(ge=0.0, le=1.0, description="Cache hit rate (0-1)")
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [],
                "total_token_usage": {
                    "total_tokens": 450,
                    "estimated_cost_usd": 0.0068,
                },
                "cache_hit_rate": 0.3,
                "processed_at": "2025-01-17T10:00:00Z",
            }
        }
    )


# ============================================================================
# Insights Endpoints
# ============================================================================


class GenerateInsightsRequest(BaseModel):
    """Request to generate AI insights."""

    patient_id: UUID = Field(description="Patient ID")
    analysis_type: str = Field(
        "comprehensive",
        description="Analysis type: comprehensive, treatment, adherence, risk, sentiment",
    )
    days: conint(ge=1, le=90) = Field(30, description="Days to analyze")
    include_medical_history: bool = Field(True, description="Include medical history")
    include_messages: bool = Field(True, description="Include message analysis")
    force_refresh: bool = Field(False, description="Force cache refresh")

    @field_validator("analysis_type")
    @classmethod
    def validate_analysis_type(cls, v):
        valid = ["comprehensive", "treatment", "adherence", "risk", "sentiment"]
        if v not in valid:
            raise ValueError(f"analysis_type must be one of: {', '.join(valid)}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "analysis_type": "comprehensive",
                "days": 30,
                "include_medical_history": True,
                "include_messages": True,
                "force_refresh": False,
            }
        }
    )


class TrendData(BaseModel):
    """Trend analysis data."""

    metric: str = Field(description="Metric name")
    direction: str = Field(description="Trend direction: improving, declining, stable")
    change_percentage: float = Field(description="Percentage change")
    current_value: Optional[float] = Field(None, description="Current value")
    previous_value: Optional[float] = Field(None, description="Previous value")
    data_points: List[Dict[str, Any]] = Field(
        default_factory=list, description="Time series data points"
    )


class InsightsResponse(BaseModel):
    """AI-generated patient insights."""

    patient_id: UUID = Field(description="Patient ID")
    overall_status: str = Field(description="Overall status summary")
    risk_level: RiskLevel = Field(description="Current risk level")
    sentiment_trends: List[TrendData] = Field(
        default_factory=list, description="Sentiment trends"
    )
    adherence_score: float = Field(
        ge=0.0, le=1.0, description="Treatment adherence score (0-1)"
    )
    key_insights: List[str] = Field(description="Key insights")
    alerts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Active alerts"
    )
    engagement_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Engagement metrics"
    )
    last_contact: Optional[datetime] = Field(None, description="Last contact time")
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage")
    cache_info: Optional[CacheInfo] = Field(None, description="Cache info")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class PatientInsightsRequest(BaseModel):
    """Request for patient-specific insights."""

    days: conint(ge=1, le=90) = Field(30, description="Days to analyze")
    force_refresh: bool = Field(False, description="Force cache refresh")


# ============================================================================
# Analysis Endpoints
# ============================================================================


class SentimentAnalysisRequest(BaseModel):
    """Request for sentiment analysis."""

    message: constr(min_length=1, max_length=5000) = Field(
        ..., description="Message to analyze"
    )
    patient_id: Optional[UUID] = Field(None, description="Patient context")
    include_medical_concerns: bool = Field(True, description="Detect medical concerns")
    include_urgency: bool = Field(True, description="Detect urgency indicators")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "I've been feeling very tired lately",
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "include_medical_concerns": True,
                "include_urgency": True,
            }
        }
    )


class SentimentAnalysisResponse(BaseModel):
    """Sentiment analysis result."""

    message: str = Field(description="Analyzed message")
    sentiment: SentimentType = Field(description="Sentiment classification")
    concern_level: ConcernLevel = Field(description="Concern level")
    confidence: float = Field(ge=0.0, le=1.0, description="Analysis confidence")
    key_phrases: List[str] = Field(default_factory=list, description="Key phrases")
    medical_concerns: List[str] = Field(
        default_factory=list, description="Medical concerns detected"
    )
    urgency_indicators: List[str] = Field(
        default_factory=list, description="Urgency indicators"
    )
    emotion_scores: Dict[str, float] = Field(
        default_factory=dict, description="Emotion scores (0-1)"
    )
    recommended_action: Optional[str] = Field(None, description="Recommended action")
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class RiskAnalysisRequest(BaseModel):
    """Request for risk analysis."""

    patient_id: UUID = Field(description="Patient ID")
    days: conint(ge=1, le=90) = Field(30, description="Days to analyze")
    include_historical: bool = Field(True, description="Include historical data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "days": 30,
                "include_historical": True,
            }
        }
    )


class RiskAnalysisResponse(BaseModel):
    """Risk analysis result."""

    patient_id: UUID = Field(description="Patient ID")
    risk_level: RiskLevel = Field(description="Overall risk level")
    risk_score: float = Field(ge=0.0, le=1.0, description="Risk score (0-1)")
    risk_factors: List[Dict[str, Any]] = Field(
        default_factory=list, description="Identified risk factors"
    )
    protective_factors: List[str] = Field(
        default_factory=list, description="Protective factors"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Risk mitigation recommendations"
    )
    trend: str = Field(description="Risk trend: increasing, decreasing, stable")
    confidence: float = Field(ge=0.0, le=1.0, description="Analysis confidence")
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class ResponseQualityRequest(BaseModel):
    """Request for response quality analysis."""

    message: constr(min_length=1, max_length=2000) = Field(
        ..., description="Message to analyze"
    )
    context: Optional[str] = Field(None, description="Message context")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Hi! Hope you're doing well today.",
                "context": "greeting",
            }
        }
    )


class ResponseQualityResponse(BaseModel):
    """Response quality analysis."""

    message: str = Field(description="Analyzed message")
    quality_score: float = Field(ge=0.0, le=100.0, description="Quality score (0-100)")
    readability_score: float = Field(
        ge=0.0, le=100.0, description="Readability (0-100)"
    )
    empathy_score: float = Field(ge=0.0, le=1.0, description="Empathy score (0-1)")
    professionalism_score: float = Field(
        ge=0.0, le=1.0, description="Professionalism (0-1)"
    )
    clarity_score: float = Field(ge=0.0, le=1.0, description="Clarity score (0-1)")
    suggestions: List[str] = Field(
        default_factory=list, description="Improvement suggestions"
    )
    strengths: List[str] = Field(default_factory=list, description="Message strengths")
    token_usage: Optional[TokenUsage] = Field(None, description="Token usage")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Health & Stats
# ============================================================================


class AIHealthResponse(BaseModel):
    """AI service health status."""

    status: str = Field(description="Overall status: healthy, degraded, unhealthy")
    services: Dict[str, str] = Field(description="Individual service statuses")
    redis_cache: Dict[str, Any] = Field(description="Redis cache status")
    gemini_api: Dict[str, Any] = Field(description="Gemini API status")
    response_time_ms: float = Field(description="Health check response time")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "services": {
                    "humanizer": "operational",
                    "sentiment_analyzer": "operational",
                    "insights_generator": "operational",
                },
                "redis_cache": {
                    "status": "operational",
                    "hit_rate": 0.73,
                    "keys": 1250,
                },
                "gemini_api": {"status": "operational", "latency_ms": 245},
                "response_time_ms": 12.5,
                "timestamp": "2025-01-17T10:00:00Z",
            }
        }
    )


class UsageStatsResponse(BaseModel):
    """Token usage statistics."""

    period: str = Field(description="Time period: hour, day, week, month")
    total_requests: int = Field(ge=0, description="Total API requests")
    total_tokens: int = Field(ge=0, description="Total tokens used")
    total_cost_usd: float = Field(ge=0.0, description="Total cost in USD")
    by_endpoint: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Usage by endpoint"
    )
    by_model: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Usage by AI model"
    )
    cache_hit_rate: float = Field(ge=0.0, le=1.0, description="Overall cache hit rate")
    cost_savings_usd: float = Field(ge=0.0, description="Cost savings from caching")
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period": "day",
                "total_requests": 1250,
                "total_tokens": 187500,
                "total_cost_usd": 28.45,
                "by_endpoint": {
                    "humanize": {"requests": 800, "tokens": 120000, "cost_usd": 18.20}
                },
                "by_model": {
                    "gemini-pro": {
                        "requests": 1000,
                        "tokens": 150000,
                        "cost_usd": 22.50,
                    }
                },
                "cache_hit_rate": 0.68,
                "cost_savings_usd": 12.30,
                "generated_at": "2025-01-17T10:00:00Z",
            }
        }
    )


class CacheStatsResponse(BaseModel):
    """Cache statistics."""

    total_keys: int = Field(ge=0, description="Total cache keys")
    hit_rate: float = Field(ge=0.0, le=1.0, description="Cache hit rate")
    miss_rate: float = Field(ge=0.0, le=1.0, description="Cache miss rate")
    total_hits: int = Field(ge=0, description="Total cache hits")
    total_misses: int = Field(ge=0, description="Total cache misses")
    memory_usage_mb: float = Field(ge=0.0, description="Memory usage in MB")
    by_endpoint: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Stats by endpoint"
    )
    oldest_entry_age_seconds: Optional[int] = Field(
        None, description="Age of oldest entry"
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_keys": 3450,
                "hit_rate": 0.72,
                "miss_rate": 0.28,
                "total_hits": 8640,
                "total_misses": 3360,
                "memory_usage_mb": 145.7,
                "by_endpoint": {
                    "humanize": {"keys": 1500, "hit_rate": 0.85, "ttl_seconds": 7200}
                },
                "oldest_entry_age_seconds": 7190,
                "generated_at": "2025-01-17T10:00:00Z",
            }
        }
    )


# ============================================================================
# Error Responses
# ============================================================================


class AIErrorResponse(BaseModel):
    """AI service error response."""

    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    fallback_used: bool = Field(False, description="Whether fallback response was used")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Recommendations Endpoints
# ============================================================================


class RecommendationItem(BaseModel):
    """Individual recommendation item."""
    
    type: str = Field(description="Type of recommendation")
    priority: str = Field(description="Priority: low, medium, high")
    description: str = Field(description="Description")
    rationale: str = Field(description="Why this is recommended")


class AIRecommendations(BaseModel):
    """AI recommendations response."""
    
    patient_id: UUID = Field(description="Patient ID")
    recommendations: List[RecommendationItem] = Field(
        default_factory=list, description="List of recommendations"
    )
