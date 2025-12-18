"""
Redis-backed storage for FollowUpSystemService.

Replaces in-memory dictionaries with persistent Redis storage:
- pending_actions: Redis Hash + Sorted Set
- active_alerts: Redis Hash + Sorted Set
- conversation_contexts: Redis String with TTL

Key patterns:
- followup:actions:{patient_id} - Hash storing patient's actions
- followup:actions:pending - Sorted Set by scheduled_for timestamp
- followup:alerts:{patient_id} - Hash storing patient's alerts
- followup:alerts:active - Sorted Set by escalation level
- followup:context:{patient_id} - String (JSON) with 7-day TTL
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from app.core.redis_unified import get_async_redis

logger = logging.getLogger(__name__)

# TTL constants
CONTEXT_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
ACTION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days for completed actions
ALERT_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days for resolved alerts

# Escalation level scores for sorted set
ESCALATION_SCORES = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
    "emergency": 5,
}


class FollowUpRedisStore:
    """
    Redis-backed storage for follow-up actions, alerts, and conversation contexts.

    Provides persistence that survives service restarts, with graceful
    fallback to in-memory storage if Redis is unavailable.
    """

    def __init__(self):
        """Initialize Redis store with fallback storage."""
        self._redis = None
        self._redis_available = True

        # Fallback in-memory storage (used if Redis unavailable)
        self._fallback_storage = {"actions": {}, "alerts": {}, "contexts": {}}

        logger.info("FollowUpRedisStore initialized")

    async def _get_redis(self):
        """Get Redis client with availability check."""
        if not self._redis_available:
            return None

        try:
            if self._redis is None:
                self._redis = await get_async_redis()
            # Test connection
            await self._redis.ping()
            return self._redis
        except Exception as e:
            logger.warning(
                f"Redis unavailable, falling back to in-memory storage: {e}",
                extra={"error": str(e)},
            )
            self._redis_available = False
            return None

    # =========================================================================
    # ACTION STORAGE
    # =========================================================================

    async def store_action(self, action: Any) -> bool:
        """
        Store a follow-up action.

        Args:
            action: FollowUpAction instance

        Returns:
            True if stored successfully
        """
        try:
            action_data = {
                "action_id": str(action.action_id),
                "patient_id": str(action.patient_id),
                "follow_up_type": action.follow_up_type.value
                if hasattr(action.follow_up_type, "value")
                else str(action.follow_up_type),
                "priority": action.priority,
                "scheduled_for": action.scheduled_for.isoformat(),
                "parameters": action.parameters,
                "created_by": action.created_by,
                "created_at": action.created_at.isoformat(),
                "status": action.status,
                "executed_at": action.executed_at.isoformat()
                if action.executed_at
                else None,
                "execution_result": action.execution_result,
            }

            redis = await self._get_redis()
            if redis:
                # Store in patient's action hash
                action_key = f"followup:actions:{action.patient_id}"
                await redis.hset(
                    action_key, str(action.action_id), json.dumps(action_data)
                )

                # Add to pending sorted set if pending
                if action.status == "pending":
                    score = action.scheduled_for.timestamp()
                    await redis.zadd(
                        "followup:actions:pending", {str(action.action_id): score}
                    )

                logger.debug(
                    "Stored action in Redis",
                    extra={
                        "action_id": str(action.action_id),
                        "patient_id": str(action.patient_id),
                    },
                )
                return True
            else:
                # Fallback to in-memory
                self._fallback_storage["actions"][str(action.action_id)] = action_data
                return True

        except Exception as e:
            logger.error(f"Failed to store action: {e}", exc_info=True)
            # Try fallback
            try:
                self._fallback_storage["actions"][str(action.action_id)] = action_data
                return True
            except Exception as fallback_error:
                logger.error(f"Fallback storage also failed: {fallback_error}")
                return False

    async def get_pending_actions(
        self, limit: int = 100, before: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get pending actions scheduled before given time.

        Args:
            limit: Maximum number of actions to return
            before: Only return actions scheduled before this time

        Returns:
            List of action dictionaries
        """
        try:
            if before is None:
                before = datetime.utcnow()

            redis = await self._get_redis()
            if redis:
                # Get action IDs from sorted set
                max_score = before.timestamp()
                action_ids = await redis.zrangebyscore(
                    "followup:actions:pending", min=0, max=max_score, start=0, num=limit
                )

                actions = []
                for action_id in action_ids:
                    action_id_str = (
                        action_id.decode()
                        if isinstance(action_id, bytes)
                        else action_id
                    )
                    # We need to find which patient this action belongs to
                    # This is a limitation - we might need a reverse index
                    # For now, scan all patient keys (not ideal for large scale)
                    pattern = "followup:actions:*"
                    async for key in redis.scan_iter(match=pattern):
                        if key == b"followup:actions:pending":
                            continue
                        action_data = await redis.hget(key, action_id_str)
                        if action_data:
                            actions.append(json.loads(action_data))
                            break

                return actions[:limit]
            else:
                # Fallback: filter in-memory storage
                now_ts = before.timestamp()
                pending = [
                    action
                    for action in self._fallback_storage["actions"].values()
                    if action.get("status") == "pending"
                    and datetime.fromisoformat(action["scheduled_for"]).timestamp()
                    <= now_ts
                ]
                return sorted(pending, key=lambda x: x["scheduled_for"])[:limit]

        except Exception as e:
            logger.error(f"Failed to get pending actions: {e}", exc_info=True)
            return []

    async def update_action_status(
        self,
        action_id: UUID,
        status: str,
        executed_at: Optional[datetime] = None,
        execution_result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update action status.

        Args:
            action_id: Action UUID
            status: New status
            executed_at: Execution timestamp
            execution_result: Execution result data

        Returns:
            True if updated successfully
        """
        try:
            redis = await self._get_redis()
            if redis:
                # Remove from pending set
                await redis.zrem("followup:actions:pending", str(action_id))

                # Find and update the action in patient hash
                pattern = "followup:actions:*"
                async for key in redis.scan_iter(match=pattern):
                    if key == b"followup:actions:pending":
                        continue
                    action_data = await redis.hget(key, str(action_id))
                    if action_data:
                        data = json.loads(action_data)
                        data["status"] = status
                        if executed_at:
                            data["executed_at"] = executed_at.isoformat()
                        if execution_result:
                            data["execution_result"] = execution_result
                        await redis.hset(key, str(action_id), json.dumps(data))

                        # Set TTL on completed actions
                        if status in ["executed", "failed"]:
                            await redis.expire(key, ACTION_TTL_SECONDS)

                        return True
                return False
            else:
                # Fallback
                if str(action_id) in self._fallback_storage["actions"]:
                    action = self._fallback_storage["actions"][str(action_id)]
                    action["status"] = status
                    if executed_at:
                        action["executed_at"] = executed_at.isoformat()
                    if execution_result:
                        action["execution_result"] = execution_result
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to update action status: {e}", exc_info=True)
            return False

    # =========================================================================
    # ALERT STORAGE
    # =========================================================================

    async def store_alert(self, alert: Any) -> bool:
        """
        Store an escalation alert.

        Args:
            alert: EscalationAlert instance

        Returns:
            True if stored successfully
        """
        try:
            alert_data = {
                "alert_id": str(alert.alert_id),
                "patient_id": str(alert.patient_id),
                "escalation_level": alert.escalation_level.value
                if hasattr(alert.escalation_level, "value")
                else str(alert.escalation_level),
                "concern_type": alert.concern_type.value
                if hasattr(alert.concern_type, "value")
                else str(alert.concern_type),
                "description": alert.description,
                "original_message": alert.original_message,
                "recommended_actions": alert.recommended_actions,
                "notification_channels": [
                    ch.value if hasattr(ch, "value") else str(ch)
                    for ch in alert.notification_channels
                ],
                "requires_immediate_response": alert.requires_immediate_response,
                "created_at": alert.created_at.isoformat(),
                "acknowledged_at": alert.acknowledged_at.isoformat()
                if alert.acknowledged_at
                else None,
                "resolved_at": alert.resolved_at.isoformat()
                if alert.resolved_at
                else None,
                "assigned_to": alert.assigned_to,
            }

            redis = await self._get_redis()
            if redis:
                # Store in patient's alert hash
                alert_key = f"followup:alerts:{alert.patient_id}"
                await redis.hset(alert_key, str(alert.alert_id), json.dumps(alert_data))

                # Add to active sorted set if not resolved
                if not alert.resolved_at:
                    level = (
                        alert.escalation_level.value
                        if hasattr(alert.escalation_level, "value")
                        else str(alert.escalation_level)
                    )
                    score = ESCALATION_SCORES.get(level.lower(), 2)
                    await redis.zadd(
                        "followup:alerts:active", {str(alert.alert_id): score}
                    )

                logger.debug(
                    "Stored alert in Redis",
                    extra={
                        "alert_id": str(alert.alert_id),
                        "patient_id": str(alert.patient_id),
                    },
                )
                return True
            else:
                self._fallback_storage["alerts"][str(alert.alert_id)] = alert_data
                return True

        except Exception as e:
            logger.error(f"Failed to store alert: {e}", exc_info=True)
            return False

    async def get_active_alerts(
        self, patient_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Get active (unresolved) alerts.

        Args:
            patient_id: Optional filter by patient

        Returns:
            List of alert dictionaries
        """
        try:
            redis = await self._get_redis()
            if redis:
                if patient_id:
                    # Get alerts for specific patient
                    alert_key = f"followup:alerts:{patient_id}"
                    alerts = await redis.hgetall(alert_key)
                    result = []
                    for alert_data in alerts.values():
                        data = json.loads(alert_data)
                        if not data.get("resolved_at"):
                            result.append(data)
                    return result
                else:
                    # Get all active alerts from sorted set
                    alert_ids = await redis.zrevrange("followup:alerts:active", 0, -1)
                    alerts = []
                    for alert_id in alert_ids:
                        alert_id_str = (
                            alert_id.decode()
                            if isinstance(alert_id, bytes)
                            else alert_id
                        )
                        # Find the alert data
                        pattern = "followup:alerts:*"
                        async for key in redis.scan_iter(match=pattern):
                            if key == b"followup:alerts:active":
                                continue
                            alert_data = await redis.hget(key, alert_id_str)
                            if alert_data:
                                alerts.append(json.loads(alert_data))
                                break
                    return alerts
            else:
                # Fallback
                alerts = list(self._fallback_storage["alerts"].values())
                if patient_id:
                    alerts = [
                        a for a in alerts if a.get("patient_id") == str(patient_id)
                    ]
                return [a for a in alerts if not a.get("resolved_at")]

        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}", exc_info=True)
            return []

    async def update_alert_status(
        self,
        alert_id: UUID,
        acknowledged_at: Optional[datetime] = None,
        resolved_at: Optional[datetime] = None,
        assigned_to: Optional[str] = None,
    ) -> bool:
        """
        Update alert status (acknowledge/resolve).

        Args:
            alert_id: Alert UUID
            acknowledged_at: Acknowledgment timestamp
            resolved_at: Resolution timestamp
            assigned_to: Who handled the alert

        Returns:
            True if updated successfully
        """
        try:
            redis = await self._get_redis()
            if redis:
                # Find and update the alert
                pattern = "followup:alerts:*"
                async for key in redis.scan_iter(match=pattern):
                    if key == b"followup:alerts:active":
                        continue
                    alert_data = await redis.hget(key, str(alert_id))
                    if alert_data:
                        data = json.loads(alert_data)
                        if acknowledged_at:
                            data["acknowledged_at"] = acknowledged_at.isoformat()
                        if resolved_at:
                            data["resolved_at"] = resolved_at.isoformat()
                            # Remove from active set
                            await redis.zrem("followup:alerts:active", str(alert_id))
                            # Set TTL on resolved alerts
                            await redis.expire(key, ALERT_TTL_SECONDS)
                        if assigned_to:
                            data["assigned_to"] = assigned_to
                        await redis.hset(key, str(alert_id), json.dumps(data))
                        return True
                return False
            else:
                # Fallback
                if str(alert_id) in self._fallback_storage["alerts"]:
                    alert = self._fallback_storage["alerts"][str(alert_id)]
                    if acknowledged_at:
                        alert["acknowledged_at"] = acknowledged_at.isoformat()
                    if resolved_at:
                        alert["resolved_at"] = resolved_at.isoformat()
                    if assigned_to:
                        alert["assigned_to"] = assigned_to
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to update alert status: {e}", exc_info=True)
            return False

    # =========================================================================
    # CONTEXT STORAGE
    # =========================================================================

    async def store_context(self, context: Any) -> bool:
        """
        Store conversation context with 7-day TTL.

        Args:
            context: ConversationContext instance

        Returns:
            True if stored successfully
        """
        try:
            context_data = {
                "patient_id": str(context.patient_id),
                "conversation_history": context.conversation_history,
                "current_topic": context.current_topic,
                "emotional_state": context.emotional_state,
                "medical_context": context.medical_context,
                "preferences": context.preferences,
                "last_updated": context.last_updated.isoformat(),
            }

            redis = await self._get_redis()
            if redis:
                context_key = f"followup:context:{context.patient_id}"
                await redis.setex(
                    context_key, CONTEXT_TTL_SECONDS, json.dumps(context_data)
                )
                logger.debug(
                    "Stored context in Redis with 7-day TTL",
                    extra={"patient_id": str(context.patient_id)},
                )
                return True
            else:
                self._fallback_storage["contexts"][str(context.patient_id)] = {
                    "data": context_data,
                    "expires_at": datetime.utcnow()
                    + timedelta(seconds=CONTEXT_TTL_SECONDS),
                }
                return True

        except Exception as e:
            logger.error(f"Failed to store context: {e}", exc_info=True)
            return False

    async def get_context(self, patient_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get conversation context for patient.

        Args:
            patient_id: Patient UUID

        Returns:
            Context dictionary or None if not found/expired
        """
        try:
            redis = await self._get_redis()
            if redis:
                context_key = f"followup:context:{patient_id}"
                context_data = await redis.get(context_key)
                if context_data:
                    return json.loads(context_data)
                return None
            else:
                # Fallback with manual TTL check
                stored = self._fallback_storage["contexts"].get(str(patient_id))
                if stored:
                    if datetime.utcnow() < stored["expires_at"]:
                        return stored["data"]
                    else:
                        # Expired - remove it
                        del self._fallback_storage["contexts"][str(patient_id)]
                return None

        except Exception as e:
            logger.error(f"Failed to get context: {e}", exc_info=True)
            return None

    # =========================================================================
    # HEALTH CHECK
    # =========================================================================

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Redis storage.

        Returns:
            Health status dictionary
        """
        try:
            redis = await self._get_redis()
            if redis:
                await redis.ping()

                # Get stats
                pending_count = await redis.zcard("followup:actions:pending")
                active_alerts_count = await redis.zcard("followup:alerts:active")

                return {
                    "healthy": True,
                    "backend": "redis",
                    "stats": {
                        "pending_actions": pending_count,
                        "active_alerts": active_alerts_count,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            else:
                return {
                    "healthy": True,
                    "backend": "in-memory-fallback",
                    "warning": "Redis unavailable, using in-memory fallback",
                    "stats": {
                        "pending_actions": len(
                            [
                                a
                                for a in self._fallback_storage["actions"].values()
                                if a.get("status") == "pending"
                            ]
                        ),
                        "active_alerts": len(
                            [
                                a
                                for a in self._fallback_storage["alerts"].values()
                                if not a.get("resolved_at")
                            ]
                        ),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def cleanup_expired(self) -> Dict[str, int]:
        """
        Clean up expired in-memory fallback data.
        Redis handles TTL automatically.

        Returns:
            Counts of cleaned items
        """
        try:
            now = datetime.utcnow()
            cleaned = {"contexts": 0}

            # Clean expired contexts from fallback storage
            expired_contexts = [
                patient_id
                for patient_id, stored in self._fallback_storage["contexts"].items()
                if stored["expires_at"] < now
            ]
            for patient_id in expired_contexts:
                del self._fallback_storage["contexts"][patient_id]
                cleaned["contexts"] += 1

            if cleaned["contexts"] > 0:
                logger.info(
                    "Cleaned up expired fallback data",
                    extra={"cleaned_contexts": cleaned["contexts"]},
                )

            return cleaned

        except Exception as e:
            logger.error(f"Failed to cleanup expired data: {e}", exc_info=True)
            return {"contexts": 0}
