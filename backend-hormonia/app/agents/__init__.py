"""
Hive-Mind Agent System for Hormonia Backend

This package contains the multi-agent system that provides distributed intelligence
for patient care, flow management, and quiz orchestration.

Agents are organized into specialized categories:
- patient/: Agents focused on patient monitoring and care
- communication/: Agents handling messages, quiz, and interactions
- analytics/: Agents for data analysis and insights

All agents inherit from BaseAgent and participate in swarm coordination.
"""

from __future__ import annotations

# DDD service agent - no LLM calls, not a pydantic-ai migration target.

from typing import TYPE_CHECKING

__all__ = [
    "AlertAnalyzerAgent",
    "BaseAgent",
    "FlowCoordinatorAgent",
    "MessageComposerAgent",
    "PatientMonitorAgent",
    "ResponseProcessorAgent",
]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .base import BaseAgent
    from .analytics.alert_analyzer import AlertAnalyzerAgent
    from .patient.flow_coordinator import FlowCoordinatorAgent
    from .patient.patient_monitor import PatientMonitorAgent
    from .communication.message_composer import MessageComposerAgent
    from .communication.response_processor import ResponseProcessorAgent


def __getattr__(name: str):
    """Lazy-load agents to avoid heavy import side effects at package import time."""
    if name == "AlertAnalyzerAgent":
        from .analytics.alert_analyzer import AlertAnalyzerAgent

        return AlertAnalyzerAgent
    if name == "BaseAgent":
        from .base import BaseAgent

        return BaseAgent
    if name == "FlowCoordinatorAgent":
        from .patient.flow_coordinator import FlowCoordinatorAgent

        return FlowCoordinatorAgent
    if name == "MessageComposerAgent":
        from .communication.message_composer import MessageComposerAgent

        return MessageComposerAgent
    if name == "PatientMonitorAgent":
        from .patient.patient_monitor import PatientMonitorAgent

        return PatientMonitorAgent
    if name == "ResponseProcessorAgent":
        from .communication.response_processor import ResponseProcessorAgent

        return ResponseProcessorAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
