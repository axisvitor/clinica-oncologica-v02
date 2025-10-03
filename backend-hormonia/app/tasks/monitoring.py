"""Celery tasks for monitoring and automated recovery."""
import logging
from datetime import datetime
from typing import Dict, Any

from celery import current_app as celery_app
from celery.schedules import crontab
from sqlalchemy.orm import Session

from app.tasks.base import MonitoringTask, get_db_session
from app.dependencies import get_redis
from app.services.flow_monitoring import FlowMonitoringService
from app.services.critical_error_escalation import CriticalErrorEscalationService
from app.services.performance_monitoring import PerformanceMonitoringService
from app.services.automated_recovery import AutomatedRecoveryService
from app.repositories.flow import FlowStateRepository
from app.services.data_corruption_detector import DataCorruptionDetector
from app.services.error_recovery import ErrorRecoveryService
from app.services.manual_correction import ManualCorrectionService
from app.services.websocket_events import WebSocketEventService

logger = logging.getLogger(__name__)


class SystemHealthCheckTask(MonitoringTask):
    """Task for performing system health checks."""
    
    def run(self) -> Dict[str, Any]:
        """Periodic system health check task.
        
        Performs comprehensive health checks on the system including database,
        Redis, and flow monitoring services.
        
        Returns:
            dict: Dictionary containing:
                - success (bool): Whether the health check completed successfully
                - health_status (str): Overall system health status
                - timestamp (str): ISO timestamp of the check
                - error (str): Error message (if failed)
                
        Raises:
            Exception: If health check operations fail
        """
        self.log_task_start("Starting system health check")
        
        try:
            with get_db_session() as db:
                redis = get_redis()
        
                # Initialize services
                flow_repo = FlowStateRepository(db)
                corruption_detector = DataCorruptionDetector(db, redis)
                
                monitoring_service = FlowMonitoringService(
                    db=db,
                    redis=redis,
                    flow_repository=flow_repo,
                    corruption_detector=corruption_detector
                )
                
                # Run health checks
                health_status = monitoring_service.get_system_health()
                
                # Store health status
                health_key = f"system_health:{datetime.utcnow().strftime('%Y-%m-%d-%H-%M')}"
                redis.setex(health_key, 3600, str(health_status))  # Keep for 1 hour
                
                result = self.create_success_result({
                    'health_status': health_status.get('status', 'unknown'),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                self.log_task_success(f"System health check completed: {health_status.get('status', 'unknown')}")
                return result
                
        except Exception as e:
            self.log_task_error(f"Error in system health check: {e}")
            return self.create_error_result(str(e))


class PerformanceMetricsCollectionTask(MonitoringTask):
    """Task for collecting performance metrics."""
    
    def run(self) -> Dict[str, Any]:
        """Periodic performance metrics collection task.
        
        Collects system performance metrics including response times,
        throughput, and resource utilization.
        
        Returns:
            dict: Dictionary containing:
                - success (bool): Whether metrics collection completed successfully
                - metrics_collected (int): Number of metrics collected
                - timestamp (str): ISO timestamp of the collection
                - error (str): Error message (if failed)
                
        Raises:
            Exception: If metrics collection fails
        """
        self.log_task_start("Starting performance metrics collection")
        
        try:
            with get_db_session() as db:
                redis = get_redis()
                
                # Initialize services
                flow_repo = FlowStateRepository(db)
                performance_service = PerformanceMonitoringService(
                    db=db,
                    redis=redis,
                    flow_repository=flow_repo
                )
                
                # Collect metrics
                metrics = performance_service.collect_performance_metrics()
                
                result = self.create_success_result({
                    'metrics_collected': len(metrics),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                self.log_task_success(f"Collected {len(metrics)} performance metrics")
                return result
                
        except Exception as e:
            self.log_task_error(f"Error collecting performance metrics: {e}")
            return self.create_error_result(str(e))


class BottleneckDetectionTask(MonitoringTask):
    """Task for detecting system bottlenecks."""
    
    def run(self) -> Dict[str, Any]:
        """Periodic bottleneck detection task.
        
        Analyzes system performance to identify bottlenecks and performance issues.
        Logs critical bottlenecks for immediate attention.
        
        Returns:
            dict: Dictionary containing:
                - success (bool): Whether detection completed successfully
                - bottlenecks_detected (int): Total number of bottlenecks found
                - critical_bottlenecks (int): Number of critical bottlenecks
                - timestamp (str): ISO timestamp of the detection
                - error (str): Error message (if failed)
                
        Raises:
            Exception: If bottleneck detection fails
        """
        self.log_task_start("Starting bottleneck detection")
        
        try:
            with get_db_session() as db:
                redis = get_redis()
                
                # Initialize services
                flow_repo = FlowStateRepository(db)
                performance_service = PerformanceMonitoringService(
                    db=db,
                    redis=redis,
                    flow_repository=flow_repo
                )
                
                # Detect bottlenecks
                bottlenecks = performance_service.detect_bottlenecks()
                
                # Log critical bottlenecks
                critical_bottlenecks = [b for b in bottlenecks if b.severity == 'critical']
                if critical_bottlenecks:
                    self.get_task_logger().warning(f"Detected {len(critical_bottlenecks)} critical bottlenecks")
                    for bottleneck in critical_bottlenecks:
                        self.get_task_logger().warning(f"Critical bottleneck: {bottleneck.description}")
                
                result = self.create_success_result({
                    'bottlenecks_detected': len(bottlenecks),
                    'critical_bottlenecks': len(critical_bottlenecks),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                self.log_task_success(f"Bottleneck detection completed: {len(bottlenecks)} bottlenecks found")
                return result
                
        except Exception as e:
             self.log_task_error(f"Error in bottleneck detection: {e}")
             return self.create_error_result(str(e))


class AlertMonitoringTask(MonitoringTask):
    """Task for monitoring and creating alerts."""
    
    def run(self) -> Dict[str, Any]:
        """Periodic alert monitoring and creation task.
        
        Monitors system conditions and creates alerts when thresholds are exceeded.
        Critical alerts are logged immediately for urgent attention.
        
        Returns:
            dict: Dictionary containing:
                - success (bool): Whether monitoring completed successfully
                - alerts_created (int): Number of alerts created
                - critical_alerts (int): Number of critical alerts created
                - timestamp (str): ISO timestamp of the monitoring
                - error (str): Error message (if failed)
                
        Raises:
            Exception: If alert monitoring fails
        """
        self.log_task_start("Starting alert monitoring")
        
        try:
            with get_db_session() as db:
                redis = get_redis()
                
                # Initialize services
                flow_repo = FlowStateRepository(db)
                corruption_detector = DataCorruptionDetector(db, redis)
                
                monitoring_service = FlowMonitoringService(
                    db=db,
                    redis=redis,
                    flow_repository=flow_repo,
                    corruption_detector=corruption_detector
                )
                
                # Check and create alerts
                alerts = monitoring_service.check_and_create_alerts()
                
                # Log critical alerts
                critical_alerts = [a for a in alerts if a.severity.value == 'critical']
                if critical_alerts:
                    self.get_task_logger().critical(f"Created {len(critical_alerts)} critical alerts")
                    for alert in critical_alerts:
                        self.get_task_logger().critical(f"Critical alert: {alert.title} - {alert.message}")
                
                result = self.create_success_result({
                    'alerts_created': len(alerts),
                    'critical_alerts': len(critical_alerts),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                self.log_task_success(f"Alert monitoring completed: {len(alerts)} alerts created")
                return result
                
        except Exception as e:
            self.log_task_error(f"Error in alert monitoring: {e}")
            return self.create_error_result(str(e))


class EscalationCheckTask(MonitoringTask):
    """Task for checking and processing alert escalations."""
    
    def run(self) -> Dict[str, Any]:
        """Periodic escalation check task.
        
        Checks for alerts that need escalation based on time thresholds
        and escalates them to higher priority levels or notification channels.
        
        Returns:
            dict: Dictionary containing:
                - success (bool): Whether escalation check completed successfully
                - escalations_processed (int): Number of escalations processed
                - timestamp (str): ISO timestamp of the check
                - error (str): Error message (if failed)
                
        Raises:
            Exception: If escalation check fails
        """
        self.log_task_start("Starting escalation check")
        
        try:
            with get_db_session() as db:
                # Initialize escalation service
                escalation_service = AlertEscalationService(db)
                
                # Process escalations
                escalations = escalation_service.process_escalations()
                
                result = self.create_success_result({
                    'escalations_processed': len(escalations),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                self.log_task_success(f"Escalation check completed: {len(escalations)} escalations processed")
                return result
                
        except Exception as e:
            self.log_task_error(f"Error in escalation check: {e}")
            return self.create_error_result(str(e))


class AutomatedRecoveryTask(MonitoringTask):
    """Task for automated system recovery procedures."""
    
    def run(self) -> Dict[str, Any]:
        """Periodic automated recovery task.
        
        Runs automated recovery procedures to fix detected issues and restore
        system functionality without manual intervention.
        
        Returns:
            dict: Dictionary containing:
                - success (bool): Whether recovery cycle completed successfully
                - recovery_results (dict): Detailed recovery operation results
                - timestamp (str): ISO timestamp of the recovery cycle
                - error (str): Error message (if failed)
                
        Raises:
            Exception: If automated recovery fails
        """
        self.log_task_start("Starting automated recovery cycle")
        
        try:
            with get_db_session() as db:
                redis = get_redis()
                
                # Initialize services
                flow_repo = FlowStateRepository(db)
                corruption_detector = DataCorruptionDetector(db, redis)
                websocket_service = WebSocketEventService(redis)
                
                monitoring_service = FlowMonitoringService(
                    db=db,
                    redis=redis,
                    flow_repository=flow_repo,
                    corruption_detector=corruption_detector
                )
                
                error_recovery_service = ErrorRecoveryService(db, redis)
                manual_correction_service = ManualCorrectionService(db, redis, flow_repo)
                
                recovery_service = AutomatedRecoveryService(
                    db=db,
                    redis=redis,
                    monitoring_service=monitoring_service,
                    error_recovery_service=error_recovery_service,
                    corruption_detector=corruption_detector,
                    manual_correction_service=manual_correction_service,
                    flow_repository=flow_repo
                )
                
                # Run automated recovery cycle
                recovery_results = recovery_service.run_automated_recovery_cycle()
                
                successful_recoveries = recovery_results.get('recoveries_successful', 0)
                failed_recoveries = recovery_results.get('recoveries_failed', 0)
                
                if successful_recoveries > 0:
                    self.get_task_logger().info(f"Automated recovery completed: {successful_recoveries} successful recoveries")
                
                if failed_recoveries > 0:
                    self.get_task_logger().warning(f"Automated recovery had {failed_recoveries} failed recovery attempts")
                
                result = self.create_success_result({
                    'recovery_results': recovery_results,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                self.log_task_success(f"Automated recovery cycle completed: {successful_recoveries} successful, {failed_recoveries} failed")
                return result
                
        except Exception as e:
            self.log_task_error(f"Error in automated recovery: {e}")
            return self.create_error_result(str(e))


class CleanupOldMonitoringDataTask(MonitoringTask):
    """Task for cleaning up old monitoring data."""
    
    def run(self) -> Dict[str, Any]:
        """Cleanup old monitoring data task.
        
        Removes expired monitoring data from Redis to maintain optimal performance
        and prevent storage bloat.
        
        Returns:
            dict: Dictionary containing:
                - success (bool): Whether cleanup completed successfully
                - keys_deleted (int): Number of Redis keys deleted
                - total_keys_checked (int): Total number of keys examined
                - timestamp (str): ISO timestamp of the cleanup
                - error (str): Error message (if failed)
                
        Raises:
            Exception: If cleanup operations fail
        """
        self.log_task_start("Starting monitoring data cleanup")
        
        try:
            # Get Redis connection
            redis = get_redis()
            
            # Cleanup old metrics
            old_metric_keys = redis.keys("metrics:*")
            old_alert_keys = redis.keys("alert:*")
            old_escalation_keys = redis.keys("escalation:*")
            old_bottleneck_keys = redis.keys("bottleneck:*")
            
            # Count keys to delete
            total_keys = len(old_metric_keys) + len(old_alert_keys) + len(old_escalation_keys) + len(old_bottleneck_keys)
            
            # Delete old keys (Redis will handle TTL, but we can force cleanup)
            deleted_count = 0
            
            # This is a simplified cleanup - in production, you'd check TTL and age
            for key_list in [old_metric_keys, old_alert_keys, old_escalation_keys, old_bottleneck_keys]:
                for key in key_list:
                    ttl = redis.ttl(key)
                    if ttl < 3600:  # Less than 1 hour remaining
                        redis.delete(key)
                        deleted_count += 1
            
            result = self.create_success_result({
                'keys_deleted': deleted_count,
                'total_keys_checked': total_keys,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            self.log_task_success(f"Monitoring data cleanup completed: {deleted_count} keys deleted out of {total_keys}")
            return result
            
        except Exception as e:
            self.log_task_error(f"Error in monitoring data cleanup: {e}")
            return self.create_error_result(str(e))


# Create task instances for Celery registration
system_health_check_task = celery_app.task(bind=True, name="monitoring.system_health_check")(SystemHealthCheckTask().run)
performance_metrics_collection_task = celery_app.task(bind=True, name="monitoring.performance_metrics_collection")(PerformanceMetricsCollectionTask().run)
bottleneck_detection_task = celery_app.task(bind=True, name="monitoring.bottleneck_detection")(BottleneckDetectionTask().run)
alert_monitoring_task = celery_app.task(bind=True, name="monitoring.alert_monitoring")(AlertMonitoringTask().run)
escalation_check_task = celery_app.task(bind=True, name="monitoring.escalation_check")(EscalationCheckTask().run)
automated_recovery_task = celery_app.task(bind=True, name="monitoring.automated_recovery")(AutomatedRecoveryTask().run)
cleanup_old_monitoring_data_task = celery_app.task(bind=True, name="monitoring.cleanup_old_data")(CleanupOldMonitoringDataTask().run)

# Task schedules for periodic execution
MONITORING_TASK_SCHEDULES = {
    'system_health_check': {
        'task': 'monitoring.system_health_check',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'performance_metrics_collection': {
        'task': 'monitoring.performance_metrics_collection',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
    'bottleneck_detection': {
        'task': 'monitoring.bottleneck_detection',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'alert_monitoring': {
        'task': 'monitoring.alert_monitoring',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'escalation_check': {
        'task': 'monitoring.escalation_check',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'automated_recovery': {
        'task': 'monitoring.automated_recovery',
        'schedule': crontab(minute='*/60'),  # Every hour
    },
    'cleanup_old_monitoring_data': {
        'task': 'monitoring.cleanup_old_data',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}