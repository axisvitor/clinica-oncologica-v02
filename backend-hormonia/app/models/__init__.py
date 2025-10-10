"""
SQLAlchemy models for Hormonia Backend System.
"""
from app.models.base import BaseModel
from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState
from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.message_events import MessageStatusEvent
from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.quiz import QuizTemplate, QuizResponse
from app.models.report import MedicalReport
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.flow_analytics import FlowAnalytics, FlowMessage, QuizQuestion
from app.models.ab_experiment import (
    ABExperiment,
    ABVariantAssignment,
    ABExperimentMetric,
    ABExperimentResult,
    ABExperimentAudit,
    ABExperimentMonitoring,
    ExperimentStatus,
    VariantType,
    PatientSafetyLevel
)
# Pydantic models for API responses (not SQLAlchemy)
from app.models.physician import (
    RiskAssessment,
    PatientRiskProfile,
    RiskAssessmentsResponse
)
# Audit logging models
from app.models.audit_log import AuditLog, AuditEventType

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

__all__ = [
    # Base
    "BaseModel",

    # User models
    "User",
    "UserRole",

    # Patient models
    "Patient",
    "FlowState",

    # Message models
    "Message",
    "MessageDirection",
    "MessageType",
    "MessageStatus",
    "MessageStatusEvent",
    "WebhookEvent",  # Re-exported from webhook_event.py as IdempotentWebhookEvent

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
    "QuizQuestion",

    # A/B Testing models
    "ABExperiment",
    "ABVariantAssignment",
    "ABExperimentMetric",
    "ABExperimentResult",
    "ABExperimentAudit",
    "ABExperimentMonitoring",
    "ExperimentStatus",
    "VariantType",
    "PatientSafetyLevel",

    # Physician API models (Pydantic)
    "RiskAssessment",
    "PatientRiskProfile",
    "RiskAssessmentsResponse",

    # Audit logging models
    "AuditLog",
    "AuditEventType",

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
]
