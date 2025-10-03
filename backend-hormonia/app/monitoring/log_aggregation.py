"""
Log Aggregation System for Centralized Logging.

Provides structured log collection, aggregation, and analysis with
HIPAA compliance for healthcare data.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict, deque
import re
from enum import Enum
import hashlib
import redis.asyncio as redis

from app.utils.logging import get_logger, SensitiveDataFilter


logger = get_logger(__name__)


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """Log categories for classification."""
    APPLICATION = "application"
    DATABASE = "database"
    SECURITY = "security"
    AUDIT = "audit"
    API = "api"
    AUTHENTICATION = "authentication"
    BUSINESS = "business"
    PERFORMANCE = "performance"
    ERROR = "error"
    SYSTEM = "system"


class LogAggregationConfig:
    """Configuration for log aggregation system."""

    def __init__(self):
        self.enabled: bool = True
        self.buffer_size: int = 1000
        self.flush_interval: int = 60  # seconds
        self.retention_days: int = 90
        self.security_retention_days: int = 365  # HIPAA requires 1 year
        self.audit_retention_days: int = 2555  # HIPAA requires 7 years
        self.enable_sampling: bool = True
        self.sample_rate: float = 0.1  # 10% for debug logs
        self.enable_compression: bool = True
        self.max_message_size: int = 10000  # characters

        # Pattern detection settings
        self.error_pattern_window: int = 300  # 5 minutes
        self.error_threshold: int = 10  # Same error 10 times triggers alert

        # HIPAA compliance settings
        self.enable_phi_detection: bool = True
        self.enable_audit_trail: bool = True
        self.enable_access_logging: bool = True


class PHIDetector:
    """Protected Health Information (PHI) detector for HIPAA compliance."""

    # Patterns for PHI detection
    PATTERNS = {
        'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        'mrn': re.compile(r'\b(MRN|mrn|medical.?record.?number):?\s*([A-Z0-9]{6,})\b', re.IGNORECASE),
        'phone': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
        'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        'cpf': re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b'),
        'date_of_birth': re.compile(r'\b(dob|birth.?date|date.?of.?birth):?\s*(\d{2}[/-]\d{2}[/-]\d{4})\b', re.IGNORECASE),
        'address': re.compile(r'\b\d+\s+[A-Za-z\s]+(?:street|st|avenue|ave|road|rd|drive|dr)\b', re.IGNORECASE)
    }

    @classmethod
    def detect_phi(cls, text: str) -> Dict[str, List[str]]:
        """Detect PHI in text and return findings."""
        findings = defaultdict(list)

        for phi_type, pattern in cls.PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                findings[phi_type].extend([m if isinstance(m, str) else m[1] for m in matches])

        return dict(findings)

    @classmethod
    def redact_phi(cls, text: str) -> str:
        """Redact PHI from text."""
        redacted = text

        for phi_type, pattern in cls.PATTERNS.items():
            redacted = pattern.sub(f'[{phi_type.upper()}_REDACTED]', redacted)

        return redacted


class LogEntry:
    """Structured log entry."""

    def __init__(
        self,
        message: str,
        level: LogLevel,
        category: LogCategory,
        timestamp: Optional[datetime] = None,
        context: Optional[Dict[str, Any]] = None,
        exception: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        patient_id: Optional[str] = None
    ):
        self.id = self._generate_id()
        self.message = message
        self.level = level
        self.category = category
        self.timestamp = timestamp or datetime.utcnow()
        self.context = context or {}
        self.exception = exception
        self.request_id = request_id
        self.user_id = user_id
        self.patient_id = patient_id

        # PHI detection and redaction
        self.contains_phi = False
        self.phi_types: List[str] = []
        self._detect_phi()

    def _generate_id(self) -> str:
        """Generate unique log entry ID."""
        return hashlib.sha256(
            f"{datetime.utcnow().isoformat()}{id(self)}".encode()
        ).hexdigest()[:16]

    def _detect_phi(self):
        """Detect and flag PHI in log message."""
        phi_findings = PHIDetector.detect_phi(self.message)
        if phi_findings:
            self.contains_phi = True
            self.phi_types = list(phi_findings.keys())

    def to_dict(self, redact_phi: bool = True) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        message = PHIDetector.redact_phi(self.message) if redact_phi and self.contains_phi else self.message

        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'category': self.category.value,
            'message': message,
            'context': self.context,
            'exception': self.exception,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'patient_id': self.patient_id,
            'contains_phi': self.contains_phi,
            'phi_types': self.phi_types
        }


class LogBuffer:
    """Buffer for batching log entries before shipping."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffer: deque = deque(maxlen=max_size)
        self.lock = asyncio.Lock()

    async def add(self, entry: LogEntry):
        """Add log entry to buffer."""
        async with self.lock:
            self.buffer.append(entry)

    async def flush(self) -> List[LogEntry]:
        """Flush buffer and return all entries."""
        async with self.lock:
            entries = list(self.buffer)
            self.buffer.clear()
            return entries

    async def size(self) -> int:
        """Get current buffer size."""
        async with self.lock:
            return len(self.buffer)


class ErrorPatternDetector:
    """Detect error patterns and anomalies in logs."""

    def __init__(self, window_seconds: int = 300, threshold: int = 10):
        self.window_seconds = window_seconds
        self.threshold = threshold
        self.error_history: Dict[str, deque] = defaultdict(lambda: deque())

    def _error_signature(self, entry: LogEntry) -> str:
        """Generate error signature for pattern matching."""
        if entry.exception:
            return f"{entry.exception.get('type', 'unknown')}:{entry.message[:100]}"
        return entry.message[:100]

    def detect_pattern(self, entry: LogEntry) -> Optional[Dict[str, Any]]:
        """Detect if error matches a pattern."""
        if entry.level not in [LogLevel.ERROR, LogLevel.CRITICAL]:
            return None

        signature = self._error_signature(entry)
        now = datetime.utcnow()

        # Add to history
        self.error_history[signature].append(now)

        # Remove old entries outside window
        cutoff = now - timedelta(seconds=self.window_seconds)
        while self.error_history[signature] and self.error_history[signature][0] < cutoff:
            self.error_history[signature].popleft()

        # Check if threshold exceeded
        count = len(self.error_history[signature])
        if count >= self.threshold:
            return {
                'pattern': signature,
                'count': count,
                'window_seconds': self.window_seconds,
                'first_occurrence': self.error_history[signature][0].isoformat(),
                'last_occurrence': now.isoformat(),
                'severity': 'high' if count > self.threshold * 2 else 'medium'
            }

        return None

    def get_top_patterns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top error patterns."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)

        patterns = []
        for signature, timestamps in self.error_history.items():
            # Filter recent timestamps
            recent = [ts for ts in timestamps if ts > cutoff]
            if recent:
                patterns.append({
                    'pattern': signature,
                    'count': len(recent),
                    'first_occurrence': min(recent).isoformat(),
                    'last_occurrence': max(recent).isoformat()
                })

        # Sort by count descending
        patterns.sort(key=lambda x: x['count'], reverse=True)
        return patterns[:limit]


class LogAggregator:
    """Main log aggregation engine."""

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        config: Optional[LogAggregationConfig] = None
    ):
        self.redis = redis_client
        self.config = config or LogAggregationConfig()

        # Buffers for different log categories
        self.buffers: Dict[LogCategory, LogBuffer] = {
            category: LogBuffer(self.config.buffer_size)
            for category in LogCategory
        }

        # Pattern detector
        self.pattern_detector = ErrorPatternDetector(
            self.config.error_pattern_window,
            self.config.error_threshold
        )

        # Statistics
        self.stats = {
            'total_logs': 0,
            'logs_by_level': defaultdict(int),
            'logs_by_category': defaultdict(int),
            'phi_detected': 0,
            'patterns_detected': 0
        }

        # Background tasks
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start log aggregation background tasks."""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("Log aggregation system started")

    async def stop(self):
        """Stop log aggregation background tasks."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self._flush_all_buffers()
        logger.info("Log aggregation system stopped")

    async def collect(
        self,
        message: str,
        level: LogLevel,
        category: LogCategory,
        context: Optional[Dict[str, Any]] = None,
        exception: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        patient_id: Optional[str] = None
    ):
        """Collect a log entry."""
        # Apply sampling for debug logs
        if level == LogLevel.DEBUG and self.config.enable_sampling:
            import random
            if random.random() > self.config.sample_rate:
                return

        # Create log entry
        entry = LogEntry(
            message=message[:self.config.max_message_size],
            level=level,
            category=category,
            context=context,
            exception=exception,
            request_id=request_id,
            user_id=user_id,
            patient_id=patient_id
        )

        # Update stats
        self.stats['total_logs'] += 1
        self.stats['logs_by_level'][level.value] += 1
        self.stats['logs_by_category'][category.value] += 1

        if entry.contains_phi:
            self.stats['phi_detected'] += 1

        # Detect error patterns
        pattern = self.pattern_detector.detect_pattern(entry)
        if pattern:
            self.stats['patterns_detected'] += 1
            await self._alert_pattern(pattern, entry)

        # Add to appropriate buffer
        await self.buffers[category].add(entry)

        # Check if immediate flush needed
        buffer_size = await self.buffers[category].size()
        if buffer_size >= self.config.buffer_size:
            await self._flush_buffer(category)

    async def _periodic_flush(self):
        """Periodically flush all buffers."""
        while self._running:
            try:
                await asyncio.sleep(self.config.flush_interval)
                await self._flush_all_buffers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")

    async def _flush_all_buffers(self):
        """Flush all category buffers."""
        for category in LogCategory:
            await self._flush_buffer(category)

    async def _flush_buffer(self, category: LogCategory):
        """Flush a specific category buffer."""
        entries = await self.buffers[category].flush()

        if not entries:
            return

        # Ship to Redis if available
        if self.redis:
            await self._ship_to_redis(category, entries)

        # Log aggregation summary
        logger.info(
            f"Flushed {len(entries)} {category.value} logs",
            extra={
                'event_type': 'log_flush',
                'category': category.value,
                'count': len(entries)
            }
        )

    async def _ship_to_redis(self, category: LogCategory, entries: List[LogEntry]):
        """Ship log entries to Redis for further processing."""
        try:
            pipeline = self.redis.pipeline()

            for entry in entries:
                # Store in category-specific list
                key = f"logs:{category.value}:{entry.timestamp.strftime('%Y-%m-%d')}"
                pipeline.rpush(key, json.dumps(entry.to_dict()))

                # Set retention based on category
                retention_days = self._get_retention_days(category)
                pipeline.expire(key, retention_days * 86400)

                # Store in search index (for Elasticsearch later)
                search_key = f"logs:search:{entry.id}"
                pipeline.setex(
                    search_key,
                    retention_days * 86400,
                    json.dumps(entry.to_dict())
                )

            await pipeline.execute()

        except Exception as e:
            logger.error(f"Failed to ship logs to Redis: {e}")

    def _get_retention_days(self, category: LogCategory) -> int:
        """Get retention days based on category and HIPAA requirements."""
        if category == LogCategory.AUDIT:
            return self.config.audit_retention_days  # 7 years
        elif category == LogCategory.SECURITY:
            return self.config.security_retention_days  # 1 year
        else:
            return self.config.retention_days  # 90 days

    async def _alert_pattern(self, pattern: Dict[str, Any], entry: LogEntry):
        """Alert on detected error pattern."""
        if not self.redis:
            return

        try:
            alert_key = f"alerts:log_pattern:{pattern['pattern'][:50]}"
            alert_data = {
                'type': 'error_pattern',
                'pattern': pattern,
                'sample_entry': entry.to_dict(),
                'timestamp': datetime.utcnow().isoformat()
            }

            await self.redis.setex(
                alert_key,
                3600,  # 1 hour
                json.dumps(alert_data)
            )

            # Publish to alert channel
            await self.redis.publish(
                'alerts:log_patterns',
                json.dumps(alert_data)
            )

        except Exception as e:
            logger.error(f"Failed to publish pattern alert: {e}")

    async def search_logs(
        self,
        query: str,
        category: Optional[LogCategory] = None,
        level: Optional[LogLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search logs with filters."""
        if not self.redis:
            return []

        try:
            # Build search pattern
            pattern = "logs:*"
            if category:
                pattern = f"logs:{category.value}:*"

            # Get all matching keys
            keys = await self.redis.keys(pattern)
            results = []

            for key in keys:
                # Get logs from key
                logs_json = await self.redis.lrange(key, 0, -1)

                for log_json in logs_json:
                    log_data = json.loads(log_json)

                    # Apply filters
                    log_time = datetime.fromisoformat(log_data['timestamp'])

                    if start_time and log_time < start_time:
                        continue
                    if end_time and log_time > end_time:
                        continue
                    if level and log_data['level'] != level.value:
                        continue
                    if query and query.lower() not in log_data['message'].lower():
                        continue

                    results.append(log_data)

                    if len(results) >= limit:
                        break

                if len(results) >= limit:
                    break

            # Sort by timestamp descending
            results.sort(key=lambda x: x['timestamp'], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Log search failed: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregation statistics."""
        return {
            'total_logs': self.stats['total_logs'],
            'logs_by_level': dict(self.stats['logs_by_level']),
            'logs_by_category': dict(self.stats['logs_by_category']),
            'phi_detected': self.stats['phi_detected'],
            'patterns_detected': self.stats['patterns_detected'],
            'top_error_patterns': self.pattern_detector.get_top_patterns()
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of log aggregation system."""
        return {
            'running': self._running,
            'redis_connected': self.redis is not None,
            'buffer_sizes': {
                category.value: asyncio.create_task(buffer.size())
                for category, buffer in self.buffers.items()
            },
            'config': {
                'enabled': self.config.enabled,
                'retention_days': self.config.retention_days,
                'phi_detection': self.config.enable_phi_detection,
                'audit_trail': self.config.enable_audit_trail
            }
        }


# Global aggregator instance
_log_aggregator: Optional[LogAggregator] = None


def get_log_aggregator(redis_client: Optional[redis.Redis] = None) -> LogAggregator:
    """Get global log aggregator instance."""
    global _log_aggregator
    if _log_aggregator is None:
        _log_aggregator = LogAggregator(redis_client)
    return _log_aggregator