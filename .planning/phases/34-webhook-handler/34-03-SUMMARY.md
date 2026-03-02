---
phase: 34-webhook-handler
plan: 03
subsystem: api
tags: [wuzapi, webhook, redis, idempotency, lgpd, dlq, testing]
requires:
  - phase: 34-01
    provides: WuzAPI webhook endpoint, HMAC validation, event-id extraction scaffold
  - phase: 34-02
    provides: WuzAPI extractor models and receipt mapping constants
provides:
  - WuzAPI webhook idempotency using AtomicWebhookIdempotency with duplicate HTTP 200 response
  - Opt-out pipeline for STOP/PARAR/CANCELAR using PhoneNormalizer + async handle_opt_out
  - LID sender routing to DLQ and API v2 router registration at /api/v2/webhooks/wuzapi
affects: [phase-36-outbound-pipeline, webhook-processing, lgpd-compliance, monitoring]
tech-stack:
  added: []
  patterns: [redis-set-nx-idempotency, fail-open-infrastructure-guard, async-opt-out-handler]
key-files:
  created: [.planning/phases/34-webhook-handler/34-03-SUMMARY.md]
  modified:
    - backend-hormonia/app/services/webhook/handlers/message_handler.py
    - backend-hormonia/app/integrations/wuzapi/webhook.py
    - backend-hormonia/app/integrations/wuzapi/__init__.py
    - backend-hormonia/app/api/v2/router.py
    - backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py
key-decisions:
  - "Keep WuzAPI router prefix external (/webhooks) and register it in API v2 router"
  - "Return HTTP 200 with status=duplicate when Redis idempotency denies acquisition"
  - "Treat Redis idempotency outage as fail-open for WuzAPI processing continuity"
patterns-established:
  - "Webhook idempotency before event routing using AtomicWebhookIdempotency"
  - "Async opt-out implementation reused across webhook integrations"
requirements-completed: [WH-05, WH-06]
duration: 26min
completed: 2026-03-02
---

# Phase 34 Plan 03: Webhook Handler Summary

**WuzAPI inbound webhook now enforces Redis-backed idempotency, LGPD opt-out handling with consent revocation hooks, and LID DLQ routing behind `/api/v2/webhooks/wuzapi`.**

## Performance

- **Duration:** 26 min
- **Started:** 2026-03-02T02:40:00Z
- **Completed:** 2026-03-02T03:06:17Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Wired WuzAPI webhook runtime with `AtomicWebhookIdempotency`, body-hash fallback event IDs, and duplicate `200` response behavior.
- Added reusable async `handle_opt_out(patient, db: AsyncSession)` and used it from WuzAPI opt-out processing via `PhoneNormalizer.find_patient_by_phone`.
- Routed LID (`@lid`) sender events to DLQ with `WebhookDLQ.send_to_dlq` and registered WuzAPI router in API v2 with external `/webhooks` prefix.
- Expanded integration coverage for dedupe, opt-out keywords, phone-hash lookup usage, LID DLQ, receipt mapping, and fail-open idempotency behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire idempotency, extractor, opt-out, LID DLQ, and router registration** - `d9bcef35` (feat)
2. **Task 2 (TDD RED): Add failing webhook integration tests** - `f62e15d2` (test)
3. **Task 2 (TDD GREEN): Fix test assertions/spies and pass suite** - `e4647a91` (test)

## Files Created/Modified
- `backend-hormonia/app/integrations/wuzapi/webhook.py` - Replaced stubs with extractor-based message/receipt handlers, idempotency guard, opt-out flow, and LID DLQ routing.
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` - Added standalone async `handle_opt_out` for async webhook consumers.
- `backend-hormonia/app/integrations/wuzapi/__init__.py` - Exported extractor symbols and receipt status mapping.
- `backend-hormonia/app/api/v2/router.py` - Registered `wuzapi_webhook_router` under `/api/v2/webhooks`.
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py` - Added integration tests for idempotency, opt-out, LID DLQ, receipt mapping, and fail-open behavior.

## Decisions Made
- Kept WuzAPI route prefix outside integration router to match existing API v2 include-router pattern.
- Preserved fail-open behavior for idempotency infrastructure errors so webhook delivery remains available.
- Used direct symbol imports (`is_opt_out_message`, `handle_opt_out`, `PhoneNormalizer`) from shared webhook services to avoid duplicate logic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `python` binary unavailable in environment**
- **Found during:** Task 1 verification commands
- **Issue:** Plan command examples used `python`, but runtime only had `python3`.
- **Fix:** Switched verification and pytest invocations to `python3`.
- **Files modified:** None (execution-time adjustment only)
- **Verification:** Route import checks and pytest runs succeeded under `python3`.
- **Committed in:** `d9bcef35` / `e4647a91` verification flow

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope change; only command-runtime compatibility update.

## Issues Encountered
- Initial TDD RED run failed on test helper usage (`pytest.ANY` does not exist); resolved in GREEN by importing `ANY` from `unittest.mock` and correcting spy type.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- WuzAPI inbound webhook now has production-safe dedupe, opt-out, and LID review queue handling.
- API registration and integration tests are in place, so downstream phases can focus on business processing/outbound pipelines.

## Self-Check: PASSED

- FOUND: `.planning/phases/34-webhook-handler/34-03-SUMMARY.md`
- FOUND: `d9bcef35`
- FOUND: `f62e15d2`
- FOUND: `e4647a91`

---
*Phase: 34-webhook-handler*
*Completed: 2026-03-02*
