"""
Audit Services Module - LGPD and HIPAA Compliance

This module provides comprehensive audit logging:
- AuditService (from service.py): Legacy LGPD-compliant audit service with quiz and AI methods
  - Composed from BaseAuditService, QuizAuditMixin, AIAuditMixin, AuditReportsMixin
  - Synchronous API for backward compatibility
- AuditService from audit_service.py: HIPAA-compliant async audit service
  - Tamper-proof integrity controls
  - PHI access tracking
  - Async/await API
- AuditRepository: Database operations for audit logs
- AuditEventContext: Structured context for audit events

Usage:
    # Legacy LGPD service (synchronous)
    from app.services.audit import AuditService as LegacyAuditService
    audit = LegacyAuditService(db)
    audit.log_link_created(...)

    # HIPAA async service
    from app.services.audit.audit_service import AuditService, AuditEventContext
    audit = AuditService(db)
    await audit.log_event(...)
"""

# Legacy LGPD-compliant service (synchronous, mixin-based)
from app.services.audit.service import AuditService

# HIPAA async service and utilities
from app.services.audit.audit_service import AuditService as AsyncAuditService
from app.services.audit.audit_service import AuditEventContext
from app.services.audit.audit_repository import AuditRepository

__all__ = [
    # Legacy sync service (default export for backward compatibility)
    "AuditService",
    # HIPAA async service
    "AsyncAuditService",
    "AuditEventContext",
    "AuditRepository",
]
