"""
Recovery helpers for Flow Services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class RecoveryContext:
    """Metadata passed to recovery strategies."""

    flow_id: Any
    step_id: Optional[str]
    attempt: int


class FlowRecoveryStrategy:
    """Simple pluggable recovery strategy."""

    def __init__(self, handler: Callable[[RecoveryContext], Awaitable[None]]):
        self.handler = handler

    async def execute(self, context: RecoveryContext) -> None:
        try:
            await self.handler(context)
        except Exception as exc:
            logger.exception("Recovery handler failed for flow %s: %s", context.flow_id, exc)
            raise


__all__ = ["FlowRecoveryStrategy", "RecoveryContext"]
