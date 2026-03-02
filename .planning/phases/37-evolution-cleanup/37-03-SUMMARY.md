---
phase: 37-evolution-cleanup
plan: 03
subsystem: api
tags: [wuzapi, whatsapp, settings, cleanup, validation]
requires:
  - phase: 37-01
    provides: Evolution tombstones and import cutover baseline
  - phase: 37-02
    provides: Stack B cleanup and Evolution config removal baseline
provides:
  - Canonical phone validation import in WhatsApp message service
  - Runtime settings cleanup removing residual WHATSAPP_EVOLUTION references
  - Production env template aligned to WuzAPI variables
affects: [phase-37-verification, whatsapp-runtime, startup-import-chain]
tech-stack:
  added: []
  patterns: [canonical validator reuse, WuzAPI-only runtime config]
key-files:
  created: []
  modified:
    - backend-hormonia/app/integrations/whatsapp/services/message_service.py
    - backend-hormonia/app/config/settings/__init__.py
    - backend-hormonia/app/services/unified_whatsapp_service.py
    - backend-hormonia/.env.production.example
key-decisions:
  - "Use validate_and_format_phone(request.to, strict=False) with 3-tuple unpacking to match legacy tuple-based flow without async await."
  - "Remove WHATSAPP_EVOLUTION instance fallback and rely on resolved/default instance handling in UnifiedWhatsAppService."
patterns-established:
  - "Phone validation must come from app.schemas.validators.phone in active WhatsApp services."
  - "Production templates and runtime parsing must expose only WuzAPI WhatsApp provider variables."
requirements-completed: [CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04, CLEAN-05, CLEAN-06]
duration: 10min
completed: 2026-03-02
---

# Phase 37 Plan 03: Evolution Cleanup Summary

**Startup import chain now bypasses tombstoned Evolution code and runtime configuration is fully WuzAPI-only across message validation, settings parsing, unified service fallback, and production env template.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-02T22:31:00Z
- **Completed:** 2026-03-02T22:41:09Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Replaced tombstoned `evolution_client` phone validation import in `message_service.py` with canonical `validate_and_format_phone` and updated call semantics (sync + 3-tuple + `strict=False`).
- Removed residual `WHATSAPP_EVOLUTION_*` runtime/config usage from settings boolean parsing and unified WhatsApp instance fallback logic.
- Updated `backend-hormonia/.env.production.example` webhook and provider block to WuzAPI variable names and values.
- Verified no remaining `WHATSAPP_EVOLUTION` references in active `backend-hormonia/app/*.py` code paths.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix message_service.py tombstoned import -- replace with canonical phone validator** - `52c6d7ec` (fix)
2. **Task 2: Remove residual WHATSAPP_EVOLUTION_* from settings parser, unified service, and production env template** - `22378ffc` (refactor)

## Files Created/Modified

- `backend-hormonia/app/integrations/whatsapp/services/message_service.py` - switched to canonical phone validator import and updated send_message validation path.
- `backend-hormonia/app/config/settings/__init__.py` - removed deprecated Evolution mock boolean parser field and updated IntegrationsSettings docstring.
- `backend-hormonia/app/services/unified_whatsapp_service.py` - removed Evolution instance-name fallback from initialization logic.
- `backend-hormonia/.env.production.example` - replaced Evolution webhook/provider variables with WuzAPI equivalents.

## Decisions Made

- Keep validation behavior non-raising in send path by calling `validate_and_format_phone(..., strict=False)` and using returned `phone_error` in ValueError messaging.
- Keep default instance fallback behavior local to unified service (`"default"`) without reading deprecated Evolution settings.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Verification command for full app boot reached a non-import SQLAlchemy pool configuration error (`ArgumentError`), which is outside this plan's import-chain objective; ImportError path is resolved.
- Environment lacks `rg`; full sweep was validated with repository grep tooling instead.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 37 gap-closure scope is implemented and committed with atomic task history.
- Ready for phase verification rerun against CLEAN-01..CLEAN-06.

## Self-Check: PASSED

- FOUND: `.planning/phases/37-evolution-cleanup/37-03-SUMMARY.md`
- FOUND: `52c6d7ec`
- FOUND: `22378ffc`

---
*Phase: 37-evolution-cleanup*
*Completed: 2026-03-02*
