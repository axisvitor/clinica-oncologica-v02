---
phase: 37-evolution-cleanup
plan: 04
subsystem: api
tags: [wuzapi, whatsapp, webhook, tombstone, cleanup]
requires:
  - phase: 37-evolution-cleanup
    provides: Evolution cleanup baseline from plans 01-03
provides:
  - Severs remaining runtime imports tied to tombstoned Evolution modules
  - Rebinds queue failure classification to WuzAPIError contract
  - Removes webhook_router package export and tombstones webhook integration tests
affects: [webhook-runtime, queue-failure-routing, phase-37-verification]
tech-stack:
  added: []
  patterns: [log-only defensive no-op for deprecated paths, tombstone skip for dead integration tests]
key-files:
  created: []
  modified:
    - backend-hormonia/app/services/webhook/handlers/message_handler.py
    - backend-hormonia/app/integrations/whatsapp/queue/manager.py
    - backend-hormonia/app/integrations/whatsapp/api/__init__.py
    - backend-hormonia/tests/integration/whatsapp/test_webhook_scenarios.py
    - backend-hormonia/tests/integration/whatsapp/test_webhook_fail_closed_and_queue_batch.py
key-decisions:
  - "Keep unauthorized-response path as log-only no-op rather than re-implementing outbound behavior for unregistered numbers."
  - "Use WuzAPIError as direct EvolutionAPIError replacement for queue failure categorization."
patterns-established:
  - "Tombstoned runtime surfaces are removed from package exports to prevent transitive ImportError chains."
  - "Webhook tests importing dead modules are replaced by explicit skip tombstones."
requirements-completed: [CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04, CLEAN-05, CLEAN-06]
duration: 10 min
completed: 2026-03-02
---

# Phase 37 Plan 04: Evolution Cleanup Final Gap Closure Summary

**Final Evolution cleanup gaps closed by disabling unauthorized outbound fallback, switching queue error typing to WuzAPIError, and removing/tombstoning webhook import surfaces.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-02T23:29:31Z
- **Completed:** 2026-03-02T23:39:41Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Stack A runtime dependency removal completed by replacing unauthorized sender logic with a log-only no-op.
- Stack B runtime dependency removal completed by replacing EvolutionAPIError checks with WuzAPIError checks.
- WhatsApp API package export chain cleaned and both dead webhook integration tests tombstoned with collection-safe skips.

## Task Commits

Each task was committed atomically:

1. **Task 1: Sever Stack A and Stack B runtime imports from tombstoned Evolution modules** - `f7f5ade5` (fix)
2. **Task 2: Remove tombstoned webhook import from API package init and tombstone 2 test files** - `e3f2eb4a` (fix)

_Plan metadata commit pending state/roadmap updates._

## Files Created/Modified
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` - Replaced Evolution unauthorized sender path with warning-only no-op.
- `backend-hormonia/app/integrations/whatsapp/queue/manager.py` - Switched queue failure typing from EvolutionAPIError to WuzAPIError.
- `backend-hormonia/app/integrations/whatsapp/api/__init__.py` - Removed webhook_router import/export.
- `backend-hormonia/tests/integration/whatsapp/test_webhook_scenarios.py` - Replaced with skip tombstone for dead webhook module.
- `backend-hormonia/tests/integration/whatsapp/test_webhook_fail_closed_and_queue_batch.py` - Replaced with skip tombstone for dead webhook module.

## Decisions Made
- Kept unauthorized response behavior disabled and log-only to avoid reintroducing outbound behavior on unregistered numbers during WuzAPI migration hard cut.
- Used WuzAPIError status checks as the queue failure classifier to preserve RATE_LIMIT/API_ERROR categorization semantics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Verification shell lacked `python` alias**
- **Found during:** Task 1 verification
- **Issue:** Plan verification command used `python`, but environment only exposed `python3`.
- **Fix:** Switched verification invocations to `python3`.
- **Files modified:** None
- **Verification:** All task and plan verification commands ran successfully with `python3`.
- **Committed in:** N/A (execution-only adjustment)

**2. [Rule 3 - Blocking] Runtime imports required WuzAPI token in environment**
- **Found during:** Task 1/2 import verification
- **Issue:** Import chain failed settings validation without `WHATSAPP_WUZAPI_TOKEN`.
- **Fix:** Scoped verification commands with `WHATSAPP_WUZAPI_TOKEN=dummy`.
- **Files modified:** None
- **Verification:** Import and boot checks passed under scoped env override.
- **Committed in:** N/A (execution-only adjustment)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** No code scope change; fixes only unblocked local verification execution.

## Issues Encountered
- Initial combined verification chain used strict `&&` semantics where zero-match grep checks aborted command flow; reran checks with explicit pass/fail guards for zero-match expectations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 37 now has all 4 plans completed and verification truths for import-chain cleanup are satisfied.
- Ready for phase transition/state finalization.

## Self-Check
PASSED

---
*Phase: 37-evolution-cleanup*
*Completed: 2026-03-02*
