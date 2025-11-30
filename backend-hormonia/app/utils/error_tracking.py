"""
Error tracking and alerting utilities.
"""
import logging
import traceback
from datetime import datetime, timedelta
from typing import Any, Optional, List
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum

from app.utils.logging import get_logger, log_security_event
from app.config import settings


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorEvent:
    """Represents an error event for tracking."""
    error_type: str
    message: str
    timestamp: datetime
    severity: ErrorSeverity
    context: dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    count: int = 1


class ErrorTracker:
    """In-memory error tracking and alerting system."""
    
    def __init__(self, max_events: int = 1000, alert_threshold: int = 5, 
                 alert_window_minutes: int = 5):
        self.max_events = max_events
        self.alert_threshold = alert_threshold
        self.alert_window = timedelta(minutes=alert_window_minutes)
        
        # Store recent errors
        self.recent_errors: deque = deque(maxlen=max_events)
        
        # Track error counts by type
        self.error_counts: dict[str, int] = defaultdict(int)
        
        # Track when we last alerted for each error type
        self.last_alert_time: dict[str, datetime] = {}
        
        # Logger for error tracking
        self.logger = get_logger(__name__)
    
    def track_error(self, error: Exception, context: Optional[dict[str, Any]] = None,
                   request_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
        """Track an error event."""
        error_type = type(error).__name__
        severity = self._determine_severity(error)
        
        # Create error event
        error_event = ErrorEvent(
            error_type=error_type,
            message=str(error),
            timestamp=datetime.utcnow(),
            severity=severity,
            context=context or {},
            stack_trace=traceback.format_exc(),
            request_id=request_id,
            user_id=user_id
        )
        
        # Check if this is a duplicate recent error
        duplicate_event = self._find_duplicate_error(error_event)
        if duplicate_event:
            duplicate_event.count += 1
            duplicate_event.timestamp = error_event.timestamp
        else:
            self.recent_errors.append(error_event)
        
        # Update error counts
        self.error_counts[error_type] += 1
        
        # Log the error
        self._log_error_event(error_event)
        
        # Check if we should send an alert
        self._check_alert_conditions(error_event)
    
    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """Determine error severity based on error type."""
        error_type = type(error).__name__
        
        # Critical errors
        critical_errors = {
            'DatabaseError', 'ConnectionError', 'TimeoutError',
            'OutOfMemoryError', 'SystemExit', 'KeyboardInterrupt'
        }
        
        # High severity errors
        high_errors = {
            'ValueError', 'TypeError', 'AttributeError', 'KeyError',
            'IndexError', 'ImportError', 'ModuleNotFoundError'
        }
        
        # Medium severity errors
        medium_errors = {
            'HTTPException', 'ValidationError', 'PermissionError',
            'FileNotFoundError', 'IOError'
        }
        
        if error_type in critical_errors:
            return ErrorSeverity.CRITICAL
        elif error_type in high_errors:
            return ErrorSeverity.HIGH
        elif error_type in medium_errors:
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    def _find_duplicate_error(self, error_event: ErrorEvent) -> Optional[ErrorEvent]:
        """Find if this error is a duplicate of a recent error."""
        for existing_error in reversed(self.recent_errors):
            if (existing_error.error_type == error_event.error_type and
                existing_error.message == error_event.message and
                (error_event.timestamp - existing_error.timestamp) < timedelta(minutes=1)):
                return existing_error
        return None
    
    def _log_error_event(self, error_event: ErrorEvent) -> None:
        """Log the error event with structured data."""
        log_level = logging.ERROR
        if error_event.severity == ErrorSeverity.CRITICAL:
            log_level = logging.CRITICAL
        elif error_event.severity == ErrorSeverity.HIGH:
            log_level = logging.ERROR
        elif error_event.severity == ErrorSeverity.MEDIUM:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        self.logger.log(
            log_level,
            f"Error tracked: {error_event.error_type} - {error_event.message}",
            extra={
                'event_type': 'error_tracked',
                'error_type': error_event.error_type,
                'error_message': error_event.message,
                'severity': error_event.severity.value,
                'context': error_event.context,
                'stack_trace': error_event.stack_trace,
                'request_id': error_event.request_id,
                'user_id': error_event.user_id,
                'error_count': error_event.count,
                'timestamp': error_event.timestamp.isoformat()
            }
        )
    
    def _check_alert_conditions(self, error_event: ErrorEvent) -> None:
        """Check if alert conditions are met and send alerts."""
        error_type = error_event.error_type
        now = datetime.utcnow()
        
        # Check if we've exceeded the alert threshold
        recent_errors_of_type = [
            e for e in self.recent_errors
            if e.error_type == error_type and (now - e.timestamp) <= self.alert_window
        ]
        
        total_count = sum(e.count for e in recent_errors_of_type)
        
        # Check if we should alert
        should_alert = (
            total_count >= self.alert_threshold and
            (error_type not in self.last_alert_time or
             (now - self.last_alert_time[error_type]) > self.alert_window)
        )
        
        if should_alert:
            self._send_alert(error_event, total_count)
            self.last_alert_time[error_type] = now
    
    def _send_alert(self, error_event: ErrorEvent, count: int) -> None:
        """Send an alert for the error."""
        alert_message = (
            f"Error Alert: {error_event.error_type} occurred {count} times "
            f"in the last {self.alert_window.total_seconds() / 60:.0f} minutes"
        )
        
        # Log the alert
        self.logger.critical(
            alert_message,
            extra={
                'event_type': 'error_alert',
                'error_type': error_event.error_type,
                'error_count': count,
                'severity': error_event.severity.value,
                'alert_threshold': self.alert_threshold,
                'time_window_minutes': self.alert_window.total_seconds() / 60,
                'recent_error_message': error_event.message,
                'context': error_event.context
            }
        )
        
        # In a real implementation, you would send notifications here
        # (email, Slack, PagerDuty, etc.)
        self._send_notification(alert_message, error_event, count)
    
    def _send_notification(self, message: str, error_event: ErrorEvent, count: int) -> None:
        """Send notification to external systems."""
        # This is where you would integrate with notification systems
        # For now, we'll just log it
        
        notification_data = {
            'alert_type': 'error_threshold_exceeded',
            'message': message,
            'error_type': error_event.error_type,
            'severity': error_event.severity.value,
            'count': count,
            'environment': settings.APP_ENVIRONMENT,
            'service': 'hormonia-backend'
        }
        
        self.logger.info(
            "Notification sent",
            extra={
                'event_type': 'notification_sent',
                'notification_type': 'error_alert',
                'data': notification_data
            }
        )
    
    def get_error_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get error summary for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        recent_errors = [
            e for e in self.recent_errors
            if e.timestamp >= cutoff_time
        ]
        
        # Group by error type
        error_summary = defaultdict(lambda: {
            'count': 0,
            'severity': ErrorSeverity.LOW,
            'last_occurrence': None,
            'messages': set()
        })
        
        for error in recent_errors:
            summary = error_summary[error.error_type]
            summary['count'] += error.count
            
            # Update severity to highest seen
            if error.severity.value > summary['severity'].value:
                summary['severity'] = error.severity
            
            # Update last occurrence
            if (summary['last_occurrence'] is None or 
                error.timestamp > summary['last_occurrence']):
                summary['last_occurrence'] = error.timestamp
            
            summary['messages'].add(error.message)
        
        # Convert to serializable format
        result = {}
        for error_type, summary in error_summary.items():
            result[error_type] = {
                'count': summary['count'],
                'severity': summary['severity'].value,
                'last_occurrence': summary['last_occurrence'].isoformat() if summary['last_occurrence'] else None,
                'unique_messages': len(summary['messages']),
                'sample_messages': list(summary['messages'])[:3]  # First 3 unique messages
            }
        
        return {
            'time_period_hours': hours,
            'total_errors': len(recent_errors),
            'unique_error_types': len(result),
            'errors_by_type': result,
            'summary_generated_at': datetime.utcnow().isoformat()
        }
    
    def clear_old_errors(self, hours: int = 24) -> int:
        """Clear errors older than specified hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        original_count = len(self.recent_errors)
        
        # Filter out old errors
        self.recent_errors = deque(
            [e for e in self.recent_errors if e.timestamp >= cutoff_time],
            maxlen=self.max_events
        )
        
        cleared_count = original_count - len(self.recent_errors)
        
        if cleared_count > 0:
            self.logger.info(
                f"Cleared {cleared_count} old error events",
                extra={
                    'event_type': 'error_cleanup',
                    'cleared_count': cleared_count,
                    'remaining_count': len(self.recent_errors),
                    'cutoff_hours': hours
                }
            )
        
        return cleared_count


# Global error tracker instance
error_tracker = ErrorTracker()


def track_error(error: Exception, context: Optional[dict[str, Any]] = None,
               request_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """Convenience function to track an error."""
    error_tracker.track_error(error, context, request_id, user_id)


def get_error_summary(hours: int = 24) -> dict[str, Any]:
    """Get error summary for the specified time period."""
    return error_tracker.get_error_summary(hours)


def clear_old_errors(hours: int = 24) -> int:
    """Clear old errors."""
    return error_tracker.clear_old_errors(hours)