"""
Message deduplication service for follow-up messages.
Prevents duplicate follow-up messages within a configured window.
"""

import hashlib
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from app.core.redis_manager import get_async_redis_client
from app.monitoring.metrics import (
    follow_up_dedup_misses_total,
    follow_up_dedup_cache_hits,
    follow_up_dedup_redis_errors,
    follow_up_messages_deduplicated_total,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

DEFAULT_FOLLOW_UP_DEDUP_WINDOW_SECONDS = 24 * 60 * 60
DEDUP_KEY_PREFIX = "follow_up:dedup:"


def _parse_positive_int_env(var_name: str, default: int) -> int:
    try:
        value = int(os.getenv(var_name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(value, 0)


class MessageDeduplicationService:
    """Redis-backed deduplication for follow-up messages."""

    def __init__(self, window_seconds: Optional[int] = None) -> None:
        self.window_seconds = (
            window_seconds
            if window_seconds is not None
            else _parse_positive_int_env(
                "FOLLOW_UP_DEDUP_WINDOW_SECONDS", DEFAULT_FOLLOW_UP_DEDUP_WINDOW_SECONDS
            )
        )
        self.key_prefix = DEDUP_KEY_PREFIX
        self._cache_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"hits": 0, "misses": 0}
        )

    @staticmethod
    def _normalize_content(message_content: str) -> str:
        normalized = " ".join(message_content.split())
        return normalized.lower()

    def _generate_dedup_key(
        self, patient_id: UUID, message_content: str, follow_up_type: str
    ) -> str:
        normalized_content = self._normalize_content(message_content)
        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
        combined = f"{patient_id}:{content_hash}:{follow_up_type}"
        dedup_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return f"{self.key_prefix}{dedup_hash}"

    def _record_cache_metric(self, follow_up_type: str, hit: bool) -> None:
        message_type = follow_up_type or "unknown"
        stats = self._cache_stats[message_type]
        if hit:
            stats["hits"] += 1
        else:
            stats["misses"] += 1

        total = stats["hits"] + stats["misses"]
        hit_rate = (stats["hits"] / total * 100) if total > 0 else 0.0
        follow_up_dedup_cache_hits.labels(message_type=message_type).set(hit_rate)

    async def check_duplicate(
        self, patient_id: UUID, message_content: str, follow_up_type: str
    ) -> bool:
        dedup_key = self._generate_dedup_key(patient_id, message_content, follow_up_type)
        try:
            redis = await get_async_redis_client()
            if not redis:
                follow_up_dedup_redis_errors.labels(operation="check_duplicate").inc()
                logger.warning(
                    "Redis unavailable for follow-up message deduplication",
                    extra={
                        "patient_id": str(patient_id),
                        "follow_up_type": follow_up_type,
                        "dedup_key": dedup_key,
                    },
                )
                return False

            value = await redis.get(dedup_key)
            if value:
                follow_up_messages_deduplicated_total.labels(
                    message_type=follow_up_type, source="deduplication_service"
                ).inc()
                self._record_cache_metric(follow_up_type, hit=True)
                logger.info(
                    f"Duplicate follow-up message blocked for patient {patient_id}, type: {follow_up_type}",
                    extra={
                        "patient_id": str(patient_id),
                        "follow_up_type": follow_up_type,
                        "dedup_key": dedup_key,
                    },
                )
                return True

            self._record_cache_metric(follow_up_type, hit=False)
            follow_up_dedup_misses_total.labels(
                message_type=follow_up_type, source="deduplication_service"
            ).inc()
            logger.info(
                "Follow-up message dedup cache miss",
                extra={
                    "patient_id": str(patient_id),
                    "follow_up_type": follow_up_type,
                    "dedup_key": dedup_key,
                },
            )
            return False

        except Exception as e:
            follow_up_dedup_redis_errors.labels(operation="check_duplicate").inc()
            logger.warning(
                "Redis error during follow-up message deduplication check",
                extra={
                    "patient_id": str(patient_id),
                    "follow_up_type": follow_up_type,
                    "dedup_key": dedup_key,
                    "error": str(e),
                },
                exc_info=True,
            )
            return False

    async def mark_as_sent(
        self, patient_id: UUID, message_content: str, follow_up_type: str
    ) -> bool:
        dedup_key = self._generate_dedup_key(patient_id, message_content, follow_up_type)
        try:
            redis = await get_async_redis_client()
            if not redis:
                follow_up_dedup_redis_errors.labels(operation="mark_as_sent").inc()
                logger.warning(
                    "Redis unavailable while marking follow-up message as sent",
                    extra={
                        "patient_id": str(patient_id),
                        "follow_up_type": follow_up_type,
                        "dedup_key": dedup_key,
                    },
                )
                return False

            payload = {
                "sent_at": now_sao_paulo().isoformat(),
                "patient_id": str(patient_id),
            }
            await redis.setex(dedup_key, self.window_seconds, json.dumps(payload))
            return True

        except Exception as e:
            follow_up_dedup_redis_errors.labels(operation="mark_as_sent").inc()
            logger.warning(
                "Redis error while marking follow-up message as sent",
                extra={
                    "patient_id": str(patient_id),
                    "follow_up_type": follow_up_type,
                    "dedup_key": dedup_key,
                    "error": str(e),
                },
                exc_info=True,
            )
            return False

    async def health_check(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {
            "healthy": False,
            "redis_available": False,
            "window_seconds": self.window_seconds,
            "key_prefix": self.key_prefix,
        }
        try:
            redis = await get_async_redis_client()
            if not redis:
                return status

            await redis.ping()
            status["healthy"] = True
            status["redis_available"] = True
            return status

        except Exception as e:
            follow_up_dedup_redis_errors.labels(operation="health_check").inc()
            logger.warning(
                "Redis error during follow-up deduplication health check",
                extra={"error": str(e)},
                exc_info=True,
            )
            status["error"] = str(e)
            return status
