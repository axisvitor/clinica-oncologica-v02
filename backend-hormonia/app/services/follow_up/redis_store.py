"""
Redis-backed storage for FollowUpSystemService.

Replaces in-memory dictionaries with persistent Redis storage:
- pending_actions: Redis Hash + Sorted Set
- active_alerts: Redis Hash + Sorted Set
- conversation_contexts: Redis String with TTL

Key patterns:
- followup:actions:{patient_id} - Hash storing patient's actions
- followup:actions:pending - Sorted Set by scheduled_for timestamp
- followup:action_index:{action_id} - Reverse index: action_id -> patient_id (O(1))
- followup:alerts:{patient_id} - Hash storing patient's alerts
- followup:alerts:active - Sorted Set by escalation level
- followup:alert_index:{alert_id} - Reverse index: alert_id -> patient_id (O(1))
- followup:context:{patient_id} - String (JSON) with 1-hour TTL
- sent_messages:{patient_id} - String (ISO timestamp) with TTL for deduplication
- follow_up_locks:{patient_id} - String lock to avoid concurrent sends
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.redis_manager import get_async_redis_client as get_async_redis

logger = logging.getLogger(__name__)

# TTL constants
CONTEXT_TTL_SECONDS = 60 * 60  # 1 hour
ACTION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days for completed actions
ALERT_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days for resolved alerts
DEDUP_LOCK_TTL_SECONDS = 5 * 60  # 5 minutes lock for follow-up deduplication
PENDING_ACTIONS_FETCH_MULTIPLIER = 5

# Reverse index TTL should outlive the data it points to
INDEX_TTL_SECONDS = 120 * 24 * 60 * 60  # 120 days

# Priority ordering (lower rank = higher priority)
PRIORITY_RANKS = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "normal": 3,
    "low": 4,
}

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
        self._redis_retry_delay = 1
        self._redis_retry_max_delay = 30
        self._redis_retry_at: Optional[datetime] = None

        # Fallback in-memory storage (used if Redis unavailable)
        self._fallback_storage = {
            "actions": {},
            "alerts": {},
            "contexts": {},
            "dedup": {},
            "locks": {},
        }

        logger.info("FollowUpRedisStore initialized")

    def _schedule_redis_retry(self, now: datetime) -> None:
        delay = max(self._redis_retry_delay, 1)
        self._redis_retry_at = now + timedelta(seconds=delay)
        self._redis_retry_delay = min(delay * 2, self._redis_retry_max_delay)

    async def _attempt_reconnect(self, now: datetime):
        try:
            self._redis = await get_async_redis()
            await self._redis.ping()
            self._redis_available = True
            self._redis_retry_delay = 1
            self._redis_retry_at = None
            logger.info("Redis reconnected for follow-up store")
            return self._redis
        except Exception as e:
            logger.warning(
                f"Redis still unavailable, retrying later: {e}",
                extra={"error": str(e)},
            )
            self._redis_available = False
            self._redis = None
            self._schedule_redis_retry(now)
            return None

    async def _get_redis(self):
        """Get Redis client with availability check."""
        now = datetime.now(timezone.utc)
        if not self._redis_available:
            if self._redis_retry_at is None:
                return None
            if now < self._redis_retry_at:
                return None
            return await self._attempt_reconnect(now)

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
            self._redis = None
            self._schedule_redis_retry(now)
            return None

    def is_redis_available(self) -> bool:
        """Return cached Redis availability status."""
        return self._redis_available

    def _get_dedup_key(self, patient_id: UUID) -> str:
        """Return Redis key for follow-up message deduplication."""
        return f"sent_messages:{patient_id}"

    def _get_lock_key(self, patient_id: UUID) -> str:
        """Return Redis key for follow-up send lock."""
        return f"follow_up_locks:{patient_id}"

    def _get_priority_rank(self, priority: Optional[str]) -> int:
        """Return numeric rank for priority sorting."""
        if not priority:
            return len(PRIORITY_RANKS)
        return PRIORITY_RANKS.get(str(priority).lower(), len(PRIORITY_RANKS))

    def _get_scheduled_for_timestamp(self, scheduled_for: Optional[str]) -> float:
        """Parse scheduled_for timestamp safely."""
        if not scheduled_for:
            return 0.0
        try:
            parsed = datetime.fromisoformat(scheduled_for)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            return 0.0

    @staticmethod
    def _action_index_key(action_id) -> str:
        """Return Redis key for action reverse index."""
        return f"followup:action_index:{action_id}"

    @staticmethod
    def _alert_index_key(alert_id) -> str:
        """Return Redis key for alert reverse index."""
        return f"followup:alert_index:{alert_id}"

    async def _resolve_patient_for_action(
        self, redis, action_id_str: str,
    ) -> Optional[str]:
        """Resolve patient_id for an action via reverse index, with scan fallback."""
        patient_id = await redis.get(self._action_index_key(action_id_str))
        if patient_id:
            return patient_id.decode() if isinstance(patient_id, bytes) else patient_id

        # Migration fallback: scan to find, then backfill the index
        async for key in redis.scan_iter(match="followup:actions:*"):
            key_str = key.decode() if isinstance(key, bytes) else key
            if key_str == "followup:actions:pending":
                continue
            if await redis.hget(key, action_id_str):
                pid = key_str.rsplit(":", 1)[-1]
                await redis.setex(
                    self._action_index_key(action_id_str), INDEX_TTL_SECONDS, pid,
                )
                return pid
        return None

    async def _resolve_patient_for_alert(
        self, redis, alert_id_str: str,
    ) -> Optional[str]:
        """Resolve patient_id for an alert via reverse index, with scan fallback."""
        patient_id = await redis.get(self._alert_index_key(alert_id_str))
        if patient_id:
            return patient_id.decode() if isinstance(patient_id, bytes) else patient_id

        # Migration fallback: scan to find, then backfill the index
        async for key in redis.scan_iter(match="followup:alerts:*"):
            key_str = key.decode() if isinstance(key, bytes) else key
            if key_str == "followup:alerts:active":
                continue
            if await redis.hget(key, alert_id_str):
                pid = key_str.rsplit(":", 1)[-1]
                await redis.setex(
                    self._alert_index_key(alert_id_str), INDEX_TTL_SECONDS, pid,
                )
                return pid
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
                aid_str = str(action.action_id)
                pid_str = str(action.patient_id)
                await redis.hset(action_key, aid_str, json.dumps(action_data))

                # Write reverse index: action_id -> patient_id
                await redis.setex(
                    self._action_index_key(aid_str), INDEX_TTL_SECONDS, pid_str,
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
                before = datetime.now(timezone.utc)

            redis = await self._get_redis()
            if redis:
                # Get action IDs from sorted set
                max_score = before.timestamp()
                fetch_limit = max(limit * PENDING_ACTIONS_FETCH_MULTIPLIER, limit)
                action_ids = await redis.zrangebyscore(
                    "followup:actions:pending",
                    min=0,
                    max=max_score,
                    start=0,
                    num=fetch_limit,
                )

                actions = []
                for action_id in action_ids:
                    action_id_str = (
                        action_id.decode()
                        if isinstance(action_id, bytes)
                        else action_id
                    )
                    # O(1) lookup via reverse index
                    patient_id = await self._resolve_patient_for_action(
                        redis, action_id_str,
                    )
                    if not patient_id:
                        continue
                    action_data = await redis.hget(
                        f"followup:actions:{patient_id}", action_id_str,
                    )
                    if action_data:
                        actions.append(json.loads(action_data))

                sorted_actions = sorted(
                    actions,
                    key=lambda action: (
                        self._get_priority_rank(action.get("priority")),
                        self._get_scheduled_for_timestamp(
                            action.get("scheduled_for")
                        ),
                    ),
                )
                return sorted_actions[:limit]
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
                sorted_pending = sorted(
                    pending,
                    key=lambda action: (
                        self._get_priority_rank(action.get("priority")),
                        self._get_scheduled_for_timestamp(
                            action.get("scheduled_for")
                        ),
                    ),
                )
                return sorted_pending[:limit]

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
                aid_str = str(action_id)
                # Remove from pending set
                await redis.zrem("followup:actions:pending", aid_str)

                # O(1) lookup via reverse index
                patient_id = await self._resolve_patient_for_action(redis, aid_str)
                if not patient_id:
                    return False

                action_key = f"followup:actions:{patient_id}"
                raw = await redis.hget(action_key, aid_str)
                if not raw:
                    return False

                data = json.loads(raw)
                data["status"] = status
                if executed_at:
                    data["executed_at"] = executed_at.isoformat()
                if execution_result:
                    data["execution_result"] = execution_result
                await redis.hset(action_key, aid_str, json.dumps(data))

                # Set TTL on completed actions and their reverse index
                if status in ("executed", "completed", "failed"):
                    await redis.expire(action_key, ACTION_TTL_SECONDS)
                    await redis.expire(
                        self._action_index_key(aid_str), ACTION_TTL_SECONDS,
                    )

                return True
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

    async def claim_pending_action(
        self, action_id: UUID, in_progress_at: Optional[datetime] = None
    ) -> bool:
        """
        Atomically claim a pending action for execution.

        This prevents two workers from executing the same pending action.

        Args:
            action_id: Action UUID
            in_progress_at: Optional claim timestamp

        Returns:
            True if the action was claimed, False if already claimed/executed
        """
        try:
            if in_progress_at is None:
                in_progress_at = datetime.now(timezone.utc)

            aid_str = str(action_id)
            redis = await self._get_redis()
            if redis:
                patient_id = await self._resolve_patient_for_action(redis, aid_str)
                if not patient_id:
                    return False

                action_key = f"followup:actions:{patient_id}"
                claim_script = """
                    local action_key = KEYS[1]
                    local pending_key = KEYS[2]
                    local action_id = ARGV[1]
                    local in_progress_at = ARGV[2]

                    local raw = redis.call('HGET', action_key, action_id)
                    if not raw then
                        return 0
                    end

                    local data = cjson.decode(raw)
                    if data['status'] ~= 'pending' then
                        return 0
                    end

                    data['status'] = 'in_progress'
                    data['in_progress_at'] = in_progress_at

                    redis.call('HSET', action_key, action_id, cjson.encode(data))
                    redis.call('ZREM', pending_key, action_id)
                    return 1
                """

                result = await redis.eval(
                    claim_script,
                    2,
                    action_key,
                    "followup:actions:pending",
                    aid_str,
                    in_progress_at.isoformat(),
                )
                return bool(result)

            # Fallback storage
            action = self._fallback_storage["actions"].get(aid_str)
            if not action or action.get("status") != "pending":
                return False

            action["status"] = "in_progress"
            action["in_progress_at"] = in_progress_at.isoformat()
            return True

        except Exception as e:
            logger.error(f"Failed to claim pending action: {e}", exc_info=True)
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
                alid_str = str(alert.alert_id)
                pid_str = str(alert.patient_id)
                await redis.hset(alert_key, alid_str, json.dumps(alert_data))

                # Write reverse index: alert_id -> patient_id
                await redis.setex(
                    self._alert_index_key(alid_str), INDEX_TTL_SECONDS, pid_str,
                )

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
                        # O(1) lookup via reverse index
                        pid = await self._resolve_patient_for_alert(
                            redis, alert_id_str,
                        )
                        if not pid:
                            continue
                        alert_data = await redis.hget(
                            f"followup:alerts:{pid}", alert_id_str,
                        )
                        if alert_data:
                            alerts.append(json.loads(alert_data))
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
                alid_str = str(alert_id)
                # O(1) lookup via reverse index
                pid = await self._resolve_patient_for_alert(redis, alid_str)
                if not pid:
                    return False

                alert_key = f"followup:alerts:{pid}"
                raw = await redis.hget(alert_key, alid_str)
                if not raw:
                    return False

                data = json.loads(raw)
                if acknowledged_at:
                    data["acknowledged_at"] = acknowledged_at.isoformat()
                if resolved_at:
                    data["resolved_at"] = resolved_at.isoformat()
                    # Remove from active set
                    await redis.zrem("followup:alerts:active", alid_str)
                    # Set TTL on resolved alerts and their reverse index
                    await redis.expire(alert_key, ALERT_TTL_SECONDS)
                    await redis.expire(
                        self._alert_index_key(alid_str), ALERT_TTL_SECONDS,
                    )
                if assigned_to:
                    data["assigned_to"] = assigned_to
                await redis.hset(alert_key, alid_str, json.dumps(data))
                return True
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
        Store conversation context with 1-hour TTL.

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
                    "Stored context in Redis with 1-hour TTL",
                    extra={"patient_id": str(context.patient_id)},
                )
                return True
            else:
                self._fallback_storage["contexts"][str(context.patient_id)] = {
                    "data": context_data,
                    "expires_at": datetime.now(timezone.utc)
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
                    if datetime.now(timezone.utc) < stored["expires_at"]:
                        return stored["data"]
                    else:
                        # Expired - remove it
                        del self._fallback_storage["contexts"][str(patient_id)]
                return None

        except Exception as e:
            logger.error(f"Failed to get context: {e}", exc_info=True)
            return None

    # =========================================================================
    # DEDUPLICATION & LOCKS
    # =========================================================================

    async def acquire_follow_up_lock(
        self, patient_id: UUID, ttl_seconds: int = DEDUP_LOCK_TTL_SECONDS
    ) -> bool:
        """
        Acquire a short-lived lock to prevent concurrent follow-up sends.

        Args:
            patient_id: Patient UUID
            ttl_seconds: Lock TTL in seconds

        Returns:
            True if lock acquired, False otherwise
        """
        lock_key = self._get_lock_key(patient_id)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        try:
            redis = await self._get_redis()
            if redis:
                result = await redis.set(lock_key, "1", ex=ttl_seconds, nx=True)
                return bool(result)

            # Fallback to in-memory lock
            existing = self._fallback_storage["locks"].get(str(patient_id))
            if existing and existing["expires_at"] > now:
                return False

            self._fallback_storage["locks"][str(patient_id)] = {
                "expires_at": expires_at
            }
            return True

        except Exception as e:
            logger.error(f"Failed to acquire follow-up lock: {e}", exc_info=True)
            return False

    async def release_follow_up_lock(self, patient_id: UUID) -> bool:
        """
        Release follow-up send lock.

        Args:
            patient_id: Patient UUID

        Returns:
            True if lock released, False otherwise
        """
        lock_key = self._get_lock_key(patient_id)
        try:
            redis = await self._get_redis()
            if redis:
                await redis.delete(lock_key)
                return True

            if str(patient_id) in self._fallback_storage["locks"]:
                del self._fallback_storage["locks"][str(patient_id)]
            return True

        except Exception as e:
            logger.error(f"Failed to release follow-up lock: {e}", exc_info=True)
            return False

    async def get_last_follow_up_sent_at(
        self, patient_id: UUID
    ) -> Optional[datetime]:
        """
        Get timestamp of the last follow-up message sent to patient.

        Args:
            patient_id: Patient UUID

        Returns:
            Datetime of last follow-up message or None
        """
        dedup_key = self._get_dedup_key(patient_id)
        try:
            redis = await self._get_redis()
            if redis:
                value = await redis.get(dedup_key)
                if value:
                    if isinstance(value, bytes):
                        value = value.decode()
                    parsed = datetime.fromisoformat(value)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed
                return None

            # Fallback to in-memory dedup cache
            stored = self._fallback_storage["dedup"].get(str(patient_id))
            if stored:
                if stored["expires_at"] > datetime.now(timezone.utc):
                    return stored["sent_at"]
                del self._fallback_storage["dedup"][str(patient_id)]
            return None

        except Exception as e:
            logger.error(f"Failed to get follow-up dedup timestamp: {e}", exc_info=True)
            return None

    async def set_last_follow_up_sent_at(
        self, patient_id: UUID, sent_at: datetime, ttl_seconds: int
    ) -> bool:
        """
        Set follow-up message sent timestamp with TTL.

        Args:
            patient_id: Patient UUID
            sent_at: Timestamp of the follow-up message
            ttl_seconds: TTL in seconds

        Returns:
            True if stored successfully
        """
        dedup_key = self._get_dedup_key(patient_id)
        try:
            redis = await self._get_redis()
            if redis:
                await redis.setex(dedup_key, ttl_seconds, sent_at.isoformat())
                return True

            self._fallback_storage["dedup"][str(patient_id)] = {
                "sent_at": sent_at,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            }
            return True

        except Exception as e:
            logger.error(f"Failed to set follow-up dedup timestamp: {e}", exc_info=True)
            return False

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
                    "timestamp": datetime.now(timezone.utc).isoformat(),
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
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def cleanup_expired(self) -> Dict[str, int]:
        """
        Clean up expired in-memory fallback data.
        Redis handles TTL automatically.

        Returns:
            Counts of cleaned items
        """
        try:
            now = datetime.now(timezone.utc)
            cleaned = {"contexts": 0, "dedup": 0, "locks": 0}

            # Clean expired contexts from fallback storage
            expired_contexts = [
                patient_id
                for patient_id, stored in self._fallback_storage["contexts"].items()
                if stored["expires_at"] < now
            ]
            for patient_id in expired_contexts:
                del self._fallback_storage["contexts"][patient_id]
                cleaned["contexts"] += 1

            # Clean expired dedup entries
            expired_dedup = [
                patient_id
                for patient_id, stored in self._fallback_storage["dedup"].items()
                if stored["expires_at"] < now
            ]
            for patient_id in expired_dedup:
                del self._fallback_storage["dedup"][patient_id]
                cleaned["dedup"] += 1

            # Clean expired locks
            expired_locks = [
                patient_id
                for patient_id, stored in self._fallback_storage["locks"].items()
                if stored["expires_at"] < now
            ]
            for patient_id in expired_locks:
                del self._fallback_storage["locks"][patient_id]
                cleaned["locks"] += 1

            if any(value > 0 for value in cleaned.values()):
                logger.info(
                    "Cleaned up expired fallback data",
                    extra={"cleaned": cleaned},
                )

            return cleaned

        except Exception as e:
            logger.error(f"Failed to cleanup expired data: {e}", exc_info=True)
            return {"contexts": 0, "dedup": 0, "locks": 0}
