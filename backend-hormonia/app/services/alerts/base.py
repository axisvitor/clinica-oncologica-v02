"""
Base protocols, types and interfaces for the alert system.

This module defines all protocols and abstract base classes that
establish contracts for the modular alert system components.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID
from datetime import datetime

from .types import (
    Alert,
    AlertRule,
    AlertEvaluation,
    NotificationTarget,
    NotificationResult,
    DispatchResult,
    NotificationChannel,
)


class NotificationHandlerProtocol(Protocol):
    """Protocol for notification handlers."""

    async def send_notification(
        self,
        alert: Alert,
        target: NotificationTarget,
        channel: NotificationChannel,
    ) -> NotificationResult:
        """Send a notification through a specific channel."""
        ...


class EscalationHandlerProtocol(Protocol):
    """Protocol for escalation handlers."""

    async def should_escalate(self, alert: Alert) -> bool:
        """Determine if alert should be escalated."""
        ...

    async def schedule_escalation(self, alert: Alert) -> None:
        """Schedule escalation for an alert."""
        ...

    async def get_escalation_targets(self, alert: Alert) -> List[NotificationTarget]:
        """Get escalation targets for an alert."""
        ...


class PersistenceHandlerProtocol(Protocol):
    """Protocol for persistence handlers."""

    async def store_alert(self, alert: Alert) -> Alert:
        """Store alert in persistent storage."""
        ...

    async def get_alert(self, alert_id: UUID) -> Alert:
        """Retrieve alert from storage."""
        ...

    async def update_alert(self, alert: Alert) -> Alert:
        """Update existing alert."""
        ...

    async def list_alerts(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[Alert]:
        """List alerts with optional filters."""
        ...


class ThresholdManagerProtocol(Protocol):
    """Protocol for threshold managers."""

    async def should_debounce(self, alert: Alert) -> bool:
        """Check if alert should be debounced."""
        ...

    async def check_threshold(
        self, alert: Alert, threshold_type: str, value: Any
    ) -> bool:
        """Check if threshold is exceeded."""
        ...


class MetricsCollectorProtocol(Protocol):
    """Protocol for metrics collectors."""

    def record_alert_created(self, alert: Alert) -> None:
        """Record alert creation metric."""
        ...

    def record_alert_dispatched(
        self, alert: Alert, dispatch_result: DispatchResult
    ) -> None:
        """Record alert dispatch metric."""
        ...

    def record_alert_acknowledged(self, alert: Alert) -> None:
        """Record alert acknowledgment metric."""
        ...

    def record_alert_resolved(self, alert: Alert) -> None:
        """Record alert resolution metric."""
        ...


class AlertRepository(ABC):
    """Abstract base class for alert persistence."""

    @abstractmethod
    async def create(self, alert: Alert) -> Alert:
        """Create new alert."""
        pass

    @abstractmethod
    async def get_by_id(self, alert_id: UUID) -> Optional[Alert]:
        """Get alert by ID."""
        pass

    @abstractmethod
    async def update(self, alert: Alert) -> Alert:
        """Update alert."""
        pass

    @abstractmethod
    async def find(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Alert]:
        """Find alerts matching filters."""
        pass

    @abstractmethod
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count alerts matching filters."""
        pass


class NotificationChannelHandler(ABC):
    """Abstract base class for notification channels."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize channel handler."""
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)

    @abstractmethod
    async def send(
        self, alert: Alert, target: NotificationTarget
    ) -> NotificationResult:
        """Send notification through this channel."""
        pass

    def is_enabled(self) -> bool:
        """Check if channel is enabled."""
        return self.enabled


class TargetResolverProtocol(Protocol):
    """Protocol for target resolution."""

    async def resolve_targets(self, alert: Alert) -> List[NotificationTarget]:
        """Resolve notification targets for an alert."""
        ...

    async def get_user_contact_info(
        self, user_id: UUID, channel: NotificationChannel
    ) -> Optional[Dict[str, Any]]:
        """Get contact information for a user."""
        ...
