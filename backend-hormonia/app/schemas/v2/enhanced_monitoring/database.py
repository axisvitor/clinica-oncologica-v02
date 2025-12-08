"""
Database monitoring schemas.
Query statistics, connection pool, slow queries, table stats.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict

from ..common import CursorPaginatedResponse


# ============================================================================
# DATABASE SCHEMAS
# ============================================================================


class ConnectionPoolStatsResponse(BaseModel):
    """Connection pool statistics."""

    size: int = Field(..., ge=0, description="Pool size")
    checked_out: int = Field(..., ge=0, description="Checked out connections")
    overflow: int = Field(..., ge=0, description="Overflow connections")
    checked_in: int = Field(..., ge=0, description="Available connections")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"size": 20, "checked_out": 5, "overflow": 0, "checked_in": 15}
        }
    )


class DatabaseOverviewResponse(BaseModel):
    """Database performance overview."""

    timestamp: datetime = Field(..., description="Statistics timestamp")
    query_statistics: Dict[str, Any] = Field(..., description="Query statistics")
    connection_pool: ConnectionPoolStatsResponse = Field(
        ..., description="Connection pool stats"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-11-07T12:00:00Z",
                "query_statistics": {
                    "total_queries": 5000,
                    "slow_queries": 25,
                    "avg_duration_ms": 15.5,
                },
                "connection_pool": {
                    "size": 20,
                    "checked_out": 5,
                    "overflow": 0,
                    "checked_in": 15,
                },
            }
        }
    )


class SlowQueryResponse(BaseModel):
    """Slow query information."""

    query: str = Field(..., description="SQL query text (truncated if long)")
    duration_ms: float = Field(..., ge=0, description="Query duration in milliseconds")
    timestamp: datetime = Field(..., description="Query execution timestamp")
    table: Optional[str] = Field(None, description="Primary table accessed")
    rows_examined: Optional[int] = Field(None, description="Rows examined")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "SELECT * FROM patients WHERE...",
                "duration_ms": 850.5,
                "timestamp": "2025-11-07T11:55:00Z",
                "table": "patients",
                "rows_examined": 15000,
            }
        }
    )


class SlowQueryListResponse(CursorPaginatedResponse[SlowQueryResponse]):
    """Cursor-paginated slow query list."""

    pass


class TableStatsResponse(BaseModel):
    """Statistics for a database table."""

    table: str = Field(..., description="Table name")
    query_count: int = Field(..., ge=0, description="Number of queries")
    avg_duration_ms: float = Field(..., ge=0, description="Average query duration (ms)")
    total_duration_ms: float = Field(..., ge=0, description="Total query duration (ms)")
    slow_query_count: int = Field(..., ge=0, description="Number of slow queries")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "table": "patients",
                "query_count": 1500,
                "avg_duration_ms": 25.5,
                "total_duration_ms": 38250.0,
                "slow_query_count": 15,
            }
        }
    )


class TableStatsListResponse(BaseModel):
    """List of table statistics."""

    data: List[TableStatsResponse] = Field(..., description="Table statistics")
    timestamp: datetime = Field(..., description="Statistics timestamp")
    total_tables: int = Field(..., ge=0, description="Total number of tables")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "table": "patients",
                        "query_count": 1500,
                        "avg_duration_ms": 25.5,
                        "total_duration_ms": 38250.0,
                        "slow_query_count": 15,
                    }
                ],
                "timestamp": "2025-11-07T12:00:00Z",
                "total_tables": 10,
            }
        }
    )
