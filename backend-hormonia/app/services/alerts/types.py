"""
Shared types and enums for the unified alert system.

This module defines all common types, enums, and data structures
used across the alert management system.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


class AlertStatus(str, Enum):
    """Alert lifecycle status."""

    PENDING = "pending"
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class AlertRuleType(str, Enum):
    """Types of alert rules."""

    # Patient alerts
    NO_RESPONSE = "no_response"
    MISSED_QUIZ = "missed_quiz"
    NEGATIVE_SENTIMENT = "negative_sentiment"
    TREATMENT_ADHERENCE = "treatment_adherence"
    EMERGENCY_KEYWORDS = "emergency_keywords"

    # Infrastructure alerts
    POOL_EXHAUSTION = "pool_exhaustion"
    SLOW_QUERY = "slow_query"
    CONNECTION_ERROR = "connection_error"
    QUERY_TIMEOUT = "query_timeout"
    HIGH_UTILIZATION = "high_utilization"
    UNHEALTHY_CONNECTION = "unhealthy_connection"

    # Generic
    CUSTOM = "custom"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""

    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    WEBSOCKET = "websocket"
    WEBHOOK = "webhook"
    PUSH = "push_notification"
    DASHBOARD = "dashboard_alert"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"


class EscalationStrategy(str, Enum):
    """Escalation strategies."""

    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    PROGRESSIVE = "progressive"
    NONE = "none"


class AlertRule(BaseModel):
    """Alert rule definition."""

    id: UUID
    name: str
    rule_type: AlertRuleType
    severity: AlertSeverity
    condition: Dict[str, Any]
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AlertEvaluation(BaseModel):
    """Result of alert rule evaluation."""

    rule: AlertRule
    triggered: bool
    context: Dict[str, Any]
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationTarget(BaseModel):
    """Target for notification delivery."""

    user_id: UUID
    channels: List[NotificationChannel]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationResult(BaseModel):
    """Result of notification attempt."""

    channel: NotificationChannel
    target: NotificationTarget
    success: bool
    error: Optional[str] = None
    sent_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DispatchResult(BaseModel):
    """Result of notification dispatch."""

    alert_id: UUID
    total_sent: int
    total_failed: int
    results: List[NotificationResult]
    dispatched_at: datetime


class EscalationRule(BaseModel):
    """Escalation rule configuration."""

    id: UUID
    alert_type: AlertRuleType
    escalation_delay: int  # seconds
    escalation_target: str
    escalation_strategy: EscalationStrategy
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Alert(BaseModel):
    """Alert data model."""

    id: UUID
    rule_id: UUID
    rule_type: AlertRuleType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    message: str
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Actors
    created_by: Optional[UUID] = None
    acknowledged_by: Optional[UUID] = None
    resolved_by: Optional[UUID] = None

    # Notifications
    notification_sent: bool = False
    notification_channels: List[NotificationChannel] = Field(default_factory=list)

    # Escalation
    escalated: bool = False
    escalation_level: int = 0

    class Config:
        from_attributes = True


class AlertStatistics(BaseModel):
    """Alert statistics and metrics."""

    total_alerts: int
    active_alerts: int
    acknowledged_alerts: int
    resolved_alerts: int
    expired_alerts: int

    by_severity: Dict[AlertSeverity, int] = Field(default_factory=dict)
    by_rule_type: Dict[AlertRuleType, int] = Field(default_factory=dict)
    by_status: Dict[AlertStatus, int] = Field(default_factory=dict)

    average_resolution_time: Optional[float] = None  # seconds
    average_acknowledgment_time: Optional[float] = None  # seconds

    metadata: Dict[str, Any] = Field(default_factory=dict)


class DashboardData(BaseModel):
    """Dashboard aggregated data."""

    statistics: AlertStatistics
    recent_alerts: List[Alert]
    top_alert_types: List[Dict[str, Any]]
    alert_timeline: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChannelConfig(BaseModel):
    """Configuration for a notification channel."""

    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MonitoringThresholds(BaseModel):
    """Thresholds for infrastructure monitoring."""

    pool_utilization_warning: int = 75  # %
    pool_utilization_critical: int = 85  # %
    slow_query_duration: float = 1.0  # seconds
    connection_errors_per_minute: int = 5
    query_timeout_rate: float = 0.01  # 1%
    connection_test_failure_count: int = 3
