# M004/S01 — Research

**Date:** 2026-03-14

## Summary

S01 now freezes a smaller and more honest post-S04 runtime boundary than it did at original closeout. The residue verifier remains the source of truth for what still lives inside the official auth/session runtime, but root `/session/*` retirement is no longer modeled as approved residue. That surface moved to focused route proof in `backend-hormonia/tests/auth/test_session_validation.py`, while the verifier now reports only the backend residue that still survives after the S04 transport cut: `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`.

That matters because the contract is split deliberately now:

1. **Focused route retirement proof** covers the explicit 410 tombstone for `/session/*`.
2. **`runtime-residue-allowlist.json` + `verify-runtime-residue.sh`** cover the smaller live residue inventory that still exists in backend helpers, cache/auth compatibility seams, and rejection plumbing.
3. **Frontend scopes remain present with `approved: []`** so any reintroduction of legacy auth/session transport still fails loudly.

Latest reruns for the reduced backend boundary ended with `RESULT: --report backend OK` and `RESULT: --check backend OK`.

## Recommendation

Treat the handoff pack as a two-surface contract after S04:

1. **Executable boundary for live residue:** `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` define the approved category/scope/file/anchor contract for the residue that still exists.
2. **Executable retirement proof for dead surfaces:** `backend-hormonia/tests/auth/test_session_validation.py` proves root `/session/*` stays intentionally dead with deterministic HTTP 410 semantics.
3. **Readable map:** this research artifact explains which categories remain live, which ones were retired out of the verifier, and who owns the next cuts.
4. **Condensed handoff + replay:** `S01-SUMMARY.md` and `S01-UAT.md` must move with the allowlist whenever the live boundary shrinks.

Do not delete the `frontend` scopes just because they are zero-approved. They remain the reintroduction guard for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, and `firebase_narrative`.

## Finalized Residue Boundary

### Official runtime surfaces still in scope

The frozen S01 failure surface is the union of the category roots defined in `runtime-residue-allowlist.json`, filtered by that file’s scope defaults:

- `backend` scope: Python sources under the approved auth/session/runtime roots in `backend-hormonia/app`
- `frontend` scope: TypeScript/TSX sources under the approved auth/api/websocket/admin roots in `frontend-hormonia/src` plus the shared admin types package
- Companion proof for retired root session routes: `backend-hormonia/tests/auth/test_session_validation.py`

### What left the verifier after S04

These surfaces are no longer approved residue inside the verifier boundary:

- `root_legacy_session` — removed from `runtime-residue-allowlist.json`; root `/session/*` is now proved separately as an explicit tombstone
- backend `firebase_narrative` in `backend-hormonia/app/routers/auth_session.py` — removed with the retirement router rewrite
- stale helper/doc hotspots that used to advertise `X-Session-ID` or session-as-Bearer transport — removed from the allowlist because the code no longer contains them

### What remains intentionally live inside the verifier

These strings still exist and are therefore approved rather than treated as surprise drift:

- Backend-only `firebase_uid` compatibility residue in auth/session/cache/user-adapter seams
- Backend-only `X-Session-ID` text where it still exists strictly for rejection/detection plumbing
- Backend-only `Authorization: Bearer <session_id>` text where it still exists strictly for rejection/detection plumbing
- Backend-only websocket `session_id` query fallback text where it still exists strictly for rejection plumbing
- The `frontend` scope itself, but with **no approved residue**; it exists only to catch regressions

### Out-of-scope exclusions (`runtime-residue-allowlist.json`)

| Exclusion id | Why excluded | Paths |
|---|---|---|
| `schema_model_residue` | Schema/model residue belongs to M005, not the S01 official runtime failure surface. | `backend-hormonia/app/models/**`, `backend-hormonia/app/schemas/**` |
| `historical_docs_tests` | Historical docs, generated docs, and tests may mention the legacy contract without representing live runtime drift. | `backend-hormonia/tests/**`, `backend-hormonia/docs/**`, `backend-hormonia/app/api/v2/routers/docs/**`, `frontend-hormonia/tests/**`, `frontend-hormonia/src/**/__tests__/**`, `frontend-hormonia/src/**/*.test.ts`, `frontend-hormonia/src/**/*.test.tsx`, `frontend-hormonia/src/**/*.spec.ts`, `frontend-hormonia/src/**/*.spec.tsx`, `docs/**` |
| `vendor_or_unrelated_session_strings` | WuzAPI, quiz/public session strings, mocks, and unrelated clients are not the staff auth/session runtime boundary frozen in S01. | `backend-hormonia/app/api/v2/monitoring/wuzapi.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`, `frontend-hormonia/src/features/whatsapp/**`, `frontend-hormonia/src/services/whatsapp/**`, `frontend-hormonia/src/mocks/**`, `frontend-hormonia/src/monitoring/**` |

## Approved Hotspot Inventory

### `firebase_uid`

**Meaning:** compatibility-oriented `firebase_uid` residue retained in backend fallback/cache/auth helpers after S04 retired root `/session/*` and legacy session transport from the official runtime.

- `backend` — 11 files / 107 matching lines
  - `backend-hormonia/app/api/v2/auth_session_shared.py` (5)
  - `backend-hormonia/app/api/v2/routers/admin/utils.py` (1)
  - `backend-hormonia/app/api/v2/routers/auth.py` (7)
  - `backend-hormonia/app/api/v2/user_cache_shared.py` (8)
  - `backend-hormonia/app/core/redis_manager/session_cache.py` (8)
  - `backend-hormonia/app/dependencies/auth_dependencies.py` (25)
  - `backend-hormonia/app/dependencies/auth_legacy_firebase.py` (20)
  - `backend-hormonia/app/dependencies/auth_role_dependencies.py` (4)
  - `backend-hormonia/app/dependencies/auth_session_cache.py` (24)
  - `backend-hormonia/app/dependencies/auth_session_contract.py` (4)
  - `backend-hormonia/app/dependencies/auth_user_adapter.py` (1)
- `frontend` — no approved residue
- **Post-S04 interpretation:** this is no longer mixed with root-session route or transport residue. What remains is backend compatibility/fallback/cache baggage only.
- **Cut owner:** S05.

### `x_session_id`

**Meaning:** legacy `X-Session-ID` text that survives only in backend rejection/detection plumbing after S04 removed it as accepted staff session transport.

- `backend` — 3 files / 4 matching lines
  - `backend-hormonia/app/api/v2/routers/admin/dependencies.py` (1)
  - `backend-hormonia/app/api/websockets.py` (1)
  - `backend-hormonia/app/dependencies/auth_dependencies.py` (2)
- `frontend` — no approved residue
- **Post-S04 interpretation:** these are no longer happy-path auth seams. They exist so the runtime can notice and reject legacy transport attempts or preserve dependency compatibility while ignoring them.
- **Cut owner:** S05 only if the remaining rejection/detection text can be removed without weakening diagnostics or tests.

### `session_bearer_fallback`

**Meaning:** `Authorization: Bearer <session_id>` text that survives only in backend rejection/detection plumbing after S04 removed it as accepted staff session transport.

- `backend` — 2 files / 3 matching lines
  - `backend-hormonia/app/api/v2/routers/admin/dependencies.py` (2)
  - `backend-hormonia/app/dependencies/auth_session_contract.py` (1)
- `frontend` — no approved residue
- **Post-S04 interpretation:** bearer-as-session is dead as official runtime transport. The remaining strings only support rejection/detection branches.
- **Cut owner:** S05 if later cleanup can remove them without making legacy-attempt diagnostics less attributable.

### `websocket_session_id_query`

**Meaning:** websocket `session_id` query fallback text retained only in backend rejection plumbing after S04 removed it as accepted transport.

- `backend` — 1 file / 6 matching lines
  - `backend-hormonia/app/api/websockets.py` (6)
- `frontend` — no approved residue
- **Post-S04 interpretation:** websocket auth is cookie-only on the happy path; the remaining query residue only exists so rejected legacy attempts keep the right diagnostics.
- **Cut owner:** S05 if the rejection plumbing can be simplified without collapsing `AUTH_WEBSOCKET_SESSION_INVALID` vs `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`.

### `firebase_narrative`

**Meaning:** frontend reintroduction guard only. Backend Firebase narrative was removed from the scoped runtime boundary when `auth_session.py` became a retirement router.

- `backend` — no approved residue in scope
- `frontend` — no approved residue
- **Post-S04 interpretation:** keep the category roots and empty frontend approvals so new Firebase-era narrative drift still fails loudly.
- **Cut owner:** none right now; this is guard-only state.

## Cut Order Snapshot For S02–S06

1. **S02 — backend canonical identity/session cut**
   - Removed backend happy-path `firebase_uid` dependence from canonical auth/session/cache flows while leaving fallback-only residue visible.
2. **S03 — official frontend canonical contract cut**
   - Removed official frontend emission of `X-Session-ID`, `Authorization: Bearer <session_id>`, websocket `session_id` query fallback, browser `session_id` rehydration, and Firebase-shaped auth/admin narrative/type baggage.
3. **S04 — retire legacy auth/session surfaces**
   - Removed backend acceptance of `X-Session-ID`, session-as-Bearer, and websocket query fallback.
   - Rewrote root `/session/*` as an explicit tombstone and moved that proof into focused pytest.
   - Republished the allowlist so the verifier now describes only the smaller live residue boundary.
4. **S05 — remove adjacent Firebase runtime residue**
   - Remove the remaining backend `firebase_uid` compatibility residue and any rejection/detection text that no longer earns its keep.
5. **S06 — assembled no-Firebase stack proof**
   - Replay the critical routed stack end to end with the converged backend/frontend contract and the reduced post-S04 residue map.

## Don’t Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Scoped runtime residue inventory and drift detection | `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` | Already emits the approved live boundary by category/scope and fails on unexpected files or moved anchors. |
| Machine-readable hotspot ownership | `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` | Keeps file/anchor bookkeeping explicit so later cleanup updates the contract instead of relying on memory. |
| Root `/session/*` retirement proof | `backend-hormonia/tests/auth/test_session_validation.py` | Keeps tombstone semantics explicit and separate from the live residue inventory. |
| Failure-path proof for the guardrail | `backend-hormonia/tests/unit/test_runtime_residue_guard.py` | Proves unexpected residue and moved hotspots fail with category/path/anchor diagnostics. |

## Existing Code and Patterns

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — authoritative category ids, scope names, roots, and approved hotspots for the reduced post-S04 boundary.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — authoritative `--report` / `--check` surface for the still-live residue inventory.
- `backend-hormonia/tests/auth/test_session_validation.py` — authoritative proof that root `/session/*` remains an explicit 410 tombstone.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — authoritative proof that the guard emits inspectable `unexpected_file=` and `moved_hotspot=` failures.
- `backend-hormonia/app/api/websockets.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, and `backend-hormonia/app/dependencies/auth_*` — the remaining backend rejection/detection residue that still belongs to the live boundary.

## Constraints

- S01 is still an enabling slice only. It freezes the runtime boundary; it does not prove the full milestone is done.
- Root `/session/*` is intentionally no longer part of the residue allowlist. Use the focused pytest file for that surface instead of trying to re-add it as approved debt.
- Empty `frontend` approved sets are intentional after S03 and still intentional after S04. Do not repopulate them casually.
- Anything left for M005 must be schema/migration residue, not ambiguous live runtime behavior.

## Common Pitfalls

- **Updating the allowlist but not the focused route proof** — `/session/*` retirement is now a separate contract and can drift independently.
- **Deleting empty frontend scopes** — keeping the roots with `approved: []` is what makes reintroduction visible.
- **Treating rejection/detection text as accepted transport** — after S04, remaining `X-Session-ID` / bearer / websocket query strings are debt only if they still serve diagnostics or compatibility signatures.
- **Broadening the failure scope to docs/tests/vendor code** — that makes the guard noisy and hides real runtime drift.

## Open Risks

- Backend resolver/helper drift can still hide behind the remaining `firebase_uid` compatibility seams until S05 removes them.
- Websocket rejection plumbing still contains the densest concentration of legacy transport text; careless cleanup there could collapse the diagnostic split between invalid-session and lookup-failure cases.
- The frontend scope is clean now, so stale allowlist edits will be noisy by design if future slices reintroduce legacy auth/session text.

## Sources

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`
- `backend-hormonia/tests/auth/test_session_validation.py`
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py`
- `.gsd/milestones/M004/slices/S04/tasks/T01-SUMMARY.md`
- `.gsd/milestones/M004/slices/S04/tasks/T02-SUMMARY.md`
