"""
Prometheus metrics for WhatsApp integration.
"""

from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST


class WhatsAppMetrics:
    """Prometheus metrics registry for WhatsApp integration."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()

        self.messages_sent_total = Counter(
            "whatsapp_messages_sent_total",
            "Total WhatsApp messages sent",
            ["instance", "status"],
            registry=self.registry,
        )
        self.messages_failed_total = Counter(
            "whatsapp_messages_failed_total",
            "Total WhatsApp messages failed",
            ["instance", "reason"],
            registry=self.registry,
        )
        self.webhook_events_total = Counter(
            "whatsapp_webhook_events_total",
            "Total WhatsApp webhook events",
            ["instance", "event_type"],
            registry=self.registry,
        )
        self.webhook_duplicates_total = Counter(
            "whatsapp_webhook_duplicates_total",
            "Total duplicate WhatsApp webhook events",
            ["instance"],
            registry=self.registry,
        )
        self.queue_size = Gauge(
            "whatsapp_queue_size",
            "Current WhatsApp queue size",
            ["instance"],
            registry=self.registry,
        )
        self.dlq_size = Gauge(
            "whatsapp_dlq_size",
            "Current WhatsApp DLQ size",
            ["instance"],
            registry=self.registry,
        )
        self.message_send_duration = Histogram(
            "whatsapp_message_send_duration_seconds",
            "WhatsApp message send duration",
            ["instance"],
            registry=self.registry,
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )
        self.webhook_processing_duration = Histogram(
            "whatsapp_webhook_processing_duration_seconds",
            "WhatsApp webhook processing duration",
            ["instance", "event_type"],
            registry=self.registry,
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        )
        self.circuit_breaker_state = Gauge(
            "whatsapp_circuit_breaker_state",
            "WhatsApp circuit breaker state (0=closed,1=open,2=half_open)",
            ["instance", "breaker_name"],
            registry=self.registry,
        )
        self.rate_limit_hits_total = Counter(
            "whatsapp_rate_limit_hits_total",
            "Total WhatsApp rate limit hits",
            ["limiter"],
            registry=self.registry,
        )

    def record_message_sent(self, instance: str, status: str) -> None:
        self.messages_sent_total.labels(instance=instance, status=status).inc()

    def record_message_failed(self, instance: str, reason: str) -> None:
        self.messages_failed_total.labels(instance=instance, reason=reason).inc()

    def record_webhook_event(self, instance: str, event_type: str) -> None:
        self.webhook_events_total.labels(instance=instance, event_type=event_type).inc()

    def record_webhook_duplicate(self, instance: str) -> None:
        self.webhook_duplicates_total.labels(instance=instance).inc()

    def observe_message_send_duration(self, instance: str, duration: float) -> None:
        self.message_send_duration.labels(instance=instance).observe(duration)

    def observe_webhook_processing_duration(
        self, instance: str, event_type: str, duration: float
    ) -> None:
        self.webhook_processing_duration.labels(
            instance=instance, event_type=event_type
        ).observe(duration)

    def set_queue_size(self, instance: str, size: int) -> None:
        self.queue_size.labels(instance=instance).set(size)

    def set_dlq_size(self, instance: str, size: int) -> None:
        self.dlq_size.labels(instance=instance).set(size)

    def set_circuit_breaker_state(
        self, instance: str, breaker_name: str, state: str
    ) -> None:
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        value = state_map.get(state, 0)
        self.circuit_breaker_state.labels(
            instance=instance, breaker_name=breaker_name
        ).set(value)

    def record_rate_limit_hit(self, limiter: str) -> None:
        self.rate_limit_hits_total.labels(limiter=limiter).inc()

    def render_prometheus(self) -> str:
        return generate_latest(self.registry).decode("utf-8")

    @property
    def content_type(self) -> str:
        return CONTENT_TYPE_LATEST


whatsapp_metrics = WhatsAppMetrics()
