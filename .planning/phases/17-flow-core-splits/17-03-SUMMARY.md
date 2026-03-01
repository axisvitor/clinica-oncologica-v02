---
phase: 17-flow-core-splits
plan: 03
subsystem: api
tags: [flow, service-split, compatibility-shim, pytest]

# Dependency graph
requires:
  - phase: 17-flow-core-splits
    provides: flow core split shims from plans 17-01 and 17-02
provides:
  - FlowManagementService split into state, advancement, and pause/resume lifecycle modules
  - Legacy app.services.flow_management shim mapped to canonical app.services.flow.management.service
  - Contract tests for split boundaries and file-size constraints
affects: [flow orchestration, pause-resume lifecycle, cancellation handlers, phase-14 lifecycle regressions]

# Tech tracking
tech-stack:
  added: []
  patterns: [mixin composition for service splits, legacy import-path compatibility shim, split-contract structural tests]

key-files:
  created:
    - backend-hormonia/app/services/flow/management/__init__.py
    - backend-hormonia/app/services/flow/management/state_management.py
    - backend-hormonia/app/services/flow/management/advancement.py
    - backend-hormonia/app/services/flow/management/pause_resume.py
    - backend-hormonia/app/services/flow/management/service.py
    - backend-hormonia/tests/unit/services/test_flow_management_split_contract.py
  modified:
    - backend-hormonia/app/services/flow_management.py
    - .planning/phases/17-flow-core-splits/deferred-items.md

key-decisions:
  - "Composed FlowManagementService through three focused mixins under app.services.flow.management.service"
  - "Kept app.services.flow_management as a shim and preserved monkeypatch hooks for EnhancedFlowEngine/now_sao_paulo"

patterns-established:
  - "Split Contract: assert legacy shim resolves to canonical class and split methods stay in dedicated modules"
  - "Lifecycle Compatibility: preserve old patch targets when refactoring into internal packages"

requirements-completed: [SPLIT-07]

# Metrics
duration: 9 min
completed: 2026-02-25
---

# Phase 17 Plan 03: Flow Management Split Summary

**FlowManagementService now ships as canonical split modules for state/query orchestration, advancement/migration, and pause-resume-cancel lifecycle logic while preserving the legacy import path.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-25T15:58:00Z
- **Completed:** 2026-02-25T16:07:47Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Extracted `app/services/flow_management.py` into `app/services/flow/management/` modules with mixin composition.
- Preserved legacy compatibility via shim re-export for `FlowManagementService` and flow-advance blocked constants.
- Added split contract tests validating canonical import mapping, module responsibility boundaries, and <500 LOC guardrails.
- Re-ran targeted lifecycle regressions successfully (`pause_detection`, `cancel`, `auto_resume`, plus split-contract suite).

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract FlowManagementService into split modules** - `9d772580` (feat)
2. **Task 2: Add split contract tests and rerun lifecycle regressions** - `269401fe` (fix)

## Files Created/Modified
- `backend-hormonia/app/services/flow/management/state_management.py` - state queries/history/template/start/response orchestration mixin.
- `backend-hormonia/app/services/flow/management/advancement.py` - advancement guards and version migration mixin.
- `backend-hormonia/app/services/flow/management/pause_resume.py` - pause/resume/cancel lifecycle mixin.
- `backend-hormonia/app/services/flow/management/service.py` - composed `FlowManagementService` constructor and exports.
- `backend-hormonia/app/services/flow_management.py` - compatibility shim for old import path and constants.
- `backend-hormonia/tests/unit/services/test_flow_management_split_contract.py` - split contract checks.

## Decisions Made
- Used a composed service class in `flow.management.service` to keep constructor/API stable while isolating high-change logic.
- Preserved legacy patch hooks from `app.services.flow_management` (for `EnhancedFlowEngine` and `now_sao_paulo`) because regression tests still use those patch targets.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restored legacy monkeypatch compatibility after split**
- **Found during:** Task 2 (lifecycle regression execution)
- **Issue:** Existing tests patching `app.services.flow_management.EnhancedFlowEngine` and `app.services.flow_management.now_sao_paulo` failed after module split.
- **Fix:** Added compatibility exports in shim and bridge lookups in split modules so legacy patch targets still affect runtime behavior.
- **Files modified:** `backend-hormonia/app/services/flow_management.py`, `backend-hormonia/app/services/flow/management/service.py`, `backend-hormonia/app/services/flow/management/pause_resume.py`
- **Verification:** `python3 -m pytest tests/unit/services/test_flow_management_split_contract.py tests/unit/services/test_flow_pause_detection.py tests/unit/services/test_flow_cancel.py tests/unit/tasks/test_auto_resume_flows.py -x`
- **Committed in:** `269401fe`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Compatibility fix was required for existing lifecycle regression stability; no architectural scope expansion.

## Issues Encountered
- `python3 -m pytest -x` fails outside split scope at `tests/api/critical/test_patient_security_fixes.py::TestPatientSecurityFixes::test_idempotency_rbac_denies_other_doctor` due missing DB column `patients.messaging_stopped_at` in local test schema. Logged in `.planning/phases/17-flow-core-splits/deferred-items.md`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Flow-management split for Phase 17 is complete with shim compatibility and targeted regression coverage.
- One unrelated full-suite DB schema failure remains deferred and should be handled in its owning scope.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: `.planning/phases/17-flow-core-splits/17-03-SUMMARY.md`
- FOUND: `9d772580`
- FOUND: `269401fe`
