---
phase: 36-outbound-migration
plan: 03
subsystem: api
tags: [wuzapi, whatsapp, dependency-injection, outbound-messaging]

# Dependency graph
requires:
  - phase: 36-01
    provides: UnifiedWhatsAppService outbound migration to WuzAPI
  - phase: 36-02
    provides: WhatsAppMessageService and IdempotentMessageSender WuzAPI internals
provides:
  - Outbound message API DI path wired to WuzAPI client factory
  - Follow-up and scheduler callers no longer instantiate EvolutionClient
  - Caller-level alignment with IdempotentMessageSender lazy WuzAPI loading
affects: [37-evolution-cleanup, outbound-whatsapp, follow-up-system]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Factory-based WuzAPI DI for queue service", "Lazy client injection at caller boundaries"]

key-files:
  created: []
  modified:
    - backend-hormonia/app/integrations/whatsapp/api/routes.py
    - backend-hormonia/app/services/follow_up_system/service.py
    - backend-hormonia/app/domain/messaging/scheduling/message_scheduler/scheduler.py

key-decisions:
  - "Keep Evolution DI only for instance-management endpoints in routes.py; migrate outbound message DI path to WuzAPI now."
  - "Remove explicit EvolutionClient construction from IdempotentMessageSender callers and rely on lazy WuzAPI initialization."

patterns-established:
  - "Outbound path isolation: message send/queue flows use WuzAPI while instance control remains Evolution until Phase 37"

requirements-completed: [OUT-01, OUT-02, OUT-03, OUT-04]

# Metrics
duration: 6 min
completed: 2026-03-02
---

# Phase 36 Plan 03: Outbound Wiring Gap Closure Summary

**Closed remaining outbound caller wiring so message send paths now resolve WuzAPI end-to-end while preserving Evolution only for instance-management endpoints slated for Phase 37.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-02T16:49:26Z
- **Completed:** 2026-03-02T16:55:57Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `get_wuzapi_for_queue` dependency and switched `get_message_service` to inject WuzAPI client in `routes.py`.
- Removed `EvolutionClient` construction/import from follow-up and scheduler services.
- Aligned both caller sites to `IdempotentMessageSender(db, redis_client)` so lazy WuzAPI loading handles runtime client initialization.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewire get_message_service in routes.py to inject WuzAPI client** - `50332b52` (fix)
2. **Task 2: Remove EvolutionClient injection from IdempotentMessageSender callers** - `4a71c63e` (fix)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/app/integrations/whatsapp/api/routes.py` - Added WuzAPI queue dependency and switched message service DI to WuzAPI client.
- `backend-hormonia/app/services/follow_up_system/service.py` - Removed Evolution import/instantiation and simplified sender construction.
- `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/scheduler.py` - Removed Evolution import/instantiation and simplified sender construction.

## Decisions Made
- Kept `Depends(get_evolution_client)` on instance-management endpoints untouched per Phase 36 scope boundary.
- Used `IdempotentMessageSender` lazy WuzAPI client path instead of creating explicit provider clients in callers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python executable name mismatch in verification commands**
- **Found during:** Task 1 verification
- **Issue:** `python` was unavailable in the environment, causing verification command failure.
- **Fix:** Used `python3` for all verification import checks.
- **Files modified:** None (command-only adjustment)
- **Verification:** All required imports succeeded using `python3`.
- **Committed in:** N/A (no file changes)

**2. [Rule 3 - Blocking] Runtime settings validation required WuzAPI token for import checks**
- **Found during:** Task 1 and Task 2 verification
- **Issue:** Module import bootstrap failed without `WHATSAPP_WUZAPI_TOKEN`.
- **Fix:** Passed a temporary `WHATSAPP_WUZAPI_TOKEN=dummy-token` only in verification commands.
- **Files modified:** None (command-only adjustment)
- **Verification:** Route/service/scheduler imports succeeded with temporary env injection.
- **Committed in:** N/A (no file changes)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both deviations were environment-level verification blockers only; implementation scope and code outputs stayed aligned with plan intent.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 36 outbound migration is ready for Phase 37 Evolution cleanup/tombstoning.
- No remaining Evolution caller injection in outbound message paths targeted by this plan.

---
*Phase: 36-outbound-migration*
*Completed: 2026-03-02*

## Self-Check: PASSED
- FOUND: .planning/phases/36-outbound-migration/36-03-SUMMARY.md
- FOUND: 50332b52
- FOUND: 4a71c63e
