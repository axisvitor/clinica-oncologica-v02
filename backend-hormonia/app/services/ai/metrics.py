"""
AI Metrics and Monitoring
=========================

Tracks AI service usage, performance, and costs for monitoring and optimization.
Uses Redis for distributed metrics storage with minimal overhead.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


@dataclass
class AICallMetrics:
    """Metrics for a single AI call."""

    service: str
    operation: str
    start_time: float
    end_time: Optional[float] = None
    success: bool = True
    cached: bool = False
    tokens_input: int = 0
    tokens_output: int = 0
    error_type: Optional[str] = None

    @property
    def latency_ms(self) -> float:
        """Calculate latency in milliseconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.tokens_input + self.tokens_output


@dataclass
class AIServiceStats:
    """Aggregated statistics for an AI service."""

    service: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    cached_calls: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    error_counts: Dict[str, int] = field(default_factory=dict)
    operations: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_calls == 0:
            return 0.0
        return self.cached_calls / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        non_cached = self.total_calls - self.cached_calls
        if non_cached == 0:
            return 0.0
        return self.total_latency_ms / non_cached

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service": self.service,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "cached_calls": self.cached_calls,
            "success_rate": round(self.success_rate, 4),
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "total_tokens": self.total_tokens,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "error_counts": self.error_counts,
            "operations": self.operations,
        }


class AIMetricsCollector:
    """
    Collects and aggregates AI service metrics.
    
    Features:
    - In-memory metrics with periodic flush
    - Operation-level tracking
    - Error categorization
    - Cache efficiency monitoring
    """

    def __init__(self, flush_interval_seconds: int = 60):
        """
        Initialize metrics collector.
        
        Args:
            flush_interval_seconds: Interval between metric flushes
        """
        self._metrics: Dict[str, AIServiceStats] = {}
        self._recent_calls: List[AICallMetrics] = []
        self._max_recent_calls = 100
        self._flush_interval = flush_interval_seconds
        self._last_flush = time.time()
        self._lock = asyncio.Lock()

    async def record_call(self, metrics: AICallMetrics) -> None:
        """Record an AI call's metrics."""
        async with self._lock:
            # Get or create service stats
            if metrics.service not in self._metrics:
                self._metrics[metrics.service] = AIServiceStats(service=metrics.service)
            
            stats = self._metrics[metrics.service]
            
            # Update counts
            stats.total_calls += 1
            if metrics.success:
                stats.successful_calls += 1
            else:
                stats.failed_calls += 1
                if metrics.error_type:
                    stats.error_counts[metrics.error_type] = (
                        stats.error_counts.get(metrics.error_type, 0) + 1
                    )
            
            if metrics.cached:
                stats.cached_calls += 1
            else:
                stats.total_latency_ms += metrics.latency_ms
            
            stats.total_tokens += metrics.total_tokens
            
            # Track operations
            stats.operations[metrics.operation] = (
                stats.operations.get(metrics.operation, 0) + 1
            )
            
            # Keep recent calls
            self._recent_calls.append(metrics)
            if len(self._recent_calls) > self._max_recent_calls:
                self._recent_calls = self._recent_calls[-self._max_recent_calls:]

    async def get_stats(self, service: Optional[str] = None) -> Dict[str, Any]:
        """
        Get aggregated statistics.
        
        Args:
            service: Optional service name to filter
            
        Returns:
            Dictionary of stats by service
        """
        async with self._lock:
            if service:
                if service in self._metrics:
                    return {service: self._metrics[service].to_dict()}
                return {}
            
            return {
                name: stats.to_dict()
                for name, stats in self._metrics.items()
            }

    async def get_recent_calls(
        self,
        service: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent AI calls for debugging."""
        async with self._lock:
            calls = self._recent_calls
            if service:
                calls = [c for c in calls if c.service == service]
            
            return [
                {
                    "service": c.service,
                    "operation": c.operation,
                    "success": c.success,
                    "cached": c.cached,
                    "latency_ms": round(c.latency_ms, 2),
                    "tokens": c.total_tokens,
                    "error_type": c.error_type,
                }
                for c in calls[-limit:]
            ]

    async def reset(self) -> None:
        """Reset all metrics."""
        async with self._lock:
            self._metrics.clear()
            self._recent_calls.clear()
            logger.info("AI metrics reset")


# Global metrics collector
_metrics_collector: Optional[AIMetricsCollector] = None


def get_ai_metrics() -> AIMetricsCollector:
    """Get global AI metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = AIMetricsCollector()
    return _metrics_collector


class AICallTracker:
    """
    Context manager for tracking AI calls.
    
    Usage:
        async with AICallTracker("gemini", "humanize") as tracker:
            result = await gemini_client.humanize_message(...)
            tracker.set_tokens(input=100, output=50)
    """

    def __init__(
        self,
        service: str,
        operation: str,
        collector: Optional[AIMetricsCollector] = None,
    ):
        self.service = service
        self.operation = operation
        self.collector = collector or get_ai_metrics()
        self._metrics: Optional[AICallMetrics] = None

    async def __aenter__(self) -> "AICallTracker":
        self._metrics = AICallMetrics(
            service=self.service,
            operation=self.operation,
            start_time=time.time(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._metrics:
            self._metrics.end_time = time.time()
            if exc_type:
                self._metrics.success = False
                self._metrics.error_type = exc_type.__name__
            await self.collector.record_call(self._metrics)

    def set_cached(self, cached: bool = True) -> None:
        """Mark call as cached."""
        if self._metrics:
            self._metrics.cached = cached

    def set_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Set token counts."""
        if self._metrics:
            self._metrics.tokens_input = input_tokens
            self._metrics.tokens_output = output_tokens

    def set_error(self, error_type: str) -> None:
        """Set error type."""
        if self._metrics:
            self._metrics.success = False
            self._metrics.error_type = error_type
