"""
Backward compatibility shim for FlowErrorHandler.

Use app.services.flow.errors.handler instead.
"""

from ..errors.handler import FlowErrorHandler

__all__ = ["FlowErrorHandler"]

