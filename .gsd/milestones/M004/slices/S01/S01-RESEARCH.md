# M004/S01 — Research

**Date:** 2026-03-14

## Summary

S01 now freezes a smaller and more honest post-S05 runtime boundary than it did after S04. The residue verifier is still the source of truth for what survives inside the official auth/session runtime, but its meaning changed again once S05 removed live `firebase_uid` emission from shared auth/cache restore, login-written session payloads, core Redis session storage, audit/admin/docs surfaces, and adjacent frontend types.

After the S05 republish, the verifier still reports four backend-owned categories — `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query` — plus zero-approved frontend reintroduction guards. What changed is the meaning of `firebase_uid`: it no longer covers live session/cache/login writers like `auth_session_shared.py`, `session_cache.py`, or `auth_user_adapter.py`. It now names a smaller passive-compatibility boundary concentrated in dependency fallback seams plus a small adjacent admin/auth/cache sanitizer trio.

That split matters because the contract is deliberately layered now:

1. **Focused S05 proof packs** prove the cleaned surfaces that no longer belong in the verifier boundary.
2. **`runtime-residue-allowlist.json` + `verify-runtime-residue.sh`** define the smaller live residue inventory that still survives in backend compatibility/rejection seams.
3. **Frontend scopes remain present with `approved: []`** so any reintroduction of Firebase/session-transport residue still fails loudly.
4. **Root `/session/*` retirement stays separate** under `backend-hormonia/tests/auth/test_session_validation.py` rather than re-entering the allowlist.

Latest republish reruns for the reduced boundary ended with `RESULT: --report all OK` and `RESULT: --check all OK`.

## Recommendation

Treat the handoff pack as a three-surface contract after S05:

1. **Executable boundary for surviving live residue:** `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` define the approved category/scope/file/anchor contract for what still exists.
2. **Focused proof for surfaces that left the verifier:** the S05 packs (`py_compile`, auth/session pytest, audit/admin/docs pytest, frontend vitest, frontend build) prove the cleaned runtime-adjacent surfaces that are no longer approved residue.
3. **Readable map + replay guidance:** this research artifact, `S01-SUMMARY.md`, and `S01-UAT.md` must move with the allowlist whenever the live boundary shrinks.

Do not delete the `frontend` scopes just because they are zero-approved. They remain the reintroduction guard for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, and `firebase_narrative`.

## Finalized Residue Boundary

### Official runtime surfaces still in scope

The frozen S01 failure surface is the union of the category roots defined in `runtime-residue-allowlist.json`, filtered by that file’s scope defaults:

- `backend` scope: Python sources under the approved auth/session/runtime roots in `backend-hormonia/app`
- `frontend` scope: TypeScript/TSX sources under the approved auth/api/websocket/admin roots in `frontend-hormonia/src` plus the shared admin types package
- Companion proof for retired root session routes: `backend-hormonia/tests/auth/test_session_validation.py`
- Companion proof for cleaned post-S05 adjacent surfaces:
  - `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
  - `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
  - `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
  - `cd frontend-hormonia && npm run build`

### What left the verifier after S05

These surfaces are no longer approved residue inside the verifier boundary:

- `backend-hormonia/app/api/v2/auth_session_shared.py` — shared session restore no longer keeps approved `firebase_uid` passthrough residue
- `backend-hormonia/app/core/redis_manager/session_cache.py` — core Redis session storage no longer keeps approved `firebase_uid` session payload residue
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — the shared auth user adapter no longer serializes approved `firebase_uid` runtime payload residue
- old payload-writing anchors in `backend-hormonia/app/api/v2/routers/auth.py` and `backend-hormonia/app/api/v2/user_cache_shared.py` — replaced by a compatibility comment and a sanitizer anchor, which better match the post-S05 meaning
- audit/admin/docs/frontend canonical surfaces cleaned in S05 — still verified by focused proof packs, but no longer represented as approved runtime residue in S01

### What remains intentionally live inside the verifier

These strings still exist and are therefore approved rather than treated as surprise drift:

- Backend-only `firebase_uid` compatibility residue in dependency fallback/cache helpers plus adjacent admin/auth/cache sanitizer code
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

**Meaning:** passive `firebase_uid` compatibility residue retained in backend fallback, sanitization, and adjacent admin/auth helpers after S05 removed live session/cache/login/audit/docs/frontend runtime emission.

- `backend` — 8 files / 79 matching lines
  - `backend-hormonia/app/api/v2/routers/admin/utils.py` (1)
  - `backend-hormonia/app/api/v2/routers/auth.py` (1)
  - `backend-hormonia/app/api/v2/user_cache_shared.py` (1)
  - `backend-hormonia/app/dependencies/auth_dependencies.py` (25)
  - `backend-hormonia/app/dependencies/auth_legacy_firebase.py` (20)
  - `backend-hormonia/app/dependencies/auth_role_dependencies.py` (4)
  - `backend-hormonia/app/dependencies/auth_session_cache.py` (23)
  - `backend-hormonia/app/dependencies/auth_session_contract.py` (4)
- `frontend` — no approved residue
- **Post-S05 interpretation:** these are no longer core Redis session writers, shared auth restore writers, login payload writers, audit/admin-extensions serializers, routed docs examples, or adjacent frontend type surfaces. What remains is passive compatibility/rejection-adjacent residue only.
- **Replay owner:** S06 proves the assembled stack still behaves canonically with this reduced boundary. M005 does **not** own these runtime hits; it owns excluded schema/model debt only.

### `x_session_id`

**Meaning:** legacy `X-Session-ID` text that survives only in backend rejection/detection plumbing after S04 removed it as accepted staff session transport.

- `backend` — 3 files / 4 matching lines
  - `backend-hormonia/app/api/v2/routers/admin/dependencies.py` (1)
  - `backend-hormonia/app/api/websockets.py` (1)
  - `backend-hormonia/app/dependencies/auth_dependencies.py` (2)
- `frontend` — no approved residue
- **Post-S05 interpretation:** these are still not happy-path auth seams. They exist so the runtime can notice and reject legacy transport attempts or preserve dependency compatibility while ignoring them.
- **Replay owner:** S06 proof only. M005 remains out of scope.

### `session_bearer_fallback`

**Meaning:** `Authorization: Bearer <session_id>` text that survives only in backend rejection/detection plumbing after S04 removed it as accepted staff session transport.

- `backend` — 2 files / 3 matching lines
  - `backend-hormonia/app/api/v2/routers/admin/dependencies.py` (2)
  - `backend-hormonia/app/dependencies/auth_session_contract.py` (1)
- `frontend` — no approved residue
- **Post-S05 interpretation:** bearer-as-session is still dead as official runtime transport. The remaining strings only support rejection/detection branches.
- **Replay owner:** S06 proof only. M005 remains out of scope.

### `websocket_session_id_query`

**Meaning:** websocket `session_id` query fallback text retained only in backend rejection plumbing after S04 removed it as accepted transport.

- `backend` — 1 file / 6 matching lines
  - `backend-hormonia/app/api/websockets.py` (6)
- `frontend` — no approved residue
- **Post-S05 interpretation:** websocket auth is cookie-only on the happy path; the remaining query residue only exists so rejected legacy attempts keep the right diagnostics.
- **Replay owner:** S06 proof only. M005 remains out of scope.

### `firebase_narrative`

**Meaning:** frontend reintroduction guard only. Backend Firebase narrative was removed from the scoped runtime boundary when `auth_session.py` became a retirement router and S05 cleaned the adjacent frontend/admin/docs story.

- `backend` — no approved residue in scope
- `frontend` — no approved residue
- **Post-S05 interpretation:** keep the category roots and empty frontend approvals so new Firebase-era narrative drift still fails loudly.
- **Replay owner:** guard-only state.

## Cut Order Snapshot For S02–S06

1. **S02 — backend canonical identity/session cut**
   - Removed backend happy-path `firebase_uid` dependence from canonical auth/session/cache flows while leaving fallback-only residue visible.
2. **S03 — official frontend canonical contract cut**
   - Removed official frontend emission of `X-Session-ID`, `Authorization: Bearer <session_id>`, websocket `session_id` query fallback, browser `session_id` storage/rehydration, and Firebase-shaped auth/admin narrative/type baggage.
3. **S04 — retire legacy auth/session surfaces**
   - Removed backend acceptance of `X-Session-ID`, session-as-Bearer, and websocket query fallback.
   - Rewrote root `/session/*` as an explicit tombstone and moved that proof into focused pytest.
   - Republished the allowlist so the verifier described only the smaller live residue boundary.
4. **S05 — remove adjacent Firebase runtime residue**
   - Removed live `firebase_uid` session/cache/login/shared-adapter emission from the core runtime path.
   - Converged audit/admin-extensions/docs output and adjacent frontend types on the canonical cookie-backed session contract.
   - Republished the allowlist so `firebase_uid` now means passive compatibility/sanitization/admin-adjacent residue only.
5. **S06 — assembled no-Firebase stack proof**
   - Replay the critical routed stack end to end with the converged backend/frontend contract and the reduced post-S05 residue map.

## Don’t Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Scoped runtime residue inventory and drift detection | `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` | Already emits the approved live boundary by category/scope and fails on unexpected files or moved anchors. |
| Machine-readable hotspot ownership | `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` | Keeps file/anchor bookkeeping explicit so later cleanup updates the contract instead of relying on memory. |
| Root `/session/*` retirement proof | `backend-hormonia/tests/auth/test_session_validation.py` | Keeps tombstone semantics explicit and separate from the live residue inventory. |
| Focused post-S05 cleanup proof | The S05 py_compile/pytest/vitest/build packs | Proves the cleaned auth/cache/login/audit/docs/type surfaces stay out of the live boundary instead of silently drifting back in. |
| Failure-path proof for the guardrail | `backend-hormonia/tests/unit/test_runtime_residue_guard.py` | Proves unexpected residue and moved hotspots fail with category/path/anchor diagnostics. |

## Existing Code and Patterns

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — authoritative category ids, scope names, roots, and approved hotspots for the reduced post-S05 boundary.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — authoritative `--report` / `--check` surface for the still-live residue inventory.
- `backend-hormonia/tests/auth/test_session_validation.py` — authoritative proof that root `/session/*` remains an explicit 410 tombstone.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — authoritative proof that the guard emits inspectable `unexpected_file=` and `moved_hotspot=` failures.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`, `tests/unit/test_session_cache.py`, `tests/api/v2/test_auth_session_shared_canonical_identity.py`, `tests/api/v2/test_auth_local_login.py`, `tests/api/test_websocket_session_auth_contract.py`, `tests/services/audit/test_audit_service.py`, `tests/api/v2/test_admin_extensions.py`, `tests/api/v2/test_docs.py`, and the frontend S05 type/build checks — authoritative proof that the surfaces removed from the verifier boundary stay clean.

## Constraints

- S01 is still an enabling slice only. It freezes the runtime boundary; it does not prove the full milestone is done.
- Root `/session/*` is intentionally no longer part of the residue allowlist. Use the focused pytest file for that surface instead of trying to re-add it as approved debt.
- Empty `frontend` approved sets remain intentional after S05. Do not repopulate them casually.
- Anything left for M005 must be schema/migration residue, not ambiguous live runtime behavior.
- S06 owns assembled-stack replay, not another allowlist expansion.

## Common Pitfalls

- **Updating the allowlist but not the focused S05 proof packs** — cleaned surfaces can drift back in even if the verifier still passes.
- **Deleting empty frontend scopes** — keeping the roots with `approved: []` is what makes reintroduction visible.
- **Treating rejection/detection text as accepted transport** — after S04 and S05, remaining `X-Session-ID` / bearer / websocket query strings are only honest if they stay diagnostic, not functional.
- **Broadening the failure scope to docs/tests/vendor code** — that makes the guard noisy and hides real runtime drift.
- **Assuming M005 will clean runtime residue for you** — its debt is schema/model structural residue, not this runtime boundary.

## Open Risks

- Backend dependency/helper drift can still hide behind the remaining `firebase_uid` compatibility seams until a later runtime slice decides to delete them outright.
- `backend-hormonia/app/api/websockets.py` still contains the densest concentration of legacy transport text; careless cleanup there could collapse the diagnostic split between invalid-session and lookup-failure cases.
- `backend-hormonia/app/api/v2/routers/admin/utils.py` still serializes `firebase_uid` in a generic admin helper even though the audited/admin-extensions contract is already canonical; any later cleanup needs to decide whether that field is still justified or should leave the runtime boundary entirely.
- The frontend scope is clean now, so stale allowlist edits will be noisy by design if future slices reintroduce legacy auth/session text.

## Sources

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`
- `backend-hormonia/tests/auth/test_session_validation.py`
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py`
- `.gsd/milestones/M004/slices/S05/tasks/T01-SUMMARY.md`
- `.gsd/milestones/M004/slices/S05/tasks/T02-SUMMARY.md`
- `.gsd/milestones/M004/slices/S05/tasks/T03-SUMMARY.md`
- `.gsd/milestones/M004/slices/S05/tasks/T04-SUMMARY.md`
