"""
Audit Service - Complete Implementation.

Combines all mixins to create the full AuditService class with:
- Core logging functionality (AuditServiceBase)
- Quiz-specific audit methods (QuizAuditMixin)
- AI-specific audit methods (AIAuditMixin)
- Compliance reporting methods (AuditReportsMixin)

This service provides comprehensive audit logging for LGPD and HIPAA compliance.
"""

from app.services.audit_service.base import AuditServiceBase
from app.services.audit_service.quiz_audit import QuizAuditMixin
from app.services.audit_service.ai_audit import AIAuditMixin
from app.services.audit_service.reports import AuditReportsMixin


class AuditService(QuizAuditMixin, AIAuditMixin, AuditReportsMixin, AuditServiceBase):
    """
    Complete Audit Service with LGPD and HIPAA compliance.

    Combines all audit functionality through multiple inheritance:
    - QuizAuditMixin: Quiz link and access logging
    - AIAuditMixin: AI chat, insights, and analysis logging
    - AuditReportsMixin: Compliance reporting and queries
    - AuditServiceBase: Core log_event method and database access

    Usage:
        audit_service = AuditService(db_session)

        # Quiz logging
        audit_service.log_link_created(...)
        audit_service.log_response_submitted(...)

        # AI logging
        audit_service.log_ai_chat_request(...)
        audit_service.log_ai_insights_generation(...)

        # Compliance reporting
        report = audit_service.get_ai_audit_report(...)
        export = audit_service.export_ai_audit_data(...)
    """

    pass
