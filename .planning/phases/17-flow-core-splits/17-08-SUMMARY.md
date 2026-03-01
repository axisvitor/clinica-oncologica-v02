---
phase: 17-flow-core-splits
plan: 08
subsystem: testing
tags: [pytest, postgresql, audit_logs, constraints, api-contracts]
requires:
  - phase: 17-flow-core-splits
    provides: Flow-core split compatibility shims and prior schema guard baseline
provides:
  - Audit-log event_category constraint compatibility guard for test bootstrap
  - User activity contract fixture alignment with migration-compatible category
  - Fresh fail-fast evidence confirming valid_event_category blocker closure
affects: [phase-17-verification, phase-18-flow-service-splits, backend-tests]
tech-stack:
  added: []
  patterns: [Non-destructive Postgres test-schema patching via DROP CONSTRAINT IF EXISTS plus additive re-create]
key-files:
  created: [.planning/phases/17-flow-core-splits/17-08-SUMMARY.md]
  modified:
    - backend-hormonia/tests/conftest.py
    - backend-hormonia/tests/api/critical/conftest.py
    - backend-hormonia/tests/api/test_api_contracts.py
    - .planning/phases/17-flow-core-splits/deferred-items.md
key-decisions:
  - "Use fixture-time constraint rewrite for audit_logs.valid_event_category to support both HIPAA uppercase and production lowercase categories without touching migrations."
  - "Set user_activity fixture event_category to SYSTEM for immediate compatibility while retaining user_action in broadened guard list."
patterns-established:
  - "Schema guard pattern: detect Postgres + table presence, then idempotently replace legacy check constraint with broadened compatibility set."
requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-07]
duration: 17 min
completed: 2026-02-25
---

# Phase 17 Plan 08: Audit Logs Constraint Closure Summary

**Audit-log test bootstrap now rewrites valid_event_category to accept both migration and production category sets, unblocking user activity contract inserts and advancing fail-fast to a new unrelated patient endpoint failure.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-02-25T22:04:32Z
- **Completed:** 2026-02-25T22:21:38Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Replaced `event_category="user_action"` with `event_category="SYSTEM"` in `user_activity` fixture to satisfy baseline migration constraints immediately.
- Added `_ensure_audit_logs_event_category_constraint(engine)` to both root and critical conftests, with idempotent PostgreSQL guard logic and broadened value set.
- Wired the new guard into every engine bootstrap path immediately after audit-log column alignment.
- Captured fresh fail-fast evidence showing the `valid_event_category` blocker is closed and that a distinct first failure now gates suite completion.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix fixture and add constraint guards** - `815db9d5` (fix)
2. **Task 2: Re-run fail-fast and capture evidence** - `fc5e4505` (docs)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/tests/api/test_api_contracts.py` - Updated user activity fixture category to migration-compatible value.
- `backend-hormonia/tests/conftest.py` - Added root-suite audit_logs constraint rewrite guard and bootstrap invocation.
- `backend-hormonia/tests/api/critical/conftest.py` - Added critical-suite audit_logs constraint rewrite guard and bootstrap invocation in both DB paths.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - Appended timestamped post-fix fail-fast evidence and blocker status.

## Decisions Made
- Applied a test-only schema compatibility strategy (constraint rewrite) rather than modifying production migrations or model enums.
- Kept `user_action` in the broadened check constraint to preserve compatibility for other existing fixtures while standardizing this fixture on `SYSTEM`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `python3 -m pytest -x --tb=short` is not fully green yet; first failure moved to `tests/api/test_patients_endpoints.py::TestPatientCRUDEndpoints::test_create_patient_success` with `AssertionError` (`422 != 201`), separate from audit_logs constraint work.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Audit-log `valid_event_category` blocker is closed with fresh evidence.
- Phase 17 fail-fast gate still requires follow-up on the new patient-create validation failure before full green verification can be claimed.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-25*

## Self-Check: PASSED
- FOUND: `.planning/phases/17-flow-core-splits/17-08-SUMMARY.md`
- FOUND: `815db9d5`
- FOUND: `fc5e4505`
