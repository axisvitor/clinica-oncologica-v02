from typing import Any
"""
HIPAA Audit Services Module - Phase 3 Sprint 1

This module provides comprehensive HIPAA-compliant audit logging:
- AuditService: High-level audit logging with tamper-proof integrity
- AuditRepository: Database operations for audit logs
- AuditEventContext: Structured context for audit events

Example Usage:
    from app.services.audit import AuditService, AuditEventContext
    from app.models.audit_log import AuditEventType

    # Create audit service
    audit_service = AuditService(db)

    # Log PHI access
    await audit_service.log_event(
        event_type=AuditEventType.PHI_PATIENT_VIEW,
        event_category="PHI_ACCESS",
        context=AuditEventContext(
            user_id=user.id,
            resource_type="PATIENT",
            resource_id=patient.id,
            ip_address=request.client.host,
            status="SUCCESS"
        )
    )

    # Verify integrity
    integrity_result = await audit_service.verify_integrity()
    if integrity_result['has_tampering']:
        # Alert security team!
        pass
"""

from app.services.audit.audit_service import AuditService, AuditEventContext
from app.services.audit.audit_repository import AuditRepository

__all__ = [
    "AuditService",
    "AuditEventContext",
    "AuditRepository",
]
