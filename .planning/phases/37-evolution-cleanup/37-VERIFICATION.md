---
phase: 37-evolution-cleanup
verified: 2026-03-02T23:54:07Z
status: passed
score: 6/6 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 3/6
  gaps_closed:
    - "Stack A runtime import path in message_handler unauthorized flow is removed; method is log-only no-op"
    - "Stack B runtime import path in queue manager now uses WuzAPIError classification"
    - "WhatsApp API package no longer imports tombstoned webhook router; package import chain is clean"
  gaps_remaining: []
  regressions: []
---

# Phase 37: Evolution Cleanup Verification Report

**Phase Goal:** All Evolution API code is tombstoned in a single commit — both Stack A and Stack B clients, the Evolution webhook handler, the Baileys message parser, LID resolution methods, and deprecated env vars are all removed from the active runtime.
**Verified:** 2026-03-02T23:54:07Z
**Status:** passed
**Re-verification:** Yes — after gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Stack A has zero active runtime importers | ✓ VERIFIED | `backend-hormonia/app/services/webhook/handlers/message_handler.py:1054` now implements `_send_unauthorized_response` as log-only no-op; no `get_evolution_client` matches under `backend-hormonia/app` and `python3` import check for `MessageWebhookHandler` succeeds. |
| 2 | Stack B has zero active runtime importers | ✓ VERIFIED | `backend-hormonia/app/integrations/whatsapp/queue/manager.py:19` imports `WuzAPIError`; no `EvolutionAPIError` matches under `backend-hormonia/app`; `python3` import check for `QueueManager` succeeds. |
| 3 | WhatsApp API package imports cleanly without webhook router | ✓ VERIFIED | `backend-hormonia/app/integrations/whatsapp/api/__init__.py:5` imports only `whatsapp_router` and `__all__` excludes webhook router; `python3` import check for `whatsapp_router` succeeds. |
| 4 | Queue manager classifies WuzAPI 429 as RATE_LIMIT and generic WuzAPI errors as API_ERROR | ✓ VERIFIED | `_categorize_failure` uses `isinstance(error, WuzAPIError)` branches at `backend-hormonia/app/integrations/whatsapp/queue/manager.py:486` and `backend-hormonia/app/integrations/whatsapp/queue/manager.py:488`; runtime check returns `rate_limit` and `api_error` respectively. |
| 5 | Unauthorized response path is disabled (log-only no-op) | ✓ VERIFIED | Caller still exists at `backend-hormonia/app/services/webhook/handlers/message_handler.py:495`; callee body at `backend-hormonia/app/services/webhook/handlers/message_handler.py:1054` only logs warning and sends no outbound message. |
| 6 | Both Evolution webhook integration tests are tombstoned and collection-safe | ✓ VERIFIED | `backend-hormonia/tests/integration/whatsapp/test_webhook_scenarios.py:1` and `backend-hormonia/tests/integration/whatsapp/test_webhook_fail_closed_and_queue_batch.py:1` are skip tombstones with `pytest.mark.skip`; no direct `from app.integrations.whatsapp.api import webhooks` usage remains in tests. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend-hormonia/app/services/webhook/handlers/message_handler.py` | Unauthorized response method disabled as log-only no-op, zero Evolution imports | ✓ VERIFIED | Exists; substantive `_send_unauthorized_response` no-op implemented; wired via call site at line 495. |
| `backend-hormonia/app/integrations/whatsapp/queue/manager.py` | WuzAPIError import replaces EvolutionAPIError for failure categorization | ✓ VERIFIED | Exists; substantive import and `_categorize_failure` branches use `WuzAPIError`; wired in runtime failure path. |
| `backend-hormonia/app/integrations/whatsapp/api/__init__.py` | Clean package init exporting only `whatsapp_router`, no `webhook_router` | ✓ VERIFIED | Exists; substantive minimal init; wired to `routes.py` router export and import chain succeeds. |
| `backend-hormonia/tests/integration/whatsapp/test_webhook_scenarios.py` | Skip-tombstoned test file | ✓ VERIFIED | Exists; substantive tombstone with `pytestmark = pytest.mark.skip(...)`; no tombstoned module import. |
| `backend-hormonia/tests/integration/whatsapp/test_webhook_fail_closed_and_queue_batch.py` | Skip-tombstoned test file | ✓ VERIFIED | Exists; substantive tombstone with `pytestmark = pytest.mark.skip(...)`; no tombstoned module import. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `backend-hormonia/app/integrations/whatsapp/queue/manager.py` | `backend-hormonia/app/integrations/wuzapi/errors.py` | `from app.integrations.wuzapi.errors import WuzAPIError` | ✓ WIRED | Import and usage both present (`manager.py:19`, `manager.py:486`, `manager.py:488`). |
| `backend-hormonia/app/integrations/whatsapp/api/__init__.py` | `backend-hormonia/app/integrations/whatsapp/api/routes.py` | `from .routes import router as whatsapp_router` | ✓ WIRED | Import/export path is active (`__init__.py:5`, `__init__.py:7`) and runtime import succeeds. |
| `backend-hormonia/app/services/webhook/handlers/message_handler.py` | unauthorized response call path | `await self._send_unauthorized_response(...)` | ✓ WIRED | Call site remains (`message_handler.py:495`) and target implementation is safe log-only no-op (`message_handler.py:1054`). |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| CLEAN-01 | `37-01-PLAN.md`, `37-03-PLAN.md`, `37-04-PLAN.md` | Stack A tombstoned and removed from active runtime | ✓ SATISFIED | No `get_evolution_client` usage in `backend-hormonia/app`; unauthorized path now log-only (`message_handler.py:1054`). |
| CLEAN-02 | `37-02-PLAN.md`, `37-03-PLAN.md`, `37-04-PLAN.md` | Stack B tombstoned and removed from active runtime | ✓ SATISFIED | `queue/manager.py` imports `WuzAPIError` (`manager.py:19`) and no `EvolutionAPIError` remains under `backend-hormonia/app`. |
| CLEAN-03 | `37-02-PLAN.md`, `37-03-PLAN.md`, `37-04-PLAN.md` | Evolution webhook wiring removed from runtime | ✓ SATISFIED | `api/__init__.py` exports only `whatsapp_router`; package import succeeds; webhook tests are skip-tombstoned. |
| CLEAN-04 | `37-02-PLAN.md`, `37-03-PLAN.md`, `37-04-PLAN.md` | Baileys/Evolution message extractor tombstoned | ✓ SATISFIED | `backend-hormonia/app/services/webhook/utils/message_extractor.py:9` raises ImportError sentinel; no active `extract_message_data` usage (only legacy comment reference). |
| CLEAN-05 | `37-02-PLAN.md`, `37-03-PLAN.md`, `37-04-PLAN.md` | LID resolution methods removed from runtime logic | ✓ SATISFIED | `backend-hormonia/app/services/webhook/utils/phone_normalizer.py` has no `resolve_phone_from_lid`/helper methods; no `@lid` branch in webhook message handler. |
| CLEAN-06 | `37-02-PLAN.md`, `37-03-PLAN.md`, `37-04-PLAN.md` | Deprecated `WHATSAPP_EVOLUTION_*` removed from runtime/env templates | ✓ SATISFIED | No `WHATSAPP_EVOLUTION` matches under `backend-hormonia/app`; `backend-hormonia/.env.production.example` has only WuzAPI variables (`:150`, `:156`, `:157`). |

Orphaned requirements for Phase 37 in `.planning/REQUIREMENTS.md`: none (all Phase 37 IDs `CLEAN-01..CLEAN-06` are declared in plan frontmatter and verified).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| N/A | N/A | No TODO/FIXME/placeholder/empty-impl patterns found in phase-04 key files | ℹ️ Info | No blocker anti-patterns detected for phase goal. |

### Human Verification Required

None. The phase goal is import/wiring/tombstone cleanup and was fully verified via static checks plus targeted runtime import checks.

### Gaps Summary

No remaining gaps. Previously failed runtime links (Stack A unauthorized-path import, Stack B error-type import, and API webhook router import) are closed, and prior verified cleanup truths remain stable.

---

_Verified: 2026-03-02T23:54:07Z_
_Verifier: Claude (gsd-verifier)_
