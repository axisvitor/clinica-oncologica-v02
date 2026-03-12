---
id: S01
parent: M001
milestone: M001
provides:
  - Counter-based recovery for sequential gate context mismatches instead of silent permanent waiting
  - Structured reset semantics for awaiting_response and pending_response_context after repeated mismatch failures
  - Regression coverage for mismatch counting, reset, and success-path counter clearing
  - Celery retry task for failed outbound flow sends with exponential backoff and jitter
  - Background retry enqueueing when sequential flow sends fail or return false
  - Permanent-failure bookkeeping in flow state when retry exhaustion is reached
  - Celery retry task for deferred follow-up sends that fail during execution
  - Scheduler-backed MessageExecutor retry enqueueing instead of silent follow-up drops
  - Atomic day completion helper with optimistic locking and verification flagging
  - Dedicated structural validation for template day_config payloads
  - Fail-fast flow-start behavior with explicit validation_errors payloads
  - Safety-net handling at send-day entry for propagated validation failures
requires: []
affects: []
key_files: []
key_decisions:
  - "Reset `awaiting_response` only after hitting `MAX_CONTEXT_MISMATCH_RETRIES`, preserving normal waiting behavior for transient mismatches."
  - "Clear `context_mismatch_count` on the next successful match so self-correcting retries do not accumulate stale failure history."
  - "Persist permanent delivery failures into active flow state so later recovery/observability phases can surface the exact broken message."
  - "Extract retry enqueueing into `delivery.py` to keep `sequencing.py` under the enforced 500-line split contract."
  - "Retry deferred follow-up sends through Celery using persisted follow-up metadata so execution failures are re-queued instead of disappearing in-process."
  - "Move day completion into `advance_day_atomic()` so `day_complete` and verification metadata are written in a controlled optimistic-lock flow."
  - "Keep `None`/missing day configs on the existing skip path while treating structurally malformed configs as explicit errors with `validation_errors` details."
  - "Catch propagated `DayConfigValidationError` at `send_day_messages()` as a safety net so callers get a deterministic error payload rather than a generic exception."
patterns_established:
  - "Sequential-gate mismatch handling now records a bounded counter in `step_data` and emits structured warning logs only on the terminal reset path."
  - "Sequential flow delivery failures now fan out into Celery retries without blocking the immediate caller path."
  - "Silent follow-up send failures now transition into explicit retry or terminal-failure state updates."
  - "Template validation now aggregates all structural errors before failing, making operator diagnosis explicit at flow start."
observability_surfaces: []
drill_down_paths: []
duration: 12m
verification_result: passed
completed_at: 2026-03-06
blocker_discovered: false
---
# S01: Pipeline Reliability

**# Phase 50 Plan 01: Sequential Gate Context Mismatch Recovery Summary**

## What Happened

# Phase 50 Plan 01: Sequential Gate Context Mismatch Recovery Summary

**Sequential gate mismatches now recover deterministically instead of leaving the patient stuck in a silent waiting state**

## Performance

- **Duration:** 25m
- **Started:** 2026-03-06T16:01:03-03:00
- **Completed:** 2026-03-06T16:26:19-03:00
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments

- Added `context_mismatch_count` tracking plus `reset_awaiting_on_mismatch_limit()` so repeated correlation failures eventually clear `awaiting_response` and `pending_response_context`.
- Updated `load_response_context()` to persist mismatch counts, emit structured warning logs on terminal reset, and clear the counter again after a valid self-correcting match.
- Verified the behavior with dedicated mismatch-recovery tests covering incremental waiting, terminal reset, successful counter clearing, and default context behavior preservation.

## Task Commits

Task 1 executed via a TDD pair:

1. **Failing coverage for mismatch recovery** - `2480f535` (test)
2. **Implement mismatch counter + reset flow recovery** - `1c939b1b` (feat)

## Files Created/Modified

- `backend-hormonia/app/services/flow/_flow_response_flow.py` - Persists mismatch counters, resets terminally stuck wait state, and clears counters after successful correlation.
- `backend-hormonia/app/services/flow/sequential_response_gate.py` - Adds the mismatch limit constant and helper that normalizes reset-vs-waiting results.
- `backend-hormonia/tests/unit/services/flow/test_sequential_gate_mismatch_recovery.py` - Covers mismatch increments, reset behavior, and success-path cleanup.
- `.planning/phases/50-pipeline-reliability/50-01-SUMMARY.md` - Records the completed recovery work and verification evidence.

## Deviations from Plan

- The first delegated executor stalled after producing only the failing test commit. The implementation was completed locally against that TDD baseline without changing the task scope.

## Self-Check: PASSED

- Verified `backend-hormonia/tests/unit/services/flow/test_sequential_gate_mismatch_recovery.py` passes.
- Verified `tests/unit/services/flow -k "not 30_days"` passes with the mismatch recovery changes included.
- Verified commits `2480f535` and `1c939b1b` exist in git history.

---
*Phase: 50-pipeline-reliability*
*Completed: 2026-03-06*

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

# Phase 50 Plan 03: Deferred Follow-Up Retry And Atomic Day Advancement Summary

**Deferred follow-up send failures now retry in the background, and day completion writes verification metadata instead of leaving silent inconsistent state**

## Performance

- **Duration:** 20m
- **Started:** 2026-03-06T16:26:11-03:00
- **Completed:** 2026-03-06T16:46:04-03:00
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added `retry_failed_followup_send`, a Celery task that replays deferred follow-up message actions with backoff and jitter, updates Redis-backed action status on success, and marks terminal failures explicitly after retry exhaustion.
- Updated `MessageExecutor` and `FollowUpSystemService` so deferred message execution failures enqueue the retry task through a scheduler callback instead of being silently dropped.
- Added `advance_day_atomic()` and routed sequential day-completion paths through it so optimistic-lock version checks, `day_complete`, and `day_advance_verified` writes happen in a deterministic verified flow.

## Task Commits

Each task was committed atomically:

1. **Task 1: Retry failed deferred follow-up sends** - `695dccb3` (feat)
2. **Task 2: Verify day completion with atomic advancement helper** - `5d8de8d7` (feat)

## Files Created/Modified

- `backend-hormonia/app/tasks/flows/followup_retry.py` - Implements the deferred follow-up retry task, retry schedule, and terminal failure bookkeeping.
- `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py` - Covers retry success, retry scheduling, missing-action skips, and terminal failure handling.
- `backend-hormonia/app/services/follow_up_system/execution/message.py` - Enqueues retry work when deferred follow-up message execution fails.
- `backend-hormonia/app/services/follow_up_system/service.py` - Injects the scheduler-backed retry path into `MessageExecutor`.
- `backend-hormonia/app/tasks/flows/__init__.py` - Exports the new follow-up retry task for Celery autodiscovery.
- `backend-hormonia/app/services/flow/management/advancement.py` - Adds `advance_day_atomic()` with optimistic-lock version checks and verification writes.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` - Replaces inline day-completion writes with the shared atomic advancement helper.
- `backend-hormonia/tests/unit/services/test_day_advancement_atomic.py` - Verifies successful verification writes, commit failure behavior, and optimistic-lock handling.

## Deviations from Plan

- The implementation routes multiple deferred message action types through the retryable message executor path so the retry protection covers the real follow-up execution surface instead of a narrower single action branch.

## Self-Check: PASSED

- Verified `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py` passes.
- Verified `backend-hormonia/tests/unit/services/test_day_advancement_atomic.py` passes.
- Verified `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler_split_contract.py` passes after the day-completion refactor.
- Verified `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py -k "completes_day_if_all_non_response"` passes with atomic advancement enabled.
- Verified `backend-hormonia/tests/unit/services/flow -k "not 30_days"` passes with the new advancement helper.
- Verified `backend-hormonia/tests/tasks/test_follow_up_tasks.py` and `backend-hormonia/tests/services/follow_up_system/test_message_scheduler_integration.py` pass with deferred retry wiring enabled.
- Verified commits `695dccb3` and `5d8de8d7` exist in git history.

---
*Phase: 50-pipeline-reliability*
*Completed: 2026-03-06*

# Phase 50 Plan 04: Template Day Config Validation Summary

**Flow startup now validates template day configs up front and fails fast with explicit validation details instead of progressing with malformed data**

## Performance

- **Duration:** 12m
- **Started:** 2026-03-06T16:14:22-03:00
- **Completed:** 2026-03-06T16:26:10-03:00
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `validate_day_config()` plus `DayConfigValidationError`, covering invalid shapes, missing `messages`, blank/typed `content`, invalid `send_mode`, loose boolean coercion, and multi-error accumulation.
- Updated `load_flow_context()` to validate day configs before message dispatch, returning explicit `validation_errors` and structured warning logs instead of generic type failures.
- Added a safety-net `DayConfigValidationError` handler at `send_day_messages()` and shared the response/logging path through `delivery.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create day_config validation module + tests** - `64ec1000` (feat)
2. **Task 2: Fail fast from flow loading / send-day entry** - `6ab4208c` (shared feat with 50-02)

## Files Created/Modified

- `backend-hormonia/app/services/flow/config_validation.py` - Implements structural validation, normalization, and aggregated error reporting for day configs.
- `backend-hormonia/tests/unit/services/flow/test_day_config_validation.py` - Covers valid configs, malformed structures, blank content, invalid send modes, bool coercion, and multiple simultaneous validation failures.
- `backend-hormonia/app/services/flow/_flow_message_flow.py` - Validates configs early and returns explicit error payloads with `validation_errors`.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` - Catches propagated validation errors at the send-day entry point.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/delivery.py` - Centralizes the send-day validation error response to keep `sequencing.py` within the package split contract.

## Deviations from Plan

- The shared `sequencing.py` integration commit also carried the outbound-retry wiring from Plan `50-02`, because both plans touched the same orchestration boundary and the split-contract test required extracting shared helpers.

## Self-Check: PASSED

- Verified `backend-hormonia/tests/unit/services/flow/test_day_config_validation.py` passes.
- Verified `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler_split_contract.py` passes after the helper extraction.
- Verified `tests/unit/services/flow -k "not 30_days"` passes with fail-fast validation enabled.
- Verified commits `64ec1000` and `6ab4208c` exist in git history.

---
*Phase: 50-pipeline-reliability*
*Completed: 2026-03-06*
