"""
Flow Coordinator Package - Modular flow coordination system.

This package provides a decomposed, maintainable architecture for patient flow coordination.
All components work together to make intelligent decisions about patient treatment flows.
"""

from __future__ import annotations

from app.agents.patient.flow_coordinator.consensus_manager import ConsensusManager
from app.agents.patient.flow_coordinator.coordinator import FlowCoordinatorAgent
from app.agents.patient.flow_coordinator.decision_engine import DecisionEngine
from app.agents.patient.flow_coordinator.message_generator import MessageGenerator
from app.agents.patient.flow_coordinator.models import FlowContext, FlowDecision
from app.agents.patient.flow_coordinator.state_manager import StateManager
from app.agents.patient.flow_coordinator.transition_handler import TransitionHandler

__all__ = [
    "ConsensusManager",
    "DecisionEngine",
    "FlowContext",
    "FlowCoordinatorAgent",
    "FlowDecision",
    "MessageGenerator",
    "StateManager",
    "TransitionHandler",
]

__version__ = "2.0.0"
__author__ = "Backend Hormonia Team"
