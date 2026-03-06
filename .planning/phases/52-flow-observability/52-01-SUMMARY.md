---
phase: 52-flow-observability
plan: 01
subsystem: api
tags: [flow-health, admin-api, stall-alert, sqlalchemy]
requires:
  - phase: 51-flow-recovery
    provides: stalled/recovery markers and admin extension patterns consumed by flow observability
provides:
  - admin flow health summary endpoint
  - stalled-flow alert fan-out with structured logs and optional webhook
  - response schemas and tests for operator-facing flow observability
affects: [phase-53, admin-extensions, flow-observability]
tech-stack:
  added: []
  patterns: [admin observability endpoints, stalled-flow health queries, optional webhook alerting]
key-files:
  created:
    - backend-hormonia/app/services/flow/health.py
    - backend-hormonia/app/api/v2/routers/admin_extensions/flow_health.py
    - backend-hormonia/tests/unit/services/flow/test_flow_health.py
    - backend-hormonia/tests/unit/api/test_admin_flow_health.py
  modified:
    - backend-hormonia/app/config/settings/tasks.py
    - backend-hormonia/app/api/v2/routers/admin_extensions/__init__.py
    - backend-hormonia/app/schemas/v2/admin_extensions.py
key-decisions:
  - "Kept flow health counts in a dedicated service so the admin router stays thin and testable."
  - "Used structured warnings plus an optional webhook URL for stall alerts so operators can wire notifications without coupling the service to a single vendor."
patterns-established:
  - "Admin observability routes now follow the same auth, rate-limit, audit-log, and Pydantic response pattern as the existing admin extension surface."
  - "Stalled-flow alerting is query-first: derive active/stalled/failed/completed counts from PatientFlowState, then fan out warnings/webhooks from the same stalled set."
requirements-completed: [OBS-01, OBS-02]
duration: 17m
completed: 2026-03-06
---

# Phase 52 Plan 01: Flow Health Summary

**Admin operators can now query real-time flow health counts and trigger stalled-flow alerts backed by structured logging plus optional webhook delivery**

## Performance

- **Duration:** 17m
- **Started:** 2026-03-06T19:31:58-03:00
- **Completed:** 2026-03-06T19:48:55-03:00
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `FlowHealthService` with count queries for active, stalled, failed, and completed flows plus stalled-flow alert payload generation.
- Added `/admin-ext/flow-health/` and `/admin-ext/flow-health/check-stalls` with admin auth, rate limits, and audit logging.
- Covered the service and router with focused unit tests for counts, logging/webhook behavior, response payloads, and auth gating.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create FlowHealthService with count queries and stall alert**
   - `28af7a1e` (`test`) RED: added failing coverage for health summary counts and stalled-flow alert behavior
   - `0f85e686` (`feat`) GREEN: implemented flow health queries, stall alert settings, and optional webhook delivery
2. **Task 2: Create admin flow health API endpoint and wire into admin_extensions**
   - `91b52bf8` (`feat`) GREEN: added admin routes, schemas, router registration, and endpoint-level tests

## Files Created/Modified

- `backend-hormonia/app/services/flow/health.py` - Provides flow health counts and stalled-flow alert execution.
- `backend-hormonia/app/config/settings/tasks.py` - Adds `TASK_FLOW_STALL_ALERT_HOURS` and `TASK_FLOW_STALL_ALERT_WEBHOOK_URL`.
- `backend-hormonia/app/api/v2/routers/admin_extensions/flow_health.py` - Exposes GET health summary and POST stalled-flow checks.
- `backend-hormonia/app/api/v2/routers/admin_extensions/__init__.py` - Registers the new admin flow health router.
- `backend-hormonia/app/schemas/v2/admin_extensions.py` - Adds flow health response models.
- `backend-hormonia/tests/unit/services/flow/test_flow_health.py` - Covers counts, structured warnings, and webhook fan-out behavior.
- `backend-hormonia/tests/unit/api/test_admin_flow_health.py` - Covers endpoint payloads, audit logging, and auth rejection.

## Decisions Made

- Reused `PatientFlowState` plus `Patient.deleted_at` filters instead of persisting a second observability table, keeping the admin view real-time and consistent with live state.
- Returned the stalled-flow list from the POST endpoint so operators can see which patients are affected immediately after running the check.

## Deviations from Plan

- The delegated executor stalled after finishing task 1, so task 2 was completed locally on top of the existing TDD baseline without scope changes.

## Issues Encountered

- The app bootstrap requires `WHATSAPP_WUZAPI_TOKEN`; verification was run with `WHATSAPP_WUZAPI_TOKEN=test-token` to unblock imports during the focused pytest run.

## User Setup Required

- Set `TASK_FLOW_STALL_ALERT_HOURS` if the default 6-hour stalled threshold should be changed.
- Set `TASK_FLOW_STALL_ALERT_WEBHOOK_URL` to send stalled-flow payloads to an external alerting endpoint.

## Next Phase Readiness

- Operators now have a real-time health surface and explicit stalled-flow alerts to pair with the recovery mechanics built in Phase 51.
- Phase 53 can verify these observability surfaces end-to-end alongside pipeline retry and recovery scenarios.

## Self-Check: PASSED

- Verified `WHATSAPP_WUZAPI_TOKEN=test-token ./.venv/bin/python -m pytest tests/unit/services/flow/test_flow_health.py tests/unit/api/test_admin_flow_health.py tests/unit/services/flow/test_flow_metrics.py tests/unit/integrations/test_wuzapi_correlation_id.py tests/integrations/wuzapi/test_wuzapi_webhook.py -x -q` passes.
- Verified commits `28af7a1e`, `0f85e686`, and `91b52bf8` exist in git history.

---
*Phase: 52-flow-observability*
*Completed: 2026-03-06*
