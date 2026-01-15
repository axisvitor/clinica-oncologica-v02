# Observability Status

Logging:
- 45 logger statements in `app/orchestration/saga_orchestrator/`.
- Some logs include `extra` metadata, but many are plain strings.
- Added step and transaction duration logs (this change).

Metrics:
- No Prometheus counters/histograms found in saga orchestrator modules.

Alerts:
- Alerting exists for max retry failures in `backend-hormonia/app/tasks/saga_retry.py` via `_alert_admin_max_retries_exceeded()`.

Tracing:
- No OpenTelemetry tracing in saga orchestrator modules.
