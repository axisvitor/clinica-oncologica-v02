"""
Performance monitoring schemas for API v2
Pydantic V2 models for unified performance monitoring.
"""

from typing import List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


# Enums
class PerformanceStatus(str, Enum):
    """Performance status levels."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNHEALTHY = "unhealthy"


class OptimizationBenefit(str, Enum):
    """Optimization benefit levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IndexType(str, Enum):
    """Database index types."""

    BTREE = "btree"
    HASH = "hash"
    GIN = "gin"
    GIST = "gist"


# Cache Schemas
class CacheMetrics(BaseModel):
    """Cache performance metrics."""

    hits: int = Field(..., description="Total cache hits")
    misses: int = Field(..., description="Total cache misses")
    hit_rate_percentage: float = Field(
        ..., ge=0, le=100, description="Hit rate percentage"
    )
    total_keys: int = Field(..., description="Total keys in cache")
    memory_usage_mb: Optional[float] = Field(None, description="Memory usage in MB")
    evictions: int = Field(0, description="Total evictions")
    invalidations: int = Field(0, description="Total invalidations")
    warming_operations: int = Field(0, description="Cache warming operations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hits": 15420,
                "misses": 2340,
                "hit_rate_percentage": 86.8,
                "total_keys": 342,
                "memory_usage_mb": 45.2,
                "evictions": 120,
                "invalidations": 45,
                "warming_operations": 12,
            }
        }
    )


class CacheStats(BaseModel):
    """Detailed cache statistics."""

    hits: int = Field(..., description="Cache hits")
    misses: int = Field(..., description="Cache misses")
    errors: int = Field(0, description="Cache errors")
    hit_rate_percent: float = Field(
        ..., ge=0, le=100, description="Hit rate percentage"
    )
    total_operations: int = Field(..., description="Total cache operations")
    avg_response_time_ms: Optional[float] = Field(
        None, description="Average response time"
    )
    status: HealthStatus = Field(..., description="Cache health status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hits": 15420,
                "misses": 2340,
                "errors": 3,
                "hit_rate_percent": 86.8,
                "total_operations": 17763,
                "avg_response_time_ms": 2.4,
                "status": "healthy",
            }
        }
    )


class CacheInvalidationRequest(BaseModel):
    """Request to invalidate cache entries."""

    cache_type: Optional[str] = Field(None, description="Cache type to invalidate")
    doctor_id: Optional[UUID] = Field(
        None, description="Doctor ID for targeted invalidation"
    )
    keys: Optional[List[str]] = Field(None, description="Specific keys to invalidate")
    pattern: Optional[str] = Field(None, description="Pattern for bulk invalidation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cache_type": "analytics",
                "doctor_id": "123e4567-e89b-12d3-a456-426614174000",
                "pattern": "dashboard:*",
            }
        }
    )


class CacheInvalidationResponse(BaseModel):
    """Response from cache invalidation."""

    success: bool = Field(..., description="Whether invalidation succeeded")
    message: str = Field(..., description="Result message")
    cache_type: Optional[str] = Field(None, description="Cache type invalidated")
    doctor_id: Optional[str] = Field(None, description="Doctor ID")
    invalidated_count: int = Field(..., description="Number of keys invalidated")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Cache invalidated successfully",
                "cache_type": "analytics",
                "invalidated_count": 42,
            }
        }
    )


class CacheClearResponse(BaseModel):
    """Response from cache clear operation."""

    success: bool = Field(..., description="Whether clear succeeded")
    message: str = Field(..., description="Result message")
    cleared_count: int = Field(..., description="Number of keys cleared")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Cache cleared successfully",
                "cleared_count": 342,
            }
        }
    )


# Performance Schemas
class ComponentPerformance(BaseModel):
    """Individual component performance metrics."""

    name: str = Field(..., description="Component name")
    status: PerformanceStatus = Field(..., description="Component status")
    score: float = Field(..., ge=0, le=100, description="Performance score (0-100)")
    response_time_ms: Optional[float] = Field(None, description="Average response time")
    error_rate_percent: float = Field(
        0, ge=0, le=100, description="Error rate percentage"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "cache",
                "status": "excellent",
                "score": 92.5,
                "response_time_ms": 2.3,
                "error_rate_percent": 0.1,
            }
        }
    )


class PerformanceOverview(BaseModel):
    """Overall system performance overview."""

    score: float = Field(..., ge=0, le=100, description="Overall performance score")
    status: PerformanceStatus = Field(..., description="Overall status")
    components: List[ComponentPerformance] = Field(..., description="Component metrics")
    recommendations: List[str] = Field(
        default_factory=list, description="Optimization recommendations"
    )
    timestamp: datetime = Field(..., description="Metrics timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 88.5,
                "status": "good",
                "components": [
                    {
                        "name": "cache",
                        "status": "excellent",
                        "score": 92.5,
                        "response_time_ms": 2.3,
                        "error_rate_percent": 0.1,
                    }
                ],
                "recommendations": ["Consider increasing cache TTL"],
                "timestamp": "2025-11-07T15:30:00-03:00",
            }
        }
    )


class DatabasePerformance(BaseModel):
    """Database performance metrics."""

    avg_query_time_ms: float = Field(..., description="Average query time")
    slow_query_count: int = Field(..., description="Number of slow queries")
    slow_query_percentage: float = Field(
        ..., ge=0, le=100, description="Slow query percentage"
    )
    pool_utilization_percent: float = Field(
        ..., ge=0, le=100, description="Connection pool utilization"
    )
    active_connections: int = Field(..., description="Active database connections")
    pool_healthy: bool = Field(..., description="Connection pool health")
    total_queries: int = Field(..., description="Total queries executed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "avg_query_time_ms": 45.2,
                "slow_query_count": 12,
                "slow_query_percentage": 3.5,
                "pool_utilization_percent": 65.0,
                "active_connections": 13,
                "pool_healthy": True,
                "total_queries": 342,
            }
        }
    )


class APIPerformance(BaseModel):
    """API endpoint performance metrics."""

    endpoint: str = Field(..., description="API endpoint path")
    avg_latency_ms: float = Field(..., description="Average latency")
    request_count: int = Field(..., description="Total requests")
    error_count: int = Field(..., description="Total errors")
    error_rate_percent: float = Field(
        ..., ge=0, le=100, description="Error rate percentage"
    )
    p95_latency_ms: Optional[float] = Field(None, description="95th percentile latency")
    p99_latency_ms: Optional[float] = Field(None, description="99th percentile latency")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "endpoint": "/api/v2/patients",
                "avg_latency_ms": 125.5,
                "request_count": 1542,
                "error_count": 3,
                "error_rate_percent": 0.19,
                "p95_latency_ms": 250.0,
                "p99_latency_ms": 450.0,
            }
        }
    )


class SlowQuery(BaseModel):
    """Slow query analysis."""

    query_text: str = Field(..., description="SQL query text")
    avg_duration_ms: float = Field(..., description="Average execution time")
    execution_count: int = Field(..., description="Number of executions")
    total_duration_ms: float = Field(..., description="Total execution time")
    suggestion: Optional[str] = Field(None, description="Optimization suggestion")
    tables_involved: List[str] = Field(
        default_factory=list, description="Tables used in query"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query_text": "SELECT * FROM patients WHERE doctor_id = ?",
                "avg_duration_ms": 1250.5,
                "execution_count": 45,
                "total_duration_ms": 56272.5,
                "suggestion": "Add index on doctor_id column",
                "tables_involved": ["patients"],
            }
        }
    )


class OptimizationRecommendation(BaseModel):
    """Performance optimization recommendation."""

    type: str = Field(..., description="Recommendation type")
    severity: str = Field(..., description="Severity level (high, medium, low)")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    impact: OptimizationBenefit = Field(..., description="Expected impact")
    effort: str = Field(..., description="Implementation effort")
    action_items: List[str] = Field(default_factory=list, description="Action items")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "index",
                "severity": "high",
                "title": "Add missing index on patients.doctor_id",
                "description": "Query performance would improve significantly",
                "impact": "high",
                "effort": "low",
                "action_items": [
                    "CREATE INDEX idx_patients_doctor_id ON patients(doctor_id)"
                ],
            }
        }
    )


# Database Health Schemas
class ConnectionPoolStatus(BaseModel):
    """Connection pool status metrics."""

    pool_size: int = Field(..., description="Pool size")
    max_overflow: int = Field(..., description="Max overflow connections")
    checked_out: int = Field(..., description="Currently checked out")
    checked_in: int = Field(..., description="Currently available")
    total_capacity: int = Field(..., description="Total capacity")
    utilization_percent: float = Field(
        ..., ge=0, le=100, description="Utilization percentage"
    )
    health_status: HealthStatus = Field(..., description="Pool health status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pool_size": 20,
                "max_overflow": 10,
                "checked_out": 13,
                "checked_in": 7,
                "total_capacity": 30,
                "utilization_percent": 43.3,
                "health_status": "healthy",
            }
        }
    )


class ActiveConnection(BaseModel):
    """Active database connection details."""

    pid: int = Field(..., description="Process ID")
    user: str = Field(..., description="Database user")
    database: str = Field(..., description="Database name")
    client_addr: Optional[str] = Field(None, description="Client address")
    state: str = Field(..., description="Connection state")
    query: Optional[str] = Field(None, description="Current query")
    duration_ms: Optional[float] = Field(None, description="Query duration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pid": 12345,
                "user": "app_user",
                "database": "clinica_db",
                "client_addr": "192.168.1.100",
                "state": "active",
                "query": "SELECT * FROM patients WHERE...",
                "duration_ms": 125.5,
            }
        }
    )


class DatabaseLock(BaseModel):
    """Database lock information."""

    lock_type: str = Field(..., description="Type of lock")
    relation: Optional[str] = Field(None, description="Table/relation name")
    mode: str = Field(..., description="Lock mode")
    granted: bool = Field(..., description="Whether lock is granted")
    pid: int = Field(..., description="Process ID holding lock")
    query: Optional[str] = Field(None, description="Query holding lock")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "lock_type": "relation",
                "relation": "patients",
                "mode": "AccessShareLock",
                "granted": True,
                "pid": 12345,
                "query": "SELECT * FROM patients",
            }
        }
    )


class DatabaseHealth(BaseModel):
    """Comprehensive database health status."""

    status: HealthStatus = Field(..., description="Overall health status")
    connection_pool: ConnectionPoolStatus = Field(
        ..., description="Connection pool status"
    )
    active_connections: int = Field(..., description="Number of active connections")
    locks_count: int = Field(..., description="Number of active locks")
    response_time_ms: float = Field(..., description="Health check response time")
    timestamp: datetime = Field(..., description="Check timestamp")
    issues: List[str] = Field(default_factory=list, description="Detected issues")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "connection_pool": {
                    "pool_size": 20,
                    "utilization_percent": 43.3,
                    "health_status": "healthy",
                },
                "active_connections": 13,
                "locks_count": 2,
                "response_time_ms": 5.2,
                "timestamp": "2025-11-07T15:30:00-03:00",
                "issues": [],
            }
        }
    )


# Database Optimization Schemas
class IndexRecommendation(BaseModel):
    """Database index recommendation."""

    table_name: str = Field(..., description="Table name")
    columns: List[str] = Field(..., description="Columns for index")
    index_type: IndexType = Field(..., description="Recommended index type")
    reason: str = Field(..., description="Reason for recommendation")
    estimated_benefit: OptimizationBenefit = Field(..., description="Estimated benefit")
    query_patterns: List[str] = Field(
        default_factory=list, description="Query patterns that would benefit"
    )
    existing_index: Optional[str] = Field(None, description="Existing similar index")
    create_sql: Optional[str] = Field(None, description="SQL to create index")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "table_name": "patients",
                "columns": ["doctor_id"],
                "index_type": "btree",
                "reason": "Frequent filtering and joining on doctor_id",
                "estimated_benefit": "high",
                "query_patterns": ["WHERE doctor_id = ?", "JOIN ON doctor_id"],
                "create_sql": "CREATE INDEX idx_patients_doctor_id ON patients(doctor_id)",
            }
        }
    )


class IndexAnalysis(BaseModel):
    """Database index usage analysis."""

    table_name: str = Field(..., description="Table name")
    index_name: str = Field(..., description="Index name")
    size_mb: float = Field(..., description="Index size in MB")
    scans: int = Field(..., description="Number of index scans")
    tuples_read: int = Field(..., description="Tuples read using index")
    tuples_fetched: int = Field(..., description="Tuples fetched using index")
    effectiveness: float = Field(
        ..., ge=0, le=100, description="Index effectiveness percentage"
    )
    is_redundant: bool = Field(..., description="Whether index might be redundant")
    recommendation: Optional[str] = Field(None, description="Recommendation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "table_name": "patients",
                "index_name": "idx_patients_email",
                "size_mb": 2.5,
                "scans": 15420,
                "tuples_read": 45230,
                "tuples_fetched": 15420,
                "effectiveness": 92.5,
                "is_redundant": False,
                "recommendation": "Keep - highly effective",
            }
        }
    )


class VacuumRequest(BaseModel):
    """Request to perform VACUUM operation."""

    table_name: Optional[str] = Field(None, description="Specific table (None for all)")
    full: bool = Field(False, description="Perform FULL VACUUM")
    analyze: bool = Field(True, description="Also run ANALYZE")
    confirm: bool = Field(False, description="Confirmation required for FULL VACUUM")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "table_name": "patients",
                "full": False,
                "analyze": True,
                "confirm": True,
            }
        }
    )


class VacuumResponse(BaseModel):
    """Response from VACUUM operation."""

    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Result message")
    table_name: Optional[str] = Field(None, description="Table vacuumed")
    reclaimed_space_mb: Optional[float] = Field(
        None, description="Space reclaimed in MB"
    )
    duration_ms: float = Field(..., description="Operation duration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "VACUUM completed successfully",
                "table_name": "patients",
                "reclaimed_space_mb": 125.5,
                "duration_ms": 2500.0,
            }
        }
    )


class TableStatistics(BaseModel):
    """Table statistics and health metrics."""

    table_name: str = Field(..., description="Table name")
    row_count: int = Field(..., description="Approximate row count")
    size_mb: float = Field(..., description="Table size in MB")
    indexes_size_mb: float = Field(..., description="Total indexes size")
    total_size_mb: float = Field(..., description="Total size including indexes")
    dead_tuples: int = Field(..., description="Number of dead tuples")
    bloat_ratio: float = Field(..., ge=0, le=100, description="Table bloat percentage")
    last_vacuum: Optional[datetime] = Field(None, description="Last vacuum time")
    last_analyze: Optional[datetime] = Field(None, description="Last analyze time")
    needs_vacuum: bool = Field(..., description="Whether table needs VACUUM")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "table_name": "patients",
                "row_count": 15420,
                "size_mb": 125.5,
                "indexes_size_mb": 45.2,
                "total_size_mb": 170.7,
                "dead_tuples": 542,
                "bloat_ratio": 3.5,
                "last_vacuum": "2025-11-06T10:30:00-03:00",
                "last_analyze": "2025-11-06T10:30:00-03:00",
                "needs_vacuum": False,
            }
        }
    )


class OptimizationSuggestion(BaseModel):
    """Database optimization suggestion."""

    category: str = Field(..., description="Suggestion category")
    table: Optional[str] = Field(None, description="Affected table")
    suggestion: str = Field(..., description="Optimization suggestion")
    impact: OptimizationBenefit = Field(..., description="Expected impact")
    cost: str = Field(..., description="Implementation cost/effort")
    priority: int = Field(..., ge=1, le=5, description="Priority (1=highest)")
    sql_commands: List[str] = Field(
        default_factory=list, description="SQL commands to execute"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "category": "indexes",
                "table": "patients",
                "suggestion": "Add index on doctor_id for faster lookups",
                "impact": "high",
                "cost": "low",
                "priority": 1,
                "sql_commands": [
                    "CREATE INDEX idx_patients_doctor_id ON patients(doctor_id)"
                ],
            }
        }
    )


# List response schemas with cursor pagination
class SlowQueriesResponse(BaseModel):
    """Paginated slow queries response."""

    queries: List[SlowQuery] = Field(..., description="Slow queries")
    total: int = Field(..., description="Total slow queries")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Result offset")
    has_more: bool = Field(..., description="Whether more results exist")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "queries": [],
                "total": 45,
                "limit": 20,
                "offset": 0,
                "has_more": True,
            }
        }
    )


class ActiveConnectionsResponse(BaseModel):
    """Paginated active connections response."""

    connections: List[ActiveConnection] = Field(..., description="Active connections")
    total: int = Field(..., description="Total active connections")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Result offset")
    has_more: bool = Field(..., description="Whether more results exist")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "connections": [],
                "total": 13,
                "limit": 20,
                "offset": 0,
                "has_more": False,
            }
        }
    )


class DatabaseLocksResponse(BaseModel):
    """Paginated database locks response."""

    locks: List[DatabaseLock] = Field(..., description="Database locks")
    total: int = Field(..., description="Total locks")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Result offset")
    has_more: bool = Field(..., description="Whether more results exist")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "locks": [],
                "total": 2,
                "limit": 20,
                "offset": 0,
                "has_more": False,
            }
        }
    )
