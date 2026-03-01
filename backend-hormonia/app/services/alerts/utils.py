"""
Shared utility functions for the alert system.
"""
from typing import Any, Dict, List

from .types import Alert


def apply_alert_filters(
    alerts: List[Alert], filters: Dict[str, Any]
) -> List[Alert]:
    """Apply filters to an alert list."""
    filtered = alerts
    if "severity" in filters:
        filtered = [a for a in filtered if a.severity == filters["severity"]]
    if "rule_type" in filters:
        filtered = [a for a in filtered if a.rule_type == filters["rule_type"]]
    if "status" in filters:
        filtered = [a for a in filtered if a.status == filters["status"]]
    if "patient_id" in filters:
        filtered = [a for a in filtered if a.patient_id == filters["patient_id"]]
    start_date = filters.get("start_date") or filters.get("date_from")
    if start_date:
        filtered = [a for a in filtered if a.created_at >= start_date]
    end_date = filters.get("end_date") or filters.get("date_to")
    if end_date:
        filtered = [a for a in filtered if a.created_at <= end_date]
    if "escalated" in filters:
        filtered = [a for a in filtered if a.escalated == filters["escalated"]]
    return filtered
