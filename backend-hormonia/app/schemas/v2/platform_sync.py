"""
V2 Platform Sync Schemas
Pydantic models for multi-platform synchronization with conflict resolution.
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl, validator, root_validator
from uuid import UUID


# ============================================================================
# ENUMS
# ============================================================================
class PlatformType(str, Enum):
    """External platform types"""
    EHR = "ehr"  # Electronic Health Records
    ANALYTICS = "analytics"  # Analytics platforms
    NOTIFICATIONS = "notifications"  # Notification services
    WAREHOUSE = "warehouse"  # Data warehouses
    CRM = "crm"  # Customer Relationship Management
    BILLING = "billing"  # Billing systems


class SyncJobStatus(str, Enum):
    """Sync job status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLING_BACK = "rolling_back"


class SyncStrategy(str, Enum):
    """Sync execution strategy"""
    FULL = "full"  # Complete data snapshot
    INCREMENTAL = "incremental"  # Changes only
    SELECTIVE = "selective"  # Specific entities


class ConflictStrategy(str, Enum):
    """Conflict resolution strategy"""
    LAST_WRITE_WINS = "last_write_wins"  # Most recent update wins
    MANUAL = "manual"  # Require manual resolution
    FIELD_LEVEL = "field_level"  # Field-by-field resolution
    VERSION_TRACKING = "version_tracking"  # Track all versions


class SyncDirection(str, Enum):
    """Sync direction"""
    PUSH = "push"  # Local to remote
    PULL = "pull"  # Remote to local
    BIDIRECTIONAL = "bidirectional"  # Both directions


class ConflictResolutionStrategy(str, Enum):
    """How to resolve a specific conflict"""
    USE_LOCAL = "use_local"
    USE_REMOTE = "use_remote"
    MERGE = "merge"
    SKIP = "skip"


# ============================================================================
# SYNC JOB SCHEMAS
# ============================================================================
class SyncJobCreate(BaseModel):
    """Create new sync job"""
    platform: PlatformType = Field(..., description="Target platform")
    strategy: SyncStrategy = Field(..., description="Sync strategy")
    direction: SyncDirection = Field(SyncDirection.BIDIRECTIONAL, description="Sync direction")
    entity_types: Optional[List[str]] = Field(None, description="Entity types to sync")
    entity_ids: Optional[List[str]] = Field(None, description="Specific entity IDs (for selective)")
    batch_size: int = Field(1000, ge=1, le=10000, description="Items per batch")
    dry_run: bool = Field(False, description="Simulate without applying changes")

    @validator("entity_ids")
    def validate_selective_sync(cls, v, values):
        """Validate entity_ids for selective sync"""
        if values.get("strategy") == SyncStrategy.SELECTIVE and not v:
            raise ValueError("entity_ids required for selective sync")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "ehr",
                "strategy": "incremental",
                "direction": "bidirectional",
                "entity_types": ["patients", "appointments"],
                "batch_size": 1000,
                "dry_run": False
            }
        }


class SyncJobUpdate(BaseModel):
    """Update sync job"""
    status: Optional[SyncJobStatus] = Field(None, description="Job status")
    cancel_reason: Optional[str] = Field(None, max_length=500, description="Cancellation reason")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "cancelled",
                "cancel_reason": "Manual cancellation by admin"
            }
        }


class SyncJobResponse(BaseModel):
    """Sync job response"""
    id: UUID = Field(..., description="Job ID")
    platform: str = Field(..., description="Target platform")
    strategy: str = Field(..., description="Sync strategy")
    direction: str = Field(..., description="Sync direction")
    status: str = Field(..., description="Job status")
    transaction_id: str = Field(..., description="Transaction ID")
    entity_types: Optional[List[str]] = Field(None, description="Entity types")
    total_items: int = Field(0, description="Total items to sync")
    processed_items: int = Field(0, description="Items processed")
    successful_items: int = Field(0, description="Items synced successfully")
    failed_items: int = Field(0, description="Items failed")
    skipped_items: int = Field(0, description="Items skipped")
    conflicts_detected: int = Field(0, description="Conflicts detected")
    conflicts_resolved: int = Field(0, description="Conflicts resolved")
    created_at: datetime = Field(..., description="Job creation time")
    started_at: Optional[datetime] = Field(None, description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    duration_seconds: Optional[float] = Field(None, description="Duration in seconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "platform": "ehr",
                "strategy": "incremental",
                "direction": "bidirectional",
                "status": "completed",
                "transaction_id": "sync_txn_abc123",
                "entity_types": ["patients", "appointments"],
                "total_items": 500,
                "processed_items": 500,
                "successful_items": 495,
                "failed_items": 3,
                "skipped_items": 2,
                "conflicts_detected": 5,
                "conflicts_resolved": 5,
                "created_at": "2025-01-01T10:00:00Z",
                "started_at": "2025-01-01T10:00:05Z",
                "completed_at": "2025-01-01T10:15:00Z",
                "duration_seconds": 895.5,
                "error_message": None
            }
        }


class SyncJobList(BaseModel):
    """Paginated sync job list"""
    data: List[SyncJobResponse] = Field(..., description="Sync jobs")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="More items available")
    total: Optional[int] = Field(None, description="Total count")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "next_cursor": "eyJpZCI6MTIzfQ==",
                "has_more": True,
                "total": 50
            }
        }


# ============================================================================
# SYNC TRIGGER & STATUS SCHEMAS
# ============================================================================
class SyncTriggerRequest(BaseModel):
    """Request to trigger manual sync"""
    platform: PlatformType = Field(..., description="Target platform")
    strategy: SyncStrategy = Field(..., description="Sync strategy")
    direction: SyncDirection = Field(SyncDirection.BIDIRECTIONAL, description="Sync direction")
    entity_types: Optional[List[str]] = Field(None, description="Entity types to sync")
    entity_ids: Optional[List[str]] = Field(None, description="Specific entity IDs")
    batch_size: int = Field(1000, ge=1, le=10000, description="Items per batch")
    conflict_strategy: ConflictStrategy = Field(
        ConflictStrategy.LAST_WRITE_WINS,
        description="Conflict resolution strategy"
    )
    dry_run: bool = Field(False, description="Simulate without applying changes")

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "ehr",
                "strategy": "incremental",
                "direction": "bidirectional",
                "entity_types": ["patients"],
                "batch_size": 1000,
                "conflict_strategy": "last_write_wins",
                "dry_run": False
            }
        }


class SyncTriggerResponse(BaseModel):
    """Response for sync trigger"""
    job_id: UUID = Field(..., description="Created job ID")
    transaction_id: str = Field(..., description="Transaction ID")
    status: SyncJobStatus = Field(..., description="Initial status")
    message: str = Field(..., description="Status message")
    estimated_items: int = Field(..., description="Estimated items to sync")
    started_at: datetime = Field(..., description="Start timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "transaction_id": "sync_txn_abc123",
                "status": "pending",
                "message": "Sync job created successfully",
                "estimated_items": 500,
                "started_at": "2025-01-01T10:00:00Z"
            }
        }


class SyncStatusResponse(BaseModel):
    """Real-time sync status"""
    job_id: UUID = Field(..., description="Job ID")
    status: str = Field(..., description="Current status")
    progress_percentage: float = Field(..., ge=0, le=100, description="Progress percentage")
    total_items: int = Field(..., description="Total items")
    processed_items: int = Field(..., description="Processed items")
    current_batch: int = Field(..., description="Current batch number")
    total_batches: int = Field(..., description="Total batches")
    items_per_second: float = Field(..., description="Processing rate")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    current_entity_type: Optional[str] = Field(None, description="Currently processing entity type")
    errors: List[str] = Field(default_factory=list, description="Recent errors")
    warnings: List[str] = Field(default_factory=list, description="Warnings")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "running",
                "progress_percentage": 65.5,
                "total_items": 500,
                "processed_items": 327,
                "current_batch": 4,
                "total_batches": 5,
                "items_per_second": 8.5,
                "estimated_completion": "2025-01-01T10:15:00Z",
                "current_entity_type": "patients",
                "errors": [],
                "warnings": ["3 items skipped due to validation errors"]
            }
        }


# ============================================================================
# SYNC CONFIGURATION SCHEMAS
# ============================================================================
class SyncConfigCreate(BaseModel):
    """Create sync configuration"""
    platform: PlatformType = Field(..., description="Platform type")
    name: str = Field(..., min_length=1, max_length=100, description="Configuration name")
    description: Optional[str] = Field(None, max_length=500, description="Description")
    endpoint_url: HttpUrl = Field(..., description="Platform API endpoint")
    auth_type: str = Field(..., description="Authentication type (bearer, api_key, oauth2)")
    auth_token: Optional[str] = Field(None, description="Authentication token (not stored in response)")
    enabled: bool = Field(True, description="Enable automatic sync")
    sync_interval_minutes: int = Field(60, ge=5, le=1440, description="Auto-sync interval (5-1440 min)")
    conflict_strategy: ConflictStrategy = Field(
        ConflictStrategy.LAST_WRITE_WINS,
        description="Default conflict strategy"
    )
    retry_enabled: bool = Field(True, description="Enable automatic retries")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts")
    batch_size: int = Field(1000, ge=1, le=10000, description="Items per batch")
    timeout_seconds: int = Field(30, ge=5, le=300, description="Request timeout")
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom HTTP headers")
    custom_settings: Optional[Dict[str, Any]] = Field(None, description="Platform-specific settings")

    @validator("auth_type")
    def validate_auth_type(cls, v):
        """Validate authentication type"""
        allowed = {"bearer", "api_key", "oauth2", "basic"}
        if v not in allowed:
            raise ValueError(f"auth_type must be one of: {', '.join(allowed)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "ehr",
                "name": "Main EHR System",
                "description": "Primary electronic health records integration",
                "endpoint_url": "https://ehr.example.com/api/v1",
                "auth_type": "bearer",
                "enabled": True,
                "sync_interval_minutes": 60,
                "conflict_strategy": "last_write_wins",
                "retry_enabled": True,
                "max_retries": 3,
                "batch_size": 1000,
                "timeout_seconds": 30
            }
        }


class SyncConfigUpdate(BaseModel):
    """Update sync configuration"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Configuration name")
    description: Optional[str] = Field(None, max_length=500, description="Description")
    endpoint_url: Optional[HttpUrl] = Field(None, description="Platform API endpoint")
    auth_type: Optional[str] = Field(None, description="Authentication type")
    auth_token: Optional[str] = Field(None, description="Authentication token")
    enabled: Optional[bool] = Field(None, description="Enable automatic sync")
    sync_interval_minutes: Optional[int] = Field(None, ge=5, le=1440, description="Auto-sync interval")
    conflict_strategy: Optional[ConflictStrategy] = Field(None, description="Conflict strategy")
    retry_enabled: Optional[bool] = Field(None, description="Enable retries")
    max_retries: Optional[int] = Field(None, ge=0, le=10, description="Max retries")
    batch_size: Optional[int] = Field(None, ge=1, le=10000, description="Batch size")
    timeout_seconds: Optional[int] = Field(None, ge=5, le=300, description="Timeout")
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom headers")
    custom_settings: Optional[Dict[str, Any]] = Field(None, description="Custom settings")

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": False,
                "sync_interval_minutes": 120,
                "description": "Updated configuration"
            }
        }


class SyncConfigResponse(BaseModel):
    """Sync configuration response"""
    id: UUID = Field(..., description="Configuration ID")
    platform: str = Field(..., description="Platform type")
    name: str = Field(..., description="Configuration name")
    description: Optional[str] = Field(None, description="Description")
    endpoint_url: str = Field(..., description="Platform API endpoint")
    auth_type: str = Field(..., description="Authentication type")
    enabled: bool = Field(..., description="Automatic sync enabled")
    sync_interval_minutes: int = Field(..., description="Auto-sync interval")
    conflict_strategy: str = Field(..., description="Conflict resolution strategy")
    retry_enabled: bool = Field(..., description="Retry enabled")
    max_retries: int = Field(..., description="Maximum retries")
    batch_size: int = Field(..., description="Batch size")
    timeout_seconds: int = Field(..., description="Request timeout")
    custom_headers: Dict[str, str] = Field(default_factory=dict, description="Custom headers")
    custom_settings: Dict[str, Any] = Field(default_factory=dict, description="Custom settings")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")
    last_sync_at: Optional[datetime] = Field(None, description="Last sync time")
    last_sync_status: Optional[str] = Field(None, description="Last sync status")
    total_syncs: int = Field(0, description="Total sync jobs")
    successful_syncs: int = Field(0, description="Successful syncs")
    failed_syncs: int = Field(0, description="Failed syncs")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "platform": "ehr",
                "name": "Main EHR System",
                "description": "Primary EHR integration",
                "endpoint_url": "https://ehr.example.com/api/v1",
                "auth_type": "bearer",
                "enabled": True,
                "sync_interval_minutes": 60,
                "conflict_strategy": "last_write_wins",
                "retry_enabled": True,
                "max_retries": 3,
                "batch_size": 1000,
                "timeout_seconds": 30,
                "custom_headers": {},
                "custom_settings": {},
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T10:00:00Z",
                "last_sync_at": "2025-01-01T09:00:00Z",
                "last_sync_status": "completed",
                "total_syncs": 150,
                "successful_syncs": 148,
                "failed_syncs": 2
            }
        }


class SyncConfigList(BaseModel):
    """Paginated sync configuration list"""
    data: List[SyncConfigResponse] = Field(..., description="Sync configurations")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="More items available")
    total: Optional[int] = Field(None, description="Total count")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "next_cursor": "eyJpZCI6MTIzfQ==",
                "has_more": True,
                "total": 10
            }
        }


# ============================================================================
# PLATFORM TESTING SCHEMAS
# ============================================================================
class PlatformTestRequest(BaseModel):
    """Request to test platform connection"""
    platform: PlatformType = Field(..., description="Platform to test")
    endpoint_url: HttpUrl = Field(..., description="API endpoint")
    auth_type: str = Field(..., description="Authentication type")
    auth_token: Optional[str] = Field(None, description="Authentication token")
    timeout_seconds: int = Field(10, ge=1, le=60, description="Test timeout")
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom headers")

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "ehr",
                "endpoint_url": "https://ehr.example.com/api/v1/health",
                "auth_type": "bearer",
                "auth_token": "test_token_123",
                "timeout_seconds": 10
            }
        }


class PlatformTestResponse(BaseModel):
    """Platform connection test result"""
    success: bool = Field(..., description="Test successful")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    message: str = Field(..., description="Test result message")
    platform_info: Optional[Dict[str, Any]] = Field(None, description="Platform information")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    warnings: List[str] = Field(default_factory=list, description="Warnings")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "status_code": 200,
                "response_time_ms": 245.5,
                "message": "Connection successful",
                "platform_info": {
                    "status": "available",
                    "version": "2.0",
                    "features": ["sync", "webhooks"]
                },
                "errors": [],
                "warnings": []
            }
        }


# ============================================================================
# CONFLICT RESOLUTION SCHEMAS
# ============================================================================
class ConflictResolutionRequest(BaseModel):
    """Request to resolve sync conflict"""
    conflict_id: UUID = Field(..., description="Conflict ID")
    resolution_strategy: ConflictResolutionStrategy = Field(..., description="Resolution strategy")
    merged_data: Optional[Dict[str, Any]] = Field(None, description="Merged data (for merge strategy)")
    notes: Optional[str] = Field(None, max_length=1000, description="Resolution notes")

    @validator("merged_data")
    def validate_merge_data(cls, v, values):
        """Validate merged_data for merge strategy"""
        if values.get("resolution_strategy") == ConflictResolutionStrategy.MERGE and not v:
            raise ValueError("merged_data required for merge strategy")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "conflict_id": "550e8400-e29b-41d4-a716-446655440000",
                "resolution_strategy": "use_local",
                "notes": "Local version is more accurate"
            }
        }


class ConflictResolutionResponse(BaseModel):
    """Response for conflict resolution"""
    conflict_id: UUID = Field(..., description="Conflict ID")
    status: str = Field(..., description="Resolution status")
    resolution_strategy: str = Field(..., description="Strategy used")
    resolved_value: Dict[str, Any] = Field(..., description="Final resolved value")
    message: str = Field(..., description="Status message")
    resolved_at: datetime = Field(..., description="Resolution timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "conflict_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "resolved",
                "resolution_strategy": "use_local",
                "resolved_value": {"name": "John Doe", "age": 35},
                "message": "Conflict resolved successfully",
                "resolved_at": "2025-01-01T10:00:00Z"
            }
        }


# ============================================================================
# SYNC HISTORY SCHEMAS
# ============================================================================
class SyncHistoryResponse(BaseModel):
    """Sync history entry with detailed logs"""
    id: UUID = Field(..., description="History entry ID")
    job_id: UUID = Field(..., description="Sync job ID")
    transaction_id: str = Field(..., description="Transaction ID")
    platform: str = Field(..., description="Platform")
    strategy: str = Field(..., description="Strategy used")
    status: str = Field(..., description="Final status")
    total_items: int = Field(..., description="Total items")
    successful_items: int = Field(..., description="Successful items")
    failed_items: int = Field(..., description="Failed items")
    duration_seconds: float = Field(..., description="Duration")
    started_at: datetime = Field(..., description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    error_summary: Optional[str] = Field(None, description="Error summary")
    detailed_logs: List[Dict[str, Any]] = Field(default_factory=list, description="Detailed logs")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "transaction_id": "sync_txn_abc123",
                "platform": "ehr",
                "strategy": "incremental",
                "status": "completed",
                "total_items": 500,
                "successful_items": 495,
                "failed_items": 5,
                "duration_seconds": 895.5,
                "started_at": "2025-01-01T10:00:00Z",
                "completed_at": "2025-01-01T10:15:00Z",
                "error_summary": "5 items failed validation",
                "detailed_logs": []
            }
        }


class SyncHistoryList(BaseModel):
    """Paginated sync history list"""
    data: List[SyncHistoryResponse] = Field(..., description="History entries")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="More items available")
    total: Optional[int] = Field(None, description="Total count")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [],
                "next_cursor": "eyJpZCI6MTIzfQ==",
                "has_more": True,
                "total": 200
            }
        }


# ============================================================================
# ROLLBACK SCHEMAS
# ============================================================================
class SyncRollbackRequest(BaseModel):
    """Request to rollback sync transaction"""
    transaction_id: str = Field(..., description="Transaction ID to rollback")
    reason: str = Field(..., min_length=1, max_length=500, description="Rollback reason")
    dry_run: bool = Field(False, description="Simulate rollback without applying")

    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": "sync_txn_abc123",
                "reason": "Data corruption detected in sync batch",
                "dry_run": False
            }
        }


class SyncRollbackResponse(BaseModel):
    """Response for rollback operation"""
    rollback_job_id: UUID = Field(..., description="Rollback job ID")
    original_transaction_id: str = Field(..., description="Original transaction ID")
    status: str = Field(..., description="Rollback status")
    message: str = Field(..., description="Status message")
    estimated_items_to_revert: int = Field(..., description="Estimated items to revert")
    started_at: datetime = Field(..., description="Rollback start time")

    class Config:
        json_schema_extra = {
            "example": {
                "rollback_job_id": "550e8400-e29b-41d4-a716-446655440002",
                "original_transaction_id": "sync_txn_abc123",
                "status": "pending",
                "message": "Rollback initiated successfully",
                "estimated_items_to_revert": 495,
                "started_at": "2025-01-01T11:00:00Z"
            }
        }
