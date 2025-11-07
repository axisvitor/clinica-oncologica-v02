"""
Alert schemas for API v2

Enhanced alert models with:
- Pydantic V2 validation and field constraints
- Comprehensive type hints and documentation
- Nested models for complex data structures
- Alert rule engine schemas
- Risk scoring models
- Escalation workflow schemas
- Bulk operation models
- Trend analysis schemas

CRITICAL: These schemas validate patient safety alert data.
All validation rules must be thorough to prevent data integrity issues.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, validator, constr, conint, confloat

from app.models.alert import AlertSeverity, AlertStatus
from .common import CursorPaginatedResponse


# ============================================================================
# Enums and Constants
# ============================================================================

class AlertTypeEnum(str, Enum):
    """Standard alert types for the system."""
    MISSED_MEDICATION = "missed_medication"
    ABNORMAL_VITAL_SIGNS = "abnormal_vital_signs"
    QUIZ_FAILED = "quiz_failed"
    TREATMENT_DELAY = "treatment_delay"
    SIDE_EFFECT_REPORTED = "side_effect_reported"
    EMERGENCY = "emergency"
    APPOINTMENT_MISSED = "appointment_missed"
    LAB_RESULT_ABNORMAL = "lab_result_abnormal"
    CUSTOM = "custom"


class RiskLevel(str, Enum):
    """Patient risk levels based on alert history."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EscalationStatus(str, Enum):
    """Alert escalation workflow status."""
    NOT_ESCALATED = "not_escalated"
    ESCALATED_TO_PHYSICIAN = "escalated_to_physician"
    ESCALATED_TO_SPECIALIST = "escalated_to_specialist"
    ESCALATED_TO_EMERGENCY = "escalated_to_emergency"


# ============================================================================
# Base Schemas
# ============================================================================

class AlertV2Base(BaseModel):
    """Base alert schema with common fields."""

    alert_type: constr(min_length=1, max_length=100) = Field(
        ...,
        description="Type of alert (e.g., missed_medication, abnormal_vital_signs)"
    )
    severity: AlertSeverity = Field(
        ...,
        description="Alert severity level (LOW, MEDIUM, HIGH, CRITICAL)"
    )
    description: constr(min_length=1, max_length=2000) = Field(
        ...,
        description="Detailed description of the alert"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional structured data (JSONB field)"
    )

    @validator("description")
    def validate_description(cls, v):
        """Ensure description is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Description cannot be empty or whitespace only")
        return v.strip()

    @validator("data")
    def validate_data(cls, v):
        """Ensure data field doesn't contain PII without proper handling."""
        if v:
            # Ensure no direct SSN, credit card numbers, etc. in raw data
            sensitive_keywords = ["ssn", "credit_card", "password"]
            for key in v.keys():
                if any(keyword in key.lower() for keyword in sensitive_keywords):
                    raise ValueError(f"Sensitive field '{key}' should not be stored in alert data")
        return v


class PatientV2Brief(BaseModel):
    """Brief patient information for alert response."""

    id: str
    name: str
    email: Optional[str] = None

    class Config:
        from_attributes = True


class UserV2Brief(BaseModel):
    """Brief user information for alert response."""

    id: str
    name: str
    email: str

    class Config:
        from_attributes = True


# ============================================================================
# Request Schemas
# ============================================================================

class AlertV2Create(AlertV2Base):
    """Schema for creating a new alert."""

    patient_id: UUID = Field(
        ...,
        description="UUID of the patient this alert is for"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "123e4567-e89b-12d3-a456-426614174000",
                "alert_type": "missed_medication",
                "severity": "HIGH",
                "description": "Patient missed medication dose at 14:00",
                "data": {
                    "medication_name": "Anastrozole",
                    "scheduled_time": "14:00",
                    "missed_time": "14:30"
                }
            }
        }


class AlertV2Update(BaseModel):
    """Schema for updating an alert."""

    alert_type: Optional[constr(max_length=100)] = None
    severity: Optional[AlertSeverity] = None
    description: Optional[constr(max_length=2000)] = None
    data: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "severity": "MEDIUM",
                "description": "Updated: Patient took medication at 15:00 (delayed)"
            }
        }


class AlertV2Acknowledge(BaseModel):
    """Schema for acknowledging an alert."""

    notes: Optional[constr(max_length=1000)] = Field(
        None,
        description="Optional notes about the acknowledgment"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "notes": "Reviewed with patient. Patient confirmed medication taken."
            }
        }


class AlertV2Resolve(BaseModel):
    """Schema for resolving an alert."""

    notes: constr(min_length=1, max_length=2000) = Field(
        ...,
        description="Required notes explaining the resolution"
    )

    @validator("notes")
    def validate_notes(cls, v):
        """Ensure resolution notes are meaningful."""
        if not v or not v.strip():
            raise ValueError("Resolution notes are required and cannot be empty")
        if len(v.strip()) < 10:
            raise ValueError("Resolution notes must be at least 10 characters")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "notes": "Patient contacted. Confirmed medication adherence plan. Will monitor for next 48 hours."
            }
        }


class AlertV2Dismiss(BaseModel):
    """Schema for dismissing an alert (false positive)."""

    reason: constr(min_length=10, max_length=1000) = Field(
        ...,
        description="Required reason for dismissal (for audit trail)"
    )

    @validator("reason")
    def validate_reason(cls, v):
        """Ensure dismissal reason is meaningful."""
        if not v or not v.strip():
            raise ValueError("Dismissal reason is required")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "reason": "False positive: Patient had taken medication earlier than scheduled with physician approval."
            }
        }


# ============================================================================
# Response Schemas
# ============================================================================

class AlertV2Response(AlertV2Base):
    """Full alert response with all fields."""

    id: str = Field(description="Alert UUID")
    patient_id: str = Field(description="Patient UUID")
    status: str = Field(description="Alert status (pending, acknowledged, resolved)")
    acknowledged: bool = Field(description="Whether alert has been acknowledged")
    acknowledged_by: Optional[str] = Field(None, description="UUID of user who acknowledged")
    acknowledged_at: Optional[datetime] = Field(None, description="When alert was acknowledged")
    created_at: datetime = Field(description="When alert was created")
    updated_at: datetime = Field(description="When alert was last updated")

    # Optional eager-loaded relationships
    patient: Optional[PatientV2Brief] = None
    acknowledged_by_user: Optional[UserV2Brief] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "patient_id": "223e4567-e89b-12d3-a456-426614174001",
                "alert_type": "missed_medication",
                "severity": "HIGH",
                "description": "Patient missed medication dose at 14:00",
                "status": "acknowledged",
                "acknowledged": True,
                "acknowledged_by": "323e4567-e89b-12d3-a456-426614174002",
                "acknowledged_at": "2025-01-17T15:30:00Z",
                "created_at": "2025-01-17T14:30:00Z",
                "updated_at": "2025-01-17T15:30:00Z",
                "data": {
                    "medication_name": "Anastrozole",
                    "scheduled_time": "14:00"
                },
                "patient": {
                    "id": "223e4567-e89b-12d3-a456-426614174001",
                    "name": "Jane Doe",
                    "email": "jane@example.com"
                }
            }
        }


class AlertV2List(CursorPaginatedResponse[AlertV2Response]):
    """Paginated list of alerts with cursor-based pagination."""
    pass


# ============================================================================
# Alert Summary and Statistics Schemas
# ============================================================================

class PatientAlertSummaryV2(BaseModel):
    """Comprehensive alert summary for a patient."""

    patient_id: UUID = Field(description="Patient UUID")
    total_alerts: conint(ge=0) = Field(description="Total number of alerts")
    pending_alerts: conint(ge=0) = Field(description="Number of unresolved alerts")
    critical_alerts: conint(ge=0) = Field(description="Number of critical severity alerts")
    high_alerts: conint(ge=0) = Field(description="Number of high severity alerts")
    medium_alerts: conint(ge=0) = Field(description="Number of medium severity alerts")
    low_alerts: conint(ge=0) = Field(description="Number of low severity alerts")
    recent_alerts_7d: conint(ge=0) = Field(description="Alerts in last 7 days")
    last_alert_at: Optional[datetime] = Field(None, description="Timestamp of most recent alert")
    risk_score: confloat(ge=0) = Field(description="Calculated risk score")
    risk_level: str = Field(description="Risk level (LOW, MEDIUM, HIGH, CRITICAL)")
    risk_factors: List[str] = Field(default_factory=list, description="Contributing risk factors")

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "223e4567-e89b-12d3-a456-426614174001",
                "total_alerts": 15,
                "pending_alerts": 3,
                "critical_alerts": 1,
                "high_alerts": 4,
                "medium_alerts": 7,
                "low_alerts": 3,
                "recent_alerts_7d": 5,
                "last_alert_at": "2025-01-17T14:30:00Z",
                "risk_score": 45.5,
                "risk_level": "HIGH",
                "risk_factors": [
                    "Recent critical alert",
                    "Unresolved high alert",
                    "Multiple medication alerts"
                ]
            }
        }


class AlertStatisticsV2(BaseModel):
    """System-wide alert statistics and analytics."""

    total_alerts: conint(ge=0) = Field(description="Total alerts in period")
    pending_alerts: conint(ge=0) = Field(description="Unresolved alerts")
    acknowledged_alerts: conint(ge=0) = Field(description="Acknowledged alerts")
    resolved_alerts: conint(ge=0) = Field(description="Resolved alerts")
    critical_count: conint(ge=0) = Field(description="Critical severity count")
    high_count: conint(ge=0) = Field(description="High severity count")
    medium_count: conint(ge=0) = Field(description="Medium severity count")
    low_count: conint(ge=0) = Field(description="Low severity count")
    avg_response_time_minutes: confloat(ge=0) = Field(description="Average acknowledgment time")
    top_alert_types: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Most common alert types"
    )
    analysis_period_days: conint(ge=1) = Field(description="Analysis period in days")

    class Config:
        json_schema_extra = {
            "example": {
                "total_alerts": 450,
                "pending_alerts": 23,
                "acknowledged_alerts": 380,
                "resolved_alerts": 340,
                "critical_count": 12,
                "high_count": 67,
                "medium_count": 234,
                "low_count": 137,
                "avg_response_time_minutes": 45.5,
                "top_alert_types": [
                    {"type": "missed_medication", "count": 120},
                    {"type": "quiz_failed", "count": 85},
                    {"type": "treatment_delay", "count": 67}
                ],
                "analysis_period_days": 30
            }
        }


# ============================================================================
# Risk Scoring Schemas
# ============================================================================

class PatientRiskScoreV2(BaseModel):
    """Comprehensive patient risk assessment based on alert history."""

    patient_id: UUID = Field(description="Patient UUID")
    risk_score: confloat(ge=0) = Field(description="Calculated risk score (0-100+)")
    risk_level: RiskLevel = Field(description="Risk level category")
    risk_factors: List[str] = Field(
        default_factory=list,
        description="Key factors contributing to risk score"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable recommendations based on risk"
    )
    calculated_at: datetime = Field(description="When risk score was calculated")
    alert_count_30d: conint(ge=0) = Field(description="Alert count in last 30 days")
    unresolved_count: conint(ge=0) = Field(description="Current unresolved alerts")

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "223e4567-e89b-12d3-a456-426614174001",
                "risk_score": 65.5,
                "risk_level": "CRITICAL",
                "risk_factors": [
                    "Recent critical alert",
                    "Multiple unresolved high alerts",
                    "Pattern of missed medications"
                ],
                "recommendations": [
                    "Immediate physician review required",
                    "Consider escalating to specialist",
                    "Address 3 unresolved alerts"
                ],
                "calculated_at": "2025-01-17T15:00:00Z",
                "alert_count_30d": 12,
                "unresolved_count": 3
            }
        }


# ============================================================================
# Alert Rule Engine Schemas
# ============================================================================

class AlertRuleV2(BaseModel):
    """Alert rule configuration for automated alert generation."""

    id: str = Field(description="Rule UUID")
    rule_type: constr(min_length=1, max_length=100) = Field(
        description="Type of rule (e.g., medication_adherence, vital_signs)"
    )
    name: constr(min_length=1, max_length=200) = Field(description="Human-readable rule name")
    description: Optional[str] = Field(None, description="Rule description")
    severity: AlertSeverity = Field(description="Severity for alerts generated by this rule")
    enabled: bool = Field(default=True, description="Whether rule is active")
    conditions: Dict[str, Any] = Field(
        ...,
        description="Rule conditions (threshold, time_window, etc.)"
    )
    alert_template: str = Field(
        ...,
        description="Template for alert description (supports variables)"
    )
    created_at: datetime = Field(description="When rule was created")
    updated_at: datetime = Field(description="When rule was last updated")
    created_by: str = Field(description="UUID of user who created rule")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "423e4567-e89b-12d3-a456-426614174003",
                "rule_type": "medication_adherence",
                "name": "Missed Medication Alert",
                "description": "Alert when patient misses scheduled medication",
                "severity": "HIGH",
                "enabled": True,
                "conditions": {
                    "threshold_minutes": 30,
                    "medications": ["Anastrozole", "Letrozole"]
                },
                "alert_template": "Patient missed {medication_name} at {scheduled_time}",
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-01-15T14:00:00Z",
                "created_by": "323e4567-e89b-12d3-a456-426614174002"
            }
        }


class AlertRuleV2Create(BaseModel):
    """Schema for creating alert rules."""

    rule_type: constr(min_length=1, max_length=100) = Field(description="Type of rule")
    name: constr(min_length=1, max_length=200) = Field(description="Rule name")
    description: Optional[str] = Field(None, max_length=1000)
    severity: AlertSeverity = Field(description="Severity for generated alerts")
    enabled: bool = Field(default=True)
    conditions: Dict[str, Any] = Field(..., description="Rule conditions")
    alert_template: constr(min_length=1, max_length=500) = Field(
        description="Alert description template"
    )

    @validator("conditions")
    def validate_conditions(cls, v):
        """Validate that conditions have required fields."""
        if not v:
            raise ValueError("Conditions cannot be empty")
        # Add specific validation based on rule type if needed
        return v


class AlertRuleV2Update(BaseModel):
    """Schema for updating alert rules."""

    name: Optional[constr(max_length=200)] = None
    description: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    enabled: Optional[bool] = None
    conditions: Optional[Dict[str, Any]] = None
    alert_template: Optional[constr(max_length=500)] = None


# ============================================================================
# Bulk Operations Schemas
# ============================================================================

class BulkAlertOperation(BaseModel):
    """Schema for bulk alert operations (acknowledge, resolve, etc.)."""

    alert_ids: List[UUID] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="List of alert UUIDs to operate on (max 100)"
    )
    notes: Optional[constr(max_length=1000)] = Field(
        None,
        description="Optional notes for the bulk operation"
    )

    @validator("alert_ids")
    def validate_alert_ids(cls, v):
        """Ensure no duplicate alert IDs."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate alert IDs are not allowed")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "alert_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "223e4567-e89b-12d3-a456-426614174001",
                    "323e4567-e89b-12d3-a456-426614174002"
                ],
                "notes": "Bulk acknowledged after patient phone consultation"
            }
        }


class BulkAlertResult(BaseModel):
    """Result of a bulk alert operation."""

    success_count: conint(ge=0) = Field(description="Number of successfully processed alerts")
    failed_count: conint(ge=0) = Field(description="Number of failed operations")
    failed_ids: List[str] = Field(
        default_factory=list,
        description="UUIDs of alerts that failed to process"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success_count": 3,
                "failed_count": 0,
                "failed_ids": []
            }
        }


# ============================================================================
# Trend Analysis Schemas
# ============================================================================

class AlertTrendV2(BaseModel):
    """Alert trend data for analytics."""

    date: date = Field(description="Date of the data point")
    total_alerts: conint(ge=0) = Field(description="Total alerts on this date")
    critical_alerts: conint(ge=0) = Field(description="Critical alerts")
    high_alerts: conint(ge=0) = Field(description="High severity alerts")
    medium_alerts: conint(ge=0) = Field(description="Medium severity alerts")
    low_alerts: conint(ge=0) = Field(description="Low severity alerts")

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-01-17",
                "total_alerts": 45,
                "critical_alerts": 2,
                "high_alerts": 8,
                "medium_alerts": 23,
                "low_alerts": 12
            }
        }


# ============================================================================
# Escalation Workflow Schemas
# ============================================================================

class AlertEscalationV2(BaseModel):
    """Alert escalation information."""

    alert_id: UUID = Field(description="Alert UUID")
    escalation_status: EscalationStatus = Field(description="Current escalation status")
    escalated_at: Optional[datetime] = Field(None, description="When escalated")
    escalated_by: Optional[str] = Field(None, description="UUID of user who escalated")
    escalated_to: Optional[str] = Field(None, description="UUID of user escalated to")
    escalation_notes: Optional[str] = Field(None, description="Escalation notes")
    resolution_deadline: Optional[datetime] = Field(
        None,
        description="Deadline for resolution (based on severity)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "alert_id": "123e4567-e89b-12d3-a456-426614174000",
                "escalation_status": "escalated_to_specialist",
                "escalated_at": "2025-01-17T15:30:00Z",
                "escalated_by": "323e4567-e89b-12d3-a456-426614174002",
                "escalated_to": "423e4567-e89b-12d3-a456-426614174003",
                "escalation_notes": "Patient showing severe side effects, specialist review needed",
                "resolution_deadline": "2025-01-17T18:00:00Z"
            }
        }
