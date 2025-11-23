"""
Data integrity helpers for Flow Services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List

from ..types import FlowContext


@dataclass
class IntegrityResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)


class FlowIntegrityChecker:
    """Runs coarse-grained integrity checks over FlowContext."""

    def validate(self, context: FlowContext) -> IntegrityResult:
        errors: List[str] = []

        if not context.patient_id:
            errors.append("FlowContext missing patient_id")

        if context.started_at and context.completed_at:
            if context.completed_at < context.started_at:
                errors.append("completed_at precedes started_at")

        ttl = context.metadata.get("max_duration_minutes")
        if ttl and context.started_at:
            elapsed = (datetime.utcnow() - context.started_at).total_seconds() / 60
            if elapsed > ttl:
                errors.append("Flow exceeded max_duration_minutes")

        return IntegrityResult(is_valid=not errors, errors=errors)


__all__ = ["FlowIntegrityChecker", "IntegrityResult"]
