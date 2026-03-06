---
phase: 52-flow-observability
plan: 02
subsystem: observability
tags: [prometheus, correlation-id, wuzapi, tracing]
requires:
  - phase: 50-pipeline-reliability
    provides: sequential continuation and send pipeline stages that now receive trace correlation
provides:
  - ai personalization fallback counter with reason labels
  - correlation id propagation from webhook entry through continuation and send
  - focused tests for tracing behavior and webhook payload changes
affects: [phase-53, incident-tracing, flow-observability]
tech-stack:
  added: []
  patterns: [prometheus fallback instrumentation, contextvar-based tracing, webhook correlation echo]
key-files:
  created:
    - backend-hormonia/tests/unit/integrations/test_wuzapi_correlation_id.py
  modified:
    - backend-hormonia/app/services/flow/metrics.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/personalization.py
    - backend-hormonia/app/integrations/wuzapi/webhook.py
    - backend-hormonia/app/services/webhook/handlers/message_handler.py
    - backend-hormonia/app/services/flow/_flow_response_flow.py
    - backend-hormonia/app/services/flow/_flow_message_flow.py
    - backend-hormonia/tests/unit/services/flow/test_flow_metrics.py
    - backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py
key-decisions:
  - "Instrumented every deterministic AI fallback path with explicit reason labels so operators can separate timeout, grounding, and configuration regressions."
  - "Used the existing correlation ContextVar and echoed it back in webhook responses to keep tracing consistent across inbound request handling and downstream flow logs."
patterns-established:
  - "Flow observability now uses module-level Prometheus counters with tiny helper functions so business code only emits semantic reasons."
  - "Webhook tracing begins at ingress: set the correlation ID once, carry it through message handling/flow dispatch, and surface it in both logs and HTTP payloads."
requirements-completed: [OBS-03, OBS-04]
duration: 20m
completed: 2026-03-06
---

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
