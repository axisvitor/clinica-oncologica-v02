---
id: T02
parent: S04
milestone: M001
provides:
  - integration coverage for stuck-flow detection and auto-recovery
  - integration coverage for outbound send retry success, backoff, and exhaustion
  - integration coverage for deferred follow-up retry success and terminal failure
requires: []
affects: []
key_files: []
key_decisions: []
patterns_established: []
observability_surfaces: []
drill_down_paths: []
duration: 45m
verification_result: passed
completed_at: 2026-03-06
blocker_discovered: false
---
# T02: Recovery and retry integration tests

**# Phase 53 Plan 02: Recovery And Retry Summary**

## What Happened

# Phase 53 Plan 02: Recovery And Retry Summary

**Stuck-flow detection, auto-recovery, outbound send retry, and deferred follow-up retry now have passing integration coverage against the real task entry points and persisted flow state**

## Performance

- **Duration:** 45m
- **Started:** 2026-03-06T23:11:00-03:00
- **Completed:** 2026-03-06T23:56:06-03:00
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added five recovery-focused integration tests covering stale-flow detection, task-driven recovery, day-advance recovery, idempotency locking, and manual-intervention exhaustion.
- Added five retry-focused integration tests covering send retry success, backoff scheduling, permanent failure recording, follow-up retry success, and follow-up retry exhaustion.
- Verified the full phase-53 suite passes when the pipeline and recovery files run together.

## Task Commits

Each task was committed atomically where practical:

1. **Task 1: Create stuck flow detection and auto-recovery integration tests**
   - `216b41de` (`test`) RED: added failing recovery integration coverage skeleton
   - `e617f4ca` (`test`) GREEN: completed the real recovery task coverage and passing helpers
2. **Task 2: Create outbound send retry and follow-up retry integration tests**
   - `e617f4ca` (`test`) GREEN: expanded the same integration module to cover retry success, backoff, and exhaustion paths

## Files Created/Modified

- `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py` - Covers stuck-flow detection, task-driven recovery, send retry success/backoff/exhaustion, and follow-up retry success/exhaustion.

## Decisions Made

- Reused the real Postgres-backed `db_session` fixture so `find_stuck_flows()` exercises its production JSON and timestamp filters instead of a mocked query chain.
- Patched `retry_failed_flow_send.delay()` back into `retry_failed_flow_send.run()` during the stuck-flow task test so the full recovery path remains synchronous and verifiable inside the test transaction.

## Deviations from Plan

- Both retry sub-tasks landed in the same GREEN commit because they share one integration module, helper layer, and task-context fixture; splitting them after the RED draft would have duplicated setup without improving isolation.

## Issues Encountered

- The retry tasks rely on `async_to_sync()` around async service calls, so the suite needed an explicit bridge helper to keep task execution deterministic under pytest without a worker process.

## User Setup Required

None - the suite runs locally with the existing test environment and `WHATSAPP_WUZAPI_TOKEN=test-token`.

## Next Phase Readiness

- Phase verification can now assert TEST-02 and TEST-03 from passing task-level integration coverage with real persisted flow/message state.
- The recovery suite is safe to run independently or together with the pipeline suite for full phase-53 verification.

## Self-Check: PASSED

- Verified `WHATSAPP_WUZAPI_TOKEN=test-token ./.venv/bin/python -m pytest tests/integration/test_flow_recovery_retry_e2e.py -q` passes.
- Verified `WHATSAPP_WUZAPI_TOKEN=test-token ./.venv/bin/python -m pytest tests/integration/test_flow_pipeline_e2e.py tests/integration/test_flow_recovery_retry_e2e.py -q` passes.
- Verified commit history contains `216b41de` and `e617f4ca`.

---
*Phase: 53-pipeline-verification*
*Completed: 2026-03-06*
