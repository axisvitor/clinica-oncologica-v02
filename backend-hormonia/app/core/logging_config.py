"""
Logging rate limiting and optimization configuration.

This module provides rate-limited logging capabilities to prevent log flooding
and optimize logging performance under high load conditions.
"""
import time
import logging
import hashlib
from typing import Dict, List, Optional, Set
from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock

class RateLimitedLogger:
    """
    Logger with rate limiting capabilities to prevent log flooding.
    
    Features:
    - Per-second log rate limiting with configurable thresholds
    - Log deduplication for repeated error messages
    - Sampling for high-frequency log messages
    - Thread-safe operation
    """
    
    def __init__(
        self,
        max_logs_per_second: int = 100,
        deduplication_window: int = 300,  # 5 minutes
        sampling_rate: float = 0.1,  # 10% sampling for high-frequency logs
        enable_deduplication: bool = True
    ):
        self.max_logs_per_second = max_logs_per_second
        self.deduplication_window = deduplication_window
        self.sampling_rate = sampling_rate
        self.enable_deduplication = enable_deduplication
        
        # Rate limiting tracking
        self.log_counts: Dict[str, deque] = defaultdict(deque)
        self.last_cleanup = time.time()
        self.cleanup_interval = 60  # Clean up every minute
        
        # Deduplication tracking
        self.message_hashes: Dict[str, Dict] = {}  # hash -> {count, first_seen, last_seen}
        self.suppressed_count = 0
        
        # Thread safety
        self._lock = Lock()
        
        # Sampling tracking
        self.sample_counters: Dict[str, int] = defaultdict(int)
    
    def should_log(self, log_key: str, message: str = "", level: int = logging.INFO) -> bool:
        """
        Check if we should log based on rate limiting and deduplication.
        
        Args:
            log_key: Unique key for rate limiting (e.g., logger name + level)
            message: Log message for deduplication
            level: Log level
            
        Returns:
            True if the message should be logged, False otherwise
        """
        with self._lock:
            now = time.time()
            
            # Clean up old entries periodically
            if now - self.last_cleanup > self.cleanup_interval:
                self._cleanup_old_entries(now)
                self.last_cleanup = now
            
            # Check deduplication first
            if self.enable_deduplication and message:
                if not self._should_log_deduplicated(message, now):
                    return False
            
            # Check rate limiting
            if not self._should_log_rate_limited(log_key, now):
                return False
            
            # Check sampling for high-frequency logs
            if level <= logging.DEBUG:
                return self._should_log_sampled(log_key)
            
            return True
    
    def _should_log_deduplicated(self, message: str, now: float) -> bool:
        """Check if message should be logged based on deduplication."""
        # Create hash of message for deduplication
        message_hash = hashlib.md5(message.encode()).hexdigest()
        
        if message_hash in self.message_hashes:
            entry = self.message_hashes[message_hash]
            
            # Check if within deduplication window
            if now - entry['first_seen'] < self.deduplication_window:
                entry['count'] += 1
                entry['last_seen'] = now
                
                # Log every 10th occurrence or after significant time gap
                if entry['count'] % 10 == 0 or now - entry['last_logged'] > 60:
                    entry['last_logged'] = now
                    return True
                
                self.suppressed_count += 1
                return False
            else:
                # Outside window, reset entry
                self.message_hashes[message_hash] = {
                    'count': 1,
                    'first_seen': now,
                    'last_seen': now,
                    'last_logged': now
                }
                return True
        else:
            # New message
            self.message_hashes[message_hash] = {
                'count': 1,
                'first_seen': now,
                'last_seen': now,
                'last_logged': now
            }
            return True
    
    def _should_log_rate_limited(self, log_key: str, now: float) -> bool:
        """Check if message should be logged based on rate limiting."""
        # Clean old entries for this key
        timestamps = self.log_counts[log_key]
        window_start = now - 1.0  # 1 second window
        
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()
        
        # Check if under rate limit
        if len(timestamps) < self.max_logs_per_second:
            timestamps.append(now)
            return True
        
        return False
    
    def _should_log_sampled(self, log_key: str) -> bool:
        """Check if debug message should be logged based on sampling."""
        self.sample_counters[log_key] += 1
        
        # Log every Nth message based on sampling rate
        sample_interval = int(1 / self.sampling_rate) if self.sampling_rate > 0 else 1
        return self.sample_counters[log_key] % sample_interval == 0
    
    def _cleanup_old_entries(self, now: float) -> None:
        """Clean up old entries to prevent memory leaks."""
        # Clean up rate limiting entries
        for key, timestamps in list(self.log_counts.items()):
            window_start = now - 1.0
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()
            
            # Remove empty queues
            if not timestamps:
                del self.log_counts[key]
        
        # Clean up deduplication entries
        cutoff_time = now - self.deduplication_window
        for message_hash in list(self.message_hashes.keys()):
            entry = self.message_hashes[message_hash]
            if entry['last_seen'] < cutoff_time:
                del self.message_hashes[message_hash]
        
        # Clean up sampling counters (reset periodically)
        if len(self.sample_counters) > 1000:
            self.sample_counters.clear()
    
    def get_stats(self) -> Dict:
        """Get logging statistics."""
        with self._lock:
            total_rate_limited_keys = len(self.log_counts)
            total_deduplicated_messages = len(self.message_hashes)
            
            return {
                'rate_limited_keys': total_rate_limited_keys,
                'deduplicated_messages': total_deduplicated_messages,
                'suppressed_count': self.suppressed_count,
                'max_logs_per_second': self.max_logs_per_second,
                'deduplication_window': self.deduplication_window,
                'sampling_rate': self.sampling_rate
            }

class OptimizedRequestLogger:
    """
    Optimized logger for request middleware with appropriate log levels.
    """
    
    def __init__(self, rate_limiter: Optional[RateLimitedLogger] = None):
        self.rate_limiter = rate_limiter or RateLimitedLogger()
        self.logger = logging.getLogger(__name__)
        
        # Define which paths should be logged at DEBUG level
        self.debug_paths = {
            '/health', '/metrics', '/docs', '/redoc', '/openapi.json',
            '/favicon.ico', '/robots.txt'
        }
        
        # Define which paths should have reduced logging
        self.quiet_paths = {
            '/api/v1/health', '/api/v1/metrics', '/api/v1/system/health'
        }
        
        # Error types that should not include stack traces
        self.no_stacktrace_errors = {
            'ValidationError', 'HTTPException', 'AuthenticationError',
            'AuthorizationError', 'NotFoundError'
        }
    
    def log_request_start(self, method: str, path: str, client_ip: str, correlation_id: str) -> None:
        """Log request start with appropriate level."""
        log_key = f"request_start_{path}"
        
        # Determine log level based on path
        if path in self.quiet_paths:
            return  # Don't log health checks and metrics
        
        level = logging.DEBUG if path in self.debug_paths else logging.INFO
        message = f"Request started: {method} {path}"
        
        if self.rate_limiter.should_log(log_key, message, level):
            if level == logging.DEBUG:
                self.logger.debug(
                    message,
                    extra={
                        'event_type': 'request_start',
                        'method': method,
                        'path': path,
                        'client_ip': client_ip,
                        'correlation_id': correlation_id
                    }
                )
            else:
                self.logger.info(
                    message,
                    extra={
                        'event_type': 'request_start',
                        'method': method,
                        'path': path,
                        'client_ip': client_ip,
                        'correlation_id': correlation_id
                    }
                )
    
    def log_request_complete(
        self,
        method: str,
        path: str,
        status_code: int,
        process_time: float,
        correlation_id: str
    ) -> None:
        """Log request completion with appropriate level."""
        log_key = f"request_complete_{path}_{status_code}"
        
        # Skip logging for quiet paths
        if path in self.quiet_paths:
            return
        
        # Determine log level based on status code and path
        if status_code >= 500:
            level = logging.ERROR
        elif status_code >= 400:
            level = logging.WARNING
        elif path in self.debug_paths:
            level = logging.DEBUG
        else:
            level = logging.INFO
        
        message = f"Request completed: {method} {path} - {status_code} ({process_time:.3f}s)"
        
        if self.rate_limiter.should_log(log_key, message, level):
            extra_data = {
                'event_type': 'request_complete',
                'method': method,
                'path': path,
                'status_code': status_code,
                'process_time': process_time,
                'correlation_id': correlation_id
            }
            
            if level == logging.ERROR:
                self.logger.error(message, extra=extra_data)
            elif level == logging.WARNING:
                self.logger.warning(message, extra=extra_data)
            elif level == logging.DEBUG:
                self.logger.debug(message, extra=extra_data)
            else:
                self.logger.info(message, extra=extra_data)
    
    def log_request_error(
        self,
        method: str,
        path: str,
        error: Exception,
        process_time: float,
        correlation_id: str
    ) -> None:
        """Log request error with appropriate level and stack trace handling."""
        log_key = f"request_error_{path}_{type(error).__name__}"
        error_type = type(error).__name__
        
        # Determine if we should include stack trace
        include_stacktrace = error_type not in self.no_stacktrace_errors
        
        # For 4xx errors, use WARNING level; for 5xx errors, use ERROR level
        if hasattr(error, 'status_code'):
            level = logging.WARNING if 400 <= error.status_code < 500 else logging.ERROR
        else:
            level = logging.ERROR
        
        message = f"Request error: {method} {path} - {error_type}: {str(error)}"
        
        if self.rate_limiter.should_log(log_key, message, level):
            extra_data = {
                'event_type': 'request_error',
                'method': method,
                'path': path,
                'error_type': error_type,
                'error_message': str(error),
                'process_time': process_time,
                'correlation_id': correlation_id
            }
            
            if level == logging.ERROR:
                self.logger.error(message, extra=extra_data, exc_info=include_stacktrace)
            else:
                self.logger.warning(message, extra=extra_data, exc_info=include_stacktrace)

def configure_optimized_logging(
    log_level: str = "INFO",
    max_logs_per_second: int = 100,
    enable_rate_limiting: bool = True,
    enable_deduplication: bool = True
) -> RateLimitedLogger:
    """
    Configure optimized logging with rate limiting and deduplication.
    
    Args:
        log_level: Base logging level
        max_logs_per_second: Maximum logs per second before rate limiting
        enable_rate_limiting: Whether to enable rate limiting
        enable_deduplication: Whether to enable log deduplication
        
    Returns:
        Configured RateLimitedLogger instance
    """
    # Set up basic logging configuration
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with optimized formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Use structured logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.error').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    
    # Create rate limiter if enabled
    if enable_rate_limiting:
        rate_limiter = RateLimitedLogger(
            max_logs_per_second=max_logs_per_second,
            enable_deduplication=enable_deduplication
        )
        return rate_limiter
    
    return None