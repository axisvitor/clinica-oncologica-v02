"""
Backward-compatible audit models module.

Legacy tests import ``app.models.audit`` while the actual implementation
resides in ``app.models.audit_log``. This module re-exports the canonical
classes to preserve those imports without duplicating logic.
"""

from app.models.audit_log import AuditLog, AuditEventType

__all__ = ["AuditLog", "AuditEventType"]
