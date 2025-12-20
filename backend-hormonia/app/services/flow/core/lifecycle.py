"""
Lifecycle helpers for Flow Services (QW-021).

The lifecycle manager encapsulates status transitions (start, pause,
resume, cancel, complete) so FlowManager stays focused on orchestration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
from typing import Optional, Dict, Any
import logging

from ..types import FlowContext, FlowStatus
from .context import FlowContextRepository

logger = logging.getLogger(__name__)


class FlowLifecycleManager:
    """High-level lifecycle operations for flows."""

    def __init__(self, repository: FlowContextRepository):
        self.repository = repository

    async def start(
        self,
        context: FlowContext,
        template: Optional[Dict[str, Any]],
        expires_at: Optional[datetime],
    ) -> FlowContext:
        context.status = FlowStatus.ACTIVE
        context.started_at = context.started_at or datetime.now(timezone.utc)
        context.expires_at = expires_at
        await self.repository.save(context, template)
        return context

    async def pause(self, context: FlowContext, reason: Optional[str]) -> FlowContext:
        context.status = FlowStatus.PAUSED
        context.metadata["pause_reason"] = reason or "manual"
        context.metadata["paused_at"] = datetime.now(timezone.utc).isoformat()
        await self.repository.save(context)
        return context

    async def resume(self, context: FlowContext) -> FlowContext:
        context.status = FlowStatus.ACTIVE
        context.metadata["resumed_at"] = datetime.now(timezone.utc).isoformat()
        await self.repository.save(context)
        return context

    async def cancel(
        self,
        context: FlowContext,
        reason: Optional[str],
    ) -> FlowContext:
        context.status = FlowStatus.CANCELLED
        context.completed_at = datetime.now(timezone.utc)
        context.metadata["cancel_reason"] = reason or "manual"
        await self.repository.save(context)
        return context

    async def complete(self, context: FlowContext) -> FlowContext:
        context.status = FlowStatus.COMPLETED
        context.completed_at = datetime.now(timezone.utc)
        await self.repository.save(context)
        return context

    async def delete(self, flow_id: UUID) -> None:
        await self.repository.delete(flow_id)


__all__ = ["FlowLifecycleManager"]
