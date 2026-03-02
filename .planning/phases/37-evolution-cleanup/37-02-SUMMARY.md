---
phase: 37-evolution-cleanup
plan: 02
subsystem: api
tags: [wuzapi, evolution, cleanup, webhooks, settings]

requires:
  - phase: 37-01
    provides: Stack A evolution tombstones and hard-cut provider migration baseline
provides:
  - Removed remaining Evolution/LID logic from Stack B webhook utilities and handlers
  - Replaced webhook secret wiring to WHATSAPP_WUZAPI_WEBHOOK_SECRET across security, middleware, and service layers
  - Removed WHATSAPP_EVOLUTION settings/env surface from integration settings and example env files
affects: [whatsapp, webhook-security, monitoring, config-validation, worker-env]

tech-stack:
  added: []
  patterns: [provider-secret normalization, post-tombstone namespace cleanup]

key-files:
  created:
    - .planning/phases/37-evolution-cleanup/37-02-SUMMARY.md
  modified:
    - backend-hormonia/app/services/webhook/utils/phone_normalizer.py
    - backend-hormonia/app/services/webhook/handlers/message_handler.py
    - backend-hormonia/app/config/settings/integrations.py
    - backend-hormonia/app/services/whatsapp/security.py
    - backend-hormonia/app/middleware/webhook_validator.py
    - backend-hormonia/app/services/webhook_service.py
    - backend-hormonia/app/api/v2/routers/system/validation.py
    - backend-hormonia/app/api/v2/monitoring/whatsapp.py
    - backend-hormonia/.env.example
    - backend-hormonia/worker/.env.example
    - backend-hormonia/app/services/webhook/utils/__init__.py

key-decisions:
  - "Removed all LID resolution paths instead of replacing with fallback logic, matching hard-cut Evolution retirement."
  - "Monitoring defaults now use literal 'wuzapi' instance names to avoid removed Evolution settings dependencies."

patterns-established:
  - "Provider-specific webhook secret references must point only to WHATSAPP_WUZAPI_WEBHOOK_SECRET."
  - "When tombstoning a utility module, remove any package __init__ re-export to avoid import-time failures."

requirements-completed: [CLEAN-02, CLEAN-03, CLEAN-04, CLEAN-05, CLEAN-06]

duration: 15 min
completed: 2026-03-02
---

# Phase 37 Plan 02: Evolution Cleanup Summary

**Stack B cleanup removed remaining Evolution settings, LID resolution paths, and webhook secret wiring so WuzAPI is the only active WhatsApp provider surface.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-02T19:00:41Z
- **Completed:** 2026-03-02T19:15:28Z
- **Tasks:** 2
- **Files modified:** 21

## Accomplishments

- Removed `PhoneNormalizer` LID resolution cache/methods and deleted `@lid` resolution branch from message handling.
- Removed remaining `WHATSAPP_EVOLUTION_*` settings/env declarations and switched validation/monitoring defaults to WuzAPI-compatible values.
- Standardized webhook signature secret references to `WHATSAPP_WUZAPI_WEBHOOK_SECRET` in middleware, service, and security checks.
- Fixed residual package export importing tombstoned `message_extractor` via `app/services/webhook/utils/__init__.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Tombstone Stack B files, Evolution webhooks, message extractor, and deregister routes** - `18188e27` (refactor)
2. **Task 2: Remove LID methods and Evolution settings; rewire secrets to WuzAPI** - `3b1bfee9` (refactor)

**Plan metadata:** pending (created after summary/state updates)

## Files Created/Modified

- `backend-hormonia/app/services/webhook/utils/phone_normalizer.py` - Removed `resolve_phone_from_lid` and related Evolution chat helper methods.
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` - Removed `message_extractor` import and `@lid` resolution block.
- `backend-hormonia/app/config/settings/integrations.py` - Deleted legacy Evolution settings fields and updated module header language.
- `backend-hormonia/app/services/whatsapp/security.py` - Repointed webhook secret lookup and log messages to WuzAPI secret.
- `backend-hormonia/app/middleware/webhook_validator.py` - Updated usage/config docs and production error text to WuzAPI secret name.
- `backend-hormonia/app/services/webhook_service.py` - Updated signature verification secret source to `WHATSAPP_WUZAPI_WEBHOOK_SECRET`.
- `backend-hormonia/app/api/v2/routers/system/validation.py` - Switched external-service warning check to `WHATSAPP_WUZAPI_TOKEN`.
- `backend-hormonia/app/api/v2/monitoring/whatsapp.py` - Set default instance identifiers to literal `"wuzapi"`.
- `backend-hormonia/.env.example` - Removed `WHATSAPP_EVOLUTION_TIMEOUT_SECONDS`.
- `backend-hormonia/worker/.env.example` - Replaced Evolution block with WuzAPI vars.
- `backend-hormonia/app/services/webhook/utils/__init__.py` - Removed tombstoned `extract_message_data` re-export.

## Decisions Made

- Preserved plan intent for hard-cut migration by fully removing LID fallback behavior instead of introducing new alternate lookup logic.
- Kept verification-time environment overrides (`TESTING=1`, `WHATSAPP_WUZAPI_TOKEN=dummy`) scoped to commands, without modifying runtime env files.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Tombstoned extractor was still re-exported by utils package**
- **Found during:** Task 2 verification
- **Issue:** Importing webhook utilities failed because `app/services/webhook/utils/__init__.py` still imported tombstoned `message_extractor`.
- **Fix:** Removed `extract_message_data` import/export references from package `__init__.py`.
- **Files modified:** `backend-hormonia/app/services/webhook/utils/__init__.py`
- **Verification:** Re-ran cleanup validation command successfully after the change.
- **Committed in:** `3b1bfee9` (part of Task 2 commit)

**2. [Rule 3 - Blocking] `python` binary unavailable in shell runtime**
- **Found during:** Task 2 verification
- **Issue:** Verification command failed with `/bin/bash: python: command not found`.
- **Fix:** Executed verification using `python3`.
- **Files modified:** None
- **Verification:** Verification command completed with expected pass output.
- **Committed in:** N/A (execution command fix)

**3. [Rule 3 - Blocking] Startup settings validation required WuzAPI token for imports**
- **Found during:** Task 2 verification
- **Issue:** Module imports triggered Settings validation error for missing `WHATSAPP_WUZAPI_TOKEN`.
- **Fix:** Scoped verification with `TESTING=1 WHATSAPP_WUZAPI_TOKEN=dummy` environment overrides.
- **Files modified:** None
- **Verification:** Cleanup assertions passed with overrides in place.
- **Committed in:** N/A (execution command fix)

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** Deviations were required for execution correctness and verification continuity; no scope expansion.

## Authentication Gates

None.

## Issues Encountered

- Verification imports initialize large parts of the app and generate noisy startup logs; assertions still validated expected cleanup outcomes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 37 cleanup plans are fully implemented with both Task 1 and Task 2 committed.
- Codebase is ready for downstream verification/audit of zero active Evolution runtime paths.

---
*Phase: 37-evolution-cleanup*
*Completed: 2026-03-02*

## Self-Check: PASSED

- FOUND: `.planning/phases/37-evolution-cleanup/37-02-SUMMARY.md`
- FOUND: `18188e27`
- FOUND: `3b1bfee9`
