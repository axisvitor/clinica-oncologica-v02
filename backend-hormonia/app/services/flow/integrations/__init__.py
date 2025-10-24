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
from .manager import FlowIntegrationManager

# Singleton instance
_integration_manager_instance = None


def get_integration_manager() -> FlowIntegrationManager:
    """
    Get or create the global FlowIntegrationManager singleton instance.

    Returns:
        FlowIntegrationManager: The singleton instance
    """
    global _integration_manager_instance
    if _integration_manager_instance is None:
        _integration_manager_instance = FlowIntegrationManager()
    return _integration_manager_instance


def reset_integration_manager():
    """Reset the global FlowIntegrationManager instance (for testing)."""
    global _integration_manager_instance
    _integration_manager_instance = None


__all__ = [
    "QuizFlowIntegration",
    "AIFlowIntegration",
    "FlowIntegrationManager",
    "get_integration_manager",
    "reset_integration_manager",
]
