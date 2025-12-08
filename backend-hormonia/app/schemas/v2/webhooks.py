"""
V2 Webhook Schemas
Pydantic models for webhook management with validation.
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator, ConfigDict
from uuid import UUID


class WebhookEventType(str, Enum):
    """Available webhook event types"""
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_READ = "message.read"
    MESSAGE_FAILED = "message.failed"
    CONNECTION_OPEN = "connection.open"
    CONNECTION_CLOSE = "connection.close"
    INSTANCE_READY = "instance.ready"
    INSTANCE_ERROR = "instance.error"
    QR_CODE_UPDATED = "qrcode.updated"
    PATIENT_CREATED = "patient.created"
    PATIENT_UPDATED = "patient.updated"
    QUIZ_COMPLETED = "quiz.completed"
    FLOW_STATE_CHANGED = "flow.state.changed"


class WebhookStatus(str, Enum):
    """Webhook configuration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    ERROR = "error"


class DeliveryStatus(str, Enum):
    """Webhook delivery status"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookCreate(BaseModel):
    """Create new webhook configuration"""
    url: HttpUrl = Field(..., description="Webhook endpoint URL")
    events: List[WebhookEventType] = Field(..., min_length=1, description="Events to subscribe to")
    description: Optional[str] = Field(None, max_length=500, description="Webhook description")
    secret: Optional[str] = Field(None, min_length=16, max_length=256, description="Custom HMAC secret (auto-generated if not provided)")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Custom HTTP headers")
    timeout: int = Field(30, ge=5, le=300, description="Request timeout in seconds")
    retry_enabled: bool = Field(True, description="Enable automatic retries")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts")

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, v):
        """Prevent setting authentication headers"""
        forbidden = {"authorization", "x-webhook-signature", "x-webhook-timestamp", "x-webhook-id"}
        if v:
            keys_lower = {k.lower() for k in v.keys()}
            if keys_lower & forbidden:
                raise ValueError(f"Headers cannot include: {', '.join(forbidden)}")
        return v

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "url": "https://api.example.com/webhooks",
                "events": ["message.received", "message.sent"],
                "description": "Production webhook for messages",
                "headers": {"X-Api-Key": "secret123"},
                "timeout": 30,
                "retry_enabled": True,
                "max_retries": 3
            }
        })


class WebhookUpdate(BaseModel):
    """Update webhook configuration"""
    url: Optional[HttpUrl] = Field(None, description="Webhook endpoint URL")
    events: Optional[List[WebhookEventType]] = Field(None, min_length=1, description="Events to subscribe to")
    description: Optional[str] = Field(None, max_length=500, description="Webhook description")
    status: Optional[WebhookStatus] = Field(None, description="Webhook status")
    headers: Optional[Dict[str, str]] = Field(None, description="Custom HTTP headers")
    timeout: Optional[int] = Field(None, ge=5, le=300, description="Request timeout in seconds")
    retry_enabled: Optional[bool] = Field(None, description="Enable automatic retries")
    max_retries: Optional[int] = Field(None, ge=0, le=10, description="Maximum retry attempts")

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, v):
        """Prevent setting authentication headers"""
        if v:
            forbidden = {"authorization", "x-webhook-signature", "x-webhook-timestamp", "x-webhook-id"}
            keys_lower = {k.lower() for k in v.keys()}
            if keys_lower & forbidden:
                raise ValueError(f"Headers cannot include: {', '.join(forbidden)}")
        return v

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "status": "active",
                "events": ["message.received", "message.sent", "message.delivered"],
                "description": "Updated webhook configuration"
            }
        })


class WebhookResponse(BaseModel):
    """Webhook configuration response"""
    id: UUID = Field(..., description="Webhook ID")
    url: str = Field(..., description="Webhook endpoint URL")
    events: List[str] = Field(..., description="Subscribed events")
    description: Optional[str] = Field(None, description="Webhook description")
    status: str = Field(..., description="Webhook status")
    secret_preview: str = Field(..., description="First 8 characters of secret")
    headers: Dict[str, str] = Field(default_factory=dict, description="Custom headers")
    timeout: int = Field(..., description="Request timeout in seconds")
    retry_enabled: bool = Field(..., description="Retry enabled")
    max_retries: int = Field(..., description="Maximum retry attempts")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_triggered_at: Optional[datetime] = Field(None, description="Last trigger timestamp")
    success_count: int = Field(0, description="Successful deliveries")
    failure_count: int = Field(0, description="Failed deliveries")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "url": "https://api.example.com/webhooks",
                "events": ["message.received", "message.sent"],
                "description": "Production webhook",
                "status": "active",
                "secret_preview": "wh_secret",
                "headers": {"X-Api-Key": "***"},
                "timeout": 30,
                "retry_enabled": True,
                "max_retries": 3,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "last_triggered_at": "2025-01-01T12:00:00Z",
                "success_count": 1250,
                "failure_count": 5
            }
        })


class WebhookList(BaseModel):
    """Paginated webhook list response"""
    data: List[WebhookResponse] = Field(..., description="Webhook configurations")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="More items available")
    total: Optional[int] = Field(None, description="Total count")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "data": [],
                "next_cursor": "eyJpZCI6MTIzfQ==",
                "has_more": True,
                "total": 50
            }
        })


class WebhookTestRequest(BaseModel):
    """Request to test webhook"""
    event_type: WebhookEventType = Field(..., description="Event type to test")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom test payload")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "event_type": "message.received",
                "payload": {"test": True, "message": "Test webhook"}
            }
        })


class WebhookTestResponse(BaseModel):
    """Webhook test result"""
    success: bool = Field(..., description="Test successful")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    response_time_ms: float = Field(..., description="Response time in milliseconds")
    response_body: Optional[str] = Field(None, description="Response body preview")
    error: Optional[str] = Field(None, description="Error message if failed")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "success": True,
                "status_code": 200,
                "response_time_ms": 245.5,
                "response_body": "{\"status\":\"ok\"}",
                "error": None
            }
        })


class WebhookDelivery(BaseModel):
    """Webhook delivery attempt"""
    id: UUID = Field(..., description="Delivery ID")
    webhook_id: UUID = Field(..., description="Webhook ID")
    event_type: str = Field(..., description="Event type")
    status: str = Field(..., description="Delivery status")
    attempt: int = Field(..., description="Attempt number (1-indexed)")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    response_time_ms: Optional[float] = Field(None, description="Response time")
    error: Optional[str] = Field(None, description="Error message")
    next_retry_at: Optional[datetime] = Field(None, description="Next retry timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "webhook_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "message.received",
                "status": "success",
                "attempt": 1,
                "status_code": 200,
                "response_time_ms": 156.3,
                "error": None,
                "next_retry_at": None,
                "created_at": "2025-01-01T12:00:00Z",
                "completed_at": "2025-01-01T12:00:00Z"
            }
        })


class WebhookDeliveryList(BaseModel):
    """Paginated delivery list"""
    data: List[WebhookDelivery] = Field(..., description="Delivery attempts")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="More items available")
    total: Optional[int] = Field(None, description="Total count")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "data": [],
                "next_cursor": "eyJpZCI6MTIzfQ==",
                "has_more": True,
                "total": 5000
            }
        })


class WebhookRetryRequest(BaseModel):
    """Request to retry failed delivery"""
    force: bool = Field(False, description="Force retry even if max attempts reached")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "force": False
            }
        })


class WebhookRetryResponse(BaseModel):
    """Retry operation result"""
    success: bool = Field(..., description="Retry initiated")
    delivery_id: UUID = Field(..., description="Delivery ID")
    attempt: int = Field(..., description="New attempt number")
    message: str = Field(..., description="Result message")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "success": True,
                "delivery_id": "550e8400-e29b-41d4-a716-446655440001",
                "attempt": 2,
                "message": "Retry scheduled successfully"
            }
        })


class WebhookSecretRotate(BaseModel):
    """Rotate webhook secret"""
    new_secret: Optional[str] = Field(None, min_length=16, max_length=256, description="New secret (auto-generated if not provided)")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "new_secret": None
            }
        })


class WebhookSecretResponse(BaseModel):
    """Secret rotation response"""
    secret_preview: str = Field(..., description="Preview of new secret")
    rotated_at: datetime = Field(..., description="Rotation timestamp")
    message: str = Field(..., description="Success message")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "secret_preview": "wh_new_se",
                "rotated_at": "2025-01-01T12:00:00Z",
                "message": "Secret rotated successfully. Save your new secret securely."
            }
        })


class WebhookLog(BaseModel):
    """Webhook activity log entry"""
    id: UUID = Field(..., description="Log entry ID")
    webhook_id: UUID = Field(..., description="Webhook ID")
    event_type: str = Field(..., description="Event type")
    action: str = Field(..., description="Action performed")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    created_at: datetime = Field(..., description="Timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "webhook_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "message.received",
                "action": "delivery_success",
                "details": {"status_code": 200, "response_time_ms": 145.2},
                "created_at": "2025-01-01T12:00:00Z"
            }
        })


class WebhookLogList(BaseModel):
    """Paginated log list"""
    data: List[WebhookLog] = Field(..., description="Log entries")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="More items available")
    total: Optional[int] = Field(None, description="Total count")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "data": [],
                "next_cursor": "eyJpZCI6MTIzfQ==",
                "has_more": True,
                "total": 10000
            }
        })


class WebhookStats(BaseModel):
    """Webhook statistics"""
    total_webhooks: int = Field(..., description="Total webhooks configured")
    active_webhooks: int = Field(..., description="Active webhooks")
    total_deliveries: int = Field(..., description="Total delivery attempts")
    successful_deliveries: int = Field(..., description="Successful deliveries")
    failed_deliveries: int = Field(..., description="Failed deliveries")
    pending_deliveries: int = Field(..., description="Pending deliveries")
    average_response_time_ms: float = Field(..., description="Average response time")
    success_rate: float = Field(..., description="Success rate (0-100)")
    last_24h_deliveries: int = Field(..., description="Deliveries in last 24 hours")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "total_webhooks": 10,
                "active_webhooks": 8,
                "total_deliveries": 15000,
                "successful_deliveries": 14850,
                "failed_deliveries": 150,
                "pending_deliveries": 25,
                "average_response_time_ms": 185.5,
                "success_rate": 99.0,
                "last_24h_deliveries": 1250
            }
        })


class WebhookHealth(BaseModel):
    """Webhook health status"""
    webhook_id: UUID = Field(..., description="Webhook ID")
    status: str = Field(..., description="Health status")
    uptime_percentage: float = Field(..., description="Uptime percentage (last 24h)")
    recent_failures: int = Field(..., description="Recent failures (last 1h)")
    average_response_time_ms: float = Field(..., description="Average response time")
    last_success_at: Optional[datetime] = Field(None, description="Last successful delivery")
    last_failure_at: Optional[datetime] = Field(None, description="Last failed delivery")
    recommendations: List[str] = Field(default_factory=list, description="Health recommendations")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "webhook_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "healthy",
                "uptime_percentage": 99.8,
                "recent_failures": 0,
                "average_response_time_ms": 156.3,
                "last_success_at": "2025-01-01T12:00:00Z",
                "last_failure_at": "2024-12-31T10:00:00Z",
                "recommendations": []
            }
        })


class WebhookInboundEvent(BaseModel):
    """Inbound webhook event (received from external systems)"""
    event: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event payload")
    timestamp: Optional[str] = Field(None, description="Event timestamp")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "event": "message.received",
                "data": {
                    "message_id": "msg_123",
                    "from": "+5511999999999",
                    "text": "Hello"
                },
                "timestamp": "1704067200"
            }
        })


class WebhookInboundResponse(BaseModel):
    """Response for inbound webhook"""
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")
    webhook_id: Optional[str] = Field(None, description="Webhook ID (for idempotency)")
    message_id: Optional[str] = Field(None, description="Created message ID")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "status": "success",
                "message": "Message processed successfully",
                "webhook_id": "wh_evt_123456",
                "message_id": "msg_789"
            }
        })


class WebhookEventTypeInfo(BaseModel):
    """Information about webhook event type"""
    event: str = Field(..., description="Event type name")
    description: str = Field(..., description="Event description")
    payload_schema: Dict[str, Any] = Field(..., description="Expected payload structure")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "event": "message.received",
                "description": "Triggered when a new message is received",
                "payload_schema": {
                    "message_id": "string",
                    "from": "string",
                    "text": "string",
                    "timestamp": "string"
                }
            }
        })


class WebhookEventTypeList(BaseModel):
    """List of available webhook event types"""
    events: List[WebhookEventTypeInfo] = Field(..., description="Available events")
    total: int = Field(..., description="Total event types")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "events": [],
                "total": 14
            }
        })


class FailedWebhook(BaseModel):
    """Failed webhook summary"""
    webhook_id: UUID = Field(..., description="Webhook ID")
    url: str = Field(..., description="Webhook URL")
    description: Optional[str] = Field(None, description="Description")
    consecutive_failures: int = Field(..., description="Consecutive failures")
    last_failure_at: datetime = Field(..., description="Last failure timestamp")
    last_error: Optional[str] = Field(None, description="Last error message")
    status: str = Field(..., description="Current status")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "webhook_id": "550e8400-e29b-41d4-a716-446655440000",
                "url": "https://api.example.com/webhooks",
                "description": "Production webhook",
                "consecutive_failures": 5,
                "last_failure_at": "2025-01-01T12:00:00Z",
                "last_error": "Connection timeout",
                "status": "error"
            }
        })


class FailedWebhookList(BaseModel):
    """List of failed webhooks"""
    data: List[FailedWebhook] = Field(..., description="Failed webhooks")
    total: int = Field(..., description="Total failed webhooks")

    model_config = ConfigDict(json_schema_extra={
            "example": {
                "data": [],
                "total": 3
            }
        })
