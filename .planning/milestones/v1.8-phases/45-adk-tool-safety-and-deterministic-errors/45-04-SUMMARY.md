---
phase: 45-adk-tool-safety-and-deterministic-errors
plan: 04
subsystem: api
tags: [adk, policy, runtime, safety, regression]
requires:
  - phase: 45-adk-tool-safety-and-deterministic-errors
    provides: runtime policy evaluation and deterministic ADK error classes from plans 45-01 through 45-03
provides:
  - Immutable operator policy keys in runner callback context resolution
  - Immutable operator policy keys in ADK tool dispatch context merging
  - Negative regression coverage for tool-call policy overwrite and fabricated required-context bypasses
affects: [phase-46, adk-runtime, verification]
tech-stack:
  added: []
  patterns: [protected policy key restoration, required-context path restoration]
key-files:
  created: []
  modified:
    - backend-hormonia/app/ai/adk/runtime.py
    - backend-hormonia/app/ai/adk/tools.py
    - backend-hormonia/tests/unit/test_adk_tools_runtime.py
key-decisions:
  - "Runner callback policy evaluation restores operator-owned required-context paths before evaluating `required_context_keys`, so model-generated tool args cannot satisfy missing-context policies."
  - "Tool dispatch continues to merge non-policy context for approved executions, but always restores operator `tool_policy`, `policy`, and `required_context_keys` metadata after `context_json` merge."
patterns-established:
  - "Callback-time policy evaluation trusts operator context for protected policy keys and policy-required context paths only."
  - "ADK dispatch merges may enrich non-policy payloads, but protected policy metadata is immutable once set by the operator."
requirements-completed: [ADK-11, ADK-12]
duration: 4m
completed: 2026-03-05
---

# Phase 45 Plan 04: ADK Tool Safety and Deterministic Errors Summary

**Runner and tool-dispatch context merges now preserve operator ADK policy metadata and reject fabricated required-context bypasses**

## Performance

- **Duration:** 4m
- **Started:** 2026-03-05T21:48:58-03:00
- **Completed:** 2026-03-05T21:53:20-03:00
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Hardened `runtime.py:_resolve_callback_context()` so model-supplied `context_json` and `context` can no longer overwrite operator `tool_policy`, `policy`, or `required_context_keys`.
- Restored operator-owned required-context paths during callback evaluation so fabricated tool-call payloads cannot satisfy missing-context policy checks.
- Preserved operator policy metadata inside `tools.py:_merge_context()` and added four negative regressions, then re-ran the full Phase 45 suite with only the expected local `google-adk` skips.

## Task Commits

Each task was committed atomically:

1. **Task 1: Harden context merge to protect operator-supplied policy keys from tool-call overwrite** - `f1e93352` (test), `72a72d31` (feat)
2. **Task 2: Re-run full Phase 45 suite and confirm zero regressions** - `969c1732` (test)

**Plan metadata:** to be committed separately in this run

_Note: Task 1 used TDD and therefore produced separate RED and GREEN commits._

## Files Created/Modified

- `backend-hormonia/app/ai/adk/runtime.py` - Restores protected policy keys and required policy paths before callback-time policy evaluation.
- `backend-hormonia/app/ai/adk/tools.py` - Restores protected policy keys after ADK tool dispatch `context_json` merges.
- `backend-hormonia/tests/unit/test_adk_tools_runtime.py` - Adds four negative regressions covering callback overwrite attempts, fabricated required context, and tool-dispatch merge preservation.

## Decisions Made

- Protected-key restoration stays O(1) and localized to the merge layer instead of deep-copying full clinical contexts.
- Callback evaluation uses operator-owned values for any path referenced by `required_context_keys`, while approved tool execution may still receive additional non-policy context.
- The local Phase 45 regression contract continues to treat real `google-adk` integration coverage as conditional when the package is unavailable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restore required policy paths during callback merge**
- **Found during:** Task 1 (Harden context merge to protect operator-supplied policy keys from tool-call overwrite)
- **Issue:** Restoring only `tool_policy`, `policy`, and `required_context_keys` still allowed fabricated `patient_context.*` values from tool-call args to satisfy operator `required_context_keys` checks.
- **Fix:** Added targeted path restoration/removal for operator-owned required-context paths before `_evaluate_tool_policy()` runs.
- **Files modified:** `backend-hormonia/app/ai/adk/runtime.py`
- **Verification:** `cd backend-hormonia && pytest tests/unit/test_adk_tools_runtime.py -q -k "override" --tb=short`
- **Committed in:** `72a72d31` (part of Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The extra fix stayed inside the planned merge layer, was required for correctness, and closed the exact fabricated-context bypass the verification gap described.

## Issues Encountered

- A transient `git index.lock` conflict occurred when `git status` and `git commit` were accidentally run in parallel during execution; no repository data was changed, the stale lock was cleared, and task commits proceeded sequentially.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The ADK-11 runner-path policy bypass is closed in local code and regression coverage.
- Phase 45 is ready for verification/state closeout with the same documented conditional `google-adk` follow-up for environments where the package is installed.

## Self-Check: PASSED

- Verified `.planning/phases/45-adk-tool-safety-and-deterministic-errors/45-04-SUMMARY.md` exists on disk.
- Verified task commits `f1e93352`, `72a72d31`, and `969c1732` exist in git history.

---
*Phase: 45-adk-tool-safety-and-deterministic-errors*
*Completed: 2026-03-05*
