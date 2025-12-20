"""
Scheduling helper for flow steps.

This module centralizes wait/backoff calculations so FlowEngine can
delegate the responsibility and remain stateless.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from ..types import FlowContext
from ..config import get_flow_config


class FlowScheduler:
    """Computes scheduling boundaries for FlowContext operations."""

    def __init__(self):
        self.execution_config = get_flow_config().execution

    def compute_wait_until(
        self,
        context: FlowContext,
        step_def: Dict[str, Any],
    ) -> Optional[datetime]:
        """
        Return the timestamp when the engine should resume execution
        after a wait step.
        """
        wait_seconds = step_def.get("wait_seconds")
        wait_minutes = step_def.get("wait_minutes")

        if wait_seconds is None and wait_minutes is None:
            return None

        delta = timedelta(seconds=wait_seconds or 0, minutes=wait_minutes or 0)
        return datetime.now(timezone.utc) + delta

    def expires_at(self, template: Dict[str, Any]) -> datetime:
        """Default expiration timestamp for a newly started flow."""
        timeout_minutes = template.get(
            "default_timeout_minutes",
            self.execution_config.default_flow_timeout_minutes,
        )
        timeout_minutes = min(
            timeout_minutes, self.execution_config.max_flow_timeout_hours * 60
        )
        return datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes)


__all__ = ["FlowScheduler"]
