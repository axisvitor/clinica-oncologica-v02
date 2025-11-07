"""
Enhanced Analytics schemas for API v2
Complex analytics models with validation and examples.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


# Enums for analytics parameters
class TimeRange(str, Enum):
    """Time range options for analytics queries."""
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    LAST_6_MONTHS = "6m"
    LAST_YEAR = "1y"
    CUSTOM = "custom"


class MetricType(str, Enum):
    """Metric type categories."""
    PATIENTS = "patients"
    QUIZ = "quiz"
    MESSAGES = "messages"
    FLOWS = "flows"
    ENGAGEMENT = "engagement"
    OUTCOMES = "outcomes"


class AggregationLevel(str, Enum):
    """Data aggregation levels."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class CohortFilter(str, Enum):
    """Patient cohort filter types."""
    ALL = "all"
    NEW_PATIENTS = "new_patients"
    ACTIVE = "active"
    HIGH_ENGAGEMENT = "high_engagement"
    LOW_ENGAGEMENT = "low_engagement"
    AT_RISK = "at_risk"


class FunnelStage(str, Enum):
    """Engagement funnel stages."""
    ENROLLED = "enrolled"
    FIRST_QUIZ_SENT = "first_quiz_sent"
    FIRST_QUIZ_COMPLETED = "first_quiz_completed"
    CONSISTENT_ENGAGEMENT = "consistent_engagement"
    HIGH_ENGAGEMENT = "high_engagement"


class ExportFormat(str, Enum):
    """Export file formats."""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


class AggregationType(str, Enum):
    """Custom metric aggregation types."""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"


# Response Models

class EnhancedDashboardMetrics(BaseModel):
    """Enhanced dashboard metrics with advanced analytics."""

    time_range: str = Field(..., description="Selected time range")
    period: Dict[str, str] = Field(..., description="Date range")
    metrics: Dict[str, Any] = Field(..., description="Core KPI metrics")
    risk_stratification: Dict[str, int] = Field(..., description="Risk level distribution")
    treatment_distribution: Dict[str, int] = Field(..., description="Patients by treatment type")
    alerts: Dict[str, int] = Field(..., description="System alerts by severity")
    generated_at: str = Field(..., description="Generation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "time_range": "30d",
                "period": {
                    "start_date": "2025-01-01T00:00:00Z",
                    "end_date": "2025-01-31T23:59:59Z"
                },
                "metrics": {
                    "total_patients": 150,
                    "active_patients": 120,
                    "new_patients": 15,
                    "patient_growth_rate": 12.5,
                    "total_quizzes": 450,
                    "completed_quizzes": 380,
                    "completion_rate": 84.44,
                    "avg_response_time_hours": 2.5,
                    "engagement_score": 78.5
                },
                "risk_stratification": {
                    "high_risk": 10,
                    "medium_risk": 30,
                    "low_risk": 110
                },
                "treatment_distribution": {
                    "Quimioterapia": 60,
                    "Radioterapia": 45,
                    "Imunoterapia": 30
                },
                "alerts": {
                    "critical": 2,
                    "warning": 5,
                    "info": 12
                },
                "generated_at": "2025-01-31T12:00:00Z"
            }
        }


class CohortMetrics(BaseModel):
    """Cohort-level metrics."""

    cohort_size: int = Field(..., ge=0, description="Number of patients in cohort")
    total_matching: int = Field(..., ge=0, description="Total patients matching filter")
    avg_quizzes_per_patient: float = Field(..., ge=0, description="Average quizzes per patient")
    completion_rate: float = Field(..., ge=0, le=100, description="Quiz completion rate %")
    retention_rate: float = Field(..., ge=0, le=100, description="Patient retention rate %")


class Demographics(BaseModel):
    """Demographic breakdown for cohort."""

    treatment_breakdown: Dict[str, int] = Field(..., description="Patients by treatment type")
    age_distribution: Dict[str, int] = Field(default_factory=dict, description="Patients by age group")


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    limit: int = Field(..., ge=1, le=200, description="Results per page")
    cursor: Optional[str] = Field(None, description="Current cursor position")
    next_cursor: Optional[str] = Field(None, description="Next page cursor")
    has_more: bool = Field(..., description="More results available")


class PatientCohortAnalysis(BaseModel):
    """Patient cohort analysis with segmentation."""

    cohort_filter: str = Field(..., description="Applied cohort filter")
    time_range: str = Field(..., description="Analysis time range")
    period: Dict[str, str] = Field(..., description="Date range")
    cohort_metrics: CohortMetrics = Field(..., description="Cohort metrics")
    demographics: Demographics = Field(..., description="Demographic breakdown")
    pagination: PaginationInfo = Field(..., description="Pagination info")
    generated_at: str = Field(..., description="Generation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "cohort_filter": "high_engagement",
                "time_range": "90d",
                "period": {
                    "start_date": "2024-11-01T00:00:00Z",
                    "end_date": "2025-01-31T23:59:59Z"
                },
                "cohort_metrics": {
                    "cohort_size": 50,
                    "total_matching": 50,
                    "avg_quizzes_per_patient": 8.5,
                    "completion_rate": 92.3,
                    "retention_rate": 87.5
                },
                "demographics": {
                    "treatment_breakdown": {
                        "Quimioterapia": 25,
                        "Radioterapia": 15,
                        "Imunoterapia": 10
                    },
                    "age_distribution": {
                        "18-30": 5,
                        "31-50": 20,
                        "51-70": 20,
                        "70+": 5
                    }
                },
                "pagination": {
                    "limit": 50,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": False
                },
                "generated_at": "2025-01-31T12:00:00Z"
            }
        }


class FunnelStageMetrics(BaseModel):
    """Metrics for a single funnel stage."""

    stage: str = Field(..., description="Funnel stage name")
    count: int = Field(..., ge=0, description="Patients at this stage")
    conversion_rate: float = Field(..., ge=0, le=100, description="Conversion rate from previous stage %")
    drop_off_rate: float = Field(..., ge=0, le=100, description="Drop-off rate from previous stage %")


class EngagementFunnelMetrics(BaseModel):
    """Engagement funnel analysis."""

    time_range: str = Field(..., description="Analysis time range")
    period: Dict[str, str] = Field(..., description="Date range")
    treatment_type: Optional[str] = Field(None, description="Treatment type filter")
    funnel_stages: List[FunnelStageMetrics] = Field(..., description="Funnel stage metrics")
    overall_conversion: float = Field(..., ge=0, le=100, description="Overall funnel conversion %")
    total_enrolled: int = Field(..., ge=0, description="Total enrolled patients")
    total_converted: int = Field(..., ge=0, description="Total fully engaged patients")
    generated_at: str = Field(..., description="Generation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "time_range": "30d",
                "period": {
                    "start_date": "2025-01-01T00:00:00Z",
                    "end_date": "2025-01-31T23:59:59Z"
                },
                "treatment_type": None,
                "funnel_stages": [
                    {"stage": "enrolled", "count": 100, "conversion_rate": 100.0, "drop_off_rate": 0.0},
                    {"stage": "first_quiz_sent", "count": 85, "conversion_rate": 85.0, "drop_off_rate": 15.0},
                    {"stage": "first_quiz_completed", "count": 70, "conversion_rate": 82.35, "drop_off_rate": 17.65},
                    {"stage": "consistent_engagement", "count": 50, "conversion_rate": 71.43, "drop_off_rate": 28.57},
                    {"stage": "high_engagement", "count": 30, "conversion_rate": 60.0, "drop_off_rate": 40.0}
                ],
                "overall_conversion": 30.0,
                "total_enrolled": 100,
                "total_converted": 30,
                "generated_at": "2025-01-31T12:00:00Z"
            }
        }


class PredictionPoint(BaseModel):
    """Single prediction data point."""

    date: str = Field(..., description="Prediction date (ISO format)")
    predicted_value: float = Field(..., description="Predicted metric value")
    confidence_score: float = Field(..., ge=0, le=1, description="Prediction confidence (0-1)")
    lower_bound: float = Field(..., description="Lower confidence interval bound")
    upper_bound: float = Field(..., description="Upper confidence interval bound")


class PredictiveAnalytics(BaseModel):
    """Predictive analytics with forecasts."""

    metric_type: str = Field(..., description="Predicted metric type")
    forecast_period_days: int = Field(..., ge=7, le=90, description="Forecast period in days")
    confidence_threshold: float = Field(..., ge=0, le=1, description="Confidence threshold applied")
    predictions: List[PredictionPoint] = Field(..., description="Forecast predictions")
    trend_direction: str = Field(..., description="Overall trend direction")
    model_accuracy: float = Field(..., ge=0, le=1, description="Model accuracy score")
    generated_at: str = Field(..., description="Generation timestamp")
    notes: str = Field(..., description="Additional notes about predictions")

    class Config:
        json_schema_extra = {
            "example": {
                "metric_type": "patients",
                "forecast_period_days": 30,
                "confidence_threshold": 0.7,
                "predictions": [
                    {
                        "date": "2025-02-01",
                        "predicted_value": 155.0,
                        "confidence_score": 0.92,
                        "lower_bound": 145,
                        "upper_bound": 165
                    },
                    {
                        "date": "2025-02-15",
                        "predicted_value": 162.0,
                        "confidence_score": 0.85,
                        "lower_bound": 150,
                        "upper_bound": 174
                    }
                ],
                "trend_direction": "increasing",
                "model_accuracy": 0.85,
                "generated_at": "2025-01-31T12:00:00Z",
                "notes": "Predictions based on linear regression of 90-day historical data"
            }
        }


class CustomMetricDefinition(BaseModel):
    """Definition for custom analytics metric."""

    name: str = Field(..., min_length=1, max_length=100, description="Metric name")
    description: Optional[str] = Field(None, max_length=500, description="Metric description")
    metric_type: MetricType = Field(..., description="Base metric type")
    aggregation: Optional[AggregationType] = Field(AggregationType.COUNT, description="Aggregation function")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Filter criteria")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "High-Risk Patients Completed",
                "description": "Count of high-risk patients who completed at least one quiz",
                "metric_type": "patients",
                "aggregation": "count",
                "filters": {
                    "risk_level": "high",
                    "min_quizzes": 1
                }
            }
        }


class CustomMetricResponse(BaseModel):
    """Response for custom metric calculation."""

    metric_id: str = Field(..., description="Metric identifier")
    name: str = Field(..., description="Metric name")
    metric_type: str = Field(..., description="Metric type")
    value: float = Field(..., description="Calculated metric value")
    aggregation: str = Field(..., description="Aggregation function used")
    calculated_at: str = Field(..., description="Calculation timestamp")
    status: str = Field(..., description="Calculation status")

    class Config:
        json_schema_extra = {
            "example": {
                "metric_id": "high_risk_patients_completed",
                "name": "High-Risk Patients Completed",
                "metric_type": "patients",
                "value": 25.0,
                "aggregation": "count",
                "calculated_at": "2025-01-31T12:00:00Z",
                "status": "success"
            }
        }


class SystemHealthMetrics(BaseModel):
    """Real-time system health indicators."""

    status: str = Field(..., description="System status")
    response_time_ms: float = Field(..., ge=0, description="Average response time in ms")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")


class RealtimeAnalyticsStream(BaseModel):
    """Real-time analytics stream data."""

    timestamp: str = Field(..., description="Stream timestamp")
    active_sessions: int = Field(..., ge=0, description="Currently active sessions")
    recent_activity_1h: int = Field(..., ge=0, description="Activity in last hour")
    system_health: SystemHealthMetrics = Field(..., description="System health metrics")
    metrics: Dict[str, Any] = Field(..., description="Live metric values")

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-01-31T12:00:00Z",
                "active_sessions": 45,
                "recent_activity_1h": 125,
                "system_health": {
                    "status": "healthy",
                    "response_time_ms": 120.5,
                    "error_rate": 0.2
                },
                "metrics": {
                    "patients_active": 45,
                    "quizzes_today": 125
                }
            }
        }


class AnalyticsExportResponse(BaseModel):
    """Analytics export metadata (actual file streamed separately)."""

    export_id: str = Field(..., description="Export job ID")
    format: str = Field(..., description="Export format")
    metric_type: str = Field(..., description="Exported metric type")
    record_count: int = Field(..., ge=0, description="Number of records exported")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    generated_at: str = Field(..., description="Generation timestamp")
    download_url: str = Field(..., description="Download URL")
    expires_at: str = Field(..., description="Download URL expiration")

    class Config:
        json_schema_extra = {
            "example": {
                "export_id": "exp_abc123",
                "format": "csv",
                "metric_type": "patients",
                "record_count": 150,
                "file_size_bytes": 45678,
                "generated_at": "2025-01-31T12:00:00Z",
                "download_url": "/api/v2/enhanced-analytics/downloads/exp_abc123",
                "expires_at": "2025-01-31T18:00:00Z"
            }
        }


class PeriodMetrics(BaseModel):
    """Metrics for a specific time period."""

    start_date: str = Field(..., description="Period start date")
    end_date: str = Field(..., description="Period end date")
    value: float = Field(..., description="Metric value for period")


class ChangeMetrics(BaseModel):
    """Change metrics between periods."""

    absolute_change: float = Field(..., description="Absolute change in value")
    percent_change: float = Field(..., description="Percentage change")
    trend: str = Field(..., description="Trend direction (up/down/stable)")


class ComparativeAnalytics(BaseModel):
    """Period-over-period comparative analytics."""

    metric_type: str = Field(..., description="Compared metric type")
    current_period: PeriodMetrics = Field(..., description="Current period metrics")
    comparison_period: PeriodMetrics = Field(..., description="Comparison period metrics")
    change_metrics: ChangeMetrics = Field(..., description="Change indicators")
    generated_at: str = Field(..., description="Generation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "metric_type": "patients",
                "current_period": {
                    "start_date": "2025-01-01T00:00:00Z",
                    "end_date": "2025-01-31T23:59:59Z",
                    "value": 45.0
                },
                "comparison_period": {
                    "start_date": "2024-12-01T00:00:00Z",
                    "end_date": "2024-12-31T23:59:59Z",
                    "value": 38.0
                },
                "change_metrics": {
                    "absolute_change": 7.0,
                    "percent_change": 18.42,
                    "trend": "up"
                },
                "generated_at": "2025-01-31T12:00:00Z"
            }
        }
