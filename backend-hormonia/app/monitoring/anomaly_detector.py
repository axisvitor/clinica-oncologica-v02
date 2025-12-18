"""
Anomaly Detection System.

Machine learning-based anomaly detection for performance metrics
and business metrics.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta
from enum import Enum
import statistics
import redis.asyncio as redis


logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of anomalies."""

    SPIKE = "spike"
    DROP = "drop"
    TREND_CHANGE = "trend_change"
    OUTLIER = "outlier"
    PATTERN_BREAK = "pattern_break"


@dataclass
class Anomaly:
    """Detected anomaly."""

    metric_name: str
    anomaly_type: AnomalyType
    timestamp: datetime
    value: float
    expected_value: float
    confidence: float
    severity: str  # low, medium, high, critical
    description: str
    metadata: Dict[str, Any]


class SimpleStatisticalDetector:
    """Simple statistical anomaly detection using z-score and IQR methods."""

    def __init__(self, window_size: int = 100, z_threshold: float = 3.0):
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.metric_windows: Dict[str, deque] = {}

    def add_value(
        self, metric_name: str, value: float, timestamp: datetime
    ) -> Optional[Anomaly]:
        """Add a value and check for anomalies."""
        if metric_name not in self.metric_windows:
            self.metric_windows[metric_name] = deque(maxlen=self.window_size)

        window = self.metric_windows[metric_name]

        # Check for anomaly before adding the new value
        anomaly = None
        if len(window) >= 30:  # Need minimum data points
            anomaly = self._detect_anomaly(metric_name, value, timestamp, list(window))

        # Add new value to window
        window.append((value, timestamp))

        return anomaly

    def _detect_anomaly(
        self,
        metric_name: str,
        value: float,
        timestamp: datetime,
        historical_values: List[Tuple[float, datetime]],
    ) -> Optional[Anomaly]:
        """Detect anomaly using statistical methods."""
        values = [v[0] for v in historical_values]

        if len(values) < 10:
            return None

        # Calculate statistics
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0

        if std_dev == 0:
            return None

        # Z-score method
        z_score = abs(value - mean) / std_dev

        if z_score > self.z_threshold:
            # Determine anomaly type
            anomaly_type = AnomalyType.SPIKE if value > mean else AnomalyType.DROP

            # Determine severity based on z-score
            if z_score > 5:
                severity = "critical"
            elif z_score > 4:
                severity = "high"
            elif z_score > 3.5:
                severity = "medium"
            else:
                severity = "low"

            confidence = min(0.99, z_score / 5.0)  # Scale confidence

            return Anomaly(
                metric_name=metric_name,
                anomaly_type=anomaly_type,
                timestamp=timestamp,
                value=value,
                expected_value=mean,
                confidence=confidence,
                severity=severity,
                description=f"{anomaly_type.value.title()} detected: value {value:.2f} vs expected {mean:.2f} (z-score: {z_score:.2f})",
                metadata={
                    "z_score": z_score,
                    "std_dev": std_dev,
                    "historical_mean": mean,
                    "detection_method": "z_score",
                },
            )

        return None


class TrendDetector:
    """Detects trend changes in metrics."""

    def __init__(self, window_size: int = 50, trend_threshold: float = 0.3):
        self.window_size = window_size
        self.trend_threshold = trend_threshold
        self.metric_windows: Dict[str, deque] = {}

    def add_value(
        self, metric_name: str, value: float, timestamp: datetime
    ) -> Optional[Anomaly]:
        """Add value and check for trend changes."""
        if metric_name not in self.metric_windows:
            self.metric_windows[metric_name] = deque(maxlen=self.window_size)

        window = self.metric_windows[metric_name]
        window.append((value, timestamp))

        if len(window) >= self.window_size:
            return self._detect_trend_change(metric_name, list(window))

        return None

    def _detect_trend_change(
        self, metric_name: str, values: List[Tuple[float, datetime]]
    ) -> Optional[Anomaly]:
        """Detect trend changes using linear regression."""
        if len(values) < 20:
            return None

        # Split into two halves
        mid_point = len(values) // 2
        first_half = [v[0] for v in values[:mid_point]]
        second_half = [v[0] for v in values[mid_point:]]

        # Calculate trends for each half
        first_trend = self._calculate_trend(first_half)
        second_trend = self._calculate_trend(second_half)

        # Check for significant trend change
        trend_diff = abs(second_trend - first_trend)

        if trend_diff > self.trend_threshold:
            latest_value = values[-1][0]
            latest_timestamp = values[-1][1]

            severity = "high" if trend_diff > 0.5 else "medium"
            confidence = min(0.95, trend_diff / 0.5)

            return Anomaly(
                metric_name=metric_name,
                anomaly_type=AnomalyType.TREND_CHANGE,
                timestamp=latest_timestamp,
                value=latest_value,
                expected_value=statistics.mean(first_half),
                confidence=confidence,
                severity=severity,
                description=f"Trend change detected: from {first_trend:.3f} to {second_trend:.3f}",
                metadata={
                    "first_trend": first_trend,
                    "second_trend": second_trend,
                    "trend_difference": trend_diff,
                    "detection_method": "trend_analysis",
                },
            )

        return None

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend using simple linear regression."""
        if len(values) < 2:
            return 0.0

        n = len(values)
        x = list(range(n))

        # Calculate slope (trend)
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_xx = sum(x[i] * x[i] for i in range(n))

        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope


class AnomalyDetector:
    """Main anomaly detection system."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.statistical_detector = SimpleStatisticalDetector()
        self.trend_detector = TrendDetector()
        self.recent_anomalies: deque = deque(maxlen=1000)

        # Metric configurations
        self.metric_configs = {
            "response_time_p95": {"enable_trend": True, "z_threshold": 2.5},
            "error_rate": {"enable_trend": True, "z_threshold": 2.0},
            "cpu_percent": {"enable_trend": True, "z_threshold": 2.0},
            "memory_percent": {"enable_trend": True, "z_threshold": 2.0},
            "db_query_time": {"enable_trend": True, "z_threshold": 3.0},
            "message_delivery_rate": {"enable_trend": True, "z_threshold": 2.0},
        }

    async def process_metric(
        self, metric_name: str, value: float, timestamp: Optional[datetime] = None
    ) -> List[Anomaly]:
        """Process a metric value and detect anomalies."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        anomalies = []

        # Get configuration for this metric
        config = self.metric_configs.get(metric_name, {})

        # Statistical anomaly detection
        statistical_anomaly = self.statistical_detector.add_value(
            metric_name, value, timestamp
        )
        if statistical_anomaly:
            anomalies.append(statistical_anomaly)

        # Trend detection
        if config.get("enable_trend", True):
            trend_anomaly = self.trend_detector.add_value(metric_name, value, timestamp)
            if trend_anomaly:
                anomalies.append(trend_anomaly)

        # Store anomalies
        for anomaly in anomalies:
            self.recent_anomalies.append(anomaly)

            # Store in Redis
            if self.redis_client:
                await self._store_anomaly_redis(anomaly)

            logger.warning(f"Anomaly detected: {anomaly.description}")

        return anomalies

    async def _store_anomaly_redis(self, anomaly: Anomaly) -> None:
        """Store anomaly in Redis."""
        try:
            anomaly_data = {
                "metric_name": anomaly.metric_name,
                "anomaly_type": anomaly.anomaly_type.value,
                "timestamp": int(anomaly.timestamp.timestamp()),
                "value": anomaly.value,
                "expected_value": anomaly.expected_value,
                "confidence": anomaly.confidence,
                "severity": anomaly.severity,
                "description": anomaly.description,
                "metadata": str(anomaly.metadata),
            }

            await self.redis_client.lpush(
                "anomaly_detector:anomalies", str(anomaly_data)
            )

            # Keep only last 1000 anomalies
            await self.redis_client.ltrim("anomaly_detector:anomalies", 0, 999)

            # Update counters
            await self.redis_client.hincrby(
                "anomaly_detector:counters", f"total_{anomaly.severity}", 1
            )
            await self.redis_client.hincrby(
                "anomaly_detector:counters", f"type_{anomaly.anomaly_type.value}", 1
            )

            # Set expiration
            await self.redis_client.expire("anomaly_detector:counters", 86400)

        except Exception as e:
            logger.error(f"Failed to store anomaly in Redis: {e}")

    def get_recent_anomalies(
        self,
        hours: int = 24,
        severity_filter: Optional[str] = None,
        metric_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent anomalies with optional filtering."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        filtered_anomalies = []
        for anomaly in self.recent_anomalies:
            if anomaly.timestamp < cutoff_time:
                continue

            if severity_filter and anomaly.severity != severity_filter:
                continue

            if metric_filter and anomaly.metric_name != metric_filter:
                continue

            filtered_anomalies.append(
                {
                    "metric_name": anomaly.metric_name,
                    "anomaly_type": anomaly.anomaly_type.value,
                    "timestamp": anomaly.timestamp.isoformat(),
                    "value": anomaly.value,
                    "expected_value": anomaly.expected_value,
                    "confidence": anomaly.confidence,
                    "severity": anomaly.severity,
                    "description": anomaly.description,
                    "metadata": anomaly.metadata,
                }
            )

        # Sort by timestamp (newest first)
        return sorted(filtered_anomalies, key=lambda x: x["timestamp"], reverse=True)

    def get_anomaly_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of anomalies."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        recent_anomalies = [
            a for a in self.recent_anomalies if a.timestamp >= cutoff_time
        ]

        if not recent_anomalies:
            return {
                "time_range_hours": hours,
                "total_anomalies": 0,
                "by_severity": {},
                "by_type": {},
                "by_metric": {},
                "trend": "stable",
            }

        # Count by severity
        by_severity = {}
        for anomaly in recent_anomalies:
            by_severity[anomaly.severity] = by_severity.get(anomaly.severity, 0) + 1

        # Count by type
        by_type = {}
        for anomaly in recent_anomalies:
            type_name = anomaly.anomaly_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1

        # Count by metric
        by_metric = {}
        for anomaly in recent_anomalies:
            by_metric[anomaly.metric_name] = by_metric.get(anomaly.metric_name, 0) + 1

        # Calculate trend
        if len(recent_anomalies) >= 10:
            # Compare first and second half
            mid_point = len(recent_anomalies) // 2
            first_half_count = mid_point
            second_half_count = len(recent_anomalies) - mid_point

            if second_half_count > first_half_count * 1.5:
                trend = "increasing"
            elif second_half_count < first_half_count * 0.5:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "time_range_hours": hours,
            "total_anomalies": len(recent_anomalies),
            "by_severity": by_severity,
            "by_type": by_type,
            "by_metric": by_metric,
            "trend": trend,
        }

    def update_metric_config(self, metric_name: str, config: Dict[str, Any]) -> None:
        """Update configuration for a metric."""
        if metric_name not in self.metric_configs:
            self.metric_configs[metric_name] = {}

        self.metric_configs[metric_name].update(config)

        # Update detector thresholds if provided
        if "z_threshold" in config:
            self.statistical_detector.z_threshold = config["z_threshold"]

    def reset_detectors(self) -> None:
        """Reset all detector state."""
        self.statistical_detector = SimpleStatisticalDetector()
        self.trend_detector = TrendDetector()
        self.recent_anomalies.clear()
