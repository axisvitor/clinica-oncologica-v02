"""
Audit Service Package for LGPD Compliance and Security Logging.

This package provides comprehensive audit logging for all security-relevant
events in the system, ensuring LGPD and HIPAA compliance.

Re-exports AuditService for backward compatibility.
"""

from app.services.audit_service.service import AuditService

__all__ = ['AuditService']
