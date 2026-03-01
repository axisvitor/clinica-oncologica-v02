"""
Escalation acknowledgement and resolution operations.
"""

import logging
import json
from typing import Dict, Any

from redis import Redis

from app.utils.timezone import now_sao_paulo
from app.services.critical_error_escalation_pkg.cycle import EscalationCycleOps

logger = logging.getLogger(__name__)


class EscalationOperations:
    """Handles acknowledgement and resolution of escalations."""

    def __init__(self, redis: Redis, cycle_ops: EscalationCycleOps):
        self.redis = redis
        self._cycle_ops = cycle_ops

    async def acknowledge(
        self, escalation_id: str, acknowledged_by: str
    ) -> bool:
        """Acknowledge an escalation."""
        try:
            escalation_key = f"escalation:{escalation_id}"
            escalation_data = await self.redis.get(escalation_key)

            if not escalation_data:
                return False

            escalation_dict = json.loads(escalation_data)
            escalation_dict["acknowledged"] = True
            escalation_dict["acknowledged_by"] = acknowledged_by
            escalation_dict["acknowledged_at"] = now_sao_paulo().isoformat()

            escalation_dict["notification_history"].append(
                {
                    "action": "acknowledged",
                    "by": acknowledged_by,
                    "at": now_sao_paulo().isoformat(),
                    "level": escalation_dict["current_level"],
                }
            )

            await self.redis.setex(
                escalation_key, 86400 * 7, json.dumps(escalation_dict)
            )

            await self._cycle_ops.send_escalation_notification(
                escalation_dict,
                f"Escalation acknowledged by {acknowledged_by}",
            )

            logger.info(
                f"Escalation {escalation_id} acknowledged by {acknowledged_by}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error acknowledging escalation {escalation_id}: {e}"
            )
            return False

    async def resolve(
        self, escalation_id: str, resolved_by: str, resolution_note: str
    ) -> bool:
        """Resolve an escalation."""
        try:
            escalation_key = f"escalation:{escalation_id}"
            escalation_data = await self.redis.get(escalation_key)

            if not escalation_data:
                return False

            escalation_dict = json.loads(escalation_data)
            escalation_dict["resolved"] = True
            escalation_dict["resolved_by"] = resolved_by
            escalation_dict["resolved_at"] = now_sao_paulo().isoformat()
            escalation_dict["resolution_note"] = resolution_note

            escalation_dict["notification_history"].append(
                {
                    "action": "resolved",
                    "by": resolved_by,
                    "at": now_sao_paulo().isoformat(),
                    "note": resolution_note,
                    "level": escalation_dict["current_level"],
                }
            )

            await self.redis.setex(
                escalation_key, 86400 * 7, json.dumps(escalation_dict)
            )

            await self._cycle_ops.send_escalation_notification(
                escalation_dict,
                f"Escalation resolved by {resolved_by}: {resolution_note}",
            )

            logger.info(f"Escalation {escalation_id} resolved by {resolved_by}")
            return True

        except Exception as e:
            logger.error(
                f"Error resolving escalation {escalation_id}: {e}"
            )
            return False
