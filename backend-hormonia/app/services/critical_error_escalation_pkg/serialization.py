"""
Serialization and deserialization for escalation data.
"""

from typing import Dict, Any
from datetime import datetime

from app.services.flow_monitoring import AlertSeverity

from app.services.critical_error_escalation_pkg.models import (
    EscalationLevel,
    EscalationRule,
    ActiveEscalation,
)


def serialize_escalation(escalation: ActiveEscalation) -> Dict[str, Any]:
    """Serialize escalation to dictionary."""
    return {
        "id": escalation.id,
        "alert_id": escalation.alert_id,
        "rule": {
            "alert_severity": escalation.rule.alert_severity.value,
            "component": escalation.rule.component,
            "initial_delay": escalation.rule.initial_delay,
            "escalation_intervals": escalation.rule.escalation_intervals,
            "max_level": escalation.rule.max_level.value,
            "auto_resolve_threshold": escalation.rule.auto_resolve_threshold,
        },
        "current_level": escalation.current_level.value,
        "created_at": escalation.created_at.isoformat(),
        "last_escalated_at": escalation.last_escalated_at.isoformat(),
        "acknowledged": escalation.acknowledged,
        "acknowledged_by": escalation.acknowledged_by,
        "acknowledged_at": escalation.acknowledged_at.isoformat()
        if escalation.acknowledged_at
        else None,
        "resolved": escalation.resolved,
        "resolved_by": escalation.resolved_by,
        "resolved_at": escalation.resolved_at.isoformat()
        if escalation.resolved_at
        else None,
        "resolution_note": escalation.resolution_note,
        "notification_history": escalation.notification_history,
    }


def deserialize_escalation(data: Dict[str, Any]) -> ActiveEscalation:
    """Deserialize escalation from dictionary."""
    rule = EscalationRule(
        alert_severity=AlertSeverity(data["rule"]["alert_severity"]),
        component=data["rule"]["component"],
        initial_delay=data["rule"]["initial_delay"],
        escalation_intervals=data["rule"]["escalation_intervals"],
        max_level=EscalationLevel(data["rule"]["max_level"]),
        auto_resolve_threshold=data["rule"]["auto_resolve_threshold"],
    )

    return ActiveEscalation(
        id=data["id"],
        alert_id=data["alert_id"],
        rule=rule,
        current_level=EscalationLevel(data["current_level"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        last_escalated_at=datetime.fromisoformat(data["last_escalated_at"]),
        acknowledged=data["acknowledged"],
        acknowledged_by=data["acknowledged_by"],
        acknowledged_at=datetime.fromisoformat(data["acknowledged_at"])
        if data["acknowledged_at"]
        else None,
        resolved=data["resolved"],
        resolved_by=data["resolved_by"],
        resolved_at=datetime.fromisoformat(data["resolved_at"])
        if data["resolved_at"]
        else None,
        resolution_note=data["resolution_note"],
        notification_history=data["notification_history"],
    )
