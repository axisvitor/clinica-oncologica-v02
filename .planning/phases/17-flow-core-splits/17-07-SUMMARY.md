---
phase: 17-flow-core-splits
plan: 07
subsystem: testing
tags: [postgres, pytest, schema-guard, api-contracts]
requires:
  - phase: 17-flow-core-splits
    provides: fail-fast verification baseline from 17-06
provides:
  - additive notifications schema guards for root and critical pytest bootstraps
  - additive audit_logs schema guards for legacy test database drift
  - refreshed deferred evidence for post-notifications fail-fast blockers
affects: [phase-17-verification, backend-tests, fail-fast-gate]
tech-stack:
  added: []
  patterns: [fixture-time additive postgres schema patching, fail-fast blocker logging]
key-files:
  created: [.planning/phases/17-flow-core-splits/17-07-SUMMARY.md]
  modified:
    - backend-hormonia/tests/conftest.py
    - backend-hormonia/tests/api/critical/conftest.py
    - .planning/phases/17-flow-core-splits/deferred-items.md
key-decisions:
  - "Keep schema drift handling in pytest fixtures with ALTER TABLE ... IF NOT EXISTS patches"
  - "Treat post-notifications audit_logs constraint failure as next blocker and record it in deferred evidence"
patterns-established:
  - "Schema Guard Expansion: when legacy test DB misses multiple columns, patch additively instead of rebuilding tables"
requirements-completed: [SPLIT-05, SPLIT-06, SPLIT-07]
duration: 32 min
completed: 2026-02-25
---

# Phase 17 Plan 07: Notifications Schema Guard Closure Summary

**Notifications API contract now passes by enforcing additive fixture-time `notifications` column guards, but fail-fast remains blocked by legacy `audit_logs` check constraints after three automatic remediation attempts.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-02-25T20:51:25Z
- **Completed:** 2026-02-25T21:23:38Z
- **Tasks:** 2 executed (Task 2 incomplete)
- **Files modified:** 3

## Accomplishments
- Added `_ensure_notifications_type_column(engine)` in root and critical conftest bootstraps with additive Postgres patching before test execution.
- Extended notification guard to align additional missing notification columns required by current ORM query paths.
- Re-ran fail-fast and logged timestamped closure evidence showing notification blocker closed and new first blocker captured.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add idempotent notification_type schema guards to root and critical test bootstraps** - `690457c8` (fix)
2. **Task 2: Re-run fail-fast suite and record closure evidence for Phase 17 verification** - `868f3da4` (fix)

## Files Created/Modified
- `backend-hormonia/tests/conftest.py` - Added notification and audit_logs additive schema guards for root suite bootstrap.
- `backend-hormonia/tests/api/critical/conftest.py` - Mirrored notification and audit_logs additive schema guards for critical suite bootstrap.
- `.planning/phases/17-flow-core-splits/deferred-items.md` - Appended 17-07 fail-fast rerun evidence and current blocker details.

## Decisions Made
- Kept all schema mismatch remediation inside pytest fixture bootstrap guards to avoid runtime router/model changes.
- Logged and deferred the new `audit_logs` constraint blocker after exhausting three auto-fix attempts for Task 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Expanded notifications guard beyond `notification_type` to unblock ORM query path**
- **Found during:** Task 1
- **Issue:** After adding `notification_type`, the same contract test failed on additional missing `notifications` columns (`priority`, `title`, etc.).
- **Fix:** Expanded guard to add and backfill required notification columns additively, including indexes.
- **Files modified:** `backend-hormonia/tests/conftest.py`, `backend-hormonia/tests/api/critical/conftest.py`
- **Verification:** `python3 -m pytest tests/api/test_api_contract_fixes.py::TestNotificationsStructureFix::test_notifications_structure -x --tb=short` passed.
- **Committed in:** `690457c8`

**2. [Rule 3 - Blocking] Added audit_logs compatibility guard after fail-fast advanced past notifications**
- **Found during:** Task 2
- **Issue:** Full fail-fast first failure moved to missing `audit_logs` columns (`firebase_uid`, then additional legacy-drift columns).
- **Fix:** Added additive `audit_logs` column guard in root and critical conftests to align schema with current model inserts.
- **Files modified:** `backend-hormonia/tests/conftest.py`, `backend-hormonia/tests/api/critical/conftest.py`
- **Verification:** Targeted reruns progressed from `UndefinedColumn` to later `CheckViolation`, confirming column drift layer was addressed.
- **Committed in:** `868f3da4`

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Notification blocker closure achieved; full fail-fast closure remains incomplete due a downstream legacy constraint mismatch.

## Issues Encountered
- `python3 -m pytest -x --tb=short` now fails first at `tests/api/test_api_contracts.py::TestUserActivityAPIContract::test_user_activity_returns_activity_logs` with `psycopg.errors.CheckViolation` on `audit_logs` constraint `valid_event_category`.
- Auto-fix attempts for Task 2 reached the configured limit (3); remaining blocker was documented instead of further schema surgery.

## Deferred Issues
- `audit_logs` legacy check constraint (`valid_event_category`) rejects `event_category='user_action'` during user activity contract fixture setup.
- Full fail-fast gate remains red until that constraint compatibility is resolved.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Notifications schema blocker from Phase 17 verification truth is closed and evidenced.
- Not ready to mark Phase 17 fail-fast gate complete until the new `audit_logs` constraint blocker is resolved.

---
*Phase: 17-flow-core-splits*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: `.planning/phases/17-flow-core-splits/17-07-SUMMARY.md`
- FOUND: `690457c8`
- FOUND: `868f3da4`
