"""
Automated recovery service for handling system failures and data corruption.
Implements automated recovery mechanisms for common failure scenarios.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from redis import Redis

from app.services.flow_monitoring import FlowMonitoringService
from app.services.error_recovery import ErrorRecoveryService
from app.services.data_corruption import DataCorruptionDetector
from app.services.manual_correction import ManualCorrectionService
from app.repositories.flow import FlowStateRepository
from app.utils.timezone import now_sao_paulo

from app.services.automated_recovery_pkg.models import (
    RecoveryAction,
    RecoveryResult,
    RecoveryOperation,
)
from app.services.automated_recovery_pkg.actions import RecoveryActions
from app.services.automated_recovery_pkg.assessment import RecoveryAssessment

logger = logging.getLogger(__name__)


class AutomatedRecoveryService:
    """Service for automated system recovery and failure handling."""

    def __init__(
        self,
        db: Any,
        redis: Redis,
        monitoring_service: FlowMonitoringService,
        error_recovery_service: ErrorRecoveryService,
        corruption_detector: DataCorruptionDetector,
        manual_correction_service: ManualCorrectionService,
        flow_repository: FlowStateRepository,
    ):
        self.db = db
        self.redis = redis
        self.monitoring_service = monitoring_service
        self.error_recovery_service = error_recovery_service
        self.corruption_detector = corruption_detector
        self.manual_correction_service = manual_correction_service
        self.flow_repository = flow_repository

        self.recovery_config = {
            "max_failed_flows_threshold": 10,
            "stuck_queue_threshold": 100,
            "corruption_rate_threshold": 0.05,
            "memory_pressure_threshold": 0.9,
            "max_recovery_attempts": 3,
            "recovery_cooldown_minutes": 30,
            "batch_size": 50,
        }

        self.action_priorities = {
            RecoveryAction.RESET_CORRUPTED_STATES: 10,
            RecoveryAction.RESTART_FAILED_FLOWS: 9,
            RecoveryAction.CLEAR_STUCK_QUEUES: 8,
            RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS: 7,
            RecoveryAction.CLEANUP_ORPHANED_DATA: 6,
            RecoveryAction.CLEAR_MEMORY_PRESSURE: 5,
            RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE: 4,
            RecoveryAction.REBALANCE_LOAD: 3,
        }

        self._actions = RecoveryActions(
            redis=redis,
            error_recovery_service=error_recovery_service,
            corruption_detector=corruption_detector,
            manual_correction_service=manual_correction_service,
            recovery_config=self.recovery_config,
        )

        self._assessment = RecoveryAssessment(
            db=db,
            redis=redis,
            monitoring_service=monitoring_service,
            error_recovery_service=error_recovery_service,
            corruption_detector=corruption_detector,
            flow_repository=flow_repository,
            recovery_config=self.recovery_config,
            action_priorities=self.action_priorities,
            find_orphaned_data_fn=self._actions._find_orphaned_data,
        )

    async def run_automated_recovery_cycle(self) -> Dict[str, Any]:
        """Run complete automated recovery cycle."""
        start_time = now_sao_paulo()

        try:
            logger.info("Starting automated recovery cycle")

            if await self._is_in_recovery_cooldown():
                return {
                    "status": "skipped",
                    "reason": "Recovery is in cooldown period",
                    "next_allowed_at": await self._get_next_recovery_time(),
                }

            recovery_plan = await self._assessment.assess_recovery_needs()

            if not recovery_plan:
                return {
                    "status": "no_action_needed",
                    "message": "System health is within acceptable parameters",
                    "assessed_at": start_time.isoformat(),
                }

            recovery_results = await self._execute_recovery_plan(recovery_plan)
            await self._set_recovery_cooldown()
            report = await self._assessment.generate_recovery_report(
                recovery_results, start_time, self._get_next_recovery_time
            )

            logger.info(
                f"Automated recovery cycle completed: "
                f"{len(recovery_results)} actions executed"
            )
            return report

        except Exception as e:
            logger.error(f"Error in automated recovery cycle: {e}")
            return {
                "status": "error",
                "error": str(e),
                "started_at": start_time.isoformat(),
                "failed_at": now_sao_paulo().isoformat(),
            }

    async def _execute_recovery_plan(
        self, recovery_plan: List[RecoveryAction]
    ) -> List[RecoveryOperation]:
        """Execute recovery plan actions."""
        results = []

        action_map = {
            RecoveryAction.RESTART_FAILED_FLOWS: self._actions.restart_failed_flows,
            RecoveryAction.CLEAR_STUCK_QUEUES: self._actions.clear_stuck_queues,
            RecoveryAction.RESET_CORRUPTED_STATES: self._actions.reset_corrupted_states,
            RecoveryAction.CLEANUP_ORPHANED_DATA: self._actions.cleanup_orphaned_data,
            RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS: self._actions.refresh_external_connections,
            RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE: self._actions.optimize_database_performance,
            RecoveryAction.CLEAR_MEMORY_PRESSURE: self._actions.clear_memory_pressure,
            RecoveryAction.REBALANCE_LOAD: self._actions.rebalance_load,
        }

        for action in recovery_plan:
            try:
                logger.info(f"Executing recovery action: {action.value}")
                start_time = now_sao_paulo()

                handler = action_map.get(action)
                if handler:
                    result = await handler()
                else:
                    result = RecoveryOperation(
                        action=action,
                        result=RecoveryResult.SKIPPED,
                        description="Unknown recovery action",
                        items_processed=0,
                        items_recovered=0,
                        execution_time=0,
                    )

                result.execution_time = (
                    now_sao_paulo() - start_time
                ).total_seconds()
                results.append(result)

                if result.result == RecoveryResult.SUCCESS:
                    logger.info(
                        f"Recovery action {action.value} completed: "
                        f"{result.description}"
                    )
                elif result.result == RecoveryResult.PARTIAL_SUCCESS:
                    logger.warning(
                        f"Recovery action {action.value} partial: "
                        f"{result.description}"
                    )
                else:
                    logger.error(
                        f"Recovery action {action.value} failed: "
                        f"{result.error_message}"
                    )

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(
                    f"Error executing recovery action {action.value}: {e}"
                )
                results.append(
                    RecoveryOperation(
                        action=action,
                        result=RecoveryResult.FAILED,
                        description=f"Execution failed with error: {str(e)}",
                        items_processed=0,
                        items_recovered=0,
                        execution_time=0,
                        error_message=str(e),
                    )
                )

        return results

    # Recovery cooldown management
    async def _is_in_recovery_cooldown(self) -> bool:
        """Check if recovery is in cooldown period."""
        try:
            last_recovery = self.redis.get("last_recovery_time")
            if last_recovery:
                last_recovery_time = datetime.fromisoformat(last_recovery.decode())
                cooldown_end = last_recovery_time + timedelta(
                    minutes=self.recovery_config["recovery_cooldown_minutes"]
                )
                return now_sao_paulo() < cooldown_end
            return False
        except Exception:
            return False

    async def _set_recovery_cooldown(self) -> None:
        """Set recovery cooldown."""
        try:
            self.redis.setex(
                "last_recovery_time",
                self.recovery_config["recovery_cooldown_minutes"] * 60,
                now_sao_paulo().isoformat(),
            )
        except Exception as e:
            logger.error(f"Error setting recovery cooldown: {e}")

    async def _get_next_recovery_time(self) -> Optional[str]:
        """Get next allowed recovery time."""
        try:
            last_recovery = self.redis.get("last_recovery_time")
            if last_recovery:
                last_recovery_time = datetime.fromisoformat(last_recovery.decode())
                next_recovery = last_recovery_time + timedelta(
                    minutes=self.recovery_config["recovery_cooldown_minutes"]
                )
                return next_recovery.isoformat()
            return None
        except Exception:
            return None
