"""
Flow Integrations - Integration services for Flow Services (QW-021).

This module provides integration capabilities for the consolidated flow system,
connecting flows with Quiz, AI, and other external services.

Exports:
    - QuizFlowIntegration: Quiz service integration
    - AIFlowIntegration: AI service integration
    - FlowIntegrationManager: Main integration coordinator
    - get_integration_manager: Singleton getter for FlowIntegrationManager
"""

from .quiz_integration import QuizFlowIntegration
from .ai_integration import AIFlowIntegration
from .manager import (
    FlowIntegrationManager,
    get_integration_manager,
    reset_integration_manager,
)
from .base import FlowIntegration, IntegrationAdapter
from .plugins import QuizIntegrationPlugin, AIIntegrationPlugin

__all__ = [
    "QuizFlowIntegration",
    "AIFlowIntegration",
    "FlowIntegrationManager",
    "FlowIntegration",
    "IntegrationAdapter",
    "QuizIntegrationPlugin",
    "AIIntegrationPlugin",
    "get_integration_manager",
    "reset_integration_manager",
]
