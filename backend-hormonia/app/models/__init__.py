"""
SQLAlchemy models for Hormonia Backend System.
"""

from app.models.base import BaseModel
from app.models.user import User, UserRole, AuthProvider
from app.models.patient import Patient, FlowState
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.message_archive import MessageArchive
from app.models.template import MessageTemplate
from app.models.message_events import MessageStatusEvent, EvolutionWebhookEvent
from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.quiz import QuizTemplate, QuizResponse
from app.models.report import MedicalReport
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.flow_analytics import FlowAnalytics, FlowMessage

# Pydantic models for API responses (not SQLAlchemy)
from app.models.physician import (
    RiskAssessment,
    PatientRiskProfile,
    RiskAssessmentsResponse,
)

# Audit logging models
from app.models.audit_log import AuditLog, AuditEventType
from app.models.user_sync_log import UserSyncLog

# Sprint 1: Eager loading optimization models (P1-2)
from app.models.treatment import Treatment, TreatmentStatus, TreatmentType
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.medication import Medication
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.session import Session
from app.models.consent import Consent, ConsentType, ConsentStatus

# Sprint 2: Webhook idempotency (P6)
# Import as WebhookEvent to replace old message_events.WebhookEvent
from app.models.webhook_event import WebhookEvent
from app.models.webhook import WebhookEndpoint, WebhookDelivery, WebhookLog
from app.models.failed_message import FailedMessage, FailureReason, DLQStatus

# Error tracking models
from app.models.error_tracking import ErrorLog

# System Health models
from app.models.system_health import (
    SystemHealthSnapshot,
    SystemIncident,
    HealthStatus,
    IncidentSeverity,
    IncidentStatus,
)

# Upload tracking for quota management (P2-3)
from app.models.upload import Upload

# AI-generated patient summaries
from app.models.patient_summary import PatientSummary

# LGPD Audit models
from app.models.lgpd_audit import (
    LGPDAuditLog,
    DataAccessRequest,
    LGPDActionType,
    LGPDDataCategory,
)

# LGPD patient deletion audit (immutable append-only table, LGPD-01)
from app.models.patient_deletion_audit import PatientDeletionAudit

__all__ = [
    # Base
    "BaseModel",
    # User models
    "User",
    "UserRole",
    "AuthProvider",
    # Patient models
    "Patient",
    "FlowState",
    "PatientOnboardingSaga",
    "SagaStatus",
    # Message models
    "Message",
    "MessageDirection",
    "MessageType",
    "MessageStatus",
    "MessageArchive",
    "MessageTemplate",
    "MessageStatusEvent",
    "EvolutionWebhookEvent",  # Evolution API webhook debugging
    "WebhookEvent",  # Idempotency tracking from webhook_event.py
    # Flow models
    "PatientFlowState",
    "FlowKind",
    "FlowTemplateVersion",
    # Quiz models
    "QuizTemplate",
    "QuizResponse",
    # Report models
    "MedicalReport",
    # Alert models
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    # Analytics models
    "FlowAnalytics",
    "FlowMessage",
    # Physician API models (Pydantic)
    "RiskAssessment",
    "PatientRiskProfile",
    "RiskAssessmentsResponse",
    # Audit logging models
    "AuditLog",
    "AuditEventType",
    "UserSyncLog",
    # Sprint 1: Eager loading optimization models (P1-2)
    "Treatment",
    "TreatmentStatus",
    "TreatmentType",
    "Appointment",
    "AppointmentStatus",
    "AppointmentType",
    "Medication",
    "Notification",
    "NotificationType",
    "NotificationPriority",
    "Session",
    "Consent",
    "ConsentType",
    "ConsentStatus",
    # Sprint 2: Webhook idempotency (P6) - WebhookEvent exported above
    "FailedMessage",
    "FailureReason",
    "DLQStatus",
    # Error tracking models
    "ErrorLog",
    # System Health models
    "SystemHealthSnapshot",
    "SystemIncident",
    "HealthStatus",
    "IncidentSeverity",
    "IncidentStatus",
    # Upload tracking (P2-3)
    "Upload",
    # Webhook Management (P6)
    "WebhookEndpoint",
    "WebhookDelivery",
    "WebhookLog",
    # AI Patient Summaries
    "PatientSummary",
    # LGPD Audit models
    "LGPDAuditLog",
    "DataAccessRequest",
    "LGPDActionType",
    "LGPDDataCategory",
    # LGPD patient deletion audit (LGPD-01)
    "PatientDeletionAudit",
]
