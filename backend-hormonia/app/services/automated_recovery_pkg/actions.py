"""
Recovery action implementations for the automated recovery service.
"""

import logging
from typing import List

from redis import Redis

from app.services.error_recovery import ErrorRecoveryService
from app.services.data_corruption import DataCorruptionDetector
from app.services.manual_correction import ManualCorrectionService

from app.services.automated_recovery_pkg.models import (
    RecoveryAction,
    RecoveryResult,
    RecoveryOperation,
)

logger = logging.getLogger(__name__)


def _fail_op(action: RecoveryAction, error: Exception) -> RecoveryOperation:
    """Create a failed RecoveryOperation."""
    return RecoveryOperation(
        action=action, result=RecoveryResult.FAILED,
        description=f"Failed: {action.value}", items_processed=0,
        items_recovered=0, execution_time=0, error_message=str(error),
    )


class RecoveryActions:
    """Implements individual recovery action handlers."""

    def __init__(
        self, redis: Redis,
        error_recovery_service: ErrorRecoveryService,
        corruption_detector: DataCorruptionDetector,
        manual_correction_service: ManualCorrectionService,
        recovery_config: dict,
    ):
        self.redis = redis
        self.error_recovery_service = error_recovery_service
        self.corruption_detector = corruption_detector
        self.manual_correction_service = manual_correction_service
        self.recovery_config = recovery_config

    async def restart_failed_flows(self) -> RecoveryOperation:
        """Restart failed flows."""
        try:
            failed_flows = await self.error_recovery_service.get_failed_flows()
            recovered = 0
            for fid in failed_flows[: self.recovery_config["batch_size"]]:
                try:
                    if await self.error_recovery_service.recover_failed_flow(fid):
                        recovered += 1
                except Exception as e:
                    logger.error(f"Error recovering flow {fid}: {e}")
            result = RecoveryResult.SUCCESS if recovered == len(failed_flows) else RecoveryResult.PARTIAL_SUCCESS
            return RecoveryOperation(
                action=RecoveryAction.RESTART_FAILED_FLOWS, result=result,
                description=f"Restarted {recovered}/{len(failed_flows)} failed flows",
                items_processed=len(failed_flows), items_recovered=recovered,
                execution_time=0,
            )
        except Exception as e:
            return _fail_op(RecoveryAction.RESTART_FAILED_FLOWS, e)

    async def clear_stuck_queues(self) -> RecoveryOperation:
        """Clear stuck message queues."""
        try:
            stuck = await self._get_stuck_queue_items()
            cleared = 0
            for item in stuck:
                try:
                    await self._clear_queue_item(item)
                    cleared += 1
                except Exception as e:
                    logger.error(f"Error clearing queue item {item}: {e}")
            return RecoveryOperation(
                action=RecoveryAction.CLEAR_STUCK_QUEUES,
                result=RecoveryResult.SUCCESS if cleared > 0 else RecoveryResult.SKIPPED,
                description=f"Cleared {cleared} stuck queue items",
                items_processed=len(stuck), items_recovered=cleared, execution_time=0,
            )
        except Exception as e:
            return _fail_op(RecoveryAction.CLEAR_STUCK_QUEUES, e)

    async def reset_corrupted_states(self) -> RecoveryOperation:
        """Reset corrupted flow states."""
        try:
            report = await self.corruption_detector.detect_bulk_corruption(
                self.recovery_config["batch_size"]
            )
            corrected = 0
            for cf in report:
                try:
                    if await self.manual_correction_service.correct_flow_state(cf["flow_id"]):
                        corrected += 1
                except Exception as e:
                    logger.error(f"Error correcting flow {cf['flow_id']}: {e}")
            return RecoveryOperation(
                action=RecoveryAction.RESET_CORRUPTED_STATES,
                result=RecoveryResult.SUCCESS if corrected > 0 else RecoveryResult.SKIPPED,
                description=f"Corrected {corrected}/{len(report)} corrupted states",
                items_processed=len(report), items_recovered=corrected, execution_time=0,
            )
        except Exception as e:
            return _fail_op(RecoveryAction.RESET_CORRUPTED_STATES, e)

    async def cleanup_orphaned_data(self) -> RecoveryOperation:
        """Clean up orphaned data."""
        try:
            orphaned = await self._find_orphaned_data()
            cleaned = 0
            for item in orphaned:
                try:
                    await self._clean_orphaned_item(item)
                    cleaned += 1
                except Exception as e:
                    logger.error(f"Error cleaning orphaned item {item}: {e}")
            return RecoveryOperation(
                action=RecoveryAction.CLEANUP_ORPHANED_DATA,
                result=RecoveryResult.SUCCESS if cleaned > 0 else RecoveryResult.SKIPPED,
                description=f"Cleaned {cleaned} orphaned data items",
                items_processed=len(orphaned), items_recovered=cleaned, execution_time=0,
            )
        except Exception as e:
            return _fail_op(RecoveryAction.CLEANUP_ORPHANED_DATA, e)

    async def refresh_external_connections(self) -> RecoveryOperation:
        """Refresh external service connections."""
        try:
            services = ["whatsapp_api", "gemini_api", "database"]
            refreshed = 0
            for svc in services:
                try:
                    await self._refresh_service_connection(svc)
                    refreshed += 1
                except Exception as e:
                    logger.error(f"Error refreshing connection to {svc}: {e}")
            return RecoveryOperation(
                action=RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS,
                result=RecoveryResult.SUCCESS if refreshed > 0 else RecoveryResult.FAILED,
                description=f"Refreshed {refreshed} external service connections",
                items_processed=len(services), items_recovered=refreshed, execution_time=0,
            )
        except Exception as e:
            return _fail_op(RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS, e)

    async def optimize_database_performance(self) -> RecoveryOperation:
        """Optimize database performance."""
        try:
            tasks = ["analyze_tables", "update_statistics", "cleanup_temp_data"]
            applied = 0
            for task in tasks:
                try:
                    await self._run_database_maintenance_task(task)
                    applied += 1
                except Exception as e:
                    logger.error(f"Error running database task {task}: {e}")
            return RecoveryOperation(
                action=RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE,
                result=RecoveryResult.SUCCESS if applied > 0 else RecoveryResult.FAILED,
                description=f"Applied {applied} database optimizations",
                items_processed=len(tasks), items_recovered=applied, execution_time=0,
            )
        except Exception as e:
            return _fail_op(RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE, e)

    async def clear_memory_pressure(self) -> RecoveryOperation:
        """Clear memory pressure."""
        try:
            expired = await self._find_expired_keys()
            cleared = 0
            for key in expired:
                try:
                    self.redis.delete(key)
                    cleared += 1
                except Exception as e:
                    logger.error(f"Error deleting expired key {key}: {e}")
            return RecoveryOperation(
                action=RecoveryAction.CLEAR_MEMORY_PRESSURE,
                result=RecoveryResult.SUCCESS if cleared > 0 else RecoveryResult.SKIPPED,
                description=f"Cleared {cleared} expired cache items",
                items_processed=len(expired), items_recovered=cleared, execution_time=0,
            )
        except Exception as e:
            return _fail_op(RecoveryAction.CLEAR_MEMORY_PRESSURE, e)

    async def rebalance_load(self) -> RecoveryOperation:
        """Rebalance system load."""
        return RecoveryOperation(
            action=RecoveryAction.REBALANCE_LOAD, result=RecoveryResult.SKIPPED,
            description="Load rebalancing not implemented",
            items_processed=0, items_recovered=0, execution_time=0,
        )

    # Stub helpers
    async def _get_stuck_queue_items(self) -> List[str]:
        return []

    async def _clear_queue_item(self, item: str) -> None:
        pass

    async def _find_orphaned_data(self) -> List[str]:
        return []

    async def _clean_orphaned_item(self, item: str) -> None:
        pass

    async def _refresh_service_connection(self, service: str) -> None:
        pass

    async def _run_database_maintenance_task(self, task: str) -> None:
        pass

    async def _find_expired_keys(self) -> List[str]:
        return []
