"""
Audit Schemas for LGPD Compliance.

Pydantic schemas for audit logging and privacy management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict


class AuditLogBase(BaseModel):
    """Base schema for audit logs."""
    event_type: str = Field(..., description="Type of event")
    event_category: str = Field(..., description="Category: security, access, data_change, consent")
    severity: str = Field(default="info", description="Severity: info, warning, error, critical")
    user_id: Optional[UUID] = None
    patient_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    event_data: Optional[Dict[str, Any]] = None
    result: str = Field(default="success", description="Result: success, failure, blocked")

    @field_validator('event_category')
    @classmethod
    def validate_category(cls, v):
        allowed = ['security', 'access', 'data_change', 'consent']
        if v not in allowed:
            raise ValueError(f"Category must be one of {allowed}")
        return v

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v):
        allowed = ['info', 'warning', 'error', 'critical']
        if v not in allowed:
            raise ValueError(f"Severity must be one of {allowed}")
        return v


class AuditLogCreate(AuditLogBase):
    """Schema for creating audit logs."""
    data_subject_id: Optional[UUID] = None
    legal_basis: Optional[str] = None
    retention_days: int = Field(default=365, ge=1, le=2555)


class AuditLogResponse(AuditLogBase):
    """Schema for audit log responses."""
    id: str
    timestamp: datetime
    data_subject_id: Optional[str] = None
    legal_basis: Optional[str] = None
    retention_until: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConsentRecordBase(BaseModel):
    """Base schema for consent records."""
    patient_id: UUID
    consent_type: str = Field(..., description="Type: data_collection, data_processing, marketing")
    consent_given: bool
    consent_text: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConsentRecordCreate(ConsentRecordBase):
    """Schema for creating consent records."""
    pass


class ConsentRecordResponse(ConsentRecordBase):
    """Schema for consent record responses."""
    id: str
    given_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConsentStatus(BaseModel):
    """Schema for consent status."""
    consent_type: str
    given: bool
    given_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class PatientDataExport(BaseModel):
    """Schema for patient data export (LGPD compliance)."""
    export_date: datetime
    patient: Dict[str, Any]
    quiz_sessions: List[Dict[str, Any]]
    quiz_responses: List[Dict[str, Any]]
    consents: List[Dict[str, Any]]
    audit_trail: List[Dict[str, Any]]


class DataDeletionRequest(BaseModel):
    """Schema for data deletion request."""
    patient_id: UUID
    reason: str = Field(..., min_length=10, max_length=500)
    scope: str = Field(default="all", description="Scope: all, quiz_only, consents_only")

    @field_validator('scope')
    @classmethod
    def validate_scope(cls, v):
        allowed = ['all', 'quiz_only', 'consents_only']
        if v not in allowed:
            raise ValueError(f"Scope must be one of {allowed}")
        return v


class DataDeletionResponse(BaseModel):
    """Schema for data deletion response."""
    patient_id: UUID
    deleted_at: datetime
    deleted_counts: Dict[str, int]
    scope: str


class AnonymizationRequest(BaseModel):
    """Schema for data anonymization request."""
    patient_id: UUID
    retention_cutoff_days: int = Field(default=730, ge=1, le=3650)


class AnonymizationResponse(BaseModel):
    """Schema for anonymization response."""
    patient_id: UUID
    anonymized_at: datetime
    anonymized_counts: Dict[str, int]


class SecurityIncidentReport(BaseModel):
    """Schema for security incident reporting."""
    incident_type: str = Field(..., description="Type of security incident")
    severity: str = Field(..., description="Severity: low, medium, high, critical")
    description: str = Field(..., min_length=20)
    affected_patients: Optional[List[UUID]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    mitigation_actions: Optional[str] = None

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v):
        allowed = ['low', 'medium', 'high', 'critical']
        if v not in allowed:
            raise ValueError(f"Severity must be one of {allowed}")
        return v


# ============================================================================
# AI Audit Schemas (HIPAA Compliant)
# ============================================================================

class AIAuditLogBase(BaseModel):
    """Base schema for AI audit logs."""
    event_type: str = Field(..., description="AI event type (e.g., ai_chat_request)")
    user_id: UUID
    user_role: str
    patient_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    response_time_ms: float = Field(..., ge=0)
    cache_hit: bool = False


class AIChatAuditLog(AIAuditLogBase):
    """Schema for AI chat audit logs."""
    message_hash: str = Field(..., description="SHA256 hash of message (privacy)")
    message_length: int
    response_summary: str = Field(..., max_length=200)
    response_length: int
    has_patient_context: bool


class AIInsightsAuditLog(AIAuditLogBase):
    """Schema for AI insights audit logs."""
    timeframe_days: int = Field(..., ge=1, le=90)
    insights_count: int = Field(..., ge=0)
    risk_level: str = Field(..., description="Risk level: low, moderate, high")

    @field_validator('risk_level')
    @classmethod
    def validate_risk_level(cls, v):
        allowed = ['low', 'moderate', 'high']
        if v not in allowed:
            raise ValueError(f"Risk level must be one of {allowed}")
        return v


class AIRecommendationsAuditLog(AIAuditLogBase):
    """Schema for AI recommendations audit logs."""
    recommendations_count: int = Field(..., ge=0)
    action_items_count: int = Field(..., ge=0)
    confidence_level: float = Field(..., ge=0, le=1)


class AIAnalysisAuditLog(AIAuditLogBase):
    """Schema for AI analysis audit logs."""
    analysis_type: str
    date_range_days: int = Field(..., ge=1)
    include_messages: bool
    include_medical_history: bool


class AISentimentAuditLog(AIAuditLogBase):
    """Schema for AI sentiment analysis audit logs."""
    message_hash: str
    message_length: int
    sentiment: str
    concern_level: str
    confidence: float = Field(..., ge=0, le=1)


class AIResponseGenerationAuditLog(AIAuditLogBase):
    """Schema for AI response generation audit logs."""
    message_type: str
    template_length: int
    generated_length: int
    readability_score: float = Field(..., ge=0, le=1)


class AICacheAuditLog(BaseModel):
    """Schema for AI cache audit logs."""
    event_type: str = Field(..., description="ai_cache_hit or ai_cache_miss")
    cache_key_hash: str = Field(..., description="SHA256 hash of cache key")
    endpoint: str
    response_time_ms: float = Field(..., ge=0)
    user_id: Optional[UUID] = None


class AIAuditReportRequest(BaseModel):
    """Schema for AI audit report requests."""
    start_date: datetime
    end_date: datetime
    event_types: Optional[List[str]] = None
    user_id: Optional[UUID] = None
    patient_id: Optional[UUID] = None

    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v, info):
        if 'start_date' in info.data and v < info.data['start_date']:
            raise ValueError("end_date must be after start_date")
        return v


class AIAuditReportResponse(BaseModel):
    """Schema for AI audit report responses."""
    total_logs: int
    period: Dict[str, str]
    logs: List[AuditLogResponse]
    summary: Dict[str, Any]


class AIPerformanceMetrics(BaseModel):
    """Schema for AI performance metrics."""
    total_requests: int
    cache_hit_rate: float = Field(..., ge=0, le=1)
    error_rate: float = Field(..., ge=0, le=1)
    average_response_time_ms: float
    period: Dict[str, str]


class AISecurityEvent(BaseModel):
    """Schema for AI security events."""
    event_type: str
    severity: str
    timestamp: datetime
    actor_id: Optional[str] = None
    subject_id: Optional[str] = None
    ip_address: Optional[str] = None
    event_data: Optional[Dict[str, Any]] = None
    result: str


class PatientAIAccessHistory(BaseModel):
    """Schema for patient AI access history."""
    patient_id: UUID
    total_accesses: int
    access_logs: List[AuditLogResponse]
    summary: Dict[str, Any]


class AIAuditExport(BaseModel):
    """Schema for AI audit data export (HIPAA compliance)."""
    patient_id: UUID
    export_date: datetime
    total_logs: int
    logs: List[Dict[str, Any]]
    compliance_statement: str = Field(
        default="This export contains all AI-related audit logs for the specified patient in compliance with HIPAA regulations."
    )