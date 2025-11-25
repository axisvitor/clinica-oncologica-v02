"""
Flow Coordinator Package - Modular flow coordination system.

This package provides a decomposed, maintainable architecture for patient flow coordination.
All components work together to make intelligent decisions about patient treatment flows.
"""

# Import main classes for backward compatibility
from .coordinator import FlowCoordinatorAgent
from .models import FlowDecision, FlowContext
from .state_manager import StateManager
from .decision_engine import DecisionEngine
from .message_generator import MessageGenerator
from .transition_handler import TransitionHandler
from .consensus_manager import ConsensusManager

# Backward compatibility alias
FlowCoordinator = FlowCoordinatorAgent

# Public API
__all__ = [
    "FlowCoordinatorAgent",
    "FlowCoordinator",  # Backward compatibility alias
    "FlowDecision",
    "FlowContext",
    "StateManager",
    "DecisionEngine",
    "MessageGenerator",
    "TransitionHandler",
    "ConsensusManager",
]

# Version information
__version__ = "2.0.0"
__author__ = "Backend Hormonia Team"
