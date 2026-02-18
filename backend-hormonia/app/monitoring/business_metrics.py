"""
Business Metrics Collection System.

Tracks patient flow completion rates, message delivery,
AI response accuracy, user engagement, and treatment adherence.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from enum import Enum
import threading
import statistics
import redis.asyncio as redis
from app.monitoring.prometheus_exporters import metrics_exporter
from app.utils.timezone import now_sao_paulo


logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of business metrics."""

    PATIENT_FLOW = "patient_flow"
    MESSAGE_DELIVERY = "message_delivery"
    AI_RESPONSE = "ai_response"
    USER_ENGAGEMENT = "user_engagement"
    TREATMENT_ADHERENCE = "treatment_adherence"
    QUIZ_COMPLETION = "quiz_completion"
    ALERT_RESOLUTION = "alert_resolution"
    # New quiz-specific metrics
    QUIZ_LINK_GENERATION = "quiz_link_generation"
    QUIZ_ACCESS = "quiz_access"
    QUIZ_SUBMISSION = "quiz_submission"
    TOKEN_ROTATION = "token_rotation"
    FALLBACK_ACTIVATION = "fallback_activation"


@dataclass
class BusinessMetric:
    """A business metric event."""

    metric_type: MetricType
    timestamp: datetime
    patient_id: Optional[str] = None
    user_id: Optional[str] = None
    value: Union[float, int, bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class BusinessMetricsCollector:
    """Collects and aggregates business metrics."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.metrics_buffer: deque = deque(maxlen=10000)
        self.aggregated_stats: Dict[MetricType, Dict[str, Any]] = defaultdict(dict)
        self._lock = threading.Lock()

        # Initialize counters
        self._init_counters()

    def _init_counters(self) -> None:
        """Initialize metric counters."""
        for metric_type in MetricType:
            self.aggregated_stats[metric_type] = {
                "total_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "hourly_counts": deque(maxlen=24),
                "daily_counts": deque(maxlen=30),
                "response_times": deque(maxlen=1000),
                "last_reset": now_sao_paulo(),
            }

    async def record_metric(self, metric: BusinessMetric) -> None:
        """Record a business metric."""
        with self._lock:
            self.metrics_buffer.append(metric)

            # Update aggregated stats
            stats = self.aggregated_stats[metric.metric_type]
            stats["total_count"] += 1

            # Determine success/failure based on metric type and value
            if self._is_success_metric(metric):
                stats["success_count"] += 1
            else:
                stats["failure_count"] += 1

        # Store in Redis
        if self.redis_client:
            try:
                await self._store_metric_redis(metric)
            except Exception as e:
                logger.error(f"Failed to store business metric in Redis: {e}")

    def _is_success_metric(self, metric: BusinessMetric) -> bool:
        """Determine if a metric represents success."""
        if isinstance(metric.value, bool):
            return metric.value

        if metric.metric_type == MetricType.MESSAGE_DELIVERY:
            return metric.metadata.get("delivered", False)
        elif metric.metric_type == MetricType.AI_RESPONSE:
            return metric.metadata.get("accuracy_score", 0) > 0.7
        elif metric.metric_type == MetricType.PATIENT_FLOW:
            return metric.metadata.get("completed", False)
        elif metric.metric_type == MetricType.QUIZ_COMPLETION:
            return metric.metadata.get("completed", False)
        elif metric.metric_type == MetricType.ALERT_RESOLUTION:
            return metric.metadata.get("resolved", False)
        elif metric.metric_type == MetricType.QUIZ_LINK_GENERATION:
            return metric.value is True
        elif metric.metric_type == MetricType.QUIZ_ACCESS:
            return metric.value is True
        elif metric.metric_type == MetricType.QUIZ_SUBMISSION:
            return metric.value is True
        elif metric.metric_type == MetricType.TOKEN_ROTATION:
            return metric.value is True
        elif metric.metric_type == MetricType.FALLBACK_ACTIVATION:
            return metric.value is True
        else:
            return True  # Default to success

    async def _store_metric_redis(self, metric: BusinessMetric) -> None:
        """Store metric in Redis."""
        timestamp = int(metric.timestamp.timestamp())

        metric_data = {
            "type": metric.metric_type.value,
            "timestamp": timestamp,
            "patient_id": metric.patient_id or "",
            "user_id": metric.user_id or "",
            "value": str(metric.value) if metric.value is not None else "",
            "metadata": str(metric.metadata),
            "tags": ",".join(metric.tags),
        }

        # Store individual metric
        await self.redis_client.lpush(
            f"business_metrics:{metric.metric_type.value}", str(metric_data)
        )

        # Keep only last 10000 metrics per type
        await self.redis_client.ltrim(
            f"business_metrics:{metric.metric_type.value}", 0, 9999
        )

        # Update counters
        await self.redis_client.hincrby(
            f"business_metrics:counters:{metric.metric_type.value}", "total", 1
        )

        if self._is_success_metric(metric):
            await self.redis_client.hincrby(
                f"business_metrics:counters:{metric.metric_type.value}", "success", 1
            )
        else:
            await self.redis_client.hincrby(
                f"business_metrics:counters:{metric.metric_type.value}", "failure", 1
            )

        # Set expiration
        await self.redis_client.expire(
            f"business_metrics:counters:{metric.metric_type.value}", 86400
        )

    # Patient Flow Metrics
    async def record_patient_flow_start(self, patient_id: str, flow_type: str) -> None:
        """Record patient flow start."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.PATIENT_FLOW,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                metadata={"action": "start", "flow_type": flow_type},
            )
        )

    async def record_patient_flow_completion(
        self, patient_id: str, flow_type: str, completed: bool, duration_minutes: float
    ) -> None:
        """Record patient flow completion."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.PATIENT_FLOW,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=completed,
                metadata={
                    "action": "complete",
                    "flow_type": flow_type,
                    "completed": completed,
                    "duration_minutes": duration_minutes,
                },
            )
        )

    # Message Delivery Metrics
    async def record_message_sent(self, patient_id: str, message_type: str) -> None:
        """Record message sent."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.MESSAGE_DELIVERY,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                metadata={"action": "sent", "message_type": message_type},
            )
        )

    async def record_message_delivered(
        self,
        patient_id: str,
        message_type: str,
        delivered: bool,
        delivery_time_seconds: float,
    ) -> None:
        """Record message delivery status."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.MESSAGE_DELIVERY,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=delivered,
                metadata={
                    "action": "delivered",
                    "message_type": message_type,
                    "delivered": delivered,
                    "delivery_time_seconds": delivery_time_seconds,
                },
            )
        )

    # AI Response Metrics
    async def record_ai_response(
        self,
        patient_id: str,
        response_type: str,
        accuracy_score: float,
        response_time_ms: float,
    ) -> None:
        """Record AI response accuracy."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.AI_RESPONSE,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=accuracy_score,
                metadata={
                    "response_type": response_type,
                    "accuracy_score": accuracy_score,
                    "response_time_ms": response_time_ms,
                },
            )
        )

    # User Engagement Metrics
    async def record_user_session(
        self,
        user_id: str,
        session_duration_minutes: float,
        pages_viewed: int,
        actions_performed: int,
    ) -> None:
        """Record user engagement session."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.USER_ENGAGEMENT,
                timestamp=now_sao_paulo(),
                user_id=user_id,
                value=session_duration_minutes,
                metadata={
                    "session_duration_minutes": session_duration_minutes,
                    "pages_viewed": pages_viewed,
                    "actions_performed": actions_performed,
                },
            )
        )

    # Treatment Adherence Metrics
    async def record_treatment_adherence(
        self,
        patient_id: str,
        treatment_type: str,
        adherent: bool,
        adherence_percentage: float,
    ) -> None:
        """Record treatment adherence."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.TREATMENT_ADHERENCE,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=adherent,
                metadata={
                    "treatment_type": treatment_type,
                    "adherent": adherent,
                    "adherence_percentage": adherence_percentage,
                },
            )
        )

    # Quiz Completion Metrics
    async def record_quiz_completion(
        self,
        patient_id: str,
        quiz_id: str,
        completed: bool,
        score: float,
        duration_minutes: float,
    ) -> None:
        """Record quiz completion."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.QUIZ_COMPLETION,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=completed,
                metadata={
                    "quiz_id": quiz_id,
                    "completed": completed,
                    "score": score,
                    "duration_minutes": duration_minutes,
                },
            )
        )

    # Enhanced Quiz Metrics for Monthly Quiz System
    async def record_quiz_link_generated(
        self,
        patient_id: str,
        quiz_template_id: str,
        token_prefix: str,
        delivery_method: str,
        expires_at: datetime,
    ) -> None:
        """Record quiz link generation."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.QUIZ_LINK_GENERATION,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=True,
                metadata={
                    "quiz_template_id": quiz_template_id,
                    "token_prefix": token_prefix,
                    "delivery_method": delivery_method,
                    "expires_at": expires_at.isoformat(),
                    "action": "generated",
                },
            )
        )

        # Also record in Prometheus
        metrics_exporter.record_quiz_link_generated(delivery_method)

    async def record_quiz_access_success(
        self,
        patient_id: str,
        quiz_session_id: str,
        ip_address: str,
        user_agent: str,
        access_count: int,
    ) -> None:
        """Record successful quiz access."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.QUIZ_ACCESS,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=True,
                metadata={
                    "quiz_session_id": quiz_session_id,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "access_count": access_count,
                    "action": "access_success",
                },
            )
        )

        # Also record in Prometheus
        metrics_exporter.record_quiz_access_success()

    async def record_quiz_access_failure(
        self, patient_id: str, reason: str, ip_address: str, token_prefix: str
    ) -> None:
        """Record failed quiz access attempt."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.QUIZ_ACCESS,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=False,
                metadata={
                    "reason": reason,
                    "ip_address": ip_address,
                    "token_prefix": token_prefix,
                    "action": "access_failure",
                },
            )
        )

        # Also record in Prometheus
        metrics_exporter.record_quiz_access_failure(reason)

    async def record_quiz_submit_success(
        self,
        patient_id: str,
        quiz_session_id: str,
        question_id: str,
        response_id: str,
        is_encrypted: bool = False,
    ) -> None:
        """Record successful quiz response submission."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.QUIZ_SUBMISSION,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=True,
                metadata={
                    "quiz_session_id": quiz_session_id,
                    "question_id": question_id,
                    "response_id": response_id,
                    "is_encrypted": is_encrypted,
                    "action": "submit_success",
                },
            )
        )

        # Also record in Prometheus
        metrics_exporter.record_quiz_submit_success(is_encrypted=is_encrypted)

    async def record_quiz_submit_failure(
        self, patient_id: str, quiz_session_id: str, question_id: str, reason: str
    ) -> None:
        """Record failed quiz response submission."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.QUIZ_SUBMISSION,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=False,
                metadata={
                    "quiz_session_id": quiz_session_id,
                    "question_id": question_id,
                    "reason": reason,
                    "action": "submit_failure",
                },
            )
        )

        # Also record in Prometheus
        metrics_exporter.record_quiz_submit_failure(reason)

    async def record_token_rotated(
        self,
        patient_id: str,
        quiz_session_id: str,
        old_token_prefix: str,
        new_token_prefix: str,
        rotation_count: int,
    ) -> None:
        """Record token rotation event."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.TOKEN_ROTATION,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=True,
                metadata={
                    "quiz_session_id": quiz_session_id,
                    "old_token_prefix": old_token_prefix,
                    "new_token_prefix": new_token_prefix,
                    "rotation_count": rotation_count,
                    "action": "token_rotated",
                },
            )
        )

        # Also record in Prometheus
        metrics_exporter.record_token_rotated()

    async def record_fallback_activated(
        self,
        patient_id: str,
        quiz_session_id: str,
        reason: str,
        fallback_type: str = "whatsapp",
    ) -> None:
        """Record fallback activation (e.g., WhatsApp conversational flow)."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.FALLBACK_ACTIVATION,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=True,
                metadata={
                    "quiz_session_id": quiz_session_id,
                    "reason": reason,
                    "fallback_type": fallback_type,
                    "action": "fallback_activated",
                },
            )
        )

        # Also record in Prometheus
        metrics_exporter.record_fallback_activated(reason, fallback_type)

    # Alert Resolution Metrics
    async def record_alert_created(
        self, patient_id: str, alert_type: str, severity: str
    ) -> None:
        """Record alert creation."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.ALERT_RESOLUTION,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                metadata={
                    "action": "created",
                    "alert_type": alert_type,
                    "severity": severity,
                },
            )
        )

    async def record_alert_resolved(
        self,
        patient_id: str,
        alert_type: str,
        resolved: bool,
        resolution_time_hours: float,
    ) -> None:
        """Record alert resolution."""
        await self.record_metric(
            BusinessMetric(
                metric_type=MetricType.ALERT_RESOLUTION,
                timestamp=now_sao_paulo(),
                patient_id=patient_id,
                value=resolved,
                metadata={
                    "action": "resolved",
                    "alert_type": alert_type,
                    "resolved": resolved,
                    "resolution_time_hours": resolution_time_hours,
                },
            )
        )

    # Statistics and Analytics
    def get_metric_stats(
        self, metric_type: MetricType, time_range_hours: int = 24
    ) -> Dict[str, Any]:
        """Get statistics for a specific metric type."""
        cutoff_time = now_sao_paulo() - timedelta(hours=time_range_hours)

        with self._lock:
            # Filter metrics by type and time range
            relevant_metrics = [
                m
                for m in self.metrics_buffer
                if m.metric_type == metric_type and m.timestamp >= cutoff_time
            ]

        if not relevant_metrics:
            return {
                "metric_type": metric_type.value,
                "time_range_hours": time_range_hours,
                "total_count": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
            }

        total_count = len(relevant_metrics)
        success_count = sum(1 for m in relevant_metrics if self._is_success_metric(m))
        failure_count = total_count - success_count

        stats = {
            "metric_type": metric_type.value,
            "time_range_hours": time_range_hours,
            "total_count": total_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": (success_count / total_count) * 100,
            "failure_rate": (failure_count / total_count) * 100,
        }

        # Add type-specific statistics
        if metric_type == MetricType.AI_RESPONSE:
            accuracy_scores = [
                m.metadata.get("accuracy_score", 0)
                for m in relevant_metrics
                if "accuracy_score" in m.metadata
            ]
            if accuracy_scores:
                stats["avg_accuracy"] = statistics.mean(accuracy_scores)
                stats["min_accuracy"] = min(accuracy_scores)
                stats["max_accuracy"] = max(accuracy_scores)

        elif metric_type == MetricType.PATIENT_FLOW:
            durations = [
                m.metadata.get("duration_minutes", 0)
                for m in relevant_metrics
                if "duration_minutes" in m.metadata
            ]
            if durations:
                stats["avg_duration_minutes"] = statistics.mean(durations)
                stats["min_duration_minutes"] = min(durations)
                stats["max_duration_minutes"] = max(durations)

        elif metric_type == MetricType.MESSAGE_DELIVERY:
            delivery_times = [
                m.metadata.get("delivery_time_seconds", 0)
                for m in relevant_metrics
                if "delivery_time_seconds" in m.metadata
            ]
            if delivery_times:
                stats["avg_delivery_time_seconds"] = statistics.mean(delivery_times)
                stats["max_delivery_time_seconds"] = max(delivery_times)

        elif metric_type == MetricType.TREATMENT_ADHERENCE:
            adherence_percentages = [
                m.metadata.get("adherence_percentage", 0)
                for m in relevant_metrics
                if "adherence_percentage" in m.metadata
            ]
            if adherence_percentages:
                stats["avg_adherence_percentage"] = statistics.mean(
                    adherence_percentages
                )
                stats["min_adherence_percentage"] = min(adherence_percentages)

        return stats

    def get_all_metrics_summary(self, time_range_hours: int = 24) -> Dict[str, Any]:
        """Get summary of all business metrics."""
        summary = {
            "time_range_hours": time_range_hours,
            "timestamp": now_sao_paulo().isoformat(),
            "metrics": {},
        }

        for metric_type in MetricType:
            summary["metrics"][metric_type.value] = self.get_metric_stats(
                metric_type, time_range_hours
            )

        return summary

    def get_patient_metrics(
        self, patient_id: str, time_range_hours: int = 24
    ) -> Dict[str, Any]:
        """Get metrics for a specific patient."""
        cutoff_time = now_sao_paulo() - timedelta(hours=time_range_hours)

        with self._lock:
            patient_metrics = [
                m
                for m in self.metrics_buffer
                if m.patient_id == patient_id and m.timestamp >= cutoff_time
            ]

        if not patient_metrics:
            return {
                "patient_id": patient_id,
                "time_range_hours": time_range_hours,
                "total_interactions": 0,
                "metrics_by_type": {},
            }

        # Group by metric type
        by_type = defaultdict(list)
        for metric in patient_metrics:
            by_type[metric.metric_type].append(metric)

        metrics_by_type = {}
        for metric_type, metrics in by_type.items():
            success_count = sum(1 for m in metrics if self._is_success_metric(m))
            metrics_by_type[metric_type.value] = {
                "count": len(metrics),
                "success_count": success_count,
                "success_rate": (success_count / len(metrics)) * 100,
            }

        return {
            "patient_id": patient_id,
            "time_range_hours": time_range_hours,
            "total_interactions": len(patient_metrics),
            "metrics_by_type": metrics_by_type,
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self.metrics_buffer.clear()
            self._init_counters()
