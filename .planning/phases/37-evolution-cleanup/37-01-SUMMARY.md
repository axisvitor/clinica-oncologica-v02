---
phase: 37-evolution-cleanup
plan: 01
subsystem: api
tags: [wuzapi, evolution, tombstone, saga, health]

requires:
  - phase: 36-outbound-migration
    provides: WuzAPI outbound sender wiring with no required Evolution runtime calls
provides:
  - Tombstoned Stack A Evolution integration package with immediate ImportError sentinel
  - Caller cleanup across saga orchestration, patient CRUD, health checks, and test fixtures
  - Circuit breaker WhatsApp service label migrated to wuzapi
affects: [37-02, whatsapp, orchestration, health-monitoring, tests]

tech-stack:
  added: []
  patterns: [module tombstone with top-level ImportError, hard-cut provider removal]

key-files:
  created: []
  modified:
    - backend-hormonia/app/integrations/evolution/__init__.py
    - backend-hormonia/app/integrations/evolution/client.py
    - backend-hormonia/app/integrations/evolution/message_sender.py
    - backend-hormonia/app/integrations/evolution/request_handler.py
    - backend-hormonia/app/integrations/evolution/webhook_handler.py
    - backend-hormonia/app/integrations/evolution/rate_limiter.py
    - backend-hormonia/app/integrations/evolution/validators.py
    - backend-hormonia/app/integrations/evolution/models.py
    - backend-hormonia/app/integrations/__init__.py
    - backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py
    - backend-hormonia/app/api/v2/routers/patients/crud.py
    - backend-hormonia/app/api/v2/routers/health/service_health.py
    - backend-hormonia/app/resilience/circuit_breaker/enhanced.py
    - backend-hormonia/tests/integrations/evolution/test_client_comprehensive.py
    - backend-hormonia/tests/fixtures/saga_fixtures.py

key-decisions:
  - "Use full tombstone replacement for all 8 app.integrations.evolution modules with identical package-level ImportError message."
  - "Keep import verification non-invasive by using command-scoped environment overrides instead of repository env file edits."

patterns-established:
  - "Hard-cut integration retirement: remove imports/callers first, then enforce package tombstone sentinel."
  - "Provider identity normalization: circuit breaker service key must match active provider ('wuzapi')."

requirements-completed: [CLEAN-01]

duration: 14 min
completed: 2026-03-02
---

# Phase 37 Plan 01: Evolution Cleanup Summary

**Stack A Evolution integration was hard-cut by tombstoning all legacy modules and removing all remaining runtime/test callers so WuzAPI is the sole WhatsApp path.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-03-02T18:24:18Z
- **Completed:** 2026-03-02T18:38:54Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments
- Replaced all 8 `app/integrations/evolution/` modules with a Phase 37 tombstone `ImportError` sentinel.
- Removed Evolution exports from `app/integrations/__init__.py` and cleaned all known callers in orchestrator, CRUD, health, and fixtures.
- Updated circuit breaker WhatsApp service identity from `whatsapp_evolution_api` to `wuzapi` and tombstoned the comprehensive Evolution integration test.

## Task Commits

Each task was committed atomically:

1. **Task 1: Tombstone all 8 Stack A files and clean integrations/__init__.py** - `40c6d5a5` (chore)
2. **Task 2: Clean Stack A callers (orchestrator, crud, service_health, circuit breaker, tests)** - `396287fc` (refactor)

**Plan metadata:** pending (created after summary/state updates)

## Files Created/Modified
- `backend-hormonia/app/integrations/evolution/__init__.py` - Tombstone import sentinel.
- `backend-hormonia/app/integrations/evolution/client.py` - Tombstone import sentinel.
- `backend-hormonia/app/integrations/evolution/message_sender.py` - Tombstone import sentinel.
- `backend-hormonia/app/integrations/evolution/request_handler.py` - Tombstone import sentinel.
- `backend-hormonia/app/integrations/evolution/webhook_handler.py` - Tombstone import sentinel.
- `backend-hormonia/app/integrations/evolution/rate_limiter.py` - Tombstone import sentinel.
- `backend-hormonia/app/integrations/evolution/validators.py` - Tombstone import sentinel.
- `backend-hormonia/app/integrations/evolution/models.py` - Tombstone import sentinel.
- `backend-hormonia/app/integrations/__init__.py` - Removed Evolution exports from integration namespace.
- `backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py` - Removed Evolution dependency from constructor and imports.
- `backend-hormonia/app/api/v2/routers/patients/crud.py` - Removed Evolution client import and ctor wiring.
- `backend-hormonia/app/api/v2/routers/health/service_health.py` - Removed Evolution external service health block.
- `backend-hormonia/app/resilience/circuit_breaker/enhanced.py` - Renamed WhatsApp breaker label/comment to WuzAPI.
- `backend-hormonia/tests/integrations/evolution/test_client_comprehensive.py` - Replaced with tombstoned skipped test marker.
- `backend-hormonia/tests/fixtures/saga_fixtures.py` - Removed `mock_evolution_client` fixture and related references.

## Decisions Made
- Followed locked phase decision for hard-cut retirement by enforcing immediate import failure on every Stack A module.
- Used verification-time environment overrides (`WHATSAPP_WUZAPI_TOKEN=dummy`) to avoid modifying project env files while validating imports.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] gsd-tools bootstrap path mismatch**
- **Found during:** Executor init
- **Issue:** `$HOME/.claude/get-shit-done/bin/gsd-tools.cjs` was unresolved in this environment.
- **Fix:** Switched all gsd-tools invocations to repo-local path `.claude/get-shit-done/bin/gsd-tools.cjs`.
- **Files modified:** None
- **Verification:** `init execute-phase 37` succeeded with local path.
- **Committed in:** N/A (execution command fix)

**2. [Rule 3 - Blocking] `python` command unavailable in runtime**
- **Found during:** Task 1 verification
- **Issue:** Verification command failed with `/bin/bash: python: command not found`.
- **Fix:** Executed verification using `python3`.
- **Files modified:** None
- **Verification:** Tombstone import checks executed successfully.
- **Committed in:** N/A (execution command fix)

**3. [Rule 3 - Blocking] settings validation required WuzAPI token for import checks**
- **Found during:** Task 1/Task 2 verification imports
- **Issue:** Importing app modules triggered startup validation error for missing `WHATSAPP_WUZAPI_TOKEN`.
- **Fix:** Scoped verification commands with `WHATSAPP_WUZAPI_TOKEN=dummy` environment override.
- **Files modified:** None
- **Verification:** Import checks then completed and matched expected outcomes.
- **Committed in:** N/A (execution command fix)

**4. [Rule 3 - Blocking] circuit-breaker runtime import required unavailable dependency**
- **Found during:** Task 2 verification
- **Issue:** Importing `app.resilience.circuit_breaker.enhanced` failed because `aiobreaker` is not installed in this shell runtime.
- **Fix:** Verified required enum/comment updates via file-content grep assertions.
- **Files modified:** None
- **Verification:** `ServiceType.WHATSAPP = "wuzapi"` and `whatsapp_evolution_api` absent.
- **Committed in:** N/A (execution command fix)

---

**Total deviations:** 4 auto-fixed (4 blocking)
**Impact on plan:** All deviations were execution-environment blockers only; planned code scope remained unchanged.

## Authentication Gates

None.

## Issues Encountered

- Verification imports produce substantial startup logging/noise because full app settings initialize on import; checks still completed with expected pass/fail signals.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 37 Plan 01 objectives are complete and committed with tombstones + caller cleanup.
- Ready for `37-02-PLAN.md` execution.

---
*Phase: 37-evolution-cleanup*
*Completed: 2026-03-02*

## Self-Check: PASSED

- FOUND: `.planning/phases/37-evolution-cleanup/37-01-SUMMARY.md`
- FOUND: `40c6d5a5`
- FOUND: `396287fc`
