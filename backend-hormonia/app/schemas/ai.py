"""
AI service request/response schemas for the Hormonia Backend System.

Provides Pydantic models for AI-powered features including chat, sentiment analysis,
patient insights, and recommendations.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


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


# ============================================================================
# Chat Endpoint Schemas
# ============================================================================


class ChatRequest(BaseModel):
    """Request schema for AI chat endpoint."""

    message: str = Field(
        ..., description="User message for AI chat", min_length=1, max_length=2000
    )
    patient_id: Optional[UUID] = Field(None, description="Optional patient context ID")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        default_factory=list, description="Previous conversation messages"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional context for the conversation"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "What are the common side effects of hormone therapy?",
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "conversation_history": [
                    {"role": "user", "content": "Hello"},
                    {
                        "role": "assistant",
                        "content": "Hello! How can I help you today?",
                    },
                ],
            }
        }
    )


class ChatResponse(BaseModel):
    """Response schema for AI chat endpoint."""

    message: str = Field(..., description="AI-generated response")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Response confidence score"
    )
    sources: Optional[List[str]] = Field(
        default_factory=list, description="Information sources used"
    )
    suggestions: Optional[List[str]] = Field(
        default_factory=list, description="Follow-up suggestions"
    )
    context_used: bool = Field(..., description="Whether patient context was used")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Common side effects of hormone therapy include hot flashes, mood changes, and fatigue...",
                "confidence": 0.92,
                "sources": ["Medical guidelines", "Patient data"],
                "suggestions": [
                    "Learn about managing side effects",
                    "Schedule follow-up",
                ],
                "context_used": True,
                "timestamp": "2024-01-01T12:00:00Z",
            }
        }
    )


# ============================================================================
# Analysis Endpoint Schemas
# ============================================================================


class AnalysisRequest(BaseModel):
    """Request schema for patient data analysis."""

    patient_id: UUID = Field(..., description="Patient ID to analyze")
    analysis_type: str = Field(
        "comprehensive",
        description="Type of analysis: comprehensive, treatment, adherence, risk",
    )
    date_range_days: Optional[int] = Field(
        30, ge=1, le=365, description="Number of days to analyze"
    )
    include_medical_history: bool = Field(
        True, description="Include medical history in analysis"
    )
    include_messages: bool = Field(
        True, description="Include message history in analysis"
    )

    @field_validator("analysis_type")
    @classmethod
    def validate_analysis_type(cls, v):
        valid_types = ["comprehensive", "treatment", "adherence", "risk", "sentiment"]
        if v not in valid_types:
            raise ValueError(f"analysis_type must be one of: {', '.join(valid_types)}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "analysis_type": "comprehensive",
                "date_range_days": 30,
                "include_medical_history": True,
                "include_messages": True,
            }
        }
    )


class AnalysisResponse(BaseModel):
    """Response schema for patient analysis."""

    patient_id: UUID = Field(..., description="Analyzed patient ID")
    analysis_type: str = Field(..., description="Type of analysis performed")
    summary: str = Field(..., description="Analysis summary")
    key_findings: List[str] = Field(..., description="Key findings from analysis")
    risk_factors: List[Dict[str, Any]] = Field(
        default_factory=list, description="Identified risk factors"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Clinical recommendations"
    )
    data_quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Quality score of analyzed data"
    )
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "analysis_type": "comprehensive",
                "summary": "Patient showing good treatment adherence with mild side effects...",
                "key_findings": [
                    "85% treatment adherence over 30 days",
                    "Mild fatigue reported in 40% of check-ins",
                ],
                "risk_factors": [
                    {"factor": "Missed medication", "severity": "low", "frequency": 2}
                ],
                "recommendations": [
                    "Continue current treatment plan",
                    "Monitor fatigue levels",
                ],
                "data_quality_score": 0.87,
                "analyzed_at": "2024-01-01T12:00:00Z",
            }
        }
    )


# ============================================================================
# Generate Response Endpoint Schemas
# ============================================================================


class GenerateResponseRequest(BaseModel):
    """Request schema for generating AI responses."""

    template_message: str = Field(..., description="Template message to personalize")
    patient_id: UUID = Field(..., description="Patient ID for context")
    message_type: str = Field(
        "general",
        description="Message type: welcome, check_in, reminder, support, education",
    )
    tone: str = Field(
        "empathetic",
        description="Response tone: empathetic, professional, encouraging, neutral",
    )
    max_length: Optional[int] = Field(
        500, ge=50, le=2000, description="Maximum response length"
    )

    @field_validator("message_type")
    @classmethod
    def validate_message_type(cls, v):
        valid_types = [
            "general",
            "welcome",
            "check_in",
            "reminder",
            "support",
            "education",
        ]
        if v not in valid_types:
            raise ValueError(f"message_type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("tone")
    @classmethod
    def validate_tone(cls, v):
        valid_tones = ["empathetic", "professional", "encouraging", "neutral", "caring"]
        if v not in valid_tones:
            raise ValueError(f"tone must be one of: {', '.join(valid_tones)}")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_message": "Time to take your medication",
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "message_type": "reminder",
                "tone": "empathetic",
                "max_length": 300,
            }
        }
    )


class GenerateResponseResponse(BaseModel):
    """Response schema for generated AI responses."""

    original_message: str = Field(..., description="Original template message")
    generated_message: str = Field(..., description="AI-generated personalized message")
    personalization_notes: List[str] = Field(
        default_factory=list, description="Notes on personalization applied"
    )
    readability_score: float = Field(
        ..., ge=0.0, le=100.0, description="Readability score (higher is better)"
    )
    tone_analysis: Dict[str, float] = Field(
        default_factory=dict, description="Tone analysis scores"
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "original_message": "Time to take your medication",
                "generated_message": "Hi Maria! Just a gentle reminder about your medication. You've been doing great with your routine! 💊",
                "personalization_notes": [
                    "Added patient name",
                    "Used encouraging tone",
                    "Referenced treatment progress",
                ],
                "readability_score": 87.5,
                "tone_analysis": {"empathy": 0.9, "professionalism": 0.8},
                "generated_at": "2024-01-01T12:00:00Z",
            }
        }
    )


# ============================================================================
# Sentiment Analysis Endpoint Schemas
# ============================================================================


class SentimentAnalysisRequest(BaseModel):
    """Request schema for sentiment analysis."""

    message: str = Field(
        ..., description="Message to analyze", min_length=1, max_length=5000
    )
    patient_id: Optional[UUID] = Field(None, description="Optional patient context")
    include_medical_concerns: bool = Field(
        True, description="Include medical concern detection"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "I've been feeling very tired lately and having trouble sleeping",
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "include_medical_concerns": True,
            }
        }
    )


class SentimentAnalysisResponse(BaseModel):
    """Response schema for sentiment analysis."""

    message: str = Field(..., description="Analyzed message")
    sentiment: SentimentType = Field(
        ..., description="Overall sentiment classification"
    )
    concern_level: ConcernLevel = Field(..., description="Medical concern level")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Analysis confidence")
    key_phrases: List[str] = Field(
        default_factory=list, description="Key phrases extracted"
    )
    medical_concerns: List[str] = Field(
        default_factory=list, description="Identified medical concerns"
    )
    urgency_indicators: List[str] = Field(
        default_factory=list, description="Urgency indicators detected"
    )
    emotion_scores: Dict[str, float] = Field(
        default_factory=dict, description="Emotion analysis scores"
    )
    recommended_action: Optional[str] = Field(
        None, description="Recommended action based on analysis"
    )
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "I've been feeling very tired lately",
                "sentiment": "concerning",
                "concern_level": "medium",
                "confidence": 0.88,
                "key_phrases": ["feeling tired", "trouble sleeping"],
                "medical_concerns": ["fatigue", "sleep disturbance"],
                "urgency_indicators": ["very tired"],
                "emotion_scores": {"anxiety": 0.3, "fatigue": 0.8},
                "recommended_action": "Schedule follow-up consultation",
                "analyzed_at": "2024-01-01T12:00:00Z",
            }
        }
    )


# ============================================================================
# Patient Insights Endpoint Schemas
# ============================================================================


class TrendData(BaseModel):
    """Trend data structure."""

    metric: str = Field(..., description="Metric name")
    direction: str = Field(
        ..., description="Trend direction: improving, declining, stable"
    )
    change_percentage: float = Field(..., description="Percentage change")
    data_points: List[Dict[str, Any]] = Field(
        default_factory=list, description="Time series data points"
    )


class InsightResponse(BaseModel):
    """Response schema for patient insights."""

    patient_id: UUID = Field(..., description="Patient ID")
    overall_status: str = Field(..., description="Overall patient status summary")
    risk_level: RiskLevel = Field(..., description="Current risk assessment")
    sentiment_trends: List[TrendData] = Field(
        default_factory=list, description="Sentiment trend analysis"
    )
    adherence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Treatment adherence score"
    )
    key_insights: List[str] = Field(..., description="Key insights about patient")
    alerts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Active alerts and warnings"
    )
    engagement_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Patient engagement metrics"
    )
    last_contact: Optional[datetime] = Field(None, description="Last contact datetime")
    insights_generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "overall_status": "Patient is responding well to treatment with minor side effects",
                "risk_level": "low",
                "sentiment_trends": [
                    {
                        "metric": "mood",
                        "direction": "improving",
                        "change_percentage": 15.5,
                        "data_points": [],
                    }
                ],
                "adherence_score": 0.87,
                "key_insights": [
                    "High engagement with daily check-ins",
                    "Consistent medication adherence",
                ],
                "alerts": [],
                "engagement_metrics": {
                    "response_rate": 0.92,
                    "avg_response_time_hours": 2.5,
                },
                "last_contact": "2024-01-01T10:00:00Z",
                "insights_generated_at": "2024-01-01T12:00:00Z",
            }
        }
    )


# ============================================================================
# Recommendations Endpoint Schemas
# ============================================================================


class ActionItem(BaseModel):
    """Action item structure."""

    title: str = Field(..., description="Action item title")
    description: str = Field(..., description="Detailed description")
    priority: str = Field(..., description="Priority: high, medium, low")
    category: str = Field(
        ..., description="Category: clinical, educational, support, administrative"
    )
    estimated_impact: str = Field(..., description="Expected impact: high, medium, low")
    due_date: Optional[datetime] = Field(None, description="Recommended due date")


class RecommendationResponse(BaseModel):
    """Response schema for AI recommendations."""

    patient_id: UUID = Field(..., description="Patient ID")
    recommendations_summary: str = Field(..., description="Summary of recommendations")
    action_items: List[ActionItem] = Field(..., description="Recommended action items")
    clinical_insights: List[str] = Field(
        default_factory=list, description="Clinical insights for physicians"
    )
    patient_education: List[str] = Field(
        default_factory=list, description="Educational content suggestions"
    )
    intervention_suggestions: List[Dict[str, Any]] = Field(
        default_factory=list, description="Suggested interventions"
    )
    follow_up_schedule: Optional[Dict[str, Any]] = Field(
        None, description="Recommended follow-up schedule"
    )
    confidence_level: float = Field(
        ..., ge=0.0, le=1.0, description="Overall recommendation confidence"
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "recommendations_summary": "Patient showing good progress, minor adjustments suggested",
                "action_items": [
                    {
                        "title": "Schedule follow-up consultation",
                        "description": "Review treatment progress and side effects",
                        "priority": "medium",
                        "category": "clinical",
                        "estimated_impact": "high",
                        "due_date": "2024-01-15T00:00:00Z",
                    }
                ],
                "clinical_insights": [
                    "Patient responding well to current dosage",
                    "Minor fatigue noted, consider vitamin supplementation",
                ],
                "patient_education": [
                    "Managing fatigue during hormone therapy",
                    "Importance of regular check-ins",
                ],
                "intervention_suggestions": [],
                "follow_up_schedule": {
                    "next_check_in": "2024-01-08T00:00:00Z",
                    "frequency": "weekly",
                },
                "confidence_level": 0.85,
                "generated_at": "2024-01-01T12:00:00Z",
            }
        }
    )


# ============================================================================
# Summary Endpoint Schemas
# ============================================================================


class PatientSummaryResponse(BaseModel):
    """Comprehensive AI-generated patient summary."""

    patient_id: UUID = Field(..., description="Patient ID")
    summary_text: str = Field(..., description="Comprehensive summary text")
    treatment_overview: Dict[str, Any] = Field(
        default_factory=dict, description="Treatment overview"
    )
    clinical_highlights: List[str] = Field(
        default_factory=list, description="Key clinical highlights"
    )
    recent_concerns: List[Dict[str, Any]] = Field(
        default_factory=list, description="Recent medical concerns"
    )
    progress_indicators: Dict[str, Any] = Field(
        default_factory=dict, description="Progress indicators"
    )
    risk_assessment: Dict[str, Any] = Field(
        default_factory=dict, description="Current risk assessment"
    )
    next_steps: List[str] = Field(
        default_factory=list, description="Recommended next steps"
    )
    data_completeness: float = Field(
        ..., ge=0.0, le=1.0, description="Completeness of available data"
    )
    summary_generated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "summary_text": "Maria is a 45-year-old patient undergoing hormone therapy showing excellent adherence...",
                "treatment_overview": {
                    "type": "hormone_therapy",
                    "duration_days": 45,
                    "current_phase": "active",
                },
                "clinical_highlights": [
                    "87% treatment adherence",
                    "Mild side effects managed well",
                ],
                "recent_concerns": [
                    {
                        "concern": "Occasional fatigue",
                        "severity": "low",
                        "date": "2024-01-01T00:00:00Z",
                    }
                ],
                "progress_indicators": {
                    "engagement": "high",
                    "symptom_management": "good",
                    "adherence": "excellent",
                },
                "risk_assessment": {"level": "low", "factors": []},
                "next_steps": [
                    "Continue current treatment",
                    "Monitor fatigue levels",
                    "Schedule monthly follow-up",
                ],
                "data_completeness": 0.92,
                "summary_generated_at": "2024-01-01T12:00:00Z",
            }
        }
    )


# ============================================================================
# Error Response Schema
# ============================================================================


class AIErrorResponse(BaseModel):
    """Error response schema for AI endpoints."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ai_service_error",
                "message": "Failed to generate AI response",
                "details": {"reason": "Service temporarily unavailable"},
                "timestamp": "2024-01-01T12:00:00Z",
            }
        }
    )
