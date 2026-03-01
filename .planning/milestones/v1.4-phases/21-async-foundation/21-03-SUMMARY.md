---
phase: 21-async-foundation
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, asyncsession, dependency-injection]
requires:
  - phase: 21-01
    provides: async DB primitives (`get_async_db`, `DualSessionMixin`)
  - phase: 21-02
    provides: async DI guardrails and exports baseline
provides:
  - Domain-scoped async dependency factories for patient and flow services
  - Package-level async factory re-exports from `app.dependencies`
  - Canonical `get_async_db` re-export from `app.core.database`
affects: [phase-22, phase-23, async-service-migration, api-router-migration]
tech-stack:
  added: []
  patterns: [domain dependency modules, flat async DI injection, lazy service imports]
key-files:
  created:
    - backend-hormonia/app/dependencies/patient_services.py
    - backend-hormonia/app/dependencies/flow_services.py
    - .planning/phases/21-async-foundation/deferred-items.md
  modified:
    - backend-hormonia/app/dependencies/__init__.py
key-decisions:
  - "Keep sync factories in service_dependencies.py unchanged and add async factories in domain modules only."
  - "Export get_async_db from app.dependencies via canonical app.core.database import path."
patterns-established:
  - "Async factory pattern: async def get_async_X_service(db: AsyncSession = Depends(get_async_db)) -> XService"
  - "Lazy in-function service imports to avoid circular dependency chains in dependency packages"
requirements-completed: [FOUND-01, FOUND-02, FOUND-04]
duration: 8 min
completed: 2026-02-26
---

# Phase 21 Plan 03: Async Factory Organization Summary

**Domain-organized async DI factories now provide data-integrity, flow alerts, and flow analytics services via `Depends(get_async_db)` with package-level exports for router adoption in later phases.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-26T23:31:00Z
- **Completed:** 2026-02-26T23:39:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added `patient_services.py` with async data-integrity service factory using flat AsyncSession injection.
- Added `flow_services.py` with async flow alerts and flow analytics factory functions.
- Updated `app.dependencies` exports to include new async factories and canonical `get_async_db`.
- Verified imports and DI wiring; alerts regression test passed and async isolation guard passed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create per-domain async factory files** - `40537dcf` (feat)
2. **Task 2: Update app/dependencies/__init__.py exports** - `622716b6` (feat)
3. **Task 3: Run regression verification and log unrelated blocker** - `4fe4b2c7` (docs)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/app/dependencies/patient_services.py` - Async patient-domain factory module with data integrity service provider.
- `backend-hormonia/app/dependencies/flow_services.py` - Async flow-domain factory module with alerts and analytics providers.
- `backend-hormonia/app/dependencies/__init__.py` - Re-export layer for async factories and canonical async DB dependency.
- `.planning/phases/21-async-foundation/deferred-items.md` - Out-of-scope test failure logged per execution boundary rules.

## Decisions Made
- Kept sync dependency factories untouched to preserve Celery and existing sync call paths.
- Standardized async factory imports on `app.core.database.get_async_db` to enforce canonical dependency source.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `python3 -m pytest -x --tb=short -q` stopped on pre-existing failure: `tests/api/v2/test_admin.py::TestBulkDelete::test_bulk_delete_success` (HTTP 400 vs expected 200). Logged to `.planning/phases/21-async-foundation/deferred-items.md` and left unchanged by scope policy.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Async DI factory structure is ready for Phase 22/23 service migrations to adopt without changing sync workers.
- Phase 21 can be marked complete after metadata/state updates.

---
*Phase: 21-async-foundation*
*Completed: 2026-02-26*

## Self-Check: PASSED
