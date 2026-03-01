---
phase: 30-flow-integration-trace
plan: 03
subsystem: api
tags: [trace, flow-coordinator, saga, celery, sqlalchemy]

requires:
  - phase: 29-saga-module-audit
    provides: verified saga split modules and baseline integration assumptions
provides:
  - End-to-end TRACE-04 document for FlowCoordinatorAgent decision path
  - Data-shape and handoff mapping from payload to decision execution
  - Saga-agent indirect relationship verification via PatientFlowState integrity matrix
affects: [31-compensation-integrity, 32-test-coverage]

tech-stack:
  added: []
  patterns: [code-trace documentation, caller-callee handoff matrix, field-level integrity mapping]

key-files:
  created: [backend-hormonia/docs/traces/30-03-agent-decision-engine-trace.md]
  modified: [backend-hormonia/docs/traces/30-03-agent-decision-engine-trace.md]

key-decisions:
  - "FlowCoordinatorAgent does not directly invoke SagaOrchestrator; relationship is indirect through PatientFlowState persisted by onboarding saga."
  - "Current beat/task wiring processes daily flows through flow tasks and batch handlers, not through direct FlowCoordinatorAgent scheduling."
  - "Session split remains intentional for this trace: saga path async API session, agent path sync worker/session context."

patterns-established:
  - "Trace Pattern: document trigger -> context builder -> decision engine -> executor dispatch with explicit caller/callee contracts"
  - "Integrity Pattern: verify producer/consumer DB contract field-by-field before compensation/test phases"

requirements-completed: [TRACE-04]

duration: 2 min
completed: 2026-03-01
---

# Phase 30 Plan 03: Agent Decision Engine Trace Summary

**FlowCoordinatorAgent decision chain is fully traced from Celery-triggered daily flow processing context through FlowContext construction, deterministic FlowDecision selection, and action dispatch, with saga linkage verified as an indirect DB-mediated contract.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-28T22:28:13-03:00
- **Completed:** 2026-03-01T01:31:08Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Traced the full `FlowCoordinatorAgent._process_daily_flow` call chain and documented all handoffs.
- Documented `FlowContext` and `FlowDecision` data shapes with source queries and decision criteria.
- Verified and documented the saga-agent indirect relationship via `PatientFlowState` with a field-level integrity table and session-type analysis.

## Task Commits

Each task was committed atomically:

1. **Task 1: Trace FlowCoordinatorAgent execution path and data flow** - `e3e973b9` (docs)
2. **Task 2: Document indirect saga-agent relationship and verify data integrity** - `181b0739` (docs)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/docs/traces/30-03-agent-decision-engine-trace.md` - TRACE-04 artifact with trigger path, call chain, model shapes, integrity matrix, and findings.

## Decisions Made
- Treated saga-agent linkage as a persistence contract (`SagaOrchestrator` writes, `FlowCoordinatorAgent` reads/updates) instead of direct service invocation.
- Classified current agent execution path as not directly wired into Celery Beat schedule based on code search evidence.
- Kept session analysis descriptive (async saga vs sync agent) and scoped to correctness tracing without architecture changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected gsd-tools executable path for this repository setup**
- **Found during:** Executor bootstrap before Task 1
- **Issue:** `$HOME/.claude/get-shit-done/bin/gsd-tools.cjs` was missing in this environment.
- **Fix:** Switched execution to repo-local tool path: `.claude/get-shit-done/bin/gsd-tools.cjs`.
- **Files modified:** None (execution-only fix)
- **Verification:** `init execute-phase` and config queries succeeded with local path.
- **Committed in:** N/A (no code change)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep; required only to run plan/state tooling in this workspace.

## Authentication Gates

None.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- TRACE-04 artifact is complete and aligned with Phase 30 success criteria for agent decision-path traceability.
- Phase 31 can use the integrity matrix and session analysis as inputs for compensation correctness and targeted test coverage.

## Self-Check: PASSED
- Verified `backend-hormonia/docs/traces/30-03-agent-decision-engine-trace.md` exists.
- Verified task commits `e3e973b9` and `181b0739` exist in git history.
