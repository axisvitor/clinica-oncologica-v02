---
phase: 20-schema-fix
plan: 01
subsystem: database
tags: [sqlalchemy, postgresql, pytest, schema-guard]

requires:
  - phase: none
    provides: phase is intentionally independent
provides:
  - Alert model column mappings aligned with live PostgreSQL alerts schema
  - PostgreSQL test schema guard for legacy alerts column drift
  - Test-suite progression past alerts schema blocker
affects: [21-async-foundation, test-stability, api-v2-alerts]

tech-stack:
  added: []
  patterns:
    - PostgreSQL schema guard helpers in tests/conftest.py using inspector + ALTER TABLE patches

key-files:
  created:
    - .planning/phases/20-schema-fix/deferred-items.md
  modified:
    - backend-hormonia/app/models/alert.py
    - backend-hormonia/tests/conftest.py

key-decisions:
  - "Map Alert.alert_type directly to alert_type (remove legacy type override)."
  - "Map Alert.description directly to description after runtime evidence showed message does not exist."
  - "Use a PostgreSQL schema guard to normalize legacy alerts columns in test DB before fixture usage."

patterns-established:
  - "Schema guards run from test_engine before DB-touching tests."
  - "Column drift in local Postgres test schemas is auto-healed with idempotent ALTER TABLE guards."

requirements-completed: [SCHEMA-01, SCHEMA-02]

duration: 32 min
completed: 2026-02-26
---

# Phase 20 Plan 01: Schema Fix Summary

**Alert ORM mapping now targets real PostgreSQL columns (`alert_type`, `description`) and test bootstrapping auto-patches legacy alerts schemas so alert tests run cleanly.**

## Performance

- **Duration:** 32 min
- **Started:** 2026-02-26T19:09:45Z
- **Completed:** 2026-02-26T19:42:07Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Removed the incorrect `alerts.type` ORM mapping and aligned Alert model attribute-to-column resolution.
- Added `_ensure_alerts_columns()` guard to PostgreSQL test setup and wired it into `test_engine` fixture initialization.
- Verified `tests/api/v2/test_alerts.py` passes and full fail-fast suite proceeds beyond alerts without `alerts.type`/`alerts.message` undefined-column failures.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix Alert model column mappings to match actual PostgreSQL schema** - `d153ec38` (fix)
2. **Task 2: Add conftest schema guard for alerts table and run test verification** - `35ecb56d` (fix)
3. **Task 3: Run full test suite to verify alerts blocker is resolved** - `262bfd33` (fix)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/app/models/alert.py` - Aligned `alert_type`/`description` ORM mappings with real DB columns and updated model docstring.
- `backend-hormonia/tests/conftest.py` - Added `_ensure_alerts_columns()` and test-engine registration to normalize legacy alerts columns.
- `.planning/phases/20-schema-fix/deferred-items.md` - Logged out-of-scope fail-fast blocker found after alerts blocker was cleared.

## Decisions Made
- Correctness over assumptions: because runtime evidence showed `alerts.message` missing, `Alert.description` now maps to `description` directly.
- Keep API/repository callers unchanged: only DB column bindings changed; Python attributes (`alert_type`, `description`, `severity`, `acknowledged`) stayed stable.
- Guard-first testing strategy: apply schema healing in session-scoped test engine setup to prevent repeated `UndefinedColumn` regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Expanded alerts schema guard beyond `type` rename**
- **Found during:** Task 2 verification
- **Issue:** Legacy PostgreSQL test schema also lacked `severity`, `description/message` alignment, `data`, and acknowledgment columns, still breaking alert inserts.
- **Fix:** Extended `_ensure_alerts_columns()` to idempotently normalize these required columns before tests execute.
- **Files modified:** `backend-hormonia/tests/conftest.py`
- **Verification:** `python3 -m pytest tests/api/v2/test_alerts.py::TestListAlerts::test_list_alerts_basic -x --tb=short -q` passed.
- **Committed in:** `35ecb56d`

**2. [Rule 1 - Bug] Corrected Alert description mapping after live-schema evidence**
- **Found during:** Task 2 verification
- **Issue:** Alert inserts failed with `UndefinedColumn: alerts.message` showing model mapping was still incorrect for the active PostgreSQL schema.
- **Fix:** Changed `description = Column("message", ...)` to `description = Column(Text, ...)` and updated model docs.
- **Files modified:** `backend-hormonia/app/models/alert.py`
- **Verification:** `python3 -m pytest tests/api/v2/test_alerts.py -x --tb=short -q` passed.
- **Committed in:** `262bfd33`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Deviations were required to satisfy the plan's schema-alignment objective under real test-DB drift; no architectural scope expansion.

## Issues Encountered
- Full-suite fail-fast moved to unrelated blocker: `tests/api/v2/test_auth.py::TestSessionManagement::test_list_sessions_success` failing with `UndefinedColumn: sessions.session_token`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 20 alerts schema blocker is closed and no longer the first suite-stopping failure.
- Next work should address the new sessions schema blocker tracked in `.planning/phases/20-schema-fix/deferred-items.md`.

---
*Phase: 20-schema-fix*
*Completed: 2026-02-26*

## Self-Check: PASSED

- Verified `.planning/phases/20-schema-fix/20-01-SUMMARY.md` exists.
- Verified task commits `d153ec38`, `35ecb56d`, and `262bfd33` exist in git history.
