"""
SQLAlchemy models for Hormonia Backend System.
"""
from app.models.base import BaseModel
from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState
from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.message_events import MessageStatusEvent, WebhookEvent
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
    "WebhookEvent",

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
]
