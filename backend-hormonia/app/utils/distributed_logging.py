"""
Distributed Logging System for Hive-Mind Agents

Provides centralized logging with agent correlation, structured logging,
and distributed tracing across the multi-agent system.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
from dataclasses import dataclass, asdict
from enum import Enum
import contextvars
from collections import deque

from app.utils.logging import get_logger


class LogLevel(Enum):
    """Extended log levels for distributed system."""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    AGENT_EVENT = "AGENT_EVENT"
    SWARM_EVENT = "SWARM_EVENT"
    TASK_EVENT = "TASK_EVENT"


@dataclass
class LogContext:
    """Distributed logging context."""
    trace_id: str
    span_id: str
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    swarm_id: Optional[str] = None
    patient_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class DistributedLogEntry:
    """Structured log entry for distributed system."""
    timestamp: datetime
    level: LogLevel
    message: str
    logger_name: str
    context: LogContext
    metadata: Dict[str, Any]
    agent_type: Optional[str] = None
    component: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['level'] = self.level.value
        data['context'] = self.context.to_dict()
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


# Context variables for distributed tracing
current_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('trace_id', default=None)
current_span_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('span_id', default=None)
current_agent_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('agent_id', default=None)
current_task_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('task_id', default=None)


class DistributedLogger:
    """
    Distributed logger that correlates logs across agents and components.
    Provides structured logging with context propagation.
    """
    
    def __init__(self, name: str, max_buffer_size: int = 1000):
        """Initialize distributed logger."""
        self.name = name
        self.base_logger = get_logger(name)
        self.max_buffer_size = max_buffer_size
        
        # In-memory log buffer for analysis
        self.log_buffer: deque[DistributedLogEntry] = deque(maxlen=max_buffer_size)
        
        # Event handlers
        self.event_handlers: List[callable] = []
        
        # Configuration
        self.config = {
            "enable_trace_propagation": True,
            "enable_log_buffering": True,
            "enable_structured_output": True,
            "log_agent_events": True,
            "log_task_events": True,
            "log_swarm_events": True
        }
    
    def _get_current_context(self) -> LogContext:
        """Get current logging context from context variables."""
        trace_id = current_trace_id.get() or str(uuid4())
        span_id = current_span_id.get() or str(uuid4())
        agent_id = current_agent_id.get()
        task_id = current_task_id.get()
        
        return LogContext(
            trace_id=trace_id,
            span_id=span_id,
            agent_id=agent_id,
            task_id=task_id
        )
    
    def _create_log_entry(
        self,
        level: LogLevel,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[LogContext] = None
    ) -> DistributedLogEntry:
        """Create structured log entry."""
        if context is None:
            context = self._get_current_context()
        
        entry = DistributedLogEntry(
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            logger_name=self.name,
            context=context,
            metadata=metadata or {},
            component=self.name.split('.')[-1] if '.' in self.name else self.name
        )
        
        return entry
    
    def _log_entry(self, entry: DistributedLogEntry):
        """Process and emit log entry."""
        # Add to buffer
        if self.config["enable_log_buffering"]:
            self.log_buffer.append(entry)
        
        # Format message for standard logger
        if self.config["enable_structured_output"]:
            formatted_message = self._format_structured_message(entry)
        else:
            formatted_message = entry.message
        
        # Log to standard logger
        standard_level = self._get_standard_log_level(entry.level)
        self.base_logger.log(standard_level, formatted_message, extra={
            "trace_id": entry.context.trace_id,
            "span_id": entry.context.span_id,
            "agent_id": entry.context.agent_id,
            "task_id": entry.context.task_id
        })
        
        # Notify event handlers
        for handler in self.event_handlers:
            try:
                asyncio.create_task(handler(entry))
            except Exception as e:
                self.base_logger.error(f"Log event handler failed: {e}")
    
    def _format_structured_message(self, entry: DistributedLogEntry) -> str:
        """Format structured message with context."""
        context_parts = []
        
        if entry.context.agent_id:
            context_parts.append(f"agent={entry.context.agent_id}")
        if entry.context.task_id:
            context_parts.append(f"task={entry.context.task_id[:8]}")
        if entry.context.trace_id:
            context_parts.append(f"trace={entry.context.trace_id[:8]}")
        
        context_str = f"[{','.join(context_parts)}]" if context_parts else ""
        
        return f"{context_str} {entry.message}"
    
    def _get_standard_log_level(self, level: LogLevel) -> int:
        """Convert LogLevel to standard logging level."""
        mapping = {
            LogLevel.TRACE: logging.DEBUG,
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
            LogLevel.AGENT_EVENT: logging.INFO,
            LogLevel.SWARM_EVENT: logging.INFO,
            LogLevel.TASK_EVENT: logging.INFO
        }
        return mapping.get(level, logging.INFO)
    
    # Standard logging methods
    def trace(self, message: str, **kwargs):
        """Log trace level message."""
        entry = self._create_log_entry(LogLevel.TRACE, message, kwargs)
        self._log_entry(entry)
    
    def debug(self, message: str, **kwargs):
        """Log debug level message."""
        entry = self._create_log_entry(LogLevel.DEBUG, message, kwargs)
        self._log_entry(entry)
    
    def info(self, message: str, **kwargs):
        """Log info level message."""
        entry = self._create_log_entry(LogLevel.INFO, message, kwargs)
        self._log_entry(entry)
    
    def warning(self, message: str, **kwargs):
        """Log warning level message."""
        entry = self._create_log_entry(LogLevel.WARNING, message, kwargs)
        self._log_entry(entry)
    
    def error(self, message: str, **kwargs):
        """Log error level message."""
        entry = self._create_log_entry(LogLevel.ERROR, message, kwargs)
        self._log_entry(entry)
    
    def critical(self, message: str, **kwargs):
        """Log critical level message."""
        entry = self._create_log_entry(LogLevel.CRITICAL, message, kwargs)
        self._log_entry(entry)
    
    # Specialized logging methods for distributed system
    def agent_event(self, event_type: str, message: str, **kwargs):
        """Log agent-specific event."""
        if not self.config["log_agent_events"]:
            return
            
        kwargs["event_type"] = event_type
        entry = self._create_log_entry(LogLevel.AGENT_EVENT, message, kwargs)
        self._log_entry(entry)
    
    def task_event(self, event_type: str, message: str, **kwargs):
        """Log task-specific event."""
        if not self.config["log_task_events"]:
            return
            
        kwargs["event_type"] = event_type
        entry = self._create_log_entry(LogLevel.TASK_EVENT, message, kwargs)
        self._log_entry(entry)
    
    def swarm_event(self, event_type: str, message: str, **kwargs):
        """Log swarm-specific event."""
        if not self.config["log_swarm_events"]:
            return
            
        kwargs["event_type"] = event_type
        entry = self._create_log_entry(LogLevel.SWARM_EVENT, message, kwargs)
        self._log_entry(entry)
    
    # Context management
    def with_context(self, **context_updates) -> "LogContextManager":
        """Create context manager with updated context."""
        return LogContextManager(self, **context_updates)
    
    def set_context(self, **context_updates):
        """Update current context variables."""
        if "trace_id" in context_updates:
            current_trace_id.set(context_updates["trace_id"])
        if "span_id" in context_updates:
            current_span_id.set(context_updates["span_id"])
        if "agent_id" in context_updates:
            current_agent_id.set(context_updates["agent_id"])
        if "task_id" in context_updates:
            current_task_id.set(context_updates["task_id"])
    
    # Event handling
    def add_event_handler(self, handler: callable):
        """Add event handler for log entries."""
        self.event_handlers.append(handler)
    
    def remove_event_handler(self, handler: callable):
        """Remove event handler."""
        if handler in self.event_handlers:
            self.event_handlers.remove(handler)
    
    # Log analysis
    def get_logs_by_trace(self, trace_id: str) -> List[DistributedLogEntry]:
        """Get all logs for specific trace."""
        return [
            entry for entry in self.log_buffer
            if entry.context.trace_id == trace_id
        ]
    
    def get_logs_by_agent(self, agent_id: str) -> List[DistributedLogEntry]:
        """Get all logs for specific agent."""
        return [
            entry for entry in self.log_buffer
            if entry.context.agent_id == agent_id
        ]
    
    def get_logs_by_task(self, task_id: str) -> List[DistributedLogEntry]:
        """Get all logs for specific task."""
        return [
            entry for entry in self.log_buffer
            if entry.context.task_id == task_id
        ]
    
    def get_recent_logs(self, limit: int = 100) -> List[DistributedLogEntry]:
        """Get recent log entries."""
        logs = list(self.log_buffer)
        return logs[-limit:] if limit < len(logs) else logs
    
    def get_error_logs(self, limit: int = 50) -> List[DistributedLogEntry]:
        """Get recent error logs."""
        error_logs = [
            entry for entry in self.log_buffer
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]
        ]
        return error_logs[-limit:] if limit < len(error_logs) else error_logs


class LogContextManager:
    """Context manager for logging context."""
    
    def __init__(self, logger: DistributedLogger, **context_updates):
        """Initialize context manager."""
        self.logger = logger
        self.context_updates = context_updates
        self.original_context = {}
    
    def __enter__(self):
        """Enter context - save current and set new context."""
        # Save current context
        self.original_context = {
            "trace_id": current_trace_id.get(),
            "span_id": current_span_id.get(),
            "agent_id": current_agent_id.get(),
            "task_id": current_task_id.get()
        }
        
        # Set new context
        self.logger.set_context(**self.context_updates)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - restore original context."""
        # Restore original context
        for key, value in self.original_context.items():
            if key == "trace_id":
                current_trace_id.set(value)
            elif key == "span_id":
                current_span_id.set(value)
            elif key == "agent_id":
                current_agent_id.set(value)
            elif key == "task_id":
                current_task_id.set(value)


class LogAggregator:
    """
    Aggregates and analyzes logs from multiple distributed loggers.
    Provides system-wide log analysis and correlation.
    """
    
    def __init__(self):
        """Initialize log aggregator."""
        self.loggers: Dict[str, DistributedLogger] = {}
        self.base_logger = get_logger("log_aggregator")
        
        # Global log buffer
        self.global_buffer: deque[DistributedLogEntry] = deque(maxlen=5000)
        
        # Analysis state
        self.error_patterns: Dict[str, int] = {}
        self.performance_metrics: Dict[str, List[float]] = {}
    
    def register_logger(self, logger: DistributedLogger):
        """Register logger for aggregation."""
        self.loggers[logger.name] = logger
        
        # Add event handler to capture logs
        async def capture_log(entry: DistributedLogEntry):
            self.global_buffer.append(entry)
            await self._analyze_log_entry(entry)
        
        logger.add_event_handler(capture_log)
        self.base_logger.info(f"Registered logger: {logger.name}")
    
    async def _analyze_log_entry(self, entry: DistributedLogEntry):
        """Analyze individual log entry for patterns."""
        try:
            # Track error patterns
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                error_key = f"{entry.component}:{entry.level.value}"
                self.error_patterns[error_key] = self.error_patterns.get(error_key, 0) + 1
            
            # Track performance metrics
            if "response_time" in entry.metadata:
                component = entry.component or "unknown"
                if component not in self.performance_metrics:
                    self.performance_metrics[component] = []
                
                self.performance_metrics[component].append(entry.metadata["response_time"])
                
                # Keep only recent metrics
                if len(self.performance_metrics[component]) > 100:
                    self.performance_metrics[component] = self.performance_metrics[component][-100:]
        
        except Exception as e:
            self.base_logger.error(f"Log analysis failed: {e}")
    
    def get_trace_logs(self, trace_id: str) -> List[DistributedLogEntry]:
        """Get all logs for a trace across all loggers."""
        trace_logs = []
        
        # Check global buffer
        for entry in self.global_buffer:
            if entry.context.trace_id == trace_id:
                trace_logs.append(entry)
        
        # Sort by timestamp
        trace_logs.sort(key=lambda x: x.timestamp)
        return trace_logs
    
    def get_agent_logs(self, agent_id: str) -> List[DistributedLogEntry]:
        """Get all logs for an agent across all components."""
        agent_logs = []
        
        for entry in self.global_buffer:
            if entry.context.agent_id == agent_id:
                agent_logs.append(entry)
        
        agent_logs.sort(key=lambda x: x.timestamp)
        return agent_logs
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of error patterns."""
        total_errors = sum(self.error_patterns.values())
        
        return {
            "total_errors": total_errors,
            "error_patterns": dict(sorted(
                self.error_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),  # Top 10 error patterns
            "analysis_period": "last_session"
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary."""
        summary = {}
        
        for component, metrics in self.performance_metrics.items():
            if metrics:
                summary[component] = {
                    "avg_response_time": sum(metrics) / len(metrics),
                    "min_response_time": min(metrics),
                    "max_response_time": max(metrics),
                    "sample_count": len(metrics)
                }
        
        return summary
    
    def export_logs(
        self,
        format: str = "json",
        filter_level: Optional[LogLevel] = None,
        limit: Optional[int] = None
    ) -> str:
        """Export logs in specified format."""
        logs = list(self.global_buffer)
        
        # Apply filters
        if filter_level:
            logs = [log for log in logs if log.level == filter_level]
        
        if limit:
            logs = logs[-limit:]
        
        # Export based on format
        if format == "json":
            return json.dumps([log.to_dict() for log in logs], indent=2, default=str)
        elif format == "csv":
            # Would implement CSV export
            pass
        else:
            return "\n".join([f"{log.timestamp} [{log.level.value}] {log.message}" for log in logs])


# Global instances
_log_aggregator: Optional[LogAggregator] = None


def get_distributed_logger(name: str) -> DistributedLogger:
    """Get distributed logger instance."""
    logger = DistributedLogger(name)
    
    # Register with global aggregator
    global _log_aggregator
    if _log_aggregator is None:
        _log_aggregator = LogAggregator()
    
    _log_aggregator.register_logger(logger)
    
    return logger


def get_log_aggregator() -> LogAggregator:
    """Get global log aggregator."""
    global _log_aggregator
    if _log_aggregator is None:
        _log_aggregator = LogAggregator()
    
    return _log_aggregator


# Context utilities
def set_trace_context(trace_id: str, span_id: Optional[str] = None):
    """Set trace context for current execution."""
    current_trace_id.set(trace_id)
    if span_id:
        current_span_id.set(span_id)
    else:
        current_span_id.set(str(uuid4()))


def set_agent_context(agent_id: str):
    """Set agent context for current execution."""
    current_agent_id.set(agent_id)


def set_task_context(task_id: str):
    """Set task context for current execution."""
    current_task_id.set(task_id)


def create_trace() -> str:
    """Create new trace and set context."""
    trace_id = str(uuid4())
    span_id = str(uuid4())
    current_trace_id.set(trace_id)
    current_span_id.set(span_id)
    return trace_id