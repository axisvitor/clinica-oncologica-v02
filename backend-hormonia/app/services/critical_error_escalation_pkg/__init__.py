"""
Critical error escalation package.

Provides escalation logic for critical system errors and automated notifications
with multi-level escalation, auto-resolution, and WebSocket-based alerts.
"""

from app.services.critical_error_escalation_pkg.models import (
    EscalationLevel,
    EscalationRule,
    ActiveEscalation,
)
from app.services.critical_error_escalation_pkg.serialization import (
    serialize_escalation,
    deserialize_escalation,
)
from app.services.critical_error_escalation_pkg.service import (
    CriticalErrorEscalationService,
)

__all__ = [
    "EscalationLevel",
    "EscalationRule",
    "ActiveEscalation",
    "serialize_escalation",
    "deserialize_escalation",
    "CriticalErrorEscalationService",
]
