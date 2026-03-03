---
phase: 38-tests-ci-validation
verified: 2026-03-03T16:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Integrated STOP webhook -> real handle_opt_out mutation -> UnifiedWhatsAppService.send_message returns False — proven in test_stop_webhook_to_send_guard_integrated"
  gaps_remaining: []
  regressions: []
---

# Phase 38: Tests CI Validation Verification Report

**Phase Goal:** Close test and CI validation gaps for WuzAPI migration — webhook tests, HMAC validation, opt-out E2E, Evolution import regression guard (full test suite passes with WuzAPI contracts, LGPD-critical paths covered, and CI source guards confirm zero Evolution imports outside tombstones)
**Verified:** 2026-03-03T16:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (Plans 38-04 and 38-05 closed TEST-04 gap)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | WuzAPI contract tests pass for send/media/auth/retry/rate-limit paths | ✓ VERIFIED | `test_wuzapi_client.py` and `test_wuzapi_media.py` cover all paths; 38-05-SUMMARY.md reports `86 passed, 1 skipped` in full regression gate. |
| 2 | Webhook and extractor tests use captured WuzAPI JSON fixtures (Message, ReadReceipt, PresenceUpdate) | ✓ VERIFIED | Three JSON fixtures exist at `backend-hormonia/tests/fixtures/wuzapi/`; consumed via `load_fixture()` in both `test_wuzapi_webhook.py` (lines 19-21, 331-367) and `test_wuzapi_extractor.py` (lines 12-17, 171-190). |
| 3 | HMAC coverage includes valid signature=200, tampered payload=403, missing header=403 | ✓ VERIFIED | `test_valid_hmac_returns_200` (line 90), `test_invalid_hmac_returns_403` (line 99), `test_missing_hmac_header_returns_403` (line 125) all present in `test_wuzapi_webhook.py`. |
| 4 | Opt-out E2E chain is proven end-to-end: STOP inbound -> patient.messaging_stopped_at set by real handle_opt_out -> subsequent UnifiedWhatsAppService.send_message returns False | ✓ VERIFIED | `test_stop_webhook_to_send_guard_integrated` in `test_opt_out_lgpd.py` (lines 95-200): posts STOP to `/webhooks/wuzapi` via httpx.ASGITransport, `handle_opt_out` is NOT mocked (real mutation runs at `message_handler.py:107`), then `UnifiedWhatsAppService.send_message()` is called with the SAME patient object and asserts `result is False`. |
| 5 | CI/source guards enforce no Evolution imports outside tombstones | ✓ VERIFIED | `scripts/check_evolution_imports.py` uses AST scanning; `test_no_evolution_imports_in_app` in `test_evolution_import_regression.py` invokes it via subprocess and asserts exit 0; `test_evolution_client.py` tombstoned with `pytestmark = pytest.mark.skip`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend-hormonia/tests/fixtures/wuzapi/message_inbound.json` | Captured Message webhook payload fixture | ✓ VERIFIED | Contains `type: Message`, `event.Info.ID: 3EB0A618C4E77B6E5A3D`, `event.Info.Sender`, `event.Message.Conversation`, plus extra realistic whatsmeow fields (MessageSource, Timestamp). |
| `backend-hormonia/tests/fixtures/wuzapi/read_receipt.json` | Captured ReadReceipt webhook payload fixture | ✓ VERIFIED | Contains `type: ReadReceipt`, `event.Info.ID`, `event.Receipt.Type: read`, `event.Receipt.MessageIDs`, plus `PreviousStatus`. |
| `backend-hormonia/tests/fixtures/wuzapi/presence_update.json` | Captured unknown event payload fixture | ✓ VERIFIED | Contains `type: PresenceUpdate` and `event.JID`, `event.Unavailable`, `event.LastSeen`. |
| `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py` | Fixture-backed webhook + HMAC + idempotency + STOP coverage | ✓ VERIFIED | `load_fixture()` helper at line 19, three fixture-backed tests (lines 331-367), HMAC tests (lines 89-136), all prior tests intact. |
| `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_extractor.py` | Fixture-backed extractor coverage | ✓ VERIFIED | `load_fixture()` at line 15, `TestFixturePayloads` class with `test_extract_message_from_fixture` and `test_extract_receipt_from_fixture` (lines 171-190). |
| `backend-hormonia/tests/unit/test_opt_out_lgpd.py` | Integrated STOP webhook -> real mutation -> send guard chain test | ✓ VERIFIED | 5 tests present: `test_handle_opt_out_sets_messaging_stopped_at`, `test_send_guard_blocks_opted_out_patient_via_service`, `test_send_guard_allows_active_patient_via_service`, `test_send_guard_blocks_opted_out_patient`, and the gap-closing `test_stop_webhook_to_send_guard_integrated`. `handle_opt_out` is NOT patched in the integrated test. |
| `backend-hormonia/scripts/check_evolution_imports.py` | AST CI guard for tombstoned Evolution imports | ✓ VERIFIED | Uses `ast.parse`, scans `app/**/*.py`, excludes tombstone dirs `app/integrations/evolution` and `app/integrations/whatsapp/services`, exits non-zero on violations. |
| `backend-hormonia/tests/unit/test_evolution_import_regression.py` | Pytest wrapper for CI guard | ✓ VERIFIED | Runs guard script via `subprocess.run` with `sys.executable` and asserts `returncode == 0`. |
| `backend-hormonia/tests/unit/test_evolution_client.py` | Tombstoned safely collectable test module | ✓ VERIFIED | Module-level `pytestmark = pytest.mark.skip(reason="Evolution API tombstoned in Phase 37 ...")` present. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `tests/integrations/wuzapi/test_wuzapi_webhook.py` | `tests/fixtures/wuzapi/*.json` | `load_fixture()` at line 19 | ✓ WIRED | Fixture-backed tests call `load_fixture("message_inbound.json")`, `load_fixture("read_receipt.json")`, `load_fixture("presence_update.json")`. |
| `tests/integrations/wuzapi/test_wuzapi_extractor.py` | `tests/fixtures/wuzapi/*.json` | `load_fixture()` at line 15 | ✓ WIRED | `test_extract_message_from_fixture` and `test_extract_receipt_from_fixture` consume both fixtures. |
| `tests/integrations/wuzapi/test_wuzapi_webhook.py` | `app/integrations/wuzapi/webhook.py` | `httpx.ASGITransport` integration calls | ✓ WIRED | Tests post to `/webhooks/wuzapi` and assert handler responses end-to-end. |
| `tests/unit/test_opt_out_lgpd.py` | `app/integrations/wuzapi/webhook.py` | `httpx.ASGITransport` POST to `/webhooks/wuzapi` | ✓ WIRED | `test_stop_webhook_to_send_guard_integrated` posts STOP via ASGITransport using the same wuzapi router. |
| `tests/unit/test_opt_out_lgpd.py` | `app/services/webhook/handlers/message_handler.py:107` | real `handle_opt_out` execution (NOT patched) | ✓ WIRED | No `patch("...handle_opt_out...")` present in `test_stop_webhook_to_send_guard_integrated`; `handle_opt_out` runs its real code path and sets `patient.messaging_stopped_at`. |
| `tests/unit/test_opt_out_lgpd.py` | `app/services/unified_whatsapp_service.py:314` | `send_message()` opt-out guard | ✓ WIRED | After webhook mutation, the same patient is passed to `UnifiedWhatsAppService.send_message()` via `patch.object(service, "_ensure_patient_loaded", return_value=patient)`; guard at line 314 returns False. |
| `scripts/check_evolution_imports.py` | `app/**/*.py` | AST traversal (`ast.parse` + `rglob`) | ✓ WIRED | Script enumerates `app/` dir, excludes tombstone dirs, reports violations with file:line snippets. |
| `tests/unit/test_evolution_import_regression.py` | `scripts/check_evolution_imports.py` | `subprocess.run` with `sys.executable` | ✓ WIRED | Regression test asserts `result.returncode == 0`. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| TEST-01 | `38-01-PLAN.md` | WuzAPIClient coverage for text/media/auth/retry/rate-limit | ✓ SATISFIED | WuzAPI integration suite passes; 38-05-SUMMARY.md reports 86 passed, 1 skipped. REQUIREMENTS.md shows `[x]` checked. |
| TEST-02 | `38-01-PLAN.md`, `38-03-PLAN.md` | Real fixture-backed Message/ReadReceipt/unknown-event webhook tests | ✓ SATISFIED | JSON fixtures present and loaded in webhook/extractor tests via `load_fixture()`; five fixture-backed tests across two files. REQUIREMENTS.md shows `[x]` checked. |
| TEST-03 | `38-01-PLAN.md` | HMAC acceptance/rejection tests including missing header behavior | ✓ SATISFIED | Valid/tampered/missing-header tests present and passing in `test_wuzapi_webhook.py`. REQUIREMENTS.md shows `[x]` checked. |
| TEST-04 | `38-02-PLAN.md`, `38-04-PLAN.md`, `38-05-PLAN.md` | E2E STOP -> `messaging_stopped_at` set -> future send blocked | ✓ SATISFIED | `test_stop_webhook_to_send_guard_integrated` proves full chain in one continuous test: STOP POST -> real mutation -> `send_message() is False`. `handle_opt_out` NOT mocked. REQUIREMENTS.md shows `[x]` checked. |
| TEST-05 | `38-02-PLAN.md` | Zero Evolution imports outside tombstones | ✓ SATISFIED | Guard script passes, pytest wrapper passes, tombstoned test safely skipped. REQUIREMENTS.md shows `[x]` checked. |

Orphaned requirements for Phase 38: none. All `TEST-01` through `TEST-05` are declared in phase 38 plan frontmatter and confirmed in `REQUIREMENTS.md`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `tests/integrations/wuzapi/test_wuzapi_webhook.py` | 178, 197, 214, 246 | Existing STOP integration tests patch `handle_opt_out` with AsyncMock | ℹ️ Info | Pre-existing pattern; these tests verify webhook routing and opt-out call dispatch, NOT the mutation chain. TEST-04 is satisfied by the integrated test in `test_opt_out_lgpd.py` which does NOT patch `handle_opt_out`. No longer a blocker. |

No new anti-patterns introduced by Plans 38-04 or 38-05.

### Human Verification Required

None. All checks verified programmatically.

### Re-verification Gap Closure Analysis

**Gap that was open:** "No single end-to-end test proves STOP inbound event leads to `messaging_stopped_at` mutation and then blocked send in one continuous path."

**How closed:** Plan 38-05 added `test_stop_webhook_to_send_guard_integrated` to `backend-hormonia/tests/unit/test_opt_out_lgpd.py`. The test:

1. Creates a MagicMock patient with `messaging_stopped_at = None`
2. Posts a STOP message to `/webhooks/wuzapi` via `httpx.ASGITransport` — real HTTP layer
3. Does NOT mock `handle_opt_out` — the real function runs and sets `patient.messaging_stopped_at` at `message_handler.py:107`
4. Asserts `patient.messaging_stopped_at is not None` — proves the mutation ran
5. Instantiates `UnifiedWhatsAppService` and calls `send_message()` with the SAME patient object
6. Asserts `result is False` — proves the guard at `unified_whatsapp_service.py:314` sees the mutated state and blocks the send

The key distinction from the previous partial tests: `handle_opt_out` is never patched in this test, so the full mutation runs through real application code. The same patient object carries the mutation from step 3 into step 5, proving the continuous chain.

**Regression check on previously-passing items (1-3 and 5):** All artifacts confirmed still present and wired. No regressions detected.

---

_Verified: 2026-03-03T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
