"""
Escalation cycle operations: auto-resolution, level progression, notifications.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from redis import Redis

from app.services.websocket_events import WebSocketEventService
from app.schemas.websocket import WebSocketEventType, create_websocket_message
from app.utils.timezone import now_sao_paulo

from app.services.critical_error_escalation_pkg.models import (
    EscalationLevel,
    ActiveEscalation,
)
from app.services.critical_error_escalation_pkg.serialization import (
    serialize_escalation,
)

logger = logging.getLogger(__name__)


class EscalationCycleOps:
    """Handles escalation cycle operations: level progression and auto-resolution."""

    def __init__(self, redis: Redis, websocket_service: WebSocketEventService):
        self.redis = redis
        self.websocket_service = websocket_service

    async def check_level_progression(
        self, escalation: ActiveEscalation
    ) -> Optional[Dict[str, Any]]:
        """Check if escalation should progress to next level."""
        if escalation.acknowledged or escalation.resolved:
            return None

        time_since_last_escalation = (
            now_sao_paulo() - escalation.last_escalated_at
        ).total_seconds()
        current_level_index = list(EscalationLevel).index(escalation.current_level)

        if current_level_index < len(escalation.rule.escalation_intervals):
            required_interval = escalation.rule.escalation_intervals[
                current_level_index
            ]

            if time_since_last_escalation >= required_interval:
                next_level = list(EscalationLevel)[current_level_index + 1]

                if next_level.value <= escalation.rule.max_level.value:
                    escalation.current_level = next_level
                    escalation.last_escalated_at = now_sao_paulo()

                    escalation_key = f"escalation:{escalation.id}"
                    escalation_data = serialize_escalation(escalation)
                    await self.redis.setex(
                        escalation_key, 86400 * 7, json.dumps(escalation_data)
                    )

                    await self.send_escalation_notification(
                        escalation_data,
                        f"Escalation progressed to {next_level.value}",
                    )

                    return {
                        "alert_id": escalation.alert_id,
                        "escalation_id": escalation.id,
                        "action": "level_progression",
                        "previous_level": list(EscalationLevel)[
                            current_level_index
                        ].value,
                        "new_level": next_level.value,
                    }

        return None

    async def check_auto_resolutions(self) -> List[str]:
        """Check for escalations that should be auto-resolved."""
        auto_resolved = []

        try:
            escalation_keys = []
            async for key in self.redis.scan_iter(match="escalation:*", count=100):
                escalation_keys.append(key)

            for key in escalation_keys:
                escalation_data = await self.redis.get(key)
                if not escalation_data:
                    continue

                escalation_dict = json.loads(escalation_data)
                if escalation_dict.get("resolved", False):
                    continue

                created_at = datetime.fromisoformat(escalation_dict["created_at"])
                time_since_creation = (
                    now_sao_paulo() - created_at
                ).total_seconds()

                rule_data = escalation_dict["rule"]
                auto_resolve_threshold = rule_data.get(
                    "auto_resolve_threshold", 7200
                )

                if time_since_creation >= auto_resolve_threshold:
                    escalation_dict["resolved"] = True
                    escalation_dict["resolved_by"] = "system"
                    escalation_dict["resolved_at"] = now_sao_paulo().isoformat()
                    escalation_dict["resolution_note"] = (
                        "Auto-resolved due to timeout"
                    )

                    escalation_dict["notification_history"].append(
                        {
                            "action": "auto_resolved",
                            "by": "system",
                            "at": now_sao_paulo().isoformat(),
                            "reason": "timeout",
                        }
                    )

                    await self.redis.setex(
                        key, 86400 * 7, json.dumps(escalation_dict)
                    )

                    await self.send_escalation_notification(
                        escalation_dict,
                        "Escalation auto-resolved due to timeout",
                    )

                    auto_resolved.append(escalation_dict["id"])
                    logger.info(
                        f"Auto-resolved escalation {escalation_dict['id']}"
                    )

            return auto_resolved

        except Exception as e:
            logger.error(f"Error checking auto-resolutions: {e}")
            return []

    async def send_escalation_notification(
        self, escalation_data: Dict[str, Any], message: str
    ) -> None:
        """Send escalation notification via WebSocket."""
        try:
            event_data = {
                "escalation_id": escalation_data["id"],
                "alert_id": escalation_data["alert_id"],
                "level": escalation_data["current_level"],
                "message": message,
                "acknowledged": escalation_data.get("acknowledged", False),
                "resolved": escalation_data.get("resolved", False),
                "created_at": escalation_data["created_at"],
            }

            websocket_message = create_websocket_message(
                WebSocketEventType.ALERT_CREATED, event_data
            )

            await self.websocket_service.broadcast_to_all_authenticated(
                websocket_message.dict()
            )

        except Exception as e:
            logger.error(f"Error sending escalation notification: {e}")

    async def send_pending_notifications(self) -> int:
        """Send any pending notifications."""
        return 0
