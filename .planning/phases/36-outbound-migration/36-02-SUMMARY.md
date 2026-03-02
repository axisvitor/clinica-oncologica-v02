---
phase: 36-outbound-migration
plan: 02
subsystem: api
tags: [wuzapi, whatsapp, outbound-migration, celery]
requires:
  - phase: 36-outbound-migration
    provides: UnifiedWhatsAppService outbound migration baseline from 36-01
provides:
  - WhatsAppMessageService queue sender migrated from Evolution client calls to WuzAPI client calls
  - IdempotentMessageSender migrated to WuzAPI factory/client with decrypted-phone normalization
  - WuzAPI response ID extraction standardized on response.data.Id for both outbound call sites
affects: [37-evolution-tombstone, outbound-messaging, celery-workers]
tech-stack:
  added: []
  patterns:
    - Keep validate_phone_number import temporarily while Evolution file remains until Phase 37
    - Convert media URLs to base64 data URI via fetch_and_encode_media before WuzAPI send_media
key-files:
  created: []
  modified:
    - backend-hormonia/app/integrations/whatsapp/services/message_service.py
    - backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py
key-decisions:
  - "WhatsApp queue and idempotent senders now both call WuzAPI methods directly while preserving existing queue/idempotency flows"
  - "sync_contacts is explicitly unsupported on WuzAPI and now raises NotImplementedError pending Phase 37 removal"
patterns-established:
  - "WuzAPI IDs are always read from response.get('data', {}).get('Id')"
  - "Idempotent sender uses patient.phone_decrypted normalized to BR E164 then strips '+' for WuzAPI"
requirements-completed: [OUT-02, OUT-03]
duration: 6 min
completed: 2026-03-02
---

# Phase 36 Plan 02: Outbound Migration Summary

**Completed outbound migration by moving queue-based and idempotent WhatsApp senders from Evolution clients to WuzAPI methods with standardized response ID extraction and media encoding.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-02T05:35:00Z
- **Completed:** 2026-03-02T05:41:07Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Migrated `WhatsAppMessageService` constructor and `_send_message_impl` to `wuzapi_client.send_text`/`send_media` with `fetch_and_encode_media`.
- Updated queue sender response handling to set `external_id` from `response.get("data", {}).get("Id")` and breaker name to `wuzapi_queue`.
- Stubbed `sync_contacts` with warning plus `NotImplementedError` for WuzAPI compatibility until Phase 37 removal.
- Migrated `IdempotentMessageSender` imports/property/call path to `get_wuzapi_client` and `wuzapi_client.send_text`.
- Added phone handling in idempotent sender to use `patient.phone_decrypted`, normalize `BR_TO_E164`, and strip `+` prefix before send.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate WhatsAppMessageService to WuzAPI client** - `d2195947` (feat)
2. **Task 2: Migrate IdempotentMessageSender to WuzAPI client** - `748e615f` (feat)

**Plan metadata:** `TBD` (docs: complete plan)

## Files Created/Modified
- `backend-hormonia/app/integrations/whatsapp/services/message_service.py` - queue pipeline now sends through WuzAPI text/media methods and stubs contacts sync.
- `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py` - idempotent sender now lazy-loads WuzAPI client and sends using normalized decrypted phone.

## Decisions Made
- Preserve queue processing/idempotency logic and only swap provider integration points (client calls, response parsing, and phone/media formatting).
- Keep `validate_phone_number` import path untouched in `message_service.py` until Evolution tombstone phase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Verification command required environment bootstrap**
- **Found during:** Task 1 and Task 2 verification
- **Issue:** Module imports failed because local shell lacked `WHATSAPP_WUZAPI_TOKEN`; `python` binary alias was also unavailable.
- **Fix:** Used `python3` and injected a temporary env var in verification command (`WHATSAPP_WUZAPI_TOKEN=dummy`) to validate importability without changing repository config.
- **Files modified:** None
- **Verification:** Both module import checks returned `Import OK`
- **Committed in:** N/A (verification-only environment fix)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep; change only unblocked verification in local shell.

## Issues Encountered
- Local verification environment had no `python` alias and required a temporary WuzAPI token env var for settings validation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Outbound call sites are migrated to WuzAPI for queue and idempotent sender flows.
- Ready for Phase 37 Evolution tombstoning with reduced ImportError risk at worker startup.

---
*Phase: 36-outbound-migration*
*Completed: 2026-03-02*

## Self-Check: PASSED

- Verified summary and modified files exist on disk.
- Verified task commits `d2195947` and `748e615f` exist in git history.
