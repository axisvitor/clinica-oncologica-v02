"""
Resilience Metrics Collection and Monitoring

This package exposes resilience metrics helpers. Flask-only pieces
(`create_metrics_blueprint`) are optional so FastAPI deployments without
Flask installed don't crash during import.
"""

from .collector import ResilienceMetrics, MetricsCollector

try:  # Optional Flask blueprint
    from .dashboard import create_metrics_blueprint  # type: ignore
except Exception:  # pragma: no cover - Flask may be absent

    def create_metrics_blueprint(*_args, **_kwargs):
        raise RuntimeError(
            "create_metrics_blueprint requires Flask. Install Flask or disable the metrics dashboard."
        )


__all__ = ["ResilienceMetrics", "MetricsCollector", "create_metrics_blueprint"]
