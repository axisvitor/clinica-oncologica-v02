"""
Patient-focused agents for the Hive-Mind system.

These agents specialize in patient monitoring, flow coordination,
and alert analysis for oncology treatment workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = [
    "FlowCoordinatorAgent",
]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .flow_coordinator import FlowCoordinatorAgent


def __getattr__(name: str):
    """Lazy-load agents to avoid heavy import side effects at package import time."""
    if name == "FlowCoordinatorAgent":
        from .flow_coordinator import FlowCoordinatorAgent

        return FlowCoordinatorAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
