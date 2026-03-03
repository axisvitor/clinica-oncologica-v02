---
phase: 38-tests-ci-validation
plan: 02
subsystem: testing
tags: [pytest, lgpd, ci, ast]
requires:
  - phase: 37-evolution-cleanup
    provides: Evolution tombstones and WuzAPI-only runtime
provides:
  - Opt-out LGPD unit coverage proving messaging_stopped_at is set and respected by send guard predicate
  - AST-based CI guard script preventing Evolution imports in non-tombstone app files
  - Pytest regression test invoking CI guard script and asserting clean exit
  - Tombstoned Evolution unit test file that is safely collected as skipped
affects: [phase-38-tests-ci-validation, ci, lgpd]
tech-stack:
  added: []
  patterns: [AST source scanning guard, tombstoned test modules with pytest skip]
key-files:
  created:
    - backend-hormonia/tests/unit/test_opt_out_lgpd.py
    - backend-hormonia/scripts/check_evolution_imports.py
    - backend-hormonia/tests/unit/test_evolution_import_regression.py
  modified:
    - backend-hormonia/tests/unit/test_evolution_client.py
key-decisions:
  - "Scan app/ only in check_evolution_imports.py to match existing CI guard scope and avoid false positives from test string patches"
  - "Keep tombstoned test file collectable by pytest with module-level skip and one placeholder test"
patterns-established:
  - "CI import regression checks should run via standalone script plus pytest subprocess wrapper"
  - "LGPD opt-out correctness is validated at unit level by direct handle_opt_out invocation"
requirements-completed: [TEST-04, TEST-05]
duration: 11 min
completed: 2026-03-03
---

# Phase 38 Plan 02: Tests and CI Validation Summary

**Opt-out LGPD behavior is now locked by direct handler tests and Evolution import regressions are blocked by an AST CI guard plus pytest wrapper.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-03T10:16:27-03:00
- **Completed:** 2026-03-03T10:27:53-03:00
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added `test_handle_opt_out_sets_messaging_stopped_at` asserting `handle_opt_out` sets `patient.messaging_stopped_at` and commits.
- Added send-guard predicate coverage for opted-out vs non-opted-out patients.
- Added `scripts/check_evolution_imports.py` with AST scanning over `app/` and tombstone directory exclusions.
- Added `test_evolution_import_regression.py` that executes CI guard script and fails on non-zero exit.
- Tombstoned `test_evolution_client.py` and ensured it is collected as skipped (no collection failures).

## Task Commits

Each task was committed atomically:

1. **Task 1: Create opt-out LGPD tests and tombstone Evolution unit test** - `5348cdf8` (test)
2. **Task 2: Add Evolution import CI guard and regression test** - `753bc277` (test)

Additional verification-driven fix:

3. **Post-task fix: Ensure tombstoned test is collected as skipped** - `1cf39315` (fix)

## Files Created/Modified
- `backend-hormonia/tests/unit/test_opt_out_lgpd.py` - Direct opt-out behavior and guard predicate tests.
- `backend-hormonia/scripts/check_evolution_imports.py` - AST-based Evolution import guard script for CI.
- `backend-hormonia/tests/unit/test_evolution_import_regression.py` - Pytest regression that executes CI guard script.
- `backend-hormonia/tests/unit/test_evolution_client.py` - Tombstoned legacy test module with module-level skip.

## Decisions Made
- Kept source scan scope at `app/` only to align with existing `check_async_isolation.py` guard pattern.
- Added a placeholder skipped test so `pytest tests/unit/test_evolution_client.py` reports skip instead of no-tests-collected.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected ConsentService patch target in opt-out test**
- **Found during:** Task 1 verification
- **Issue:** Test patched `message_handler.ConsentService`, but `ConsentService` is imported inside the function from `app.services.lgpd.consent_service`.
- **Fix:** Updated patch target to `app.services.lgpd.consent_service.ConsentService`.
- **Files modified:** `backend-hormonia/tests/unit/test_opt_out_lgpd.py`
- **Verification:** `pytest tests/unit/test_opt_out_lgpd.py tests/unit/test_evolution_client.py -v`
- **Committed in:** `5348cdf8`

**2. [Rule 1 - Bug] Ensured tombstoned test file satisfies expected skipped behavior**
- **Found during:** Plan-level verification
- **Issue:** Tombstoned file had no test items, resulting in "no tests ran" instead of skipped collection signal.
- **Fix:** Added placeholder test under module-level skip mark.
- **Files modified:** `backend-hormonia/tests/unit/test_evolution_client.py`
- **Verification:** `pytest tests/unit/test_evolution_client.py -v`
- **Committed in:** `1cf39315`

---

**Total deviations:** 2 auto-fixed (2 bug)
**Impact on plan:** Both fixes were correctness-aligned and kept scope strictly within TEST-04/TEST-05 validation.

## Issues Encountered
- Verification chain initially timed out under default command timeout; resumed remaining checks with extended timeout.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 38 requirements TEST-04 and TEST-05 are satisfied with passing/skip verification commands.
- Ready for phase transition/closure once metadata/state docs commit is completed.

---
*Phase: 38-tests-ci-validation*
*Completed: 2026-03-03*

## Self-Check: PASSED
