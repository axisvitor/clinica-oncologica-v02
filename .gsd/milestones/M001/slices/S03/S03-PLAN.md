# S03: Flow Observability

**Goal:** Create a flow health API endpoint that returns real-time counts of active, stalled, failed, and completed flows, plus a stall alert mechanism that fires structured logs and optional webhook notifications when patients are stuck.
**Demo:** Create a flow health API endpoint that returns real-time counts of active, stalled, failed, and completed flows, plus a stall alert mechanism that fires structured logs and optional webhook notifications when patients are stuck.

## Must-Haves


## Tasks

- [x] **T01: Flow health summary and stall alerting** `est:17m`
  - Create a flow health API endpoint that returns real-time counts of active, stalled, failed, and completed flows, plus a stall alert mechanism that fires structured logs and optional webhook notifications when patients are stuck.

Purpose: Operators need visibility into pipeline health without querying the database directly. Silent stalls must be surfaced proactively.
Output: Flow health service, admin API endpoint, stall alert logic, and unit tests.
- [x] **T02: Correlation propagation and AI fallback metrics** `est:20m`
  - Track AI personalization fallback rate via a Prometheus counter and propagate a correlation ID from webhook entry through every processing step so operators can trace a single patient message through the entire pipeline.

Purpose: Silent AI fallback degrades patient experience without visibility. Operators need to trace any message through webhook -> gate -> continuation -> send to debug issues.
Output: Prometheus counter for fallback rate, correlation ID generation at webhook entry, propagation through processing chain, and unit tests.

## Files Likely Touched

- `backend-hormonia/app/api/v2/routers/admin_extensions/flow_health.py`
- `backend-hormonia/app/api/v2/routers/admin_extensions/__init__.py`
- `backend-hormonia/app/schemas/v2/admin_extensions.py`
- `backend-hormonia/app/services/flow/health.py`
- `backend-hormonia/app/config/settings/tasks.py`
- `backend-hormonia/tests/unit/services/flow/test_flow_health.py`
- `backend-hormonia/tests/unit/api/test_admin_flow_health.py`
- `backend-hormonia/app/services/flow/metrics.py`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/personalization.py`
- `backend-hormonia/app/integrations/wuzapi/webhook.py`
- `backend-hormonia/app/services/webhook/handlers/message_handler.py`
- `backend-hormonia/app/services/flow/_flow_response_flow.py`
- `backend-hormonia/app/services/flow/_flow_message_flow.py`
- `backend-hormonia/tests/unit/services/flow/test_flow_metrics.py`
- `backend-hormonia/tests/unit/integrations/test_wuzapi_correlation_id.py`
