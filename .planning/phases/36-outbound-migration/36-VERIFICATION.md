---
phase: 36-outbound-migration
verified: 2026-03-02T17:09:27Z
status: passed
score: 4/4 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 2/4
  gaps_closed:
    - "WhatsAppMessageService queue pipeline routes outbound messages through WuzAPIClient by constructor injection"
    - "IdempotentMessageSender uses WuzAPIClient in runtime call paths and records whatsapp_id from response.data.Id"
  gaps_remaining: []
  regressions: []
---

# Phase 36: Outbound Migration Verification Report

**Phase Goal:** All outbound WhatsApp messages flow through WuzAPIClient — UnifiedWhatsAppService, WhatsAppMessageService queue pipeline, and IdempotentMessageSender are all updated before any Evolution file is removed.
**Verified:** 2026-03-02T17:09:27Z
**Status:** passed
**Re-verification:** Yes — after gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | A patient follow-up message sent via `UnifiedWhatsAppService` is delivered using WuzAPIClient with token auth header and no Evolution client path | ✓ VERIFIED | WuzAPI import/factory/send path in `backend-hormonia/app/services/unified_whatsapp_service.py:26`, `backend-hormonia/app/services/unified_whatsapp_service.py:206`, `backend-hormonia/app/services/unified_whatsapp_service.py:532`; auth header in `backend-hormonia/app/integrations/wuzapi/client.py:77`; no `EvolutionAPIClient`/`evolution_client` references in unified service |
| 2 | Queue pipeline in `WhatsAppMessageService` routes outbound messages through WuzAPIClient by constructor injection | ✓ VERIFIED | Queue DI now uses WuzAPI in `backend-hormonia/app/integrations/whatsapp/api/routes.py:132`, `backend-hormonia/app/integrations/whatsapp/api/routes.py:134`, `backend-hormonia/app/integrations/whatsapp/api/routes.py:138`; queue sender uses `self.wuzapi_client.send_text/send_media` in `backend-hormonia/app/integrations/whatsapp/services/message_service.py:586`, `backend-hormonia/app/integrations/whatsapp/services/message_service.py:593` |
| 3 | `IdempotentMessageSender` imports/uses WuzAPIClient and stores `whatsapp_id` from `response.data.Id` | ✓ VERIFIED | WuzAPI factory import and lazy property in `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:43`, `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:101`; send + ID extraction in `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:418`, `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:424`; callers no longer inject Evolution in `backend-hormonia/app/services/follow_up_system/service.py:85` and `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/scheduler.py:51` |
| 4 | Phone numbers are sent as raw digits (no `@s.whatsapp.net`) and circuit breaker key is `wuzapi` | ✓ VERIFIED | Raw-digit normalization/strip in unified and idempotent sender at `backend-hormonia/app/services/unified_whatsapp_service.py:520`, `backend-hormonia/app/services/unified_whatsapp_service.py:527`, `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:410`, `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:415`; queue sender strips suffix at `backend-hormonia/app/integrations/whatsapp/services/message_service.py:582`; breaker key is `wuzapi` in `backend-hormonia/app/services/unified_whatsapp_service.py:149` |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend-hormonia/app/services/unified_whatsapp_service.py` | WuzAPI-backed unified outbound service | ✓ VERIFIED | Exists, substantive outbound logic, wired to `get_wuzapi_client` and queue service injection |
| `backend-hormonia/app/integrations/whatsapp/services/message_service.py` | WuzAPI-backed queue sender | ✓ VERIFIED | Exists, substantive implementation (`send_text/send_media`, `fetch_and_encode_media`, `response.data.Id`), wired from API DI path |
| `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py` | WuzAPI-backed idempotent sender | ✓ VERIFIED | Exists, substantive implementation (`send_text`, ID extraction, decrypted-phone normalization), wired through follow-up and scheduler callers |
| `backend-hormonia/app/integrations/whatsapp/api/routes.py` | WuzAPI-wired message service dependency path | ✓ VERIFIED | `get_wuzapi_for_queue` dependency is present and `get_message_service` injects WuzAPI client |
| `backend-hormonia/app/services/follow_up_system/service.py` | Idempotent sender caller without Evolution injection | ✓ VERIFIED | No `EvolutionClient` import/instantiation; constructor uses `IdempotentMessageSender(db, redis_client)` |
| `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/scheduler.py` | Idempotent sender caller without Evolution injection | ✓ VERIFIED | No `EvolutionClient` import/instantiation; constructor uses `IdempotentMessageSender(db, redis_client)` |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `backend-hormonia/app/services/unified_whatsapp_service.py` | `backend-hormonia/app/integrations/wuzapi/__init__.py` | import + factory (`get_wuzapi_client`) | WIRED | Import and runtime factory usage at `backend-hormonia/app/services/unified_whatsapp_service.py:26` and `backend-hormonia/app/services/unified_whatsapp_service.py:215` |
| `backend-hormonia/app/services/unified_whatsapp_service.py` | `backend-hormonia/app/integrations/whatsapp/services/message_service.py` | `WhatsAppMessageService(wuzapi_client, ...)` | WIRED | Constructor injection at `backend-hormonia/app/services/unified_whatsapp_service.py:225` |
| `backend-hormonia/app/integrations/whatsapp/api/routes.py` | `backend-hormonia/app/integrations/whatsapp/services/message_service.py` | `get_message_service` DI path | WIRED | WuzAPI dependency and constructor injection at `backend-hormonia/app/integrations/whatsapp/api/routes.py:134` and `backend-hormonia/app/integrations/whatsapp/api/routes.py:138` |
| `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py` | `backend-hormonia/app/integrations/wuzapi/__init__.py` | `get_wuzapi_client` import/property | WIRED | Import at `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:43` and lazy factory at `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:106` |
| `backend-hormonia/app/services/follow_up_system/service.py` | `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py` | sender construction | WIRED | Caller now uses `IdempotentMessageSender(db, redis_client)` at `backend-hormonia/app/services/follow_up_system/service.py:85` |
| `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/scheduler.py` | `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py` | sender construction | WIRED | Caller now uses `IdempotentMessageSender(db, redis_client)` at `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/scheduler.py:51` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| OUT-01 | `36-01-PLAN.md`, `36-03-PLAN.md` | UnifiedWhatsAppService uses WuzAPIClient for outbound | ✓ SATISFIED | WuzAPI import/factory/send path at `backend-hormonia/app/services/unified_whatsapp_service.py:26`, `backend-hormonia/app/services/unified_whatsapp_service.py:206`, `backend-hormonia/app/services/unified_whatsapp_service.py:532` |
| OUT-02 | `36-02-PLAN.md`, `36-03-PLAN.md` | WhatsAppMessageService queue pipeline wired to WuzAPIClient | ✓ SATISFIED | Queue DI rewired in `backend-hormonia/app/integrations/whatsapp/api/routes.py:134`, `backend-hormonia/app/integrations/whatsapp/api/routes.py:138`; WuzAPI send path in `backend-hormonia/app/integrations/whatsapp/services/message_service.py:586` |
| OUT-03 | `36-02-PLAN.md`, `36-03-PLAN.md` | IdempotentMessageSender uses WuzAPI instead of Evolution | ✓ SATISFIED | WuzAPI send and ID extraction in `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:418`, `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:424`; caller wiring removed in `backend-hormonia/app/services/follow_up_system/service.py:85` and `backend-hormonia/app/domain/messaging/scheduling/message_scheduler/scheduler.py:51` |
| OUT-04 | `36-01-PLAN.md`, `36-03-PLAN.md` | Raw-digit phone format and WuzAPI breaker key | ✓ SATISFIED | Raw-digit handling in unified/queue/idempotent paths at `backend-hormonia/app/services/unified_whatsapp_service.py:527`, `backend-hormonia/app/integrations/whatsapp/services/message_service.py:582`, `backend-hormonia/app/domain/messaging/delivery/idempotent_sender.py:415`; breaker key `wuzapi` at `backend-hormonia/app/services/unified_whatsapp_service.py:149` |

All requirement IDs declared in phase plans (`OUT-01`, `OUT-02`, `OUT-03`, `OUT-04`) were found in `.planning/REQUIREMENTS.md` and accounted for. No phase-36 orphaned requirements detected.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| N/A | N/A | No blocker TODO/placeholder/empty-implementation patterns found in modified outbound migration files | ℹ️ Info | No anti-patterns blocking phase goal achievement |

### Human Verification Required

None for code-wiring verification scope.

### Gaps Summary

Previous wiring gaps are closed: outbound API DI now injects WuzAPI into `WhatsAppMessageService`, and both `IdempotentMessageSender` runtime callers no longer instantiate/inject `EvolutionClient`. Regression checks on previously passed truths (Unified service migration and raw-digit/breaker behavior) remain intact.

---

_Verified: 2026-03-02T17:09:27Z_
_Verifier: Claude (gsd-verifier)_
