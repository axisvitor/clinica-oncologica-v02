"""
Automated recovery service for handling system failures and data corruption.
Implements automated recovery mechanisms for common failure scenarios.
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import json

from redis import Redis

from app.services.flow_monitoring import FlowMonitoringService
from app.services.error_recovery import ErrorRecoveryService
from app.services.data_corruption_detector import DataCorruptionDetector
from app.services.manual_correction import ManualCorrectionService
from app.repositories.flow import FlowStateRepository

logger = logging.getLogger(__name__)


class RecoveryAction(Enum):
    RESTART_FAILED_FLOWS = "restart_failed_flows"
    CLEAR_STUCK_QUEUES = "clear_stuck_queues"
    RESET_CORRUPTED_STATES = "reset_corrupted_states"
    CLEANUP_ORPHANED_DATA = "cleanup_orphaned_data"
    REFRESH_EXTERNAL_CONNECTIONS = "refresh_external_connections"
    OPTIMIZE_DATABASE_PERFORMANCE = "optimize_database_performance"
    CLEAR_MEMORY_PRESSURE = "clear_memory_pressure"
    REBALANCE_LOAD = "rebalance_load"


class RecoveryResult(Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RecoveryOperation:
    """Recovery operation result."""
    action: RecoveryAction
    result: RecoveryResult
    description: str
    items_processed: int
    items_recovered: int
    execution_time: float
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AutomatedRecoveryService:
    """Service for automated system recovery and failure handling."""
    
    def __init__(self, db: Any, redis: Redis, 
                 monitoring_service: FlowMonitoringService,
                 error_recovery_service: ErrorRecoveryService,
                 corruption_detector: DataCorruptionDetector,
                 manual_correction_service: ManualCorrectionService,
                 flow_repository: FlowStateRepository):
        self.db = db
        self.redis = redis
        self.monitoring_service = monitoring_service
        self.error_recovery_service = error_recovery_service
        self.corruption_detector = corruption_detector
        self.manual_correction_service = manual_correction_service
        self.flow_repository = flow_repository
        
        # Recovery thresholds and configurations
        self.recovery_config = {
            'max_failed_flows_threshold': 10,
            'stuck_queue_threshold': 100,
            'corruption_rate_threshold': 0.05,  # 5%
            'memory_pressure_threshold': 0.9,  # 90%
            'max_recovery_attempts': 3,
            'recovery_cooldown_minutes': 30,
            'batch_size': 50
        }
        
        # Recovery action priorities (higher number = higher priority)
        self.action_priorities = {
            RecoveryAction.RESET_CORRUPTED_STATES: 10,
            RecoveryAction.RESTART_FAILED_FLOWS: 9,
            RecoveryAction.CLEAR_STUCK_QUEUES: 8,
            RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS: 7,
            RecoveryAction.CLEANUP_ORPHANED_DATA: 6,
            RecoveryAction.CLEAR_MEMORY_PRESSURE: 5,
            RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE: 4,
            RecoveryAction.REBALANCE_LOAD: 3
        }
    
    async def run_automated_recovery_cycle(self) -> Dict[str, Any]:
        """Run complete automated recovery cycle."""
        start_time = datetime.utcnow()
        
        try:
            logger.info("Starting automated recovery cycle")
            
            # Check if recovery is in cooldown
            if await self._is_in_recovery_cooldown():
                return {
                    'status': 'skipped',
                    'reason': 'Recovery is in cooldown period',
                    'next_allowed_at': await self._get_next_recovery_time()
                }
            
            # Assess system health and determine needed recovery actions
            recovery_plan = await self._assess_recovery_needs()
            
            if not recovery_plan:
                return {
                    'status': 'no_action_needed',
                    'message': 'System health is within acceptable parameters',
                    'assessed_at': start_time.isoformat()
                }
            
            # Execute recovery actions in priority order
            recovery_results = await self._execute_recovery_plan(recovery_plan)
            
            # Update recovery cooldown
            await self._set_recovery_cooldown()
            
            # Generate recovery report
            report = await self._generate_recovery_report(recovery_results, start_time)
            
            logger.info(f"Automated recovery cycle completed: {len(recovery_results)} actions executed")
            return report
            
        except Exception as e:
            logger.error(f"Error in automated recovery cycle: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'started_at': start_time.isoformat(),
                'failed_at': datetime.utcnow().isoformat()
            }
    
    async def _assess_recovery_needs(self) -> List[RecoveryAction]:
        """Assess system health and determine needed recovery actions."""
        recovery_actions = []
        
        try:
            # Get system health metrics
            health_status = await self.monitoring_service.get_system_health()
            
            # Check for corrupted flow states
            corruption_rate = await self._check_corruption_rate()
            if corruption_rate > self.recovery_config['corruption_rate_threshold']:
                recovery_actions.append(RecoveryAction.RESET_CORRUPTED_STATES)
                logger.warning(f"High corruption rate detected: {corruption_rate:.2%}")
            
            # Check for failed flows
            failed_flows_count = await self._count_failed_flows()
            if failed_flows_count > self.recovery_config['max_failed_flows_threshold']:
                recovery_actions.append(RecoveryAction.RESTART_FAILED_FLOWS)
                logger.warning(f"High number of failed flows: {failed_flows_count}")
            
            # Check for stuck queues
            stuck_queue_depth = await self._check_stuck_queues()
            if stuck_queue_depth > self.recovery_config['stuck_queue_threshold']:
                recovery_actions.append(RecoveryAction.CLEAR_STUCK_QUEUES)
                logger.warning(f"Stuck queue detected with depth: {stuck_queue_depth}")
            
            # Check for orphaned data
            orphaned_data_count = await self._count_orphaned_data()
            if orphaned_data_count > 0:
                recovery_actions.append(RecoveryAction.CLEANUP_ORPHANED_DATA)
                logger.info(f"Orphaned data detected: {orphaned_data_count} items")
            
            # Check memory pressure
            memory_usage = await self._check_memory_pressure()
            if memory_usage > self.recovery_config['memory_pressure_threshold']:
                recovery_actions.append(RecoveryAction.CLEAR_MEMORY_PRESSURE)
                logger.warning(f"High memory usage: {memory_usage:.1%}")
            
            # Check external connection health
            if await self._check_external_connection_issues():
                recovery_actions.append(RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS)
                logger.warning("External connection issues detected")
            
            # Check database performance
            if await self._check_database_performance_issues():
                recovery_actions.append(RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE)
                logger.warning("Database performance issues detected")
            
            # Sort by priority
            recovery_actions.sort(key=lambda x: self.action_priorities.get(x, 0), reverse=True)
            
            return recovery_actions
            
        except Exception as e:
            logger.error(f"Error assessing recovery needs: {e}")
            return []
    
    async def _execute_recovery_plan(self, recovery_plan: List[RecoveryAction]) -> List[RecoveryOperation]:
        """Execute recovery plan actions."""
        results = []
        
        for action in recovery_plan:
            try:
                logger.info(f"Executing recovery action: {action.value}")
                start_time = datetime.utcnow()
                
                # Execute the specific recovery action
                result = await self._execute_recovery_action(action)
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                result.execution_time = execution_time
                
                results.append(result)
                
                # Log result
                if result.result == RecoveryResult.SUCCESS:
                    logger.info(f"Recovery action {action.value} completed successfully: {result.description}")
                elif result.result == RecoveryResult.PARTIAL_SUCCESS:
                    logger.warning(f"Recovery action {action.value} partially successful: {result.description}")
                else:
                    logger.error(f"Recovery action {action.value} failed: {result.error_message}")
                
                # Small delay between actions to prevent system overload
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error executing recovery action {action.value}: {e}")
                results.append(RecoveryOperation(
                    action=action,
                    result=RecoveryResult.FAILED,
                    description=f"Execution failed with error: {str(e)}",
                    items_processed=0,
                    items_recovered=0,
                    execution_time=0,
                    error_message=str(e)
                ))
        
        return results
    
    async def _execute_recovery_action(self, action: RecoveryAction) -> RecoveryOperation:
        """Execute a specific recovery action."""
        if action == RecoveryAction.RESTART_FAILED_FLOWS:
            return await self._restart_failed_flows()
        elif action == RecoveryAction.CLEAR_STUCK_QUEUES:
            return await self._clear_stuck_queues()
        elif action == RecoveryAction.RESET_CORRUPTED_STATES:
            return await self._reset_corrupted_states()
        elif action == RecoveryAction.CLEANUP_ORPHANED_DATA:
            return await self._cleanup_orphaned_data()
        elif action == RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS:
            return await self._refresh_external_connections()
        elif action == RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE:
            return await self._optimize_database_performance()
        elif action == RecoveryAction.CLEAR_MEMORY_PRESSURE:
            return await self._clear_memory_pressure()
        elif action == RecoveryAction.REBALANCE_LOAD:
            return await self._rebalance_load()
        else:
            return RecoveryOperation(
                action=action,
                result=RecoveryResult.SKIPPED,
                description="Unknown recovery action",
                items_processed=0,
                items_recovered=0,
                execution_time=0
            )
    
    async def _restart_failed_flows(self) -> RecoveryOperation:
        """Restart failed flows."""
        try:
            # Get failed flows from error recovery service
            failed_flows = await self.error_recovery_service.get_failed_flows()
            
            recovered_count = 0
            for flow_id in failed_flows[:self.recovery_config['batch_size']]:
                try:
                    success = await self.error_recovery_service.recover_failed_flow(flow_id)
                    if success:
                        recovered_count += 1
                except Exception as e:
                    logger.error(f"Error recovering flow {flow_id}: {e}")
            
            result = RecoveryResult.SUCCESS if recovered_count == len(failed_flows) else RecoveryResult.PARTIAL_SUCCESS
            
            return RecoveryOperation(
                action=RecoveryAction.RESTART_FAILED_FLOWS,
                result=result,
                description=f"Restarted {recovered_count} out of {len(failed_flows)} failed flows",
                items_processed=len(failed_flows),
                items_recovered=recovered_count,
                execution_time=0
            )
            
        except Exception as e:
            return RecoveryOperation(
                action=RecoveryAction.RESTART_FAILED_FLOWS,
                result=RecoveryResult.FAILED,
                description="Failed to restart flows",
                items_processed=0,
                items_recovered=0,
                execution_time=0,
                error_message=str(e)
            )
    
    async def _clear_stuck_queues(self) -> RecoveryOperation:
        """Clear stuck message queues."""
        try:
            # This would integrate with your actual queue system
            # For now, simulate clearing stuck items
            stuck_items = await self._get_stuck_queue_items()
            cleared_count = 0
            
            for item in stuck_items:
                try:
                    # Clear or requeue the stuck item
                    await self._clear_queue_item(item)
                    cleared_count += 1
                except Exception as e:
                    logger.error(f"Error clearing queue item {item}: {e}")
            
            return RecoveryOperation(
                action=RecoveryAction.CLEAR_STUCK_QUEUES,
                result=RecoveryResult.SUCCESS if cleared_count > 0 else RecoveryResult.SKIPPED,
                description=f"Cleared {cleared_count} stuck queue items",
                items_processed=len(stuck_items),
                items_recovered=cleared_count,
                execution_time=0
            )
            
        except Exception as e:
            return RecoveryOperation(
                action=RecoveryAction.CLEAR_STUCK_QUEUES,
                result=RecoveryResult.FAILED,
                description="Failed to clear stuck queues",
                items_processed=0,
                items_recovered=0,
                execution_time=0,
                error_message=str(e)
            )
    
    async def _reset_corrupted_states(self) -> RecoveryOperation:
        """Reset corrupted flow states."""
        try:
            # Detect corrupted flows
            corruption_report = await self.corruption_detector.detect_bulk_corruption(
                self.recovery_config['batch_size']
            )
            
            corrected_count = 0
            for corrupted_flow in corruption_report:
                try:
                    success = await self.manual_correction_service.correct_flow_state(
                        corrupted_flow['flow_id']
                    )
                    if success:
                        corrected_count += 1
                except Exception as e:
                    logger.error(f"Error correcting flow {corrupted_flow['flow_id']}: {e}")
            
            return RecoveryOperation(
                action=RecoveryAction.RESET_CORRUPTED_STATES,
                result=RecoveryResult.SUCCESS if corrected_count > 0 else RecoveryResult.SKIPPED,
                description=f"Corrected {corrected_count} out of {len(corruption_report)} corrupted states",
                items_processed=len(corruption_report),
                items_recovered=corrected_count,
                execution_time=0
            )
            
        except Exception as e:
            return RecoveryOperation(
                action=RecoveryAction.RESET_CORRUPTED_STATES,
                result=RecoveryResult.FAILED,
                description="Failed to reset corrupted states",
                items_processed=0,
                items_recovered=0,
                execution_time=0,
                error_message=str(e)
            )
    
    async def _cleanup_orphaned_data(self) -> RecoveryOperation:
        """Clean up orphaned data."""
        try:
            # Find and clean orphaned data
            orphaned_items = await self._find_orphaned_data()
            cleaned_count = 0
            
            for item in orphaned_items:
                try:
                    await self._clean_orphaned_item(item)
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"Error cleaning orphaned item {item}: {e}")
            
            return RecoveryOperation(
                action=RecoveryAction.CLEANUP_ORPHANED_DATA,
                result=RecoveryResult.SUCCESS if cleaned_count > 0 else RecoveryResult.SKIPPED,
                description=f"Cleaned {cleaned_count} orphaned data items",
                items_processed=len(orphaned_items),
                items_recovered=cleaned_count,
                execution_time=0
            )
            
        except Exception as e:
            return RecoveryOperation(
                action=RecoveryAction.CLEANUP_ORPHANED_DATA,
                result=RecoveryResult.FAILED,
                description="Failed to cleanup orphaned data",
                items_processed=0,
                items_recovered=0,
                execution_time=0,
                error_message=str(e)
            )
    
    async def _refresh_external_connections(self) -> RecoveryOperation:
        """Refresh external service connections."""
        try:
            # Refresh connections to external services
            services_refreshed = 0
            
            # This would integrate with your actual external services
            external_services = ['whatsapp_api', 'gemini_api', 'database']
            
            for service in external_services:
                try:
                    await self._refresh_service_connection(service)
                    services_refreshed += 1
                except Exception as e:
                    logger.error(f"Error refreshing connection to {service}: {e}")
            
            return RecoveryOperation(
                action=RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS,
                result=RecoveryResult.SUCCESS if services_refreshed > 0 else RecoveryResult.FAILED,
                description=f"Refreshed {services_refreshed} external service connections",
                items_processed=len(external_services),
                items_recovered=services_refreshed,
                execution_time=0
            )
            
        except Exception as e:
            return RecoveryOperation(
                action=RecoveryAction.REFRESH_EXTERNAL_CONNECTIONS,
                result=RecoveryResult.FAILED,
                description="Failed to refresh external connections",
                items_processed=0,
                items_recovered=0,
                execution_time=0,
                error_message=str(e)
            )
    
    async def _optimize_database_performance(self) -> RecoveryOperation:
        """Optimize database performance."""
        try:
            optimizations_applied = 0
            
            # Run database maintenance tasks
            maintenance_tasks = [
                'analyze_tables',
                'update_statistics',
                'cleanup_temp_data'
            ]
            
            for task in maintenance_tasks:
                try:
                    await self._run_database_maintenance_task(task)
                    optimizations_applied += 1
                except Exception as e:
                    logger.error(f"Error running database task {task}: {e}")
            
            return RecoveryOperation(
                action=RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE,
                result=RecoveryResult.SUCCESS if optimizations_applied > 0 else RecoveryResult.FAILED,
                description=f"Applied {optimizations_applied} database optimizations",
                items_processed=len(maintenance_tasks),
                items_recovered=optimizations_applied,
                execution_time=0
            )
            
        except Exception as e:
            return RecoveryOperation(
                action=RecoveryAction.OPTIMIZE_DATABASE_PERFORMANCE,
                result=RecoveryResult.FAILED,
                description="Failed to optimize database performance",
                items_processed=0,
                items_recovered=0,
                execution_time=0,
                error_message=str(e)
            )
    
    async def _clear_memory_pressure(self) -> RecoveryOperation:
        """Clear memory pressure."""
        try:
            # Clear Redis memory pressure
            cleared_items = 0
            
            # Remove expired keys
            expired_keys = await self._find_expired_keys()
            for key in expired_keys:
                try:
                    await self.redis.delete(key)
                    cleared_items += 1
                except Exception as e:
                    logger.error(f"Error deleting expired key {key}: {e}")
            
            return RecoveryOperation(
                action=RecoveryAction.CLEAR_MEMORY_PRESSURE,
                result=RecoveryResult.SUCCESS if cleared_items > 0 else RecoveryResult.SKIPPED,
                description=f"Cleared {cleared_items} expired cache items",
                items_processed=len(expired_keys),
                items_recovered=cleared_items,
                execution_time=0
            )
            
        except Exception as e:
            return RecoveryOperation(
                action=RecoveryAction.CLEAR_MEMORY_PRESSURE,
                result=RecoveryResult.FAILED,
                description="Failed to clear memory pressure",
                items_processed=0,
                items_recovered=0,
                execution_time=0,
                error_message=str(e)
            )
    
    async def _rebalance_load(self) -> RecoveryOperation:
        """Rebalance system load."""
        try:
            # This would implement load rebalancing logic
            # For now, return a placeholder
            return RecoveryOperation(
                action=RecoveryAction.REBALANCE_LOAD,
                result=RecoveryResult.SKIPPED,
                description="Load rebalancing not implemented",
                items_processed=0,
                items_recovered=0,
                execution_time=0
            )
            
        except Exception as e:
            return RecoveryOperation(
                action=RecoveryAction.REBALANCE_LOAD,
                result=RecoveryResult.FAILED,
                description="Failed to rebalance load",
                items_processed=0,
                items_recovered=0,
                execution_time=0,
                error_message=str(e)
            )
    
    # Helper methods for assessment
    async def _check_corruption_rate(self) -> float:
        """Check current corruption rate."""
        try:
            total_flows = self.db.query(self.flow_repository.model).count()
            if total_flows == 0:
                return 0.0
            
            sample_size = min(100, total_flows)
            corruption_report = await self.corruption_detector.detect_bulk_corruption(sample_size)
            
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
            # This would check your actual queue system
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
            redis_info = await self.redis.info('memory')
            used_memory = redis_info.get('used_memory', 0)
            max_memory = redis_info.get('maxmemory', 0)
            
            if max_memory > 0:
                return used_memory / max_memory
            return 0.0
        except Exception as e:
            logger.error(f"Error checking memory pressure: {e}")
            return 0.0
    
    async def _check_external_connection_issues(self) -> bool:
        """Check for external connection issues."""
        try:
            # This would check actual external service health
            return False
        except Exception as e:
            logger.error(f"Error checking external connections: {e}")
            return False
    
    async def _check_database_performance_issues(self) -> bool:
        """Check for database performance issues."""
        try:
            # This would check actual database performance metrics
            return False
        except Exception as e:
            logger.error(f"Error checking database performance: {e}")
            return False
    
    # Helper methods for recovery actions
    async def _get_stuck_queue_items(self) -> List[str]:
        """Get stuck queue items."""
        return []
    
    async def _clear_queue_item(self, item: str) -> None:
        """Clear a stuck queue item."""
        pass
    
    async def _find_orphaned_data(self) -> List[str]:
        """Find orphaned data items."""
        return []
    
    async def _clean_orphaned_item(self, item: str) -> None:
        """Clean an orphaned data item."""
        pass
    
    async def _refresh_service_connection(self, service: str) -> None:
        """Refresh connection to external service."""
        pass
    
    async def _run_database_maintenance_task(self, task: str) -> None:
        """Run database maintenance task."""
        pass
    
    async def _find_expired_keys(self) -> List[str]:
        """Find expired Redis keys."""
        return []
    
    # Recovery management methods
    async def _is_in_recovery_cooldown(self) -> bool:
        """Check if recovery is in cooldown period."""
        try:
            last_recovery = await self.redis.get("last_recovery_time")
            if last_recovery:
                last_recovery_time = datetime.fromisoformat(last_recovery.decode())
                cooldown_end = last_recovery_time + timedelta(minutes=self.recovery_config['recovery_cooldown_minutes'])
                return datetime.utcnow() < cooldown_end
            return False
        except Exception:
            return False
    
    async def _set_recovery_cooldown(self) -> None:
        """Set recovery cooldown."""
        try:
            await self.redis.setex(
                "last_recovery_time",
                self.recovery_config['recovery_cooldown_minutes'] * 60,
                datetime.utcnow().isoformat()
            )
        except Exception as e:
            logger.error(f"Error setting recovery cooldown: {e}")
    
    async def _get_next_recovery_time(self) -> Optional[str]:
        """Get next allowed recovery time."""
        try:
            last_recovery = await self.redis.get("last_recovery_time")
            if last_recovery:
                last_recovery_time = datetime.fromisoformat(last_recovery.decode())
                next_recovery = last_recovery_time + timedelta(minutes=self.recovery_config['recovery_cooldown_minutes'])
                return next_recovery.isoformat()
            return None
        except Exception:
            return None
    
    async def _generate_recovery_report(self, recovery_results: List[RecoveryOperation], start_time: datetime) -> Dict[str, Any]:
        """Generate recovery report."""
        end_time = datetime.utcnow()
        total_execution_time = (end_time - start_time).total_seconds()
        
        successful_actions = [r for r in recovery_results if r.result == RecoveryResult.SUCCESS]
        failed_actions = [r for r in recovery_results if r.result == RecoveryResult.FAILED]
        partial_actions = [r for r in recovery_results if r.result == RecoveryResult.PARTIAL_SUCCESS]
        
        total_items_processed = sum(r.items_processed for r in recovery_results)
        total_items_recovered = sum(r.items_recovered for r in recovery_results)
        
        return {
            'status': 'completed',
            'started_at': start_time.isoformat(),
            'completed_at': end_time.isoformat(),
            'total_execution_time': total_execution_time,
            'summary': {
                'total_actions': len(recovery_results),
                'successful_actions': len(successful_actions),
                'failed_actions': len(failed_actions),
                'partial_success_actions': len(partial_actions),
                'total_items_processed': total_items_processed,
                'total_items_recovered': total_items_recovered,
                'recovery_rate': (total_items_recovered / max(total_items_processed, 1)) * 100
            },
            'actions': [
                {
                    'action': r.action.value,
                    'result': r.result.value,
                    'description': r.description,
                    'items_processed': r.items_processed,
                    'items_recovered': r.items_recovered,
                    'execution_time': r.execution_time,
                    'error_message': r.error_message,
                    'metadata': r.metadata
                }
                for r in recovery_results
            ],
            'next_recovery_allowed_at': await self._get_next_recovery_time()
        }
