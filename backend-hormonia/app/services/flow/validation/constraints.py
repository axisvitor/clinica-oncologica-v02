"""
Rule set factory for FlowValidator.
"""

from __future__ import annotations

from typing import Any, List

from ..config import FlowConfig
from .rules import (
    ValidationRule,
    ManualTransitionRule,
    LoopIterationRule,
    PendingResponseRule,
    TimeoutEnvelopeRule,
)


def get_default_rules(config: FlowConfig) -> List[ValidationRule]:
    execution_config = config.execution
    max_wait_seconds = execution_config.max_flow_timeout_hours * 3600

    return [
        ManualTransitionRule(),
        LoopIterationRule(),
        PendingResponseRule(),
        TimeoutEnvelopeRule(max_wait_seconds=max_wait_seconds),
    ]


__all__ = ["get_default_rules"]
