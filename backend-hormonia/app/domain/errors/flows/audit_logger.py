"""
Error audit logging and statistics tracking for flow operations.
Handles error persistence, statistics collection, and cleanup operations.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Any
from uuid import uuid4

from app.services.websocket_events import websocket_events
from app.schemas.websocket import WebSocketEventType

from .classifier import ErrorSeverity, ErrorHandlerConstants
from .retry_manager import ErrorRecord, RecoveryResult
from .redis_scan import scan_keys
from app.utils.timezone import now_sao_paulo, to_sao_paulo

logger = logging.getLogger(__name__)


class ErrorAuditLogger:
    """Handles error logging, statistics, and audit trail."""

    def __init__(self, redis_client):
        """
        Initialize audit logger.

        Args:
            redis_client: Redis client for storage
        """
        self.redis = redis_client
        self.stats_cache = ErrorStatisticsCache(redis_client)

    async def _scan_keys(self, pattern: str, count: int = 200) -> list[Any]:
        """List keys using SCAN to avoid blocking Redis with KEYS."""
        return await scan_keys(self.redis, pattern=pattern, count=count)

    @staticmethod
    def _normalize_datetime(value: Any) -> datetime:
        """
        Parse and normalize datetime values to timezone-aware Sao Paulo time.
        Accepts datetime objects or ISO strings (aware or naive).
        """
        if isinstance(value, datetime):
            return to_sao_paulo(value)

        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return to_sao_paulo(parsed)

        raise TypeError(f"Unsupported datetime value type: {type(value)!r}")

    async def store_error(self, error_record: ErrorRecord) -> bool:
        """
        Store error record in Redis for monitoring.

        Args:
            error_record: Error record to store

        Returns:
            Success status
        """
        try:
            error_data = {
                "id": error_record.id,
                "error_type": error_record.error_type,
                "category": error_record.category.value,
                "severity": error_record.severity.value,
                "message": error_record.message,
                "patient_id": str(error_record.context.patient_id),
                "operation": error_record.context.operation,
                "recovery_attempts": error_record.recovery_attempts,
                "resolved": error_record.resolved,
                "created_at": error_record.created_at.isoformat(),
            }

            # Store with 7-day expiration
            await self.redis.setex(
                f"flow_error:{error_record.id}",
                ErrorHandlerConstants.REDIS_ERROR_TTL,
                json.dumps(error_data),
            )

            logger.debug(f"Stored error record: {error_record.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store error in Redis: {e}")
            return False

    async def publish_error_event(
        self, error_record: ErrorRecord, recovery_result: RecoveryResult
    ) -> bool:
        """
        Publish error event via WebSocket.

        Args:
            error_record: Error record
            recovery_result: Recovery result

        Returns:
            Success status
        """
        try:
            event_data = {
                "error_id": error_record.id,
                "error_type": error_record.error_type,
                "category": error_record.category.value,
                "severity": error_record.severity.value,
                "recovery_strategy": recovery_result.strategy_used.value,
                "recovery_success": recovery_result.success,
                "error_resolved": recovery_result.error_resolved,
            }

            await websocket_events.broadcast_flow_event(
                event_type=WebSocketEventType.FLOW_ERROR,
                patient_id=error_record.context.patient_id,
                flow_data={
                    "metadata": {
                        "flow_id": str(error_record.context.flow_state_id),
                        "event_data": event_data,
                    }
                },
            )

            logger.debug(f"Published error event: {error_record.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish error event: {e}")
            return False

    async def escalate_error(
        self, error_record: ErrorRecord, recovery_result: RecoveryResult
    ) -> bool:
        """
        Escalate error to healthcare providers via WebSocket.

        Args:
            error_record: Error record
            recovery_result: Recovery result

        Returns:
            Success status
        """
        try:
            if (
                error_record.severity == ErrorSeverity.CRITICAL
                or not recovery_result.success
            ):
                escalation_message = f"Critical flow error for patient {error_record.context.patient_id}: {error_record.error_type}"
                alert_data = {
                    "alert_id": str(uuid4()),
                    "patient_id": str(error_record.context.patient_id),
                    "alert_type": "critical_flow_error",
                    "severity": "critical",
                    "title": escalation_message,
                    "description": escalation_message,
                    "metadata": {
                        "error_id": error_record.id,
                        "recovery_failed": not recovery_result.success,
                    },
                }

                await websocket_events.broadcast_alert_event(
                    event_type=WebSocketEventType.ALERT_CREATED,
                    alert_data=alert_data,
                )

                logger.critical(f"Escalated critical error: {error_record.id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to escalate error: {e}")
            return False

    async def get_error_statistics(
        self, timeframe_hours: int = 24, use_cache: bool = True
    ) -> dict[str, Any]:
        """
        Get error statistics for monitoring with caching.

        Args:
            timeframe_hours: Hours to look back
            use_cache: Whether to use cached statistics

        Returns:
            Statistics dictionary
        """
        try:
            # Check cache first
            if use_cache:
                cached_stats = await self.stats_cache.get_cached_stats(timeframe_hours)
                if cached_stats:
                    return cached_stats

            cutoff_time = now_sao_paulo() - timedelta(hours=timeframe_hours)

            # Get all error keys
            error_keys = await self._scan_keys("flow_error:*")

            # Batch get all error data using pipeline
            pipeline = self.redis.pipeline()
            if error_keys:
                for key in error_keys:
                    pipeline.get(key)
                error_data_list = await pipeline.execute()
            else:
                error_data_list = []

            stats = {
                "total_errors": 0,
                "by_category": {},
                "by_severity": {},
                "resolved_errors": 0,
                "pending_errors": 0,
                "recovery_success_rate": 0.0,
                "timeframe_hours": timeframe_hours,
                "generated_at": now_sao_paulo().isoformat(),
            }

            resolved_count = 0
            total_count = 0

            # Process error data efficiently
            for error_data in error_data_list:
                if not error_data:
                    continue

                try:
                    error_info = json.loads(error_data)
                    error_time = self._normalize_datetime(error_info["created_at"])

                    if error_time >= cutoff_time:
                        total_count += 1

                        # Count by category
                        category = error_info["category"]
                        stats["by_category"][category] = (
                            stats["by_category"].get(category, 0) + 1
                        )

                        # Count by severity
                        severity = error_info["severity"]
                        stats["by_severity"][severity] = (
                            stats["by_severity"].get(severity, 0) + 1
                        )

                        # Count resolved
                        if error_info["resolved"]:
                            resolved_count += 1

                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    logger.warning(f"Failed to parse error data: {e}")
                    continue

            stats["total_errors"] = total_count
            stats["resolved_errors"] = resolved_count
            stats["pending_errors"] = total_count - resolved_count
            stats["recovery_success_rate"] = (
                (resolved_count / total_count * 100) if total_count > 0 else 0.0
            )

            # Cache the results
            if use_cache:
                await self.stats_cache.cache_stats(stats, timeframe_hours)

            return stats

        except Exception as e:
            logger.error(f"Failed to get error statistics: {e}")
            return {"error": str(e), "generated_at": now_sao_paulo().isoformat()}

    async def cleanup_old_errors(self, error_records: dict, days_old: int = 7) -> int:
        """
        Clean up old error records from memory.

        Args:
            error_records: In-memory error records dictionary
            days_old: Age threshold in days

        Returns:
            Number of cleaned records
        """
        try:
            cutoff_time = now_sao_paulo() - timedelta(days=days_old)
            cleaned_count = 0

            # Clean from memory
            to_remove = []
            for error_id, error_record in error_records.items():
                created_at = self._normalize_datetime(error_record.created_at)
                if created_at < cutoff_time:
                    to_remove.append(error_id)

            for error_id in to_remove:
                del error_records[error_id]
                cleaned_count += 1

            logger.info(f"Cleaned up {cleaned_count} old error records")
            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup old errors: {e}")
            return 0


class ErrorStatisticsCache:
    """Caches error statistics to avoid expensive Redis operations."""

    def __init__(self, redis_client, cache_ttl: int = 300):
        """
        Initialize statistics cache.

        Args:
            redis_client: Redis client
            cache_ttl: Cache TTL in seconds (default 5 minutes)
        """
        self.redis = redis_client
        self.cache_ttl = cache_ttl
        self._cache_key = "error_stats_cache"

    async def get_cached_stats(self, timeframe_hours: int) -> Optional[dict[str, Any]]:
        """
        Get cached statistics if available.

        Args:
            timeframe_hours: Timeframe for stats

        Returns:
            Cached stats or None
        """
        try:
            cache_key = f"{self._cache_key}:{timeframe_hours}"
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached stats: {e}")
        return None

    async def cache_stats(self, stats: dict[str, Any], timeframe_hours: int) -> bool:
        """
        Cache statistics.

        Args:
            stats: Statistics to cache
            timeframe_hours: Timeframe for stats

        Returns:
            Success status
        """
        try:
            cache_key = f"{self._cache_key}:{timeframe_hours}"
            await self.redis.setex(cache_key, self.cache_ttl, json.dumps(stats))
            return True
        except Exception as e:
            logger.warning(f"Failed to cache stats: {e}")
            return False
