"""
Lifecycle helpers for Flow Services (QW-021).

The lifecycle manager encapsulates status transitions (start, pause,
resume, cancel, complete) so FlowManager stays focused on orchestration.
"""

from __future__ import annotations

# Standard library imports
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

# Local application imports
from ..types import FlowContext, FlowStatus
from .context import FlowContextRepository
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class FlowLifecycleManager:
    """
    High-level lifecycle operations for flows.

    Manages flow state transitions including start, pause, resume,
    cancel, complete, and delete operations.

    Attributes:
        repository: Context repository for persistence.
    """

    def __init__(self, repository: FlowContextRepository):
        """
        Initialize the lifecycle manager.

        Args:
            repository: Flow context repository.
        """
        self.repository = repository

    def _ensure_transition(
        self,
        context: FlowContext,
        *,
        allowed_from: set[FlowStatus],
        target: FlowStatus,
        action: str,
    ) -> None:
        """Validate lifecycle transition before mutating context state."""
        current_status = context.status
        if current_status not in allowed_from:
            allowed = ", ".join(sorted(status.value for status in allowed_from))
            raise ValueError(
                f"Invalid transition for action '{action}': "
                f"{current_status.value} -> {target.value} (allowed from: {allowed})"
            )

    async def start(
        self,
        context: FlowContext,
        template: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> FlowContext:
        """
        Start a flow by setting it to active status.

        Args:
            context: Flow execution context.
            template: Optional flow template.
            expires_at: Optional expiration timestamp.

        Returns:
            Updated flow context.
        """
        self._ensure_transition(
            context,
            allowed_from={FlowStatus.PENDING},
            target=FlowStatus.ACTIVE,
            action="start",
        )
        context.status = FlowStatus.ACTIVE
        context.started_at = context.started_at or now_sao_paulo()
        context.expires_at = expires_at
        await self.repository.save(context, template)
        return context

    async def pause(self, context: FlowContext, reason: Optional[str] = None) -> FlowContext:
        """
        Pause a flow execution.

        Args:
            context: Flow execution context.
            reason: Optional reason for pausing.

        Returns:
            Updated flow context.
        """
        self._ensure_transition(
            context,
            allowed_from={FlowStatus.ACTIVE},
            target=FlowStatus.PAUSED,
            action="pause",
        )
        context.status = FlowStatus.PAUSED
        context.metadata["pause_reason"] = reason or "manual"
        context.metadata["paused_at"] = now_sao_paulo().isoformat()
        await self.repository.save(context)
        return context

    async def resume(self, context: FlowContext) -> FlowContext:
        """
        Resume a paused flow execution.

        Args:
            context: Flow execution context.

        Returns:
            Updated flow context.
        """
        self._ensure_transition(
            context,
            allowed_from={FlowStatus.PAUSED},
            target=FlowStatus.ACTIVE,
            action="resume",
        )
        context.status = FlowStatus.ACTIVE
        context.metadata["resumed_at"] = now_sao_paulo().isoformat()
        await self.repository.save(context)
        return context

    async def cancel(
        self,
        context: FlowContext,
        reason: Optional[str] = None,
    ) -> FlowContext:
        """
        Cancel a flow execution.

        Args:
            context: Flow execution context.
            reason: Optional cancellation reason.

        Returns:
            Updated flow context.
        """
        self._ensure_transition(
            context,
            allowed_from={FlowStatus.PENDING, FlowStatus.ACTIVE, FlowStatus.PAUSED, FlowStatus.FAILED},
            target=FlowStatus.CANCELLED,
            action="cancel",
        )
        context.status = FlowStatus.CANCELLED
        context.completed_at = now_sao_paulo()
        context.metadata["cancel_reason"] = reason or "manual"
        await self.repository.save(context)
        return context

    async def complete(self, context: FlowContext) -> FlowContext:
        """
        Complete a flow execution.

        Args:
            context: Flow execution context.

        Returns:
            Updated flow context.
        """
        self._ensure_transition(
            context,
            allowed_from={FlowStatus.ACTIVE},
            target=FlowStatus.COMPLETED,
            action="complete",
        )
        context.status = FlowStatus.COMPLETED
        context.completed_at = now_sao_paulo()
        await self.repository.save(context)
        return context

    async def delete(self, flow_id: UUID) -> None:
        """
        Delete a flow from storage.

        Args:
            flow_id: Flow instance UUID.
        """
        await self.repository.delete(flow_id)


__all__ = ["FlowLifecycleManager"]
