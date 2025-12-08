"""
Dashboard schemas for API v2

Enhanced dashboard models with:
- Pydantic V2 validation and field constraints
- Comprehensive type hints and documentation
- Widget configuration models
- Metric and chart data structures
- Role-based dashboard schemas
- Time range filtering enums
- Custom layout configurations

These schemas support dashboard widgets that display aggregated
patient data, system metrics, and real-time analytics.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict, constr, conint, confloat


# ============================================================================
# Enums and Constants
# ============================================================================

class TimeRangeEnum(str, Enum):
    """Time range options for dashboard metrics."""
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class WidgetTypeEnum(str, Enum):
    """Widget types for dashboard customization."""
    METRIC_CARD = "metric_card"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    DONUT_CHART = "donut_chart"
    TABLE = "table"
    ACTIVITY_FEED = "activity_feed"
    PROGRESS_BAR = "progress_bar"
    ALERT_SUMMARY = "alert_summary"
    HEATMAP = "heatmap"


class WidgetSizeEnum(str, Enum):
    """Widget size options for responsive layouts."""
    SMALL = "small"  # 1x1 grid
    MEDIUM = "medium"  # 2x1 grid
    LARGE = "large"  # 2x2 grid
    WIDE = "wide"  # 4x1 grid
    FULL = "full"  # Full width


# ============================================================================
# Base Widget Schemas
# ============================================================================

class WidgetConfig(BaseModel):
    """Configuration for a dashboard widget."""

    widget_id: str = Field(description="Unique widget identifier")
    widget_type: WidgetTypeEnum = Field(description="Type of widget")
    title: constr(min_length=1, max_length=200) = Field(description="Widget title")
    size: WidgetSizeEnum = Field(default=WidgetSizeEnum.MEDIUM, description="Widget size")
    position: Dict[str, int] = Field(
        default={"x": 0, "y": 0},
        description="Widget position in grid (x, y coordinates)"
    )
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Widget-specific configuration"
    )
    refresh_interval: Optional[conint(ge=30, le=3600)] = Field(
        None,
        description="Auto-refresh interval in seconds (30-3600)"
    )

    @field_validator("position")
    @classmethod
    def validate_position(cls, v):
        """Ensure position has x and y coordinates."""
        if "x" not in v or "y" not in v:
            raise ValueError("Position must contain x and y coordinates")
        if v["x"] < 0 or v["y"] < 0:
            raise ValueError("Position coordinates must be non-negative")
        return v

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "widget_id": "widget_patients_total",
                "widget_type": "metric_card",
                "title": "Total Patients",
                "size": "small",
                "position": {"x": 0, "y": 0},
                "config": {"metric_key": "total_patients"},
                "refresh_interval": 120
            }
        }
    )


# ============================================================================
# Widget Data Schemas
# ============================================================================

class MetricWidgetData(BaseModel):
    """Data for metric card widgets (KPIs)."""

    value: confloat() = Field(description="Current metric value")
    label: str = Field(description="Metric label")
    unit: Optional[str] = Field(None, description="Unit of measurement (%, count, etc.)")
    change: Optional[confloat()] = Field(None, description="Change from previous period")
    change_percentage: Optional[confloat()] = Field(None, description="Percentage change")
    trend: Optional[str] = Field(None, description="Trend direction (up, down, stable)")
    color: Optional[str] = Field(None, description="Display color (success, warning, danger)")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "value": 245,
                "label": "Total Patients",
                "unit": "count",
                "change": 12,
                "change_percentage": 5.2,
                "trend": "up",
                "color": "success"
            }
        }
    )


class ChartDataPoint(BaseModel):
    """Single data point for chart widgets."""

    label: str = Field(description="Data point label (date, category, etc.)")
    value: confloat() = Field(description="Data point value")
    category: Optional[str] = Field(None, description="Data category for grouped charts")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ChartWidgetData(BaseModel):
    """Data for chart widgets (line, bar, pie, etc.)."""

    chart_type: str = Field(description="Chart type (line, bar, pie, donut)")
    data_points: List[ChartDataPoint] = Field(description="Chart data points")
    x_axis_label: Optional[str] = Field(None, description="X-axis label")
    y_axis_label: Optional[str] = Field(None, description="Y-axis label")
    legend: Optional[List[str]] = Field(None, description="Legend labels")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "chart_type": "line",
                "data_points": [
                    {"label": "2025-01-10", "value": 45},
                    {"label": "2025-01-11", "value": 52},
                    {"label": "2025-01-12", "value": 48}
                ],
                "x_axis_label": "Date",
                "y_axis_label": "Messages Sent"
            }
        }
    )


class TableRow(BaseModel):
    """Single row for table widgets."""

    id: str = Field(description="Row identifier")
    cells: Dict[str, Any] = Field(description="Cell values by column key")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Row metadata")


class TableWidgetData(BaseModel):
    """Data for table widgets."""

    columns: List[Dict[str, str]] = Field(description="Column definitions (key, label, type)")
    rows: List[TableRow] = Field(description="Table rows")
    sortable: bool = Field(default=True, description="Whether table is sortable")
    total_count: Optional[int] = Field(None, description="Total row count (for pagination)")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "columns": [
                    {"key": "name", "label": "Patient Name", "type": "string"},
                    {"key": "alerts", "label": "Alerts", "type": "number"},
                    {"key": "status", "label": "Status", "type": "badge"}
                ],
                "rows": [
                    {
                        "id": "patient_1",
                        "cells": {
                            "name": "Jane Doe",
                            "alerts": 3,
                            "status": "High Risk"
                        }
                    }
                ],
                "sortable": True,
                "total_count": 25
            }
        }
    )


class ActivityItem(BaseModel):
    """Single activity item for activity feed widgets."""

    id: str = Field(description="Activity identifier")
    type: str = Field(description="Activity type (message_sent, alert_created, etc.)")
    description: str = Field(description="Activity description")
    entity_name: Optional[str] = Field(None, description="Related entity name (patient, user)")
    timestamp: str = Field(description="Activity timestamp (ISO format)")
    icon: Optional[str] = Field(None, description="Icon identifier")
    link: Optional[str] = Field(None, description="Link to related resource")


class ActivityFeedData(BaseModel):
    """Data for activity feed widgets."""

    activities: List[ActivityItem] = Field(description="List of activities")
    total_count: conint(ge=0) = Field(description="Total activity count")
    last_updated: str = Field(description="Last update timestamp")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "activities": [
                    {
                        "id": "act_1",
                        "type": "message_sent",
                        "description": "Mensagem enviada para Jane Doe",
                        "entity_name": "Jane Doe",
                        "timestamp": "2025-01-17T15:30:00Z",
                        "icon": "mail"
                    }
                ],
                "total_count": 45,
                "last_updated": "2025-01-17T15:35:00Z"
            }
        }
    )


class AlertsSummaryData(BaseModel):
    """Data for alerts summary widget."""

    total_alerts: conint(ge=0) = Field(description="Total alerts")
    pending_alerts: conint(ge=0) = Field(description="Pending alerts")
    critical_alerts: conint(ge=0) = Field(description="Critical severity alerts")
    high_alerts: conint(ge=0) = Field(description="High severity alerts")
    medium_alerts: conint(ge=0) = Field(description="Medium severity alerts")
    low_alerts: conint(ge=0) = Field(description="Low severity alerts")
    alerts_by_type: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Alert breakdown by type"
    )


# ============================================================================
# Metric Group Schemas
# ============================================================================

class PatientMetrics(BaseModel):
    """Patient metrics for dashboards."""

    total_patients: conint(ge=0) = Field(description="Total patient count")
    active_patients: conint(ge=0) = Field(description="Active patient count")
    inactive_patients: conint(ge=0) = Field(description="Inactive patient count")
    new_patients: conint(ge=0) = Field(description="New patients in time range")
    high_risk_patients: conint(ge=0) = Field(description="High-risk patient count")


class MessageMetrics(BaseModel):
    """Message metrics for dashboards."""

    total_messages: conint(ge=0) = Field(description="Total messages sent")
    sent_count: conint(ge=0) = Field(description="Successfully sent messages")
    delivered_count: conint(ge=0) = Field(description="Delivered messages")
    failed_count: conint(ge=0) = Field(description="Failed messages")
    response_count: conint(ge=0) = Field(description="Messages with patient responses")
    response_rate: confloat(ge=0, le=100) = Field(description="Response rate percentage")


class AlertMetrics(BaseModel):
    """Alert metrics for dashboards."""

    total_alerts: conint(ge=0) = Field(description="Total alerts")
    pending_alerts: conint(ge=0) = Field(description="Pending alerts")
    acknowledged_alerts: conint(ge=0) = Field(description="Acknowledged alerts")
    critical_alerts: conint(ge=0) = Field(description="Critical severity count")
    high_alerts: conint(ge=0) = Field(description="High severity count")
    medium_alerts: conint(ge=0) = Field(description="Medium severity count")
    low_alerts: conint(ge=0) = Field(description="Low severity count")


class FlowMetrics(BaseModel):
    """Flow metrics for dashboards."""

    total_flows: conint(ge=0) = Field(description="Total flows")
    active_flows: conint(ge=0) = Field(description="Active flows")
    completed_flows: conint(ge=0) = Field(description="Completed flows")
    paused_flows: conint(ge=0) = Field(description="Paused flows")
    completion_rate: confloat(ge=0, le=100) = Field(description="Flow completion rate")
    avg_completion_days: confloat(ge=0) = Field(description="Average completion time in days")


class UserMetrics(BaseModel):
    """User metrics for admin dashboard."""

    total_users: conint(ge=0) = Field(description="Total user count")
    active_users: conint(ge=0) = Field(description="Active users")
    inactive_users: conint(ge=0) = Field(description="Inactive users")
    doctors_count: conint(ge=0) = Field(description="Physician count")
    patients_count: conint(ge=0) = Field(description="Patient count")
    admins_count: conint(ge=0) = Field(description="Admin count")


# ============================================================================
# Dashboard Response Schemas
# ============================================================================

class DashboardMainResponse(BaseModel):
    """Main dashboard overview response."""

    user_role: str = Field(description="Current user role")
    time_range: str = Field(description="Time range for metrics")
    start_date: str = Field(description="Start date (ISO format)")
    end_date: str = Field(description="End date (ISO format)")
    patient_metrics: PatientMetrics = Field(description="Patient statistics")
    message_metrics: MessageMetrics = Field(description="Message statistics")
    alert_metrics: AlertMetrics = Field(description="Alert statistics")
    flow_metrics: FlowMetrics = Field(description="Flow statistics")
    recent_activity: List[ActivityItem] = Field(description="Recent activity feed")
    generated_at: str = Field(description="Response generation timestamp")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "user_role": "doctor",
                "time_range": "week",
                "start_date": "2025-01-10T00:00:00Z",
                "end_date": "2025-01-17T15:00:00Z",
                "patient_metrics": {
                    "total_patients": 150,
                    "active_patients": 142,
                    "inactive_patients": 8,
                    "new_patients": 5,
                    "high_risk_patients": 12
                },
                "message_metrics": {
                    "total_messages": 1250,
                    "sent_count": 1200,
                    "delivered_count": 1180,
                    "failed_count": 50,
                    "response_count": 890,
                    "response_rate": 71.2
                },
                "alert_metrics": {
                    "total_alerts": 45,
                    "pending_alerts": 8,
                    "acknowledged_alerts": 37,
                    "critical_alerts": 2,
                    "high_alerts": 12,
                    "medium_alerts": 23,
                    "low_alerts": 8
                },
                "flow_metrics": {
                    "total_flows": 85,
                    "active_flows": 42,
                    "completed_flows": 38,
                    "paused_flows": 5,
                    "completion_rate": 44.7,
                    "avg_completion_days": 12.5
                },
                "recent_activity": [],
                "generated_at": "2025-01-17T15:00:00Z"
            }
        }
    )


class PatientInfo(BaseModel):
    """Brief patient information for patient dashboard."""

    id: str = Field(description="Patient UUID")
    full_name: str = Field(description="Patient full name")
    email: Optional[str] = Field(None, description="Patient email")
    is_active: bool = Field(description="Active status")
    created_at: Optional[str] = Field(None, description="Registration date")


class DashboardPatientResponse(BaseModel):
    """Patient-specific dashboard response."""

    patient: PatientInfo = Field(description="Patient information")
    time_range: str = Field(description="Time range for metrics")
    start_date: str = Field(description="Start date (ISO format)")
    end_date: str = Field(description="End date (ISO format)")
    message_metrics: MessageMetrics = Field(description="Message statistics")
    alert_metrics: AlertMetrics = Field(description="Alert statistics")
    flow_metrics: FlowMetrics = Field(description="Flow statistics")
    recent_activity: List[ActivityItem] = Field(description="Recent activity feed")
    engagement_chart: List[Dict[str, Any]] = Field(description="Engagement chart data")
    generated_at: str = Field(description="Response generation timestamp")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "patient": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "full_name": "Jane Doe",
                    "email": "jane@example.com",
                    "is_active": True,
                    "created_at": "2024-01-15T10:00:00Z"
                },
                "time_range": "month",
                "start_date": "2024-12-17T00:00:00Z",
                "end_date": "2025-01-17T15:00:00Z",
                "message_metrics": {
                    "total_messages": 45,
                    "sent_count": 43,
                    "delivered_count": 42,
                    "failed_count": 2,
                    "response_count": 32,
                    "response_rate": 71.1
                },
                "alert_metrics": {
                    "total_alerts": 8,
                    "pending_alerts": 1,
                    "acknowledged_alerts": 7,
                    "critical_alerts": 0,
                    "high_alerts": 2,
                    "medium_alerts": 4,
                    "low_alerts": 2
                },
                "flow_metrics": {
                    "total_flows": 3,
                    "active_flows": 2,
                    "completed_flows": 1,
                    "paused_flows": 0,
                    "completion_rate": 33.3,
                    "avg_completion_days": 15.0
                },
                "recent_activity": [],
                "engagement_chart": [],
                "generated_at": "2025-01-17T15:00:00Z"
            }
        }
    )


class AlertSummary(BaseModel):
    """Alert summary for physician dashboard."""

    id: str = Field(description="Alert UUID")
    patient_id: str = Field(description="Patient UUID")
    severity: str = Field(description="Alert severity")
    alert_type: str = Field(description="Alert type")
    description: str = Field(description="Alert description")
    created_at: str = Field(description="Alert creation time")


class RiskPatient(BaseModel):
    """High-risk patient summary."""

    patient_id: str = Field(description="Patient UUID")
    patient_name: str = Field(description="Patient name")
    alert_count: conint(ge=0) = Field(description="Number of high-priority alerts")


class DashboardPhysicianResponse(BaseModel):
    """Physician-specific dashboard response."""

    user_id: str = Field(description="Physician UUID")
    time_range: str = Field(description="Time range for metrics")
    start_date: str = Field(description="Start date (ISO format)")
    end_date: str = Field(description="End date (ISO format)")
    patient_metrics: PatientMetrics = Field(description="Patient statistics")
    message_metrics: MessageMetrics = Field(description="Message statistics")
    alert_metrics: AlertMetrics = Field(description="Alert statistics")
    flow_metrics: FlowMetrics = Field(description="Flow statistics")
    high_priority_alerts: List[AlertSummary] = Field(description="High-priority alerts")
    top_risk_patients: List[RiskPatient] = Field(description="Top risk patients")
    generated_at: str = Field(description="Response generation timestamp")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "user_id": "223e4567-e89b-12d3-a456-426614174001",
                "time_range": "week",
                "start_date": "2025-01-10T00:00:00Z",
                "end_date": "2025-01-17T15:00:00Z",
                "patient_metrics": {
                    "total_patients": 35,
                    "active_patients": 33,
                    "inactive_patients": 2,
                    "new_patients": 2,
                    "high_risk_patients": 4
                },
                "message_metrics": {
                    "total_messages": 250,
                    "sent_count": 245,
                    "delivered_count": 240,
                    "failed_count": 5,
                    "response_count": 180,
                    "response_rate": 72.0
                },
                "alert_metrics": {
                    "total_alerts": 18,
                    "pending_alerts": 4,
                    "acknowledged_alerts": 14,
                    "critical_alerts": 1,
                    "high_alerts": 5,
                    "medium_alerts": 9,
                    "low_alerts": 3
                },
                "flow_metrics": {
                    "total_flows": 28,
                    "active_flows": 15,
                    "completed_flows": 12,
                    "paused_flows": 1,
                    "completion_rate": 42.9,
                    "avg_completion_days": 11.5
                },
                "high_priority_alerts": [],
                "top_risk_patients": [],
                "generated_at": "2025-01-17T15:00:00Z"
            }
        }
    )


class PhysicianPerformance(BaseModel):
    """Physician performance metrics."""

    physician_id: str = Field(description="Physician UUID")
    physician_name: str = Field(description="Physician name")
    patient_count: conint(ge=0) = Field(description="Number of patients")
    message_count: conint(ge=0) = Field(description="Messages sent")
    engagement_rate: confloat(ge=0, le=100) = Field(description="Patient engagement rate")


class SystemHealth(BaseModel):
    """System health indicators for admin dashboard."""

    message_success_rate: confloat(ge=0, le=100) = Field(description="Message success rate")
    alert_response_rate: confloat(ge=0, le=100) = Field(description="Alert response rate")
    flow_completion_rate: confloat(ge=0, le=100) = Field(description="Flow completion rate")
    patient_active_rate: confloat(ge=0, le=100) = Field(description="Patient active rate")


class DashboardAdminResponse(BaseModel):
    """Admin dashboard response with system-wide metrics."""

    time_range: str = Field(description="Time range for metrics")
    start_date: str = Field(description="Start date (ISO format)")
    end_date: str = Field(description="End date (ISO format)")
    patient_metrics: PatientMetrics = Field(description="Patient statistics")
    message_metrics: MessageMetrics = Field(description="Message statistics")
    alert_metrics: AlertMetrics = Field(description="Alert statistics")
    flow_metrics: FlowMetrics = Field(description="Flow statistics")
    user_metrics: UserMetrics = Field(description="User statistics")
    top_physicians: List[PhysicianPerformance] = Field(description="Top performing physicians")
    system_health: SystemHealth = Field(description="System health indicators")
    generated_at: str = Field(description="Response generation timestamp")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "time_range": "month",
                "start_date": "2024-12-17T00:00:00Z",
                "end_date": "2025-01-17T15:00:00Z",
                "patient_metrics": {
                    "total_patients": 450,
                    "active_patients": 420,
                    "inactive_patients": 30,
                    "new_patients": 25,
                    "high_risk_patients": 35
                },
                "message_metrics": {
                    "total_messages": 5500,
                    "sent_count": 5400,
                    "delivered_count": 5300,
                    "failed_count": 100,
                    "response_count": 3900,
                    "response_rate": 70.9
                },
                "alert_metrics": {
                    "total_alerts": 180,
                    "pending_alerts": 25,
                    "acknowledged_alerts": 155,
                    "critical_alerts": 8,
                    "high_alerts": 45,
                    "medium_alerts": 90,
                    "low_alerts": 37
                },
                "flow_metrics": {
                    "total_flows": 320,
                    "active_flows": 145,
                    "completed_flows": 160,
                    "paused_flows": 15,
                    "completion_rate": 50.0,
                    "avg_completion_days": 13.2
                },
                "user_metrics": {
                    "total_users": 485,
                    "active_users": 470,
                    "inactive_users": 15,
                    "doctors_count": 25,
                    "patients_count": 450,
                    "admins_count": 10
                },
                "top_physicians": [],
                "system_health": {
                    "message_success_rate": 98.2,
                    "alert_response_rate": 86.1,
                    "flow_completion_rate": 50.0,
                    "patient_active_rate": 93.3
                },
                "generated_at": "2025-01-17T15:00:00Z"
            }
        }
    )


# ============================================================================
# Custom Dashboard Schemas
# ============================================================================

class CustomDashboardResponse(BaseModel):
    """Custom dashboard configuration response."""

    dashboard_id: str = Field(description="Dashboard UUID")
    user_id: str = Field(description="Owner user UUID")
    name: constr(min_length=1, max_length=200) = Field(description="Dashboard name")
    description: Optional[str] = Field(None, description="Dashboard description")
    widgets: List[WidgetConfig] = Field(description="Dashboard widgets")
    layout: Dict[str, Any] = Field(description="Dashboard layout configuration")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "dashboard_id": "323e4567-e89b-12d3-a456-426614174002",
                "user_id": "223e4567-e89b-12d3-a456-426614174001",
                "name": "My Custom Dashboard",
                "description": "Personalized view of key metrics",
                "widgets": [
                    {
                        "widget_id": "widget_1",
                        "widget_type": "metric_card",
                        "title": "Total Patients",
                        "size": "small",
                        "position": {"x": 0, "y": 0},
                        "config": {},
                        "refresh_interval": 120
                    }
                ],
                "layout": {"columns": 4, "row_height": 100},
                "created_at": "2025-01-10T10:00:00Z",
                "updated_at": "2025-01-17T15:00:00Z"
            }
        }
    )


class DashboardLayoutUpdate(BaseModel):
    """Request schema for updating dashboard layout."""

    name: Optional[constr(max_length=200)] = Field(None, description="Dashboard name")
    description: Optional[str] = Field(None, description="Dashboard description")
    widgets: Optional[List[WidgetConfig]] = Field(None, description="Updated widgets")
    layout: Optional[Dict[str, Any]] = Field(None, description="Updated layout config")

    @field_validator("widgets")
    @classmethod
    def validate_widgets(cls, v):
        """Ensure widget IDs are unique."""
        if v:
            widget_ids = [w.widget_id for w in v]
            if len(widget_ids) != len(set(widget_ids)):
                raise ValueError("Widget IDs must be unique")
        return v

    model_config = ConfigDict(


        json_schema_extra = {
            "example": {
                "name": "Updated Dashboard",
                "description": "Modified layout",
                "widgets": [
                    {
                        "widget_id": "widget_1",
                        "widget_type": "metric_card",
                        "title": "Active Patients",
                        "size": "medium",
                        "position": {"x": 0, "y": 0},
                        "config": {"metric_key": "active_patients"}
                    }
                ],
                "layout": {"columns": 4, "row_height": 120}
            }
        }
    )
