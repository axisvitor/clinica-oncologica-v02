# T01: Flow health summary and stall alerting

**Slice:** S03 — **Milestone:** M001

## Description

Create a flow health API endpoint that returns real-time counts of active, stalled, failed, and completed flows, plus a stall alert mechanism that fires structured logs and optional webhook notifications when patients are stuck.

Purpose: Operators need visibility into pipeline health without querying the database directly. Silent stalls must be surfaced proactively.
Output: Flow health service, admin API endpoint, stall alert logic, and unit tests.

## Must-Haves

- [ ] "GET /admin-ext/flow-health/ returns JSON with active, stalled, failed, and completed flow counts"
- [ ] "Stall alert fires a structured log entry when a patient has not progressed in a configurable time window"
- [ ] "Stall alert optionally sends a webhook POST when FLOW_STALL_ALERT_WEBHOOK_URL is configured"
- [ ] "Stall detection threshold is configurable via TASK_FLOW_STALL_ALERT_HOURS env var"

## Files

- `backend-hormonia/app/api/v2/routers/admin_extensions/flow_health.py`
- `backend-hormonia/app/api/v2/routers/admin_extensions/__init__.py`
- `backend-hormonia/app/schemas/v2/admin_extensions.py`
- `backend-hormonia/app/services/flow/health.py`
- `backend-hormonia/app/config/settings/tasks.py`
- `backend-hormonia/tests/unit/services/flow/test_flow_health.py`
- `backend-hormonia/tests/unit/api/test_admin_flow_health.py`
