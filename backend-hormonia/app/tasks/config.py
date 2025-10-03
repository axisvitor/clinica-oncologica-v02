"""Configuration settings for Celery tasks."""

from typing import Dict, Any
import os
from dataclasses import dataclass


@dataclass
class TaskConfig:
    """Base configuration for tasks."""
    max_retries: int = 3
    default_retry_delay: int = 60
    retry_backoff: bool = True
    retry_jitter: bool = True
    task_time_limit: int = 300  # 5 minutes
    task_soft_time_limit: int = 240  # 4 minutes


@dataclass
class MessagingTaskConfig(TaskConfig):
    """Configuration for messaging tasks."""
    max_retries: int = 5
    default_retry_delay: int = 30
    batch_size: int = 50
    rate_limit: str = "100/m"  # 100 messages per minute
    priority: int = 5


@dataclass
class AlertTaskConfig(TaskConfig):
    """Configuration for alert tasks."""
    max_retries: int = 3
    default_retry_delay: int = 60
    escalation_delay: int = 300  # 5 minutes
    priority: int = 8  # High priority
    task_time_limit: int = 120  # 2 minutes


@dataclass
class MonitoringTaskConfig(TaskConfig):
    """Configuration for monitoring tasks."""
    max_retries: int = 2
    default_retry_delay: int = 120
    check_interval: int = 300  # 5 minutes
    cleanup_interval: int = 3600  # 1 hour
    data_retention_days: int = 30
    priority: int = 5


@dataclass
class QuizTaskConfig(TaskConfig):
    """Configuration for quiz flow tasks."""
    max_retries: int = 3
    default_retry_delay: int = 60
    session_timeout_hours: int = 48
    progress_update_threshold: int = 3  # Send progress after 3 questions
    priority: int = 6


@dataclass
class FlowTaskConfig(TaskConfig):
    """Configuration for flow management tasks."""
    max_retries: int = 3
    default_retry_delay: int = 90
    step_timeout_minutes: int = 30
    flow_timeout_hours: int = 72
    priority: int = 7


@dataclass
class ReportTaskConfig(TaskConfig):
    """Configuration for report generation tasks."""
    max_retries: int = 2
    default_retry_delay: int = 180
    task_time_limit: int = 600  # 10 minutes
    task_soft_time_limit: int = 540  # 9 minutes
    batch_size: int = 20
    priority: int = 4


class TaskConfigurations:
    """Central configuration manager for all task types."""
    
    def __init__(self):
        self.messaging = MessagingTaskConfig()
        self.alerts = AlertTaskConfig()
        self.monitoring = MonitoringTaskConfig()
        self.quiz = QuizTaskConfig()
        self.flows = FlowTaskConfig()
        self.reports = ReportTaskConfig()
        self.base = TaskConfig()
    
    def get_config(self, task_type: str) -> TaskConfig:
        """Get configuration for specific task type.
        
        Args:
            task_type: Type of task (messaging, alerts, monitoring, etc.)
            
        Returns:
            TaskConfig instance for the specified type
        """
        config_map = {
            'messaging': self.messaging,
            'alerts': self.alerts,
            'monitoring': self.monitoring,
            'quiz': self.quiz,
            'flows': self.flows,
            'reports': self.reports,
            'base': self.base
        }
        
        return config_map.get(task_type, self.base)
    
    def update_from_env(self):
        """Update configurations from environment variables."""
        # Messaging config
        if os.getenv('MESSAGING_MAX_RETRIES'):
            self.messaging.max_retries = int(os.getenv('MESSAGING_MAX_RETRIES'))
        if os.getenv('MESSAGING_RETRY_DELAY'):
            self.messaging.default_retry_delay = int(os.getenv('MESSAGING_RETRY_DELAY'))
        if os.getenv('MESSAGING_BATCH_SIZE'):
            self.messaging.batch_size = int(os.getenv('MESSAGING_BATCH_SIZE'))
        if os.getenv('MESSAGING_RATE_LIMIT'):
            self.messaging.rate_limit = os.getenv('MESSAGING_RATE_LIMIT')
        
        # Alert config
        if os.getenv('ALERT_MAX_RETRIES'):
            self.alerts.max_retries = int(os.getenv('ALERT_MAX_RETRIES'))
        if os.getenv('ALERT_ESCALATION_DELAY'):
            self.alerts.escalation_delay = int(os.getenv('ALERT_ESCALATION_DELAY'))
        
        # Monitoring config
        if os.getenv('MONITORING_CHECK_INTERVAL'):
            self.monitoring.check_interval = int(os.getenv('MONITORING_CHECK_INTERVAL'))
        if os.getenv('MONITORING_CLEANUP_INTERVAL'):
            self.monitoring.cleanup_interval = int(os.getenv('MONITORING_CLEANUP_INTERVAL'))
        if os.getenv('MONITORING_DATA_RETENTION_DAYS'):
            self.monitoring.data_retention_days = int(os.getenv('MONITORING_DATA_RETENTION_DAYS'))
        
        # Quiz config
        if os.getenv('QUIZ_SESSION_TIMEOUT_HOURS'):
            self.quiz.session_timeout_hours = int(os.getenv('QUIZ_SESSION_TIMEOUT_HOURS'))
        if os.getenv('QUIZ_PROGRESS_THRESHOLD'):
            self.quiz.progress_update_threshold = int(os.getenv('QUIZ_PROGRESS_THRESHOLD'))
        
        # Flow config
        if os.getenv('FLOW_STEP_TIMEOUT_MINUTES'):
            self.flows.step_timeout_minutes = int(os.getenv('FLOW_STEP_TIMEOUT_MINUTES'))
        if os.getenv('FLOW_TIMEOUT_HOURS'):
            self.flows.flow_timeout_hours = int(os.getenv('FLOW_TIMEOUT_HOURS'))
        
        # Report config
        if os.getenv('REPORT_BATCH_SIZE'):
            self.reports.batch_size = int(os.getenv('REPORT_BATCH_SIZE'))
        if os.getenv('REPORT_TIME_LIMIT'):
            self.reports.task_time_limit = int(os.getenv('REPORT_TIME_LIMIT'))

        # Railway-specific configurations
        if os.getenv('RAILWAY_ENVIRONMENT'):
            # Adjust for Railway resource limits
            self.messaging.batch_size = min(self.messaging.batch_size, 20)
            self.reports.batch_size = min(self.reports.batch_size, 10)

            # Reduce timeouts for Railway
            self.base.task_time_limit = min(self.base.task_time_limit, 180)
            self.base.task_soft_time_limit = min(self.base.task_soft_time_limit, 150)


# Global configuration instance
task_configs = TaskConfigurations()
task_configs.update_from_env()


# Celery task routing configuration
TASK_ROUTES = {
    'app.tasks.messaging.*': {
        'queue': 'messaging',
        'routing_key': 'messaging',
        'priority': task_configs.messaging.priority
    },
    'app.tasks.alerts.*': {
        'queue': 'alerts',
        'routing_key': 'alerts',
        'priority': task_configs.alerts.priority
    },
    'app.tasks.monitoring.*': {
        'queue': 'monitoring',
        'routing_key': 'monitoring',
        'priority': task_configs.monitoring.priority
    },
    'app.tasks.quiz_flow.*': {
        'queue': 'quiz',
        'routing_key': 'quiz',
        'priority': task_configs.quiz.priority
    },
    'app.tasks.flows.*': {
        'queue': 'flows',
        'routing_key': 'flows',
        'priority': task_configs.flows.priority
    },
    'app.tasks.reports.*': {
        'queue': 'reports',
        'routing_key': 'reports',
        'priority': task_configs.reports.priority
    }
}


# Task annotations for automatic configuration
TASK_ANNOTATIONS = {
    'app.tasks.messaging.*': {
        'rate_limit': task_configs.messaging.rate_limit,
        'time_limit': task_configs.messaging.task_time_limit,
        'soft_time_limit': task_configs.messaging.task_soft_time_limit
    },
    'app.tasks.alerts.*': {
        'time_limit': task_configs.alerts.task_time_limit,
        'soft_time_limit': task_configs.alerts.task_soft_time_limit
    },
    'app.tasks.monitoring.*': {
        'time_limit': task_configs.monitoring.task_time_limit,
        'soft_time_limit': task_configs.monitoring.task_soft_time_limit
    },
    'app.tasks.quiz_flow.*': {
        'time_limit': task_configs.quiz.task_time_limit,
        'soft_time_limit': task_configs.quiz.task_soft_time_limit
    },
    'app.tasks.flows.*': {
        'time_limit': task_configs.flows.task_time_limit,
        'soft_time_limit': task_configs.flows.task_soft_time_limit
    },
    'app.tasks.reports.*': {
        'time_limit': task_configs.reports.task_time_limit,
        'soft_time_limit': task_configs.reports.task_soft_time_limit
    }
}


# Database connection settings for tasks
DB_CONFIG = {
    'pool_size': int(os.getenv('TASK_DB_POOL_SIZE', '10')),
    'max_overflow': int(os.getenv('TASK_DB_MAX_OVERFLOW', '20')),
    'pool_timeout': int(os.getenv('TASK_DB_POOL_TIMEOUT', '30')),
    'pool_recycle': int(os.getenv('TASK_DB_POOL_RECYCLE', '3600')),
    'pool_pre_ping': True
}


# Logging configuration for tasks
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'task_formatter': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - [%(task_name)s:%(task_id)s] - %(message)s'
        }
    },
    'handlers': {
        'task_handler': {
            'class': 'logging.StreamHandler',
            'formatter': 'task_formatter',
            'level': 'INFO'
        }
    },
    'loggers': {
        'app.tasks': {
            'handlers': ['task_handler'],
            'level': os.getenv('TASK_LOG_LEVEL', 'INFO'),
            'propagate': False
        }
    }
}


# Redis configuration for task state and results
REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', '6379')),
    'db': int(os.getenv('REDIS_TASK_DB', '1')),
    'password': os.getenv('REDIS_PASSWORD'),
    'socket_timeout': 30,
    'socket_connect_timeout': 30,
    'retry_on_timeout': True,
    'health_check_interval': 30
}


# Monitoring and metrics configuration
MONITORING_CONFIG = {
    'enable_events': True,
    'task_track_started': True,
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'result_expires': 3600,  # 1 hour
    'task_result_expires': 3600,
    'worker_prefetch_multiplier': 1,
    'task_acks_late': True,
    'worker_disable_rate_limits': False
}