---
phase: 12-flow-orchestration-replacement
plan: 03
subsystem: api
tags: [langgraph, redis, lgpd, flow-orchestration, decommission]
requires:
  - phase: 12-flow-orchestration-replacement
    provides: direct async flow orchestration functions and helper import boundary
provides:
  - Tombstoned app.ai.langgraph module surface with fail-fast ImportError migration guidance
  - Redis checkpoint purge script for langgraph:checkpoint:* keys with LGPD deletion logging
  - Tombstoned LangGraph-focused tests and new verification coverage for tombstones and purge
affects: [ai-framework-migration, flow-runtime, compliance-audit]
tech-stack:
  added: []
  patterns: [tombstone-module-guard, direct-flow-only-tests, redis-scan-iter-purge]
key-files:
  created:
    - backend-hormonia/scripts/purge_langgraph_checkpoints.py
    - backend-hormonia/tests/unit/ai/test_langgraph_tombstone.py
    - backend-hormonia/tests/unit/ai/test_checkpoint_purge.py
  modified:
    - backend-hormonia/app/ai/langgraph/__init__.py
    - backend-hormonia/app/ai/langgraph/graphs.py
    - backend-hormonia/app/ai/langgraph/nodes.py
    - backend-hormonia/app/ai/langgraph/nodes_ai.py
    - backend-hormonia/app/ai/langgraph/prompts.py
    - backend-hormonia/app/ai/langgraph/runtime.py
    - backend-hormonia/app/ai/langgraph/state.py
    - backend-hormonia/app/ai/langgraph/ai_state.py
    - backend-hormonia/app/ai/langgraph/_invoke.py
    - backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py
key-decisions:
  - "Keep legacy LangGraph imports lazy inside sequential_message_handler legacy branches so startup remains safe while legacy mode intentionally fails when invoked."
  - "Use structured CRITICAL logs as primary LGPD deletion evidence and best-effort DB audit logging as secondary channel in the purge script."
patterns-established:
  - "LangGraph decommission guard: tombstone every legacy module with a uniform migration ImportError message."
  - "Compliance purge scripts must use Redis scan_iter batching (never KEYS) and emit legal audit metadata."
requirements-completed: [FLOW-04, FLOW-05]
duration: 19 min
completed: 2026-02-24
---

# Phase 12 Plan 03: LangGraph Tombstone and Checkpoint Purge Summary

**LangGraph was fully decommissioned by hard-tombstoning all nine modules, adding a Redis checkpoint purge utility with LGPD audit logging, and converting legacy LangGraph tests to tombstones while preserving direct-flow verification coverage.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-02-24T17:06:17Z
- **Completed:** 2026-02-24T17:25:32Z
- **Tasks:** 2
- **Files modified:** 19

## Accomplishments
- Replaced every `app.ai.langgraph` file with a consistent tombstone ImportError migration message.
- Added `tests/unit/ai/test_langgraph_tombstone.py` to verify all nine legacy modules fail-fast on import.
- Added `scripts/purge_langgraph_checkpoints.py` with batched `scan_iter` deletion and LGPD audit logging.
- Added `tests/unit/ai/test_checkpoint_purge.py` covering populated and empty key scenarios.
- Tombstoned six LangGraph-specific tests and updated `test_sequential_message_handler.py` to stay on direct flow path.

## Task Commits

Each task was committed atomically:

1. **Task 1: Tombstone LangGraph modules and clean tests** - `b55435b0` (fix)
2. **Task 2: Create checkpoint purge script and tests** - `296ef930` (feat)

## Files Created/Modified
- `backend-hormonia/app/ai/langgraph/__init__.py` - Tombstone guard for package import.
- `backend-hormonia/app/ai/langgraph/graphs.py` - Tombstoned legacy graph builder module.
- `backend-hormonia/app/ai/langgraph/nodes.py` - Tombstoned legacy flow node module.
- `backend-hormonia/app/ai/langgraph/nodes_ai.py` - Tombstoned legacy AI helper node module.
- `backend-hormonia/app/ai/langgraph/prompts.py` - Tombstoned prompt builder module.
- `backend-hormonia/app/ai/langgraph/runtime.py` - Tombstoned LangGraph runtime/checkpointer module.
- `backend-hormonia/app/ai/langgraph/state.py` - Tombstoned LangGraph state module.
- `backend-hormonia/app/ai/langgraph/ai_state.py` - Tombstoned legacy AI state module.
- `backend-hormonia/app/ai/langgraph/_invoke.py` - Tombstoned legacy invocation wrapper.
- `backend-hormonia/scripts/purge_langgraph_checkpoints.py` - Redis purge script with LGPD audit records.
- `backend-hormonia/tests/unit/ai/test_langgraph_tombstone.py` - Parametrized import-failure verification.
- `backend-hormonia/tests/unit/ai/test_checkpoint_purge.py` - Purge behavior unit tests.
- `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` - Direct-flow test harness updates and dependency shims.
- `backend-hormonia/tests/langgraph/test_langgraph_real_flows.py` - Tombstoned obsolete LangGraph test.
- `backend-hormonia/tests/langgraph/test_prompts_pii_redaction.py` - Tombstoned obsolete LangGraph test.
- `backend-hormonia/tests/langgraph/test_runtime_checkpointer_fallback.py` - Tombstoned obsolete LangGraph test.
- `backend-hormonia/tests/langgraph/test_state_validation.py` - Tombstoned obsolete LangGraph test.
- `backend-hormonia/tests/unit/ai/test_nodes_question_variation.py` - Tombstoned obsolete LangGraph unit test.
- `backend-hormonia/tests/unit/ai/test_runtime.py` - Tombstoned obsolete LangGraph runtime unit test.

## Decisions Made
- Kept lazy `from app.ai.langgraph...` imports only inside legacy branches in `SequentialMessageHandler` to avoid startup-time ImportError while preserving explicit failure if legacy mode is invoked.
- Implemented LGPD logging as structured critical events first, with optional DB audit service logging when database session dependencies are available.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Runtime command mismatch (`python` unavailable)**
- **Found during:** Task 1 verification
- **Issue:** Environment lacked `python` executable, causing plan verification command failure.
- **Fix:** Switched verification execution to `python3` equivalents.
- **Files modified:** None (execution adjustment only)
- **Verification:** `python3 -m pytest --noconftest tests/unit/ai/test_langgraph_tombstone.py -x -q`
- **Committed in:** N/A (no code change)

**2. [Rule 3 - Blocking] Missing optional runtime dependency (`langchain_core`) in unit test startup path**
- **Found during:** Task 1 verification of `test_sequential_message_handler.py`
- **Issue:** Import chain for service dependencies failed in this environment before test logic executed.
- **Fix:** Added lightweight in-test module shims and forced direct flow framework fixture to isolate tested behavior from optional integrations.
- **Files modified:** `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py`
- **Verification:** `python3 -m pytest --noconftest tests/unit/services/flow/test_sequential_message_handler.py -x -q`
- **Committed in:** `b55435b0`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** No scope creep; both fixes were required to execute and verify planned work in this environment.

## Issues Encountered
- `pytest` with repository `conftest.py` bootstraps full app startup and hit missing optional dependencies in this environment.
- Resolved by using `--noconftest` for targeted plan-level unit verification and keeping verification evidence command outputs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 12 LangGraph decommission implementation is complete for plan 03 artifacts and verification.
- Ready for phase transition/verification workflow across the completed phase summaries.

---
*Phase: 12-flow-orchestration-replacement*
*Completed: 2026-02-24*

## Self-Check: PASSED
