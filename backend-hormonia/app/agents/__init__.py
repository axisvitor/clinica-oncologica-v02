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

from .base import BaseAgent
from .patient.flow_coordinator import FlowCoordinatorAgent
from .communication.message_composer import MessageComposerAgent
from .communication.response_processor import ResponseProcessorAgent

__all__ = [
    "BaseAgent",
    "FlowCoordinatorAgent",
    "MessageComposerAgent",
    "ResponseProcessorAgent"
]