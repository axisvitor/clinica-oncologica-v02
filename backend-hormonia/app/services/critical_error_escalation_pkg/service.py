"""
Critical error escalation and notification system.
Implements escalation logic for critical system errors and automated notifications.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import uuid4
import json

from redis import Redis

from app.services.flow_monitoring import FlowMonitoringService, AlertSeverity
from app.services.websocket_events import WebSocketEventService
from app.utils.timezone import now_sao_paulo

from app.services.critical_error_escalation_pkg.models import (
    EscalationLevel,
    EscalationRule,
    ActiveEscalation,
)
from app.services.critical_error_escalation_pkg.serialization import (
    serialize_escalation,
    deserialize_escalation,
)
from app.services.critical_error_escalation_pkg.cycle import EscalationCycleOps
from app.services.critical_error_escalation_pkg.operations import EscalationOperations

logger = logging.getLogger(__name__)


class CriticalErrorEscalationService:
    """Service for escalating critical errors and managing notifications."""

    def __init__(
        self,
        db: Any,
        redis: Redis,
        monitoring_service: FlowMonitoringService,
        websocket_service: WebSocketEventService,
    ):
        self.db = db
        self.redis = redis
        self.monitoring_service = monitoring_service
        self.websocket_service = websocket_service

        self._cycle_ops = EscalationCycleOps(redis, websocket_service)
        self._ops = EscalationOperations(redis, self._cycle_ops)

        self.escalation_rules = [
            EscalationRule(
                alert_severity=AlertSeverity.CRITICAL,
                component="flow_processing", initial_delay=300,
                escalation_intervals=[900, 1800, 3600],
                max_level=EscalationLevel.LEVEL_4, auto_resolve_threshold=7200,
            ),
            EscalationRule(
                alert_severity=AlertSeverity.CRITICAL,
                component="database", initial_delay=60,
                escalation_intervals=[300, 900, 1800],
                max_level=EscalationLevel.LEVEL_4, auto_resolve_threshold=3600,
            ),
            EscalationRule(
                alert_severity=AlertSeverity.CRITICAL,
                component="redis", initial_delay=120,
                escalation_intervals=[600, 1200, 2400],
                max_level=EscalationLevel.LEVEL_3, auto_resolve_threshold=3600,
            ),
            EscalationRule(
                alert_severity=AlertSeverity.HIGH,
                component="message_queue", initial_delay=600,
                escalation_intervals=[1800, 3600],
                max_level=EscalationLevel.LEVEL_2, auto_resolve_threshold=10800,
            ),
            EscalationRule(
                alert_severity=AlertSeverity.CRITICAL,
                component="data_integrity", initial_delay=180,
                escalation_intervals=[600, 1800, 3600],
                max_level=EscalationLevel.LEVEL_4, auto_resolve_threshold=7200,
            ),
        ]

        self.notification_channels = {
            EscalationLevel.LEVEL_1: ["team_leads", "websocket"],
            EscalationLevel.LEVEL_2: ["team_leads", "managers", "websocket", "email"],
            EscalationLevel.LEVEL_3: [
                "team_leads", "managers", "directors",
                "websocket", "email", "sms",
            ],
            EscalationLevel.LEVEL_4: [
                "team_leads", "managers", "directors", "executives",
                "websocket", "email", "sms", "phone",
            ],
        }

    async def check_escalation_triggers(self) -> List[Dict[str, Any]]:
        """Check for alerts that should trigger escalations."""
        try:
            active_alerts = await self.monitoring_service.get_active_alerts()
            triggers = []

            for alert in active_alerts:
                matching_rule = self._find_matching_rule(alert)
                if not matching_rule:
                    continue

                escalation_key = f"escalation:{alert.id}"
                existing = await self.redis.get(escalation_key)

                if not existing:
                    elapsed = (now_sao_paulo() - alert.created_at).total_seconds()
                    if elapsed >= matching_rule.initial_delay:
                        esc = await self._create_escalation(alert, matching_rule)
                        triggers.append({
                            "alert_id": alert.id,
                            "escalation_id": esc.id,
                            "rule": {
                                "severity": matching_rule.alert_severity.value,
                                "component": matching_rule.component,
                                "initial_delay": matching_rule.initial_delay,
                            },
                            "action": "escalation_created",
                        })
                else:
                    data = json.loads(existing)
                    esc = deserialize_escalation(data)
                    if not esc.acknowledged and not esc.resolved:
                        prog = await self._cycle_ops.check_level_progression(esc)
                        if prog:
                            triggers.append(prog)

            return triggers

        except Exception as e:
            logger.error(f"Error checking escalation triggers: {e}")
            return []

    async def get_active_escalations(self) -> List[Dict[str, Any]]:
        """Get all active escalations."""
        try:
            keys = []
            async for key in self.redis.scan_iter(match="escalation:*", count=100):
                keys.append(key)
            escalations = []
            for key in keys:
                raw = await self.redis.get(key)
                if raw:
                    d = json.loads(raw)
                    if not d.get("resolved", False):
                        escalations.append(d)
            return sorted(escalations, key=lambda x: x["created_at"], reverse=True)
        except Exception as e:
            logger.error(f"Error getting active escalations: {e}")
            return []

    async def acknowledge_escalation(
        self, escalation_id: str, acknowledged_by: str
    ) -> bool:
        """Acknowledge an escalation."""
        return await self._ops.acknowledge(escalation_id, acknowledged_by)

    async def resolve_escalation(
        self, escalation_id: str, resolved_by: str, resolution_note: str
    ) -> bool:
        """Resolve an escalation."""
        return await self._ops.resolve(escalation_id, resolved_by, resolution_note)

    async def run_escalation_cycle(self) -> Dict[str, Any]:
        """Run escalation cycle."""
        try:
            results = {
                "triggers_checked": 0, "escalations_created": 0,
                "level_progressions": 0, "auto_resolutions": 0,
                "notifications_sent": 0, "errors": [],
            }
            triggers = await self.check_escalation_triggers()
            results["triggers_checked"] = len(triggers)
            for t in triggers:
                if t["action"] == "escalation_created":
                    results["escalations_created"] += 1
                elif t["action"] == "level_progression":
                    results["level_progressions"] += 1
            results["auto_resolutions"] = len(
                await self._cycle_ops.check_auto_resolutions()
            )
            results["notifications_sent"] = (
                await self._cycle_ops.send_pending_notifications()
            )
            return results
        except Exception as e:
            logger.error(f"Error running escalation cycle: {e}")
            return {"error": str(e)}

    def _find_matching_rule(self, alert) -> Optional[EscalationRule]:
        """Find escalation rule that matches the alert."""
        for rule in self.escalation_rules:
            if (
                rule.alert_severity == alert.severity
                and rule.component == alert.component
            ):
                return rule
        return None

    async def _create_escalation(
        self, alert, rule: EscalationRule
    ) -> ActiveEscalation:
        """Create a new escalation."""
        eid = str(uuid4())
        escalation = ActiveEscalation(
            id=eid, alert_id=alert.id, rule=rule,
            current_level=EscalationLevel.LEVEL_1,
            created_at=now_sao_paulo(), last_escalated_at=now_sao_paulo(),
            acknowledged=False, acknowledged_by=None, acknowledged_at=None,
            resolved=False, resolved_by=None, resolved_at=None,
            resolution_note=None, notification_history=[],
        )
        key = f"escalation:{eid}"
        data = serialize_escalation(escalation)
        await self.redis.setex(key, 86400 * 7, json.dumps(data))
        await self._cycle_ops.send_escalation_notification(
            data, f"Critical alert escalated: {alert.title}"
        )
        logger.warning(f"Created escalation {eid} for alert {alert.id}")
        return escalation
