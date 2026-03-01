"""
Data models for critical error escalation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from app.services.flow_monitoring import AlertSeverity


class EscalationLevel(Enum):
    LEVEL_1 = "level_1"  # Team lead notification
    LEVEL_2 = "level_2"  # Manager notification
    LEVEL_3 = "level_3"  # Director notification
    LEVEL_4 = "level_4"  # Executive notification


@dataclass
class EscalationRule:
    """Escalation rule configuration."""

    alert_severity: AlertSeverity
    component: str
    initial_delay: int  # seconds
    escalation_intervals: List[int]  # seconds between escalation levels
    max_level: EscalationLevel
    auto_resolve_threshold: int  # seconds after which to auto-resolve if no activity


@dataclass
class ActiveEscalation:
    """Active escalation tracking."""

    id: str
    alert_id: str
    rule: EscalationRule
    current_level: EscalationLevel
    created_at: datetime
    last_escalated_at: datetime
    acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    resolved: bool
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    resolution_note: Optional[str]
    notification_history: List[Dict[str, Any]]
