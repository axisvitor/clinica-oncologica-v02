"""
Plugin interface for Flow integrations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..types import FlowContext, FlowStepData


class FlowIntegration(ABC):
    """Base class for lifecycle-aware integrations."""

    name: str = "integration"

    async def on_flow_start(
        self,
        context: FlowContext,
        template: Dict[str, Any],
    ) -> None:  # pragma: no cover - default noop
        return None

    async def on_step_complete(
        self,
        context: FlowContext,
        template: Dict[str, Any],
        step_data: FlowStepData,
    ) -> None:  # pragma: no cover - default noop
        return None

    async def on_flow_complete(
        self,
        context: FlowContext,
        template: Dict[str, Any],
    ) -> None:  # pragma: no cover - default noop
        return None


class LegacyIntegrationAdapter(FlowIntegration):
    """
    Wraps legacy synchronous services so they can participate in the plugin pipeline.
    """

    def __init__(self, name: str, delegate: Any):
        self.name = name
        self.delegate = delegate

    async def on_flow_start(
        self, context: FlowContext, template: Dict[str, Any]
    ) -> None:
        hook = getattr(self.delegate, "on_flow_start", None)
        if callable(hook):
            result = hook(context, template)
            if hasattr(result, "__await__"):
                await result

    async def on_step_complete(
        self,
        context: FlowContext,
        template: Dict[str, Any],
        step_data: FlowStepData,
    ) -> None:
        hook = getattr(self.delegate, "on_step_complete", None)
        if callable(hook):
            result = hook(context, template, step_data)
            if hasattr(result, "__await__"):
                await result

    async def on_flow_complete(
        self, context: FlowContext, template: Dict[str, Any]
    ) -> None:
        hook = getattr(self.delegate, "on_flow_complete", None)
        if callable(hook):
            result = hook(context, template)
            if hasattr(result, "__await__"):
                await result


__all__ = ["FlowIntegration", "LegacyIntegrationAdapter"]
