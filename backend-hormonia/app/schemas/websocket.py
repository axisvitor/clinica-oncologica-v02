"""
WebSocket event schemas for real-time communication.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Optional, Union
from datetime import datetime, timezone
from uuid import UUID
from enum import Enum


class WebSocketEventType(str, Enum):
    """WebSocket event types."""

    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTHENTICATED = "authenticated"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"

    # Patient events
    PATIENT_UPDATED = "patient_updated"
    PATIENT_FLOW_CHANGED = "patient_flow_changed"
    PATIENT_STATUS_CHANGED = "patient_status_changed"

    # Flow-specific events
    FLOW_STATE_CHANGED = "flow_state_changed"
    FLOW_MESSAGE_SENT = "flow_message_sent"
    FLOW_PROGRESSION = "flow_progression"
    FLOW_PAUSED = "flow_paused"
    FLOW_RESUMED = "flow_resumed"
    FLOW_TRANSITION = "flow_transition"

    # Message events
    NEW_MESSAGE = "new_message"
    MESSAGE_STATUS_UPDATED = "message_status_updated"
    MESSAGE_SENT = "message_sent"
    MESSAGE_DELIVERED = "message_delivered"
    MESSAGE_READ = "message_read"
    MESSAGE_FAILED = "message_failed"

    # Quiz events
    QUIZ_STARTED = "quiz_started"
    QUIZ_RESPONSE_SUBMITTED = "quiz_response_submitted"
    QUIZ_COMPLETED = "quiz_completed"
    QUIZ_ANALYTICS_UPDATED = "quiz_analytics_updated"

    # Report events
    REPORT_GENERATION_STARTED = "report_generation_started"
    REPORT_GENERATION_COMPLETED = "report_generation_completed"
    REPORT_GENERATION_FAILED = "report_generation_failed"

    # Alert events
    ALERT_CREATED = "alert_created"
    ALERT_UPDATED = "alert_updated"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    ALERT_RESOLVED = "alert_resolved"

    # System events
    SYSTEM_MAINTENANCE = "system_maintenance"
    SYSTEM_NOTIFICATION = "system_notification"


class WebSocketMessage(BaseModel):
    """Base WebSocket message structure."""

    type: WebSocketEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: str}
    )

    def dict(self, **kwargs):
        """Override dict method to ensure UUID serialization."""
        data = super().dict(**kwargs)
        # Convert UUIDs to strings in nested data
        if "data" in data and isinstance(data["data"], dict):
            for key, value in data["data"].items():
                if isinstance(value, UUID):
                    data["data"][key] = str(value)
        return data


class AuthenticationRequest(BaseModel):
    """WebSocket authentication request."""

    token: str = Field(..., description="JWT authentication token")


class AuthenticationResponse(BaseModel):
    """WebSocket authentication response."""

    success: bool
    user_id: Optional[UUID] = None
    user_role: Optional[str] = None
    message: str


class JoinRoomRequest(BaseModel):
    """Request to join a patient room."""

    patient_id: UUID = Field(..., description="Patient ID to monitor")


class JoinRoomResponse(BaseModel):
    """Response to room join request."""

    success: bool
    patient_id: Optional[UUID] = None
    message: str


class PatientEventData(BaseModel):
    """Patient-related event data."""

    patient_id: UUID
    patient_name: Optional[str] = None
    doctor_id: Optional[UUID] = None
    changes: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


class MessageEventData(BaseModel):
    """Message-related event data."""

    message_id: UUID
    patient_id: UUID
    direction: str  # inbound, outbound
    type: str  # text, button, list, media
    content: Optional[str] = None
    status: Optional[str] = None
    whatsapp_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class QuizEventData(BaseModel):
    """Quiz-related event data."""

    quiz_id: Optional[UUID] = None
    patient_id: UUID
    template_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    response_id: Optional[UUID] = None
    question_id: Optional[str] = None
    answer: Optional[Any] = None
    completed: Optional[bool] = None
    score: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None


class ReportEventData(BaseModel):
    """Report-related event data."""

    report_id: UUID
    patient_id: UUID
    report_type: str
    status: str  # generating, completed, failed
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class AlertEventData(BaseModel):
    """Alert-related event data."""

    alert_id: UUID
    patient_id: UUID
    alert_type: str
    severity: str  # low, medium, high, critical
    title: str
    description: Optional[str] = None
    acknowledged: bool = False
    acknowledged_by: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None


class FlowEventData(BaseModel):
    """Flow-related event data."""

    patient_id: UUID
    flow_type: str  # initial_15_days, days_16_45, monthly_recurring
    current_day: int
    previous_day: Optional[int] = None
    is_paused: bool = False
    enrollment_date: datetime
    last_message_sent: Optional[datetime] = None
    monthly_cycle: Optional[int] = None
    changes: Optional[dict[str, Any]] = None
    milestone_reached: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class SystemEventData(BaseModel):
    """System-related event data."""

    message: str
    level: str = "info"  # info, warning, error
    affected_services: Optional[list] = None
    estimated_duration: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ConnectionStatsResponse(BaseModel):
    """WebSocket connection statistics."""

    total_connections: int
    authenticated_connections: int
    user_connections: int
    patient_rooms: int
    connections_by_user: dict[str, int]
    connections_by_patient: dict[str, int]


class ErrorResponse(BaseModel):
    """WebSocket error response."""

    error: str
    message: str
    details: Optional[dict[str, Any]] = None


# Event data type mapping
EVENT_DATA_MAPPING = {
    WebSocketEventType.PATIENT_UPDATED: PatientEventData,
    WebSocketEventType.PATIENT_FLOW_CHANGED: PatientEventData,
    WebSocketEventType.PATIENT_STATUS_CHANGED: PatientEventData,
    # Flow-specific events
    WebSocketEventType.FLOW_STATE_CHANGED: FlowEventData,
    WebSocketEventType.FLOW_MESSAGE_SENT: FlowEventData,
    WebSocketEventType.FLOW_PROGRESSION: FlowEventData,
    WebSocketEventType.FLOW_PAUSED: FlowEventData,
    WebSocketEventType.FLOW_RESUMED: FlowEventData,
    WebSocketEventType.FLOW_TRANSITION: FlowEventData,
    WebSocketEventType.NEW_MESSAGE: MessageEventData,
    WebSocketEventType.MESSAGE_STATUS_UPDATED: MessageEventData,
    WebSocketEventType.MESSAGE_SENT: MessageEventData,
    WebSocketEventType.MESSAGE_DELIVERED: MessageEventData,
    WebSocketEventType.MESSAGE_READ: MessageEventData,
    WebSocketEventType.MESSAGE_FAILED: MessageEventData,
    WebSocketEventType.QUIZ_STARTED: QuizEventData,
    WebSocketEventType.QUIZ_RESPONSE_SUBMITTED: QuizEventData,
    WebSocketEventType.QUIZ_COMPLETED: QuizEventData,
    WebSocketEventType.QUIZ_ANALYTICS_UPDATED: QuizEventData,
    WebSocketEventType.REPORT_GENERATION_STARTED: ReportEventData,
    WebSocketEventType.REPORT_GENERATION_COMPLETED: ReportEventData,
    WebSocketEventType.REPORT_GENERATION_FAILED: ReportEventData,
    WebSocketEventType.ALERT_CREATED: AlertEventData,
    WebSocketEventType.ALERT_UPDATED: AlertEventData,
    WebSocketEventType.ALERT_ACKNOWLEDGED: AlertEventData,
    WebSocketEventType.ALERT_RESOLVED: AlertEventData,
    WebSocketEventType.SYSTEM_MAINTENANCE: SystemEventData,
    WebSocketEventType.SYSTEM_NOTIFICATION: SystemEventData,
}


def create_websocket_message(
    event_type: WebSocketEventType,
    data: Union[dict[str, Any], BaseModel],
    timestamp: Optional[datetime] = None,
) -> WebSocketMessage:
    """
    Create a properly formatted WebSocket message.

    Args:
        event_type: Type of event
        data: Event data (dict or Pydantic model)
        timestamp: Optional timestamp (defaults to now)

    Returns:
        WebSocketMessage instance
    """
    if isinstance(data, BaseModel):
        data = data.dict()

    return WebSocketMessage(
        type=event_type, data=data, timestamp=timestamp or datetime.now(timezone.utc)
    )
