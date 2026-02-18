"""
Audit Services Module - LGPD and HIPAA Compliance.

Two complementary services:

1. AuditService (mixin-based, sync):
   Composed from BaseAuditService + QuizAuditMixin + AIAuditMixin + AuditReportsMixin.
   Used for quiz-link management, AI activity logging, and compliance reports.

2. AsyncAuditService (async, HIPAA):
   Tamper-proof integrity controls (SHA-256 checksums, chain of custody),
   PHI access tracking, data modification tracking, 6-year retention.
   Used by HIPAAAuditMiddleware and audit decorators.

Usage:
    # Sync service (quiz / AI / legacy callers)
    from app.services.audit import AuditService
    audit = AuditService(db)
    audit.log_link_created(...)

    # Async HIPAA service
    from app.services.audit import AsyncAuditService, AuditEventContext
    audit = AsyncAuditService(db)
    await audit.log_event(event_type=..., event_category=..., context=context)
"""

# Sync mixin-based service (default export)
from app.services.audit.service import AuditService

# Async HIPAA service and utilities
from app.services.audit.audit_service import AuditService as AsyncAuditService
from app.services.audit.audit_service import AuditEventContext
from app.services.audit.audit_repository import AuditRepository

# Re-export base for callers that need it directly
from app.services.audit.base import BaseAuditService

__all__ = [
    "AuditService",
    "AsyncAuditService",
    "AuditEventContext",
    "AuditRepository",
    "BaseAuditService",
]
