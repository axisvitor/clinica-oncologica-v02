---
id: S03
parent: M001
milestone: M001
provides:
  - admin flow health summary endpoint
  - stalled-flow alert fan-out with structured logs and optional webhook
  - response schemas and tests for operator-facing flow observability
  - ai personalization fallback counter with reason labels
  - correlation id propagation from webhook entry through continuation and send
  - focused tests for tracing behavior and webhook payload changes
requires: []
affects: []
key_files: []
key_decisions:
  - "Kept flow health counts in a dedicated service so the admin router stays thin and testable."
  - "Used structured warnings plus an optional webhook URL for stall alerts so operators can wire notifications without coupling the service to a single vendor."
  - "Instrumented every deterministic AI fallback path with explicit reason labels so operators can separate timeout, grounding, and configuration regressions."
  - "Used the existing correlation ContextVar and echoed it back in webhook responses to keep tracing consistent across inbound request handling and downstream flow logs."
patterns_established:
  - "Admin observability routes now follow the same auth, rate-limit, audit-log, and Pydantic response pattern as the existing admin extension surface."
  - "Stalled-flow alerting is query-first: derive active/stalled/failed/completed counts from PatientFlowState, then fan out warnings/webhooks from the same stalled set."
  - "Flow observability now uses module-level Prometheus counters with tiny helper functions so business code only emits semantic reasons."
  - "Webhook tracing begins at ingress: set the correlation ID once, carry it through message handling/flow dispatch, and surface it in both logs and HTTP payloads."
observability_surfaces: []
drill_down_paths: []
duration: 20m
verification_result: passed
completed_at: 2026-03-06
blocker_discovered: false
---
# S03: Flow Observability

**# Phase 52 Plan 01: Flow Health Summary**

## What Happened

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

# Phase 52 Plan 02: Correlation and Fallback Metrics Summary

**AI personalization fallbacks now emit Prometheus reason metrics, and every WuzAPI message receives a correlation ID that follows webhook ingress through continuation and send logs**

## Performance

- **Duration:** 20m
- **Started:** 2026-03-06T19:29:27-03:00
- **Completed:** 2026-03-06T19:49:31-03:00
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Added `ai_personalization_fallback_total` plus reason-based instrumentation for every deterministic fallback branch in `PersonalizationMixin`.
- Generated or reused `X-Correlation-ID` at WuzAPI ingress, echoed it in webhook responses, and propagated it through webhook, flow-context, continuation, and outbound-send logs.
- Added focused tracing tests and updated existing WuzAPI integration coverage to account for the new correlation payload field.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Prometheus fallback counter and instrument PersonalizationMixin**
   - `6b4f2e02` (`test`) RED: added failing fallback-metric coverage
   - `a2d302d0` (`feat`) GREEN: implemented the counter helper and wired every fallback path
2. **Task 2: Generate correlation ID at webhook entry and propagate through processing chain**
   - `c40c23d3` (`feat`) GREEN: added correlation propagation, webhook payload updates, and focused tracing tests

## Files Created/Modified

- `backend-hormonia/app/services/flow/metrics.py` - Defines the Prometheus fallback counter and helper export.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/personalization.py` - Records a labeled metric for every deterministic fallback branch.
- `backend-hormonia/app/integrations/wuzapi/webhook.py` - Sets/echoes correlation IDs and enriches webhook logs and responses.
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` - Carries correlation IDs through inbound processing, continuation dispatch, and outbound send logs.
- `backend-hormonia/app/services/flow/_flow_response_flow.py` - Logs correlation-aware response-context loading and continuation dispatch.
- `backend-hormonia/app/services/flow/_flow_message_flow.py` - Logs correlation-aware flow-context loading and send-mode dispatch.
- `backend-hormonia/tests/unit/services/flow/test_flow_metrics.py` - Covers metric increments and fallback reason separation.
- `backend-hormonia/tests/unit/integrations/test_wuzapi_correlation_id.py` - Covers header reuse, generated IDs, and ContextVar propagation.
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py` - Keeps integration expectations aligned with the new `correlation_id` field.

## Decisions Made

- Used the existing `correlation_id` ContextVar instead of introducing a second trace primitive, which keeps middleware, webhook handlers, and structured logging aligned.
- Extended the existing WuzAPI integration test instead of replacing it so the payload contract change is covered alongside the previous webhook behaviors.

## Deviations from Plan

- The delegated executor completed task 1 but stalled before task 2; correlation propagation and final verification were finished locally against the committed task-1 baseline.
- The task-2 verification also touched `tests/integrations/wuzapi/test_wuzapi_webhook.py` so the existing integration assertion reflects the new `correlation_id` response field.

## Issues Encountered

- The app import path validates `WHATSAPP_WUZAPI_TOKEN` during bootstrap, so verification required `WHATSAPP_WUZAPI_TOKEN=test-token` in the test command.

## User Setup Required

None - no external service setup is required for the Prometheus counter or correlation propagation itself.

## Next Phase Readiness

- Phase 53 can now assert both metric emission and trace continuity across webhook ingress, continuation, and outbound send paths.
- Operators have enough trace context to connect observability alerts from plan 52-01 back to the exact inbound message path that triggered them.

## Self-Check: PASSED

- Verified `WHATSAPP_WUZAPI_TOKEN=test-token ./.venv/bin/python -m pytest tests/unit/services/flow/test_flow_health.py tests/unit/api/test_admin_flow_health.py tests/unit/services/flow/test_flow_metrics.py tests/unit/integrations/test_wuzapi_correlation_id.py tests/integrations/wuzapi/test_wuzapi_webhook.py -x -q` passes.
- Verified commits `6b4f2e02`, `a2d302d0`, and `c40c23d3` exist in git history.

---
*Phase: 52-flow-observability*
*Completed: 2026-03-06*
