"""
Performance monitoring schemas.
APM statistics, endpoint metrics, response times, throughput.
"""

from datetime import datetime
from typing import List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict

from ..common import CursorPaginatedResponse


# ============================================================================
# APM SCHEMAS
# ============================================================================


class APMGlobalStatsResponse(BaseModel):
    """Global APM statistics."""

    timestamp: datetime = Field(..., description="Statistics timestamp")
    total_requests: int = Field(..., ge=0, description="Total request count")
    total_errors: int = Field(..., ge=0, description="Total error count")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")
    avg_response_time: float = Field(
        ..., ge=0, description="Average response time (ms)"
    )
    p50: float = Field(..., ge=0, description="50th percentile latency (ms)")
    p95: float = Field(..., ge=0, description="95th percentile latency (ms)")
    p99: float = Field(..., ge=0, description="99th percentile latency (ms)")
    requests_per_second: float = Field(..., ge=0, description="Current throughput")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "total_requests": 10000,
                "total_errors": 250,
                "error_rate": 2.5,
                "avg_response_time": 125.5,
                "p50": 85.0,
                "p95": 350.0,
                "p99": 850.0,
                "requests_per_second": 25.5,
            }
        }
    )


class APMEndpointStatsResponse(BaseModel):
    """APM statistics for a single endpoint."""

    endpoint: str = Field(..., description="Endpoint path")
    total_requests: int = Field(..., ge=0, description="Total request count")
    total_errors: int = Field(..., ge=0, description="Total error count")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")
    avg_response_time: float = Field(
        ..., ge=0, description="Average response time (ms)"
    )
    p95: float = Field(..., ge=0, description="95th percentile latency (ms)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "endpoint": "/api/v2/patients",
                "total_requests": 1500,
                "total_errors": 15,
                "error_rate": 1.0,
                "avg_response_time": 95.5,
                "p95": 250.0,
            }
        }
    )


class APMEndpointDetailResponse(BaseModel):
    """Detailed APM statistics for a specific endpoint."""

    endpoint: str = Field(..., description="Endpoint path")
    timestamp: datetime = Field(..., description="Statistics timestamp")
    total_requests: int = Field(..., ge=0, description="Total request count")
    total_errors: int = Field(..., ge=0, description="Total error count")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")
    avg_response_time: float = Field(
        ..., ge=0, description="Average response time (ms)"
    )
    min_response_time: float = Field(
        ..., ge=0, description="Minimum response time (ms)"
    )
    max_response_time: float = Field(
        ..., ge=0, description="Maximum response time (ms)"
    )
    p50: float = Field(..., ge=0, description="50th percentile latency (ms)")
    p95: float = Field(..., ge=0, description="95th percentile latency (ms)")
    p99: float = Field(..., ge=0, description="99th percentile latency (ms)")
    recent_errors: List[Dict[str, Any]] = Field(
        default_factory=list, description="Recent error details"
    )
    status_code_distribution: Dict[str, int] = Field(
        default_factory=dict, description="HTTP status code counts"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "endpoint": "/api/v2/patients/123",
                "timestamp": "2025-11-07T12:00:00Z",
                "total_requests": 500,
                "total_errors": 5,
                "error_rate": 1.0,
                "avg_response_time": 85.5,
                "min_response_time": 25.0,
                "max_response_time": 850.0,
                "p50": 75.0,
                "p95": 200.0,
                "p99": 450.0,
                "recent_errors": [
                    {"timestamp": "2025-11-07T11:55:00Z", "error": "Not Found"}
                ],
                "status_code_distribution": {"200": 495, "404": 5},
            }
        }
    )


class APMEndpointListResponse(CursorPaginatedResponse[APMEndpointStatsResponse]):
    """Cursor-paginated APM endpoint list."""

    pass


# ============================================================================
# PERFORMANCE OVERVIEW SCHEMAS
# ============================================================================


class PerformanceScore(BaseModel):
    """Performance score calculation."""

    score: float = Field(..., ge=0, le=100, description="Performance score (0-100)")
    status: str = Field(..., description="Status (excellent, good, degraded, critical)")
    deductions: List[Dict[str, Any]] = Field(
        default_factory=list, description="Score deductions"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 85.5,
                "status": "good",
                "deductions": [
                    {"reason": "high_error_rate", "deduction": 10.0},
                    {"reason": "slow_queries", "deduction": 4.5},
                ],
            }
        }
    )


class PerformanceOverviewResponse(BaseModel):
    """Enhanced performance overview."""

    timestamp: datetime = Field(..., description="Overview timestamp")
    performance_score: PerformanceScore = Field(..., description="Performance score")
    apm: Dict[str, Any] = Field(..., description="APM metrics")
    database: Dict[str, Any] = Field(..., description="Database metrics")
    resources: Dict[str, Any] = Field(..., description="Resource metrics")
    system_health: Dict[str, Any] = Field(..., description="System health status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "performance_score": {
                    "score": 85.5,
                    "status": "good",
                    "deductions": [{"reason": "high_error_rate", "deduction": 10.0}],
                },
                "apm": {"error_rate": 2.5, "avg_latency": 125.5},
                "database": {"slow_queries": 25, "avg_duration_ms": 15.5},
                "resources": {"cpu_percent": 45.2, "memory_percent": 62.8},
                "system_health": {"status": "healthy", "uptime": 86400},
            }
        }
    )
