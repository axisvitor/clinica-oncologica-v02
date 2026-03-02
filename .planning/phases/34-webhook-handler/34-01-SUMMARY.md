---
phase: 34-webhook-handler
plan: 01
subsystem: api
tags: [fastapi, webhook, hmac, wuzapi, pytest]
requires:
  - phase: 33-new-provider-foundation
    provides: WuzAPI integration package and provider foundations
provides:
  - WuzAPI webhook endpoint skeleton with HMAC validation and event routing
  - Webhook envelope models for WuzAPI payload typing
  - Unit test suite for webhook authentication and routing behavior
affects: [34-02, 34-03, whatsapp-webhooks]
tech-stack:
  added: []
  patterns: [raw-body-before-json, shared-hmac-validator-reuse, minimal-fastapi-test-app]
key-files:
  created:
    - backend-hormonia/app/integrations/wuzapi/webhook.py
    - backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py
  modified:
    - backend-hormonia/app/integrations/wuzapi/models.py
key-decisions:
  - "Reuse WebhookHMACValidator.validate_signature instead of custom HMAC logic."
  - "Read raw request bytes via await request.body() before JSON parsing to preserve HMAC input integrity."
  - "Keep missing-secret behavior permissive (warning + process) using WHATSAPP_WUZAPI_WEBHOOK_SECRET from env."
patterns-established:
  - "Webhook ingress pattern: raw bytes -> HMAC check -> JSON parse -> event type routing"
  - "WuzAPI webhook tests use FastAPI + ASGITransport with dependency overrides, not full app import"
requirements-completed: [WH-01, WH-04]
duration: 8 min
completed: 2026-03-02
---

# Phase 34 Plan 01: Webhook Handler Summary

**WuzAPI webhook ingress now validates HMAC signatures on raw body bytes, routes Message/ReadReceipt events, and is covered by dedicated endpoint tests.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-02T02:20:22Z
- **Completed:** 2026-03-02T02:29:13Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `WuzAPIMessageInfo` and `WuzAPIWebhookEvent` models to support typed webhook envelopes.
- Created `POST /webhooks/wuzapi` with raw-body HMAC validation, JSON parsing, and routing stubs for `Message` and `ReadReceipt`.
- Added 10 async tests covering HMAC accept/reject paths, missing secret behavior, invalid JSON, routing behavior, raw-body fidelity, and event-id fallback.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add webhook models and endpoint skeleton** - `8ce2b671` (feat)
2. **Task 2 (RED): Add failing webhook behavior tests** - `e45b18f6` (test)
3. **Task 2 (GREEN): Implement event-id hash fallback behavior** - `80776b48` (feat)

## Files Created/Modified
- `backend-hormonia/app/integrations/wuzapi/models.py` - Extended with webhook envelope/info Pydantic models.
- `backend-hormonia/app/integrations/wuzapi/webhook.py` - New WuzAPI webhook router with HMAC check and event routing stubs.
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py` - New isolated ASGI tests for webhook behavior.

## Decisions Made
- Reused existing `WebhookHMACValidator` for signature verification to avoid duplicate crypto logic.
- Enforced raw-body-first processing before JSON parsing to satisfy locked HMAC correctness requirement.
- Added deterministic fallback event IDs (body hash) to prevent empty identifiers when `event.Info.ID` is missing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] gsd-tools init path fallback to repo-local binary**
- **Found during:** Execution bootstrap
- **Issue:** `$HOME/.claude/get-shit-done/bin/gsd-tools.cjs` did not exist in this environment.
- **Fix:** Used repository-local `.claude/get-shit-done/bin/gsd-tools.cjs` for all gsd-tools commands.
- **Files modified:** None
- **Verification:** `init execute-phase` and `config-get` returned expected JSON output.
- **Committed in:** N/A (execution environment fix)

**2. [Rule 3 - Blocking] Python executable mismatch in verification commands**
- **Found during:** Task 1 verification
- **Issue:** `python` command was unavailable in shell.
- **Fix:** Switched verification and test commands to `python3`.
- **Files modified:** None
- **Verification:** All import checks and pytest commands succeeded with `python3`.
- **Committed in:** N/A (command-level fix)

**3. [Rule 1 - Bug] Empty message_id when webhook payload omits Info.ID**
- **Found during:** Task 2 TDD RED phase
- **Issue:** Message handler returned empty `message_id` for missing `Info.ID`, despite existing hash fallback helper.
- **Fix:** Wired `_extract_event_id(payload, raw_body)` into route flow and propagated fallback ID into message/receipt handlers.
- **Files modified:** `backend-hormonia/app/integrations/wuzapi/webhook.py`
- **Verification:** `test_missing_event_id_uses_hash_fallback` passes and full test file passes.
- **Committed in:** `80776b48`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** All deviations were correctness/execution enablers with no scope creep beyond webhook reliability.

## Issues Encountered
- Router introspection check from the plan snippet expected `'/wuzapi'`, while FastAPI route paths include router prefix and expose `'/webhooks/wuzapi'`; endpoint behavior and test verification still passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Endpoint skeleton and authentication guardrails are in place for parser-focused work in `34-02`.
- Handler stubs are ready for idempotency, opt-out, and DLQ wiring in `34-03`.

---
*Phase: 34-webhook-handler*
*Completed: 2026-03-02*

## Self-Check: PASSED

- FOUND: `.planning/phases/34-webhook-handler/34-01-SUMMARY.md`
- FOUND: `8ce2b671`
- FOUND: `e45b18f6`
- FOUND: `80776b48`
