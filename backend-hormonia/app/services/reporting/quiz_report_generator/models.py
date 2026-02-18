"""
Data models for quiz response processing and report generation.
"""

from __future__ import annotations

from typing import Any, List, Optional
from datetime import datetime
from uuid import UUID
from enum import Enum
from dataclasses import dataclass, field
from app.utils.timezone import now_sao_paulo_naive


class TrendDirection(Enum):
    """Trend direction indicators."""

    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    INSUFFICIENT_DATA = "insufficient_data"


class ConcernLevel(Enum):
    """Medical concern levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QuizMetrics:
    """Quiz response metrics."""

    session_id: UUID
    patient_id: UUID
    template_id: UUID
    completion_date: datetime
    total_questions: int
    answered_questions: int
    completion_rate: float
    average_response_time: Optional[float] = None
    response_quality_score: float = 0.0


@dataclass
class ResponseTrend:
    """Response trend analysis."""

    question_id: str
    question_text: str
    current_value: Any
    previous_values: List[Any]
    trend_direction: TrendDirection
    change_percentage: Optional[float] = None
    significance_score: float = 0.0


@dataclass
class MedicalInsight:
    """Medical insight from quiz analysis."""

    insight_type: str
    description: str
    concern_level: ConcernLevel
    recommendations: List[str]
    supporting_data: dict[str, Any]
    confidence_score: float


@dataclass
class QuizAnalysisResult:
    """Complete quiz analysis result."""

    session_id: UUID
    patient_id: UUID
    metrics: QuizMetrics
    response_trends: List[ResponseTrend]
    medical_insights: List[MedicalInsight]
    overall_health_score: float
    concern_flags: List[str]
    recommendations: List[str]
    analysis_timestamp: datetime = field(default_factory=now_sao_paulo_naive)
