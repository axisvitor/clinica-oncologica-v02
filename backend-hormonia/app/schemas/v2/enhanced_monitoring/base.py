"""
Base schemas and enums for enhanced monitoring.
Common fields, enums, and base classes.
"""

from enum import Enum

from app.models.alert import AlertSeverity  # noqa: F401 - canonical definition


# ============================================================================
# ENUMS
# ============================================================================


class MetricType(str, Enum):
    """Business metric types."""

    QUIZ_COMPLETION = "quiz_completion"
    MESSAGE_SENT = "message_sent"
    PATIENT_INTERACTION = "patient_interaction"
    FLOW_EXECUTION = "flow_execution"
    AI_REQUEST = "ai_request"


class TimeRange(str, Enum):
    """Predefined time ranges."""

    HOUR_1 = "1h"
    HOURS_6 = "6h"
    HOURS_24 = "24h"
    DAYS_7 = "7d"
    DAYS_30 = "30d"
