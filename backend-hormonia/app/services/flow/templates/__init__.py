"""
Flow Templates - Template management for Flow Services (QW-021).

This module provides template validation, repository access, and lifecycle
management for flow templates.

Exports:
    - FlowTemplateManager: Template lifecycle management
    - FlowTemplateValidator: Template validation
    - FlowTemplateRepository: Template data access
    - get_template_manager: Singleton getter for FlowTemplateManager
"""

from .manager import FlowTemplateManager
from .validator import FlowTemplateValidator
from .repository import FlowTemplateRepository

# Singleton instance
_template_manager_instance = None


def get_template_manager() -> FlowTemplateManager:
    """
    Get or create the global FlowTemplateManager singleton instance.

    Returns:
        FlowTemplateManager: The singleton instance
    """
    global _template_manager_instance
    if _template_manager_instance is None:
        _template_manager_instance = FlowTemplateManager()
    return _template_manager_instance


def reset_template_manager():
    """Reset the global FlowTemplateManager instance (for testing)."""
    global _template_manager_instance
    _template_manager_instance = None


__all__ = [
    "FlowTemplateManager",
    "FlowTemplateValidator",
    "FlowTemplateRepository",
    "get_template_manager",
    "reset_template_manager",
]
