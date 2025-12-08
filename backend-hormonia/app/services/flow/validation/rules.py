"""
Reusable validation rules for Flow Services.

Rules are lightweight asynchronous checks that FlowValidator can compose.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Tuple, Optional

from ..types import FlowContext, FlowStepData


class ValidationRule(ABC):
    """Base class for validation rules."""

    scopes: Tuple[str, ...] = ("transition", "integrity", "step")
    name: str = "validation_rule"

    async def validate(
        self,
        context: FlowContext,
        *,
        from_step: Optional[str] = None,
        to_step: Optional[str] = None,
        step_data: Optional[FlowStepData] = None,
    ) -> List[str]:
        """
        Return a list of validation errors (empty list means success).
        """
        return []


class ManualTransitionRule(ValidationRule):
    """Prevents manual transitions unless explicitly enabled."""

    scopes = ("transition",)
    name = "manual_transition_rule"

    async def validate(
        self,
        context: FlowContext,
        *,
        from_step: Optional[str] = None,
        to_step: Optional[str] = None,
        **_: object,
    ) -> List[str]:
        if context.metadata.get("allow_manual_transitions"):
            return []
        if context.metadata.get("pending_manual_transition"):
            return ["Manual transitions are disabled for this flow"]
        return []


class LoopIterationRule(ValidationRule):
    """Keeps loop iterations bounded."""

    scopes = ("step",)
    name = "loop_iteration_rule"

    async def validate(
        self,
        context: FlowContext,
        *,
        step_data: Optional[FlowStepData] = None,
        **_: object,
    ) -> List[str]:
        if not step_data or step_data.step_type.name != "LOOP":
            return []
        iteration = context.flow_data.get("loop_iteration", 0)
        if iteration > context.metadata.get("max_loop_iterations", 25):
            return [f"Loop iteration limit exceeded ({iteration})"]
        return []


class PendingResponseRule(ValidationRule):
    """Ensures QUESTION steps capture patient responses."""

    scopes = ("step",)
    name = "pending_response_rule"

    async def validate(
        self,
        context: FlowContext,
        *,
        step_data: Optional[FlowStepData] = None,
        **_: object,
    ) -> List[str]:
        if not step_data or step_data.step_type.name != "QUESTION":
            return []
        if not context.flow_data.get("pending_response"):
            return ["Question step requires pending_response data"]
        return []


class TimeoutEnvelopeRule(ValidationRule):
    """Prevents wait steps from exceeding configured ceilings."""

    scopes = ("step",)
    name = "timeout_envelope_rule"

    def __init__(self, max_wait_seconds: int):
        self.max_wait_seconds = max_wait_seconds

    async def validate(
        self,
        context: FlowContext,
        *,
        step_data: Optional[FlowStepData] = None,
        **_: object,
    ) -> List[str]:
        if not step_data or step_data.step_type.name != "WAIT":
            return []
        metadata = step_data.metadata or {}
        wait_seconds = metadata.get("duration_seconds") or metadata.get("wait_seconds")
        if wait_seconds and wait_seconds > self.max_wait_seconds:
            return [
                f"Wait duration {wait_seconds}s exceeds limit of {self.max_wait_seconds}s"
            ]
        return []


__all__ = [
    "ValidationRule",
    "ManualTransitionRule",
    "LoopIterationRule",
    "PendingResponseRule",
    "TimeoutEnvelopeRule",
]
