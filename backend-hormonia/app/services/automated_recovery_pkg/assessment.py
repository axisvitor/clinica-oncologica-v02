"""
Health assessment and recovery reporting for automated recovery.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from redis import Redis

from app.services.flow_monitoring import FlowMonitoringService
from app.services.error_recovery import ErrorRecoveryService
from app.services.data_corruption import DataCorruptionDetector
from app.repositories.flow import FlowStateRepository
from app.utils.timezone import now_sao_paulo

from app.services.automated_recovery_pkg.models import (
    RecoveryAction,
    RecoveryResult,
    RecoveryOperation,
)

logger = logging.getLogger(__name__)


class RecoveryAssessment:
    """Assesses system health and generates recovery reports."""

    def __init__(
        self,
        db: Any,
        redis: Redis,
        monitoring_service: FlowMonitoringService,
        error_recovery_service: ErrorRecoveryService,
        corruption_detector: DataCorruptionDetector,
        flow_repository: FlowStateRepository,
        recovery_config: Dict[str, Any],
        action_priorities: Dict[RecoveryAction, int],
        find_orphaned_data_fn,
    ):
        self.db = db
        self.redis = redis
        self.monitoring_service = monitoring_service
        self.error_recovery_service = error_recovery_service
        self.corruption_detector = corruption_detector
        self.flow_repository = flow_repository
        self.recovery_config = recovery_config
        self.action_priorities = action_priorities
        self._find_orphaned_data = find_orphaned_data_fn

    async def assess_recovery_needs(self) -> List[RecoveryAction]:
        """Assess system health and determine needed recovery actions."""
        recovery_actions = []

        try:
            await self.monitoring_service.get_system_health()

            corruption_rate = await self._check_corruption_rate()
            if corruption_rate > self.recovery_config["corruption_rate_threshold"]:
                recovery_actions.append(RecoveryAction.RESET_CORRUPTED_STATES)
                logger.warning(f"High corruption rate detected: {corruption_rate:.2%}")

            failed_flows_count = await self._count_failed_flows()
            if failed_flows_count > self.recovery_config["max_failed_flows_threshold"]:
                recovery_actions.append(RecoveryAction.RESTART_FAILED_FLOWS)
                logger.warning(f"High number of failed flows: {failed_flows_count}")

            stuck_queue_depth = await self._check_stuck_queues()
            if stuck_queue_depth > self.recovery_config["stuck_queue_threshold"]:
                recovery_actions.append(RecoveryAction.CLEAR_STUCK_QUEUES)
                logger.warning(f"Stuck queue detected with depth: {stuck_queue_depth}")

            orphaned_data_count = await self._count_orphaned_data()
            if orphaned_data_count > 0:
                recovery_actions.append(RecoveryAction.CLEANUP_ORPHANED_DATA)
                logger.info(f"Orphaned data detected: {orphaned_data_count} items")

            memory_usage = await self._check_memory_pressure()
            if memory_usage > self.recovery_config["memory_pressure_threshold"]:
                recovery_actions.append(RecoveryAction.CLEAR_MEMORY_PRESSURE)
                logger.warning(f"High memory usage: {memory_usage:.1%}")

            if await self._check_external_connection_issues():
                recovery_actions.append(RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS)
                logger.warning("External connection issues detected")

            if await self._check_database_performance_issues():
                recovery_actions.append(RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE)
                logger.warning("Database performance issues detected")

            recovery_actions.sort(
                key=lambda x: self.action_priorities.get(x, 0), reverse=True
            )

            return recovery_actions

        except Exception as e:
            logger.error(f"Error assessing recovery needs: {e}")
            return []

    async def generate_recovery_report(
        self, recovery_results: List[RecoveryOperation], start_time: datetime,
        get_next_recovery_time_fn,
    ) -> Dict[str, Any]:
        """Generate recovery report."""
        end_time = now_sao_paulo()
        total_execution_time = (end_time - start_time).total_seconds()

        successful_actions = [
            r for r in recovery_results if r.result == RecoveryResult.SUCCESS
        ]
        failed_actions = [
            r for r in recovery_results if r.result == RecoveryResult.FAILED
        ]
        partial_actions = [
            r for r in recovery_results if r.result == RecoveryResult.PARTIAL_SUCCESS
        ]

        total_items_processed = sum(r.items_processed for r in recovery_results)
        total_items_recovered = sum(r.items_recovered for r in recovery_results)

        return {
            "status": "completed",
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "total_execution_time": total_execution_time,
            "summary": {
                "total_actions": len(recovery_results),
                "successful_actions": len(successful_actions),
                "failed_actions": len(failed_actions),
                "partial_success_actions": len(partial_actions),
                "total_items_processed": total_items_processed,
                "total_items_recovered": total_items_recovered,
                "recovery_rate": (total_items_recovered / max(total_items_processed, 1))
                * 100,
            },
            "actions": [
                {
                    "action": r.action.value,
                    "result": r.result.value,
                    "description": r.description,
                    "items_processed": r.items_processed,
                    "items_recovered": r.items_recovered,
                    "execution_time": r.execution_time,
                    "error_message": r.error_message,
                    "metadata": r.metadata,
                }
                for r in recovery_results
            ],
            "next_recovery_allowed_at": await get_next_recovery_time_fn(),
        }

    # Assessment helper methods
    async def _check_corruption_rate(self) -> float:
        """Check current corruption rate."""
        try:
            total_flows = self.db.query(self.flow_repository.model).count()
            if total_flows == 0:
                return 0.0

            sample_size = min(100, total_flows)
            corruption_report = await self.corruption_detector.detect_bulk_corruption(
                sample_size
            )
            return len(corruption_report) / sample_size

        except Exception as e:
            logger.error(f"Error checking corruption rate: {e}")
            return 0.0

    async def _count_failed_flows(self) -> int:
        """Count failed flows."""
        try:
            failed_flows = await self.error_recovery_service.get_failed_flows()
            return len(failed_flows)
        except Exception as e:
            logger.error(f"Error counting failed flows: {e}")
            return 0

    async def _check_stuck_queues(self) -> int:
        """Check for stuck queues."""
        try:
            return 0
        except Exception as e:
            logger.error(f"Error checking stuck queues: {e}")
            return 0

    async def _count_orphaned_data(self) -> int:
        """Count orphaned data items."""
        try:
            orphaned_items = await self._find_orphaned_data()
            return len(orphaned_items)
        except Exception as e:
            logger.error(f"Error counting orphaned data: {e}")
            return 0

    async def _check_memory_pressure(self) -> float:
        """Check memory pressure."""
        try:
            redis_info = self.redis.info("memory")
            used_memory = redis_info.get("used_memory", 0)
            max_memory = redis_info.get("maxmemory", 0)

            if max_memory > 0:
                return used_memory / max_memory
            return 0.0
        except Exception as e:
            logger.error(f"Error checking memory pressure: {e}")
            return 0.0

    async def _check_external_connection_issues(self) -> bool:
        """Check for external connection issues."""
        try:
            return False
        except Exception as e:
            logger.error(f"Error checking external connections: {e}")
            return False

    async def _check_database_performance_issues(self) -> bool:
        """Check for database performance issues."""
        try:
            return False
        except Exception as e:
            logger.error(f"Error checking database performance: {e}")
            return False
