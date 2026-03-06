---
phase: 50-pipeline-reliability
plan: 02
subsystem: messaging
tags: [flow, celery, retry, whatsapp]
provides:
  - Celery retry task for failed outbound flow sends with exponential backoff and jitter
  - Background retry enqueueing when sequential flow sends fail or return false
  - Permanent-failure bookkeeping in flow state when retry exhaustion is reached
affects: [outbound-delivery, celery, sequential-message-handler]
tech-stack:
  added: []
  patterns: [background retry task, exponential backoff with jitter, permanent failure bookkeeping]
key-files:
  created:
    - .planning/phases/50-pipeline-reliability/50-02-SUMMARY.md
    - backend-hormonia/app/tasks/flows/send_retry.py
    - backend-hormonia/tests/unit/tasks/test_send_retry_task.py
  modified:
    - backend-hormonia/app/tasks/flows/__init__.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py
    - backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py
key-decisions:
  - "Persist permanent delivery failures into active flow state so later recovery/observability phases can surface the exact broken message."
  - "Extract retry enqueueing into `delivery.py` to keep `sequencing.py` under the enforced 500-line split contract."
patterns-established:
  - "Sequential flow delivery failures now fan out into Celery retries without blocking the immediate caller path."
requirements-completed: [FLOW-02]
duration: 12m
completed: 2026-03-06
---

# Phase 50 Plan 02: Outbound Message Send Retry Summary

**Failed outbound flow sends now enqueue background retries with bounded backoff instead of silently stalling the patient flow**

## Performance

- **Duration:** 12m
- **Started:** 2026-03-06T16:14:22-03:00
- **Completed:** 2026-03-06T16:26:10-03:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `retry_failed_flow_send`, a Celery task that reloads the message, reuses stored `flow_context`, retries with exponential backoff plus jitter, and marks terminal failures explicitly after exhaustion.
- Wired `_send_flow_message()` so both initial-send failures and resend failures enqueue the retry task with structured warning logs.
- Preserved the package split contract by moving shared delivery helpers into `sequential_message_handler_pkg/delivery.py` and updating `state.py` to use the shared idempotency-key helper.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create outbound flow send retry task + tests** - `10713f28` (feat)
2. **Task 2: Enqueue retries from sequential flow delivery path** - `6ab4208c` (shared feat with 50-04)

## Files Created/Modified

- `backend-hormonia/app/tasks/flows/send_retry.py` - Implements the Celery retry task, backoff calculation, idempotent skip paths, and permanent failure recording.
- `backend-hormonia/tests/unit/tasks/test_send_retry_task.py` - Covers success, retry scheduling, false-result retry, exhaustion, and flow-context preservation.
- `backend-hormonia/app/tasks/flows/__init__.py` - Exports the retry task for Celery autodiscovery.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` - Enqueues the retry task when outbound sends fail.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py` - Centralizes retry enqueueing plus shared delivery helpers introduced to preserve the package split contract.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` - Reuses the shared idempotency-key helper after the split-contract refactor.

## Deviations from Plan

- The overlapping `sequencing.py` work for Plans `50-02` and `50-04` shipped in one shared integration commit (`6ab4208c`) because both plans modified the same boundary and the split-contract test required a common helper extraction.

## Self-Check: PASSED

- Verified `backend-hormonia/tests/unit/tasks/test_send_retry_task.py` passes.
- Verified `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler_split_contract.py` passes after the helper extraction.
- Verified `tests/unit/services/flow -k "not 30_days"` passes with retry wiring enabled.
- Verified commits `10713f28` and `6ab4208c` exist in git history.

---
*Phase: 50-pipeline-reliability*
*Completed: 2026-03-06*
