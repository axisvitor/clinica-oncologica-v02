"""
Flow Engine - Modular flow processing system.

This module provides a comprehensive flow processing engine with the following components:
- FlowEngine: Main orchestrator for flow execution and management
- ContextBuilder: Builds execution context with patient data and flow state
- ConditionEvaluator: Evaluates conditions and humanizes message content using AI
- StepExecutor: Executes flow steps with intelligent humanization
- TransitionManager: Manages flow state transitions with distributed locking

All components work together to provide a robust, AI-enhanced flow processing system
for patient daily flows in the oncology clinic management system.
"""

from app.domain.flows.engine.flow_engine import FlowEngine
from app.domain.flows.engine.context_builder import ContextBuilder
from app.domain.flows.engine.condition_evaluator import ConditionEvaluator
from app.domain.flows.engine.step_executor import StepExecutor
from app.domain.flows.engine.transition_manager import TransitionManager

__all__ = [
    "FlowEngine",
    "ContextBuilder",
    "ConditionEvaluator",
    "StepExecutor",
    "TransitionManager",
]

__version__ = "2.0.0"
__author__ = "Hormonia Backend Team"
