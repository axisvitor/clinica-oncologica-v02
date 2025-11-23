from typing import Any
"""Compatibility wrapper for FlowManager.

The implementation now lives in app.services.flow.core.manager.
"""

from .core.manager import FlowManager

__all__ = ["FlowManager"]

