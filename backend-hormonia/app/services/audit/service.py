"""
Audit Service - Final Composition.

Combines all mixins into the complete AuditService class.
"""

from app.services.audit.base import BaseAuditService
from app.services.audit.quiz_audit import QuizAuditMixin
from app.services.audit.ai_audit import AIAuditMixin
from app.services.audit.reports import AuditReportsMixin


class AuditService(BaseAuditService, QuizAuditMixin, AIAuditMixin, AuditReportsMixin):
    """
    Complete Audit Service for LGPD and HIPAA Compliance.

    This service provides comprehensive audit logging for all security-relevant
    events in the monthly quiz system and AI features, ensuring LGPD and HIPAA
    compliance and traceability.

    Composition:
    - BaseAuditService: Core log_event method and initialization
    - QuizAuditMixin: Quiz-related audit methods
    - AIAuditMixin: AI-related audit methods with HIPAA compliance
    - AuditReportsMixin: Query and reporting methods

    ADAPTER VERSION: Compatible with new AuditLog model schema.
    """
    pass
