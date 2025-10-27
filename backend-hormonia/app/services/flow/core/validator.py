"""
Backward compatibility shim for FlowValidator.

Use app.services.flow.validation.validator instead of the old
app.services.flow.core.validator module.
"""

from ..validation.validator import FlowValidator

__all__ = ["FlowValidator"]

