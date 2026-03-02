---
phase: 34-webhook-handler
verified: 2026-03-02T03:24:02Z
status: human_needed
score: 20/20 must-haves verified
human_verification:
  - test: "Live WuzAPI webhook delivery with real signature"
    expected: "POST /api/v2/webhooks/wuzapi accepts valid x-hmac-signature and rejects tampered payload with 403"
    why_human: "Requires real upstream WuzAPI sender and production-style signature generation"
  - test: "LGPD opt-out persistence with real DB records"
    expected: "STOP/PARAR/CANCELAR sets patient.messaging_stopped_at and revokes active COMMUNICATION consents"
    why_human: "Current automated tests mock handle_opt_out and do not validate full DB-side effects end-to-end"
  - test: "LID sender DLQ persistence"
    expected: "@lid sender is queued for review and persisted in DLQ store for operator triage"
    why_human: "Automated tests mock DLQ call and do not verify downstream DLQ storage/observability"
---

# Phase 34: Webhook Handler Verification Report

**Phase Goal:** A new `/webhooks/wuzapi` endpoint receives WuzAPI events, validates HMAC with `x-hmac-signature`, deduplicates by `event.Info.ID`, and correctly routes Message and ReadReceipt events including LID sender detection and opt-out keyword processing.
**Verified:** 2026-03-02T03:24:02Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | POST `/webhooks/wuzapi` with valid HMAC returns 200 | ✓ VERIFIED | `test_valid_hmac_returns_200`; manual check returned `200 processed` |
| 2 | Invalid HMAC returns 403 | ✓ VERIFIED | `test_invalid_hmac_returns_403`; manual check returned `403` |
| 3 | Missing HMAC header returns 403 when secret exists | ✓ VERIFIED | Manual request with secret set + no signature returned `403` |
| 4 | No secret configured logs warning and processes event | ✓ VERIFIED | Manual request with secret unset returned `200 {'status': 'processed'}`; warning logged in `webhook.py` |
| 5 | Webhook routes by `type` (`Message`, `ReadReceipt`, unknown) | ✓ VERIFIED | `webhook.py` routes at lines 69-75; manual unknown-type request returned `{'status': 'ignored'}` |
| 6 | Raw body bytes are read before JSON parsing | ✓ VERIFIED | `await request.body()` at `backend-hormonia/app/integrations/wuzapi/webhook.py:35`, `json.loads(raw_body)` at line 47 |
| 7 | `extract_message()` returns phone/text/message_id/is_lid | ✓ VERIFIED | `test_wuzapi_extractor.py` message cases pass; extractor implementation lines 48-78 |
| 8 | `extract_receipt()` returns message_ids/receipt_type/sender_phone | ✓ VERIFIED | `test_wuzapi_extractor.py` receipt cases pass; extractor lines 81-109 |
| 9 | Receipt type mapping includes delivered/read/sent/played variants | ✓ VERIFIED | `RECEIPT_TYPE_TO_STATUS` at `extractor.py:33`; mapping assertion test passes |
| 10 | `MessageStatus` includes `PLAYED` | ✓ VERIFIED | `backend-hormonia/app/integrations/whatsapp/models/message.py:21` |
| 11 | `@lid` sender sets `is_lid=True` | ✓ VERIFIED | `extractor.py:58`; `test_extract_message_lid_jid` and `test_extract_message_hosted_lid` |
| 12 | Extractor handles wrapped and flat payloads | ✓ VERIFIED | `extractor.py` uses `payload.get('event') or payload`; flat payload test passes |
| 13 | Text extraction uses `Conversation` then `ExtendedTextMessage.Text` fallback | ✓ VERIFIED | `extractor.py:68`; related extractor tests pass |
| 14 | Duplicate `Info.ID` is deduplicated with HTTP 200 duplicate response | ✓ VERIFIED | `test_duplicate_event_returns_200_duplicate`; `AtomicWebhookIdempotency.try_acquire` in `webhook.py:62` |
| 15 | STOP triggers opt-out flow | ✓ VERIFIED | `webhook.py:93-99`; `test_opt_out_stop_sets_messaging_stopped_at` confirms branch to `handle_opt_out` |
| 16 | PARAR and CANCELAR also trigger opt-out flow | ✓ VERIFIED | `is_opt_out_message` keyword set includes both; parametric test `test_opt_out_keywords_process_opt_out` passes |
| 17 | Opt-out patient lookup uses `PhoneNormalizer.find_patient_by_phone` (phone-hash path) | ✓ VERIFIED | `webhook.py:161-163`; `test_opt_out_uses_phone_hash_lookup` verifies call |
| 18 | LID sender routes to DLQ and returns queued status | ✓ VERIFIED | `webhook.py:85-91` and `135-147`; LID DLQ tests pass |
| 19 | Router is available at `/api/v2/webhooks/wuzapi` | ✓ VERIFIED | `api_v2_router.include_router(... prefix='/webhooks')` in `backend-hormonia/app/api/v2/router.py:109`; route introspection prints `/api/v2/webhooks/wuzapi` |
| 20 | Missing `Info.ID` falls back to SHA-256 body hash for idempotency key | ✓ VERIFIED | `_extract_event_id` at `webhook.py:177-185`; `test_missing_event_id_uses_body_hash` passes |

**Score:** 20/20 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend-hormonia/app/integrations/wuzapi/webhook.py` | HMAC + routing + idempotency + opt-out + LID DLQ | ✓ VERIFIED | Exists, 185 lines, wired into API v2 router and tests |
| `backend-hormonia/app/integrations/wuzapi/extractor.py` | Message/receipt extractor + receipt mapping | ✓ VERIFIED | Exists, 124 lines, used by webhook and tests |
| `backend-hormonia/app/integrations/wuzapi/models.py` | `WuzAPIWebhookEvent`/`WuzAPIMessageInfo` models | ⚠️ ORPHANED | Exists and substantive, but symbols are not referenced outside file |
| `backend-hormonia/app/integrations/whatsapp/models/message.py` | `MessageStatus.PLAYED` enum value | ✓ VERIFIED | Exists and contains `PLAYED = "played"` |
| `backend-hormonia/app/api/v2/router.py` | WuzAPI router registration | ✓ VERIFIED | Imports `wuzapi_webhook_router` and includes with `/webhooks` prefix |
| `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py` | Webhook behavior tests | ✓ VERIFIED | Exists, 290 lines, webhook tests passing |
| `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_extractor.py` | Extractor behavior tests | ✓ VERIFIED | Exists, 154 lines, extractor tests passing |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `webhook.py` | `WebhookHMACValidator` | `validate_signature` call | WIRED | Import + call at lines 17 and 40 |
| `extractor.py` | `RECEIPT_TYPE_TO_STATUS` | dict lookup | WIRED | Constant defined and used in webhook line 113 |
| `message.py` | `MessageStatus.PLAYED` | enum member | WIRED | Enum value present and used by mapping semantics |
| `webhook.py` | `AtomicWebhookIdempotency` | `try_acquire` | WIRED | Import + runtime call at lines 23, 61-62 |
| `webhook.py` | `is_opt_out_message` | keyword detection | WIRED | Import + branch call at line 93 |
| `webhook.py` | `handle_opt_out` | opt-out handler call | WIRED | Import + awaited call at line 165 |
| `webhook.py` | `PhoneNormalizer` | patient lookup | WIRED | Import + `find_patient_by_phone` call at lines 24, 161-163 |
| `webhook.py` | `WuzAPIMessageExtractor` | extract message/receipt | WIRED | Import + calls at lines 80 and 108 |
| `api/v2/router.py` | `wuzapi_webhook_router` | `include_router` | WIRED | Import at line 55 and include at lines 109-113 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| WH-01 | 34-01 | New endpoint receives events and routes by `type` | ✓ SATISFIED | `webhook.py` routing logic; unknown/message/receipt behavior verified |
| WH-02 | 34-02 | Message parser extracts sender/text/media/id | ✓ SATISFIED | `extractor.py` fields and tests (`WuzAPIInboundMessage.raw_message` carries media payload) |
| WH-03 | 34-02 | ReadReceipt maps to SENT/DELIVERED/READ/PLAYED | ✓ SATISFIED | `RECEIPT_TYPE_TO_STATUS` mapping + receipt tests |
| WH-04 | 34-01 | HMAC validation with `x-hmac-signature` on raw bytes | ✓ SATISFIED | Raw-body-before-JSON flow and 200/403 checks |
| WH-05 | 34-03 | STOP/PARAR/CANCELAR opt-out detection | ✓ SATISFIED | `is_opt_out_message` + webhook opt-out branch tests |
| WH-06 | 34-03 | Dedup by `event.Info.ID` using Redis SET NX | ✓ SATISFIED | `AtomicWebhookIdempotency.try_acquire` + duplicate response test |

Orphaned requirements check: none (all Phase 34 requirement IDs in `REQUIREMENTS.md` are declared in phase plans).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| n/a | n/a | No TODO/FIXME/placeholder/empty-impl patterns found in scanned phase files | ℹ️ Info | No blocker anti-patterns detected |

### Human Verification Required

### 1. Live WuzAPI webhook delivery with real signature

**Test:** Send an actual WuzAPI webhook Message event to `/api/v2/webhooks/wuzapi` with valid and tampered `x-hmac-signature`.
**Expected:** Valid signature returns 200 processing response; tampered signature returns 403.
**Why human:** Requires real provider request signing behavior and deployed environment parity.

### 2. LGPD opt-out persistence with real DB records

**Test:** Trigger STOP/PARAR/CANCELAR from a known patient with active COMMUNICATION consent in a staging DB.
**Expected:** `patient.messaging_stopped_at` is set and active COMMUNICATION consent rows are revoked.
**Why human:** Current tests mock opt-out side effects instead of asserting persisted DB outcomes.

### 3. LID sender DLQ persistence

**Test:** Send payload with `Sender` ending in `@lid` and inspect DLQ backend.
**Expected:** Event is persisted in DLQ and endpoint returns `queued_for_review`.
**Why human:** Automated tests mock `send_to_dlq` and cannot validate real DLQ storage/observability.

### Gaps Summary

No blocker implementation gaps were found for Phase 34 must-haves. Automated verification confirms the goal-critical webhook flow is implemented and wired. One non-blocking design note remains: webhook envelope models in `models.py` are currently not consumed by runtime code.

---

_Verified: 2026-03-02T03:24:02Z_
_Verifier: Claude (gsd-verifier)_
