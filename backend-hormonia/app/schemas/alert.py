"""
Alert schemas for API validation and serialization.
"""
from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.models.alert import AlertSeverity, AlertStatus


class AlertBase(BaseModel):
    """Base alert schema."""
    alert_type: str = Field(..., description="Type of alert")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    description: str = Field(..., description="Alert description")
    data: Optional[dict[str, Any]] = Field(default=None, description="Additional alert data")


class AlertCreate(AlertBase):
    """Schema for creating alerts."""
    patient_id: UUID = Field(..., description="Patient ID")


class AlertUpdate(BaseModel):
    """Schema for updating alerts."""
    status: Optional[AlertStatus] = Field(None, description="Alert status")
    acknowledged_by: Optional[UUID] = Field(None, description="User who acknowledged the alert")


class AlertResponse(AlertBase):
    """Schema for alert responses."""
    id: UUID = Field(..., description="Alert ID")
    patient_id: UUID = Field(..., description="Patient ID")
    status: AlertStatus = Field(..., description="Alert status")
    acknowledged_by: Optional[UUID] = Field(None, description="User who acknowledged the alert")
    acknowledged_at: Optional[datetime] = Field(None, description="When alert was acknowledged")
    resolved_at: Optional[datetime] = Field(None, description="When alert was resolved")
    created_at: datetime = Field(..., description="When alert was created")
    updated_at: datetime = Field(..., description="When alert was last updated")

    model_config = ConfigDict(from_attributes=True)


class AlertAcknowledge(BaseModel):
    """Schema for acknowledging alerts."""
    user_id: UUID = Field(..., description="ID of user acknowledging the alert")


class AlertRuleConfig(BaseModel):
    """Schema for alert rule configuration."""
    rule_type: str = Field(..., description="Type of alert rule")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    threshold: float = Field(..., description="Threshold value for triggering alert")
    time_window_hours: int = Field(..., description="Time window in hours for evaluation")
    description_template: str = Field(..., description="Template for alert description")
    enabled: bool = Field(default=True, description="Whether rule is enabled")


class AlertStatistics(BaseModel):
    """Schema for alert statistics."""
    total_pending: int = Field(..., description="Total pending alerts")
    critical_count: int = Field(..., description="Number of critical alerts")
    high_count: int = Field(..., description="Number of high severity alerts")
    medium_count: int = Field(..., description="Number of medium severity alerts")
    low_count: int = Field(..., description="Number of low severity alerts")
    active_rules: int = Field(..., description="Number of active alert rules")


class AlertListResponse(BaseModel):
    """Schema for paginated alert list response."""
    items: list[AlertResponse] = Field(..., description="List of alerts")
    total: int = Field(..., description="Total number of alerts")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")


class PatientAlertSummary(BaseModel):
    """Schema for patient alert summary."""
    patient_id: UUID = Field(..., description="Patient ID")
    total_alerts: int = Field(..., description="Total alerts for patient")
    pending_alerts: int = Field(..., description="Pending alerts for patient")
    critical_alerts: int = Field(..., description="Critical alerts for patient")
    last_alert_at: Optional[datetime] = Field(None, description="When last alert was created")