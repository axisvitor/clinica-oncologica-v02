"""
Schemas for Platform Synchronization API.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any
from datetime import datetime
from uuid import UUID


class SyncEventResponse(BaseModel):
    """Response schema for sync events."""
    event_id: UUID
    event_type: str
    entity_id: UUID
    entity_type: str
    timestamp: datetime
    status: str
    retry_count: int
    error_message: Optional[str] = None
    data: dict[str, Any]
    metadata: dict[str, Any]

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str
        }
    )


class DataConsistencyCheckResponse(BaseModel):
    """Response schema for data consistency checks."""
    entity_id: UUID
    entity_type: str
    is_consistent: bool
    inconsistencies: List[str]
    last_checked: datetime
    resolution_actions: List[str]

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str
        }
    )


class SyncStatusResponse(BaseModel):
    """Response schema for entity sync status."""
    entity_id: UUID
    total_events: int
    completed_events: int
    failed_events: int
    pending_events: int
    last_sync: Optional[datetime] = None
    is_up_to_date: bool

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str
        }
    )


class RetryStatsResponse(BaseModel):
    """Response schema for retry statistics."""
    attempted: int
    succeeded: int
    failed: int
    skipped: int


class AuthenticationRequest(BaseModel):
    """Request schema for platform authentication."""
    token: str = Field(..., description="JWT authentication token")
    required_permissions: Optional[List[str]] = Field(
        None, 
        description="List of required permissions for the request"
    )


class AuthenticationResponse(BaseModel):
    """Response schema for platform authentication."""
    authenticated: bool
    user_id: Optional[UUID] = None
    user_role: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    message: str

    model_config = ConfigDict(
        json_encoders={
            UUID: str
        }
    )


class PatientSyncRequest(BaseModel):
    """Request schema for patient record synchronization."""
    patient_id: UUID
    flow_interaction_data: dict[str, Any]
    user_id: Optional[UUID] = None

    model_config = ConfigDict(
        json_encoders={
            UUID: str
        }
    )


class PatientSyncResponse(BaseModel):
    """Response schema for patient record synchronization."""
    sync_event_id: UUID
    patient_id: UUID
    status: str
    message: str
    timestamp: datetime

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str
        }
    )


class ConsistencyValidationRequest(BaseModel):
    """Request schema for consistency validation."""
    entity_type: str = Field(..., description="Type of entity to validate")
    entity_ids: Optional[List[UUID]] = Field(
        None, 
        description="Specific entity IDs to check"
    )
    check_all: bool = Field(
        False, 
        description="Check all entities of the specified type"
    )

    model_config = ConfigDict(
        json_encoders={
            UUID: str
        }
    )


class AuditLogEntrySchema(BaseModel):
    """Schema for audit log entries."""
    timestamp: datetime
    entity_type: str
    entity_id: UUID
    action: str
    changes: dict[str, Any]
    user_id: Optional[UUID] = None
    source: str = "flow_system"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: str
        }
    )


class PlatformHealthResponse(BaseModel):
    """Response schema for platform health status."""
    overall_status: str  # healthy, warning, critical
    health_score: float  # 0-100
    total_events: int
    recent_events: int
    failed_events: int
    retry_events: int
    last_check: datetime
    recommendations: List[Optional[str]]

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )