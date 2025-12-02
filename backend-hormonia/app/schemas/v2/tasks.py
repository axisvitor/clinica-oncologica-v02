"""
Task Management schemas for API v2

Enhanced task models with:
- Pydantic V2 validation and field constraints
- Comprehensive type hints and documentation
- Task progress tracking models
- Retry configuration schemas
- Task log entry models
- Task statistics and analytics
- Queue management schemas
- Bulk operation models

CRITICAL: These schemas manage background task execution.
All validation rules must be thorough to ensure system reliability.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator, constr, conint, confloat

from .common import CursorPaginatedResponse


# ============================================================================
# Enums and Constants
# ============================================================================

class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """Standard task types in the system."""
    MESSAGE_PROCESSING = "message_processing"
    MESSAGE_RETRY = "message_retry"
    MESSAGE_CLEANUP = "message_cleanup"
    ANALYTICS_GENERATION = "analytics_generation"
    BULK_OPERATIONS = "bulk_operations"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    SCHEDULED_JOB = "scheduled_job"
    CUSTOM = "custom"


class RetryStrategy(str, Enum):
    """Task retry strategies."""
    IMMEDIATE = "immediate"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"


# ============================================================================
# Base Schemas
# ============================================================================

class TaskV2Base(BaseModel):
    """Base task schema with common fields."""

    task_name: constr(min_length=1, max_length=200) = Field(
        ...,
        description="Human-readable task name"
    )
    task_type: TaskType = Field(
        default=TaskType.CUSTOM,
        description="Type of task"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        description="Task priority level"
    )
    description: Optional[constr(max_length=1000)] = Field(
        None,
        description="Detailed task description"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional task metadata"
    )

    @field_validator("task_name")
    @classmethod
    def validate_task_name(cls, v):
        """Ensure task name is meaningful."""
        if not v or not v.strip():
            raise ValueError("Task name cannot be empty")
        return v.strip()


class RetryConfigV2(BaseModel):
    """Task retry configuration."""

    max_retries: conint(ge=0, le=10) = Field(
        default=3,
        description="Maximum number of retry attempts"
    )
    retry_strategy: RetryStrategy = Field(
        default=RetryStrategy.EXPONENTIAL,
        description="Retry backoff strategy"
    )
    base_delay: conint(ge=1, le=3600) = Field(
        default=60,
        description="Base delay in seconds for retry"
    )
    max_delay: conint(ge=60, le=86400) = Field(
        default=3600,
        description="Maximum delay in seconds between retries"
    )
    retry_on_timeout: bool = Field(
        default=True,
        description="Whether to retry on timeout"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "max_retries": 3,
                "retry_strategy": "exponential",
                "base_delay": 60,
                "max_delay": 3600,
                "retry_on_timeout": True
            }
        }


class TaskProgressV2(BaseModel):
    """Task progress tracking information."""

    current: conint(ge=0, le=100) = Field(
        description="Current progress percentage (0-100)"
    )
    total: conint(ge=0) = Field(
        default=100,
        description="Total work units"
    )
    message: Optional[str] = Field(
        None,
        max_length=500,
        description="Progress message"
    )
    eta_seconds: Optional[confloat(ge=0)] = Field(
        None,
        description="Estimated time to completion in seconds"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When progress was last updated"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "current": 45,
                "total": 100,
                "message": "Processing batch 3 of 7",
                "eta_seconds": 120.5,
                "updated_at": "2025-01-17T15:30:00Z"
            }
        }


# ============================================================================
# Request Schemas
# ============================================================================

class TaskV2Create(TaskV2Base):
    """Schema for creating/scheduling a new task."""

    celery_task_name: constr(min_length=1, max_length=200) = Field(
        ...,
        description="Celery task function name (e.g., 'app.tasks.process_data')"
    )
    args: List[Any] = Field(
        default_factory=list,
        description="Positional arguments for task"
    )
    kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Keyword arguments for task"
    )
    schedule_at: Optional[datetime] = Field(
        None,
        description="Schedule task to run at specific time (UTC)"
    )
    retry_config: Optional[RetryConfigV2] = Field(
        None,
        description="Custom retry configuration"
    )
    timeout_seconds: Optional[conint(ge=1, le=86400)] = Field(
        None,
        description="Task execution timeout in seconds"
    )
    user_id: Optional[UUID] = Field(
        None,
        description="User who created the task"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task_name": "Generate Monthly Analytics",
                "task_type": "analytics_generation",
                "celery_task_name": "app.tasks.generate_analytics",
                "args": [],
                "kwargs": {"month": "2025-01", "include_charts": True},
                "priority": "high",
                "schedule_at": "2025-02-01T00:00:00Z",
                "retry_config": {
                    "max_retries": 3,
                    "retry_strategy": "exponential"
                },
                "timeout_seconds": 3600
            }
        }


class TaskV2Cancel(BaseModel):
    """Schema for cancelling a task."""

    reason: Optional[constr(max_length=500)] = Field(
        None,
        description="Reason for cancellation"
    )
    force: bool = Field(
        default=False,
        description="Force termination of running task"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Task no longer needed",
                "force": False
            }
        }


class TaskV2Retry(BaseModel):
    """Schema for manually retrying a failed task."""

    override_retry_limit: bool = Field(
        default=False,
        description="Retry even if max retries exceeded"
    )
    delay_seconds: Optional[conint(ge=0, le=3600)] = Field(
        None,
        description="Custom delay before retry"
    )
    notes: Optional[constr(max_length=500)] = Field(
        None,
        description="Notes about manual retry"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "override_retry_limit": True,
                "delay_seconds": 60,
                "notes": "Retrying after fixing database connection"
            }
        }


# ============================================================================
# Response Schemas
# ============================================================================

class TaskLogEntryV2(BaseModel):
    """Single task log entry."""

    timestamp: datetime = Field(description="Log entry timestamp")
    level: constr(pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$") = Field(
        description="Log level"
    )
    message: str = Field(description="Log message")
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional context data"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-01-17T15:30:00Z",
                "level": "INFO",
                "message": "Processing batch 3 of 7",
                "context": {"batch_size": 100, "processed": 300}
            }
        }


class TaskV2Response(TaskV2Base):
    """Full task response with all details."""

    id: str = Field(description="Task UUID")
    celery_task_id: str = Field(description="Celery task ID")
    status: TaskStatus = Field(description="Current task status")
    progress: Optional[TaskProgressV2] = Field(
        None,
        description="Task progress information"
    )
    result: Optional[Any] = Field(
        None,
        description="Task result (if completed successfully)"
    )
    error: Optional[str] = Field(
        None,
        description="Error message (if failed)"
    )
    traceback: Optional[str] = Field(
        None,
        description="Error traceback (if failed)"
    )
    retry_count: conint(ge=0) = Field(
        default=0,
        description="Number of retry attempts"
    )
    retry_config: Optional[RetryConfigV2] = Field(
        None,
        description="Retry configuration"
    )
    worker_name: Optional[str] = Field(
        None,
        description="Name of worker executing the task"
    )
    queue_name: Optional[str] = Field(
        None,
        description="Queue the task was sent to"
    )
    created_at: datetime = Field(description="When task was created")
    started_at: Optional[datetime] = Field(None, description="When task started executing")
    completed_at: Optional[datetime] = Field(None, description="When task completed")
    scheduled_at: Optional[datetime] = Field(None, description="When task is scheduled to run")
    timeout_seconds: Optional[int] = Field(None, description="Task timeout")
    user_id: Optional[str] = Field(None, description="User who created the task")
    runtime_seconds: Optional[float] = Field(None, description="Total execution time")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "celery_task_id": "abc123-def456-ghi789",
                "task_name": "Generate Analytics",
                "task_type": "analytics_generation",
                "status": "RUNNING",
                "priority": "high",
                "progress": {
                    "current": 45,
                    "total": 100,
                    "message": "Processing data...",
                    "eta_seconds": 120
                },
                "retry_count": 0,
                "worker_name": "celery@worker1",
                "created_at": "2025-01-17T15:00:00Z",
                "started_at": "2025-01-17T15:00:05Z"
            }
        }


class TaskV2List(CursorPaginatedResponse[TaskV2Response]):
    """Paginated list of tasks with cursor-based pagination."""
    pass


class TaskV2WithLogs(TaskV2Response):
    """Task response with log entries."""

    logs: List[TaskLogEntryV2] = Field(
        default_factory=list,
        description="Task log entries"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "task_name": "Generate Analytics",
                "status": "SUCCESS",
                "logs": [
                    {
                        "timestamp": "2025-01-17T15:00:00Z",
                        "level": "INFO",
                        "message": "Task started"
                    },
                    {
                        "timestamp": "2025-01-17T15:01:00Z",
                        "level": "INFO",
                        "message": "Processing complete"
                    }
                ]
            }
        }


# ============================================================================
# Statistics and Analytics Schemas
# ============================================================================

class TaskStatisticsV2(BaseModel):
    """Task system statistics and analytics."""

    total_tasks: conint(ge=0) = Field(description="Total tasks in period")
    pending_tasks: conint(ge=0) = Field(description="Pending tasks")
    running_tasks: conint(ge=0) = Field(description="Currently running tasks")
    completed_tasks: conint(ge=0) = Field(description="Successfully completed")
    failed_tasks: conint(ge=0) = Field(description="Failed tasks")
    cancelled_tasks: conint(ge=0) = Field(description="Cancelled tasks")
    retry_tasks: conint(ge=0) = Field(description="Tasks in retry state")

    avg_runtime_seconds: confloat(ge=0) = Field(
        description="Average task runtime"
    )
    avg_wait_time_seconds: confloat(ge=0) = Field(
        description="Average time tasks wait before execution"
    )
    success_rate: confloat(ge=0, le=100) = Field(
        description="Success rate percentage"
    )

    tasks_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Task counts by type"
    )
    tasks_by_priority: Dict[str, int] = Field(
        default_factory=dict,
        description="Task counts by priority"
    )

    slowest_tasks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Slowest tasks in period"
    )

    analysis_period_hours: conint(ge=1) = Field(
        description="Analysis period in hours"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_tasks": 1250,
                "pending_tasks": 15,
                "running_tasks": 8,
                "completed_tasks": 1180,
                "failed_tasks": 35,
                "cancelled_tasks": 12,
                "retry_tasks": 0,
                "avg_runtime_seconds": 45.5,
                "avg_wait_time_seconds": 12.3,
                "success_rate": 94.4,
                "tasks_by_type": {
                    "analytics_generation": 450,
                    "message_processing": 600
                },
                "tasks_by_priority": {
                    "low": 300,
                    "medium": 700,
                    "high": 200,
                    "critical": 50
                },
                "slowest_tasks": [
                    {"task_name": "Large Export", "runtime_seconds": 3600}
                ],
                "analysis_period_hours": 24
            }
        }


class QueueStatusV2(BaseModel):
    """Queue status information."""

    queue_name: str = Field(description="Queue name")
    pending_count: conint(ge=0) = Field(description="Tasks waiting in queue")
    active_count: conint(ge=0) = Field(description="Currently processing")
    workers: List[str] = Field(
        default_factory=list,
        description="Workers consuming from this queue"
    )
    avg_processing_time: Optional[float] = Field(
        None,
        description="Average task processing time"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "queue_name": "celery",
                "pending_count": 45,
                "active_count": 8,
                "workers": ["celery@worker1", "celery@worker2"],
                "avg_processing_time": 23.5
            }
        }


class WorkerStatusV2(BaseModel):
    """Worker status information."""

    worker_name: str = Field(description="Worker name")
    status: str = Field(description="Worker status")
    active_tasks: conint(ge=0) = Field(description="Currently executing tasks")
    processed_tasks: conint(ge=0) = Field(description="Total processed")
    failed_tasks: conint(ge=0) = Field(description="Failed task count")
    load_average: Optional[List[float]] = Field(
        None,
        description="System load average"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "worker_name": "celery@worker1",
                "status": "online",
                "active_tasks": 3,
                "processed_tasks": 1250,
                "failed_tasks": 12,
                "load_average": [0.5, 0.6, 0.55]
            }
        }


# ============================================================================
# Bulk Operations Schemas
# ============================================================================

class BulkTaskOperation(BaseModel):
    """Schema for bulk task operations."""

    task_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of task IDs to operate on (max 100)"
    )
    operation: constr(pattern="^(cancel|retry|delete)$") = Field(
        ...,
        description="Operation to perform"
    )
    reason: Optional[constr(max_length=500)] = Field(
        None,
        description="Reason for bulk operation"
    )

    @field_validator("task_ids")
    @classmethod
    def validate_task_ids(cls, v):
        """Ensure no duplicate task IDs."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate task IDs are not allowed")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "task_ids": [
                    "task-id-1",
                    "task-id-2",
                    "task-id-3"
                ],
                "operation": "cancel",
                "reason": "Cancelling outdated batch jobs"
            }
        }


class BulkTaskResult(BaseModel):
    """Result of a bulk task operation."""

    success_count: conint(ge=0) = Field(description="Successfully processed")
    failed_count: conint(ge=0) = Field(description="Failed operations")
    failed_ids: List[str] = Field(
        default_factory=list,
        description="IDs that failed to process"
    )
    errors: Dict[str, str] = Field(
        default_factory=dict,
        description="Error messages by task ID"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success_count": 3,
                "failed_count": 0,
                "failed_ids": [],
                "errors": {}
            }
        }


# ============================================================================
# Cleanup Configuration Schema
# ============================================================================

class TaskCleanupConfigV2(BaseModel):
    """Configuration for task cleanup operations."""

    days_old: conint(ge=1, le=365) = Field(
        default=90,
        description="Delete tasks older than this many days"
    )
    status_filter: Optional[List[TaskStatus]] = Field(
        None,
        description="Only clean tasks with these statuses"
    )
    task_types: Optional[List[TaskType]] = Field(
        None,
        description="Only clean these task types"
    )
    dry_run: bool = Field(
        default=True,
        description="Preview cleanup without deleting"
    )
    batch_size: conint(ge=1, le=1000) = Field(
        default=100,
        description="Process in batches of this size"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "days_old": 90,
                "status_filter": ["SUCCESS", "FAILURE"],
                "dry_run": False,
                "batch_size": 100
            }
        }


class TaskCleanupResultV2(BaseModel):
    """Result of task cleanup operation."""

    tasks_deleted: conint(ge=0) = Field(description="Number of tasks deleted")
    tasks_analyzed: conint(ge=0) = Field(description="Number of tasks analyzed")
    space_freed_mb: confloat(ge=0) = Field(description="Estimated space freed")
    dry_run: bool = Field(description="Whether this was a dry run")
    completion_time: datetime = Field(description="When cleanup completed")

    class Config:
        json_schema_extra = {
            "example": {
                "tasks_deleted": 1250,
                "tasks_analyzed": 1500,
                "space_freed_mb": 45.3,
                "dry_run": False,
                "completion_time": "2025-01-17T15:30:00Z"
            }
        }
