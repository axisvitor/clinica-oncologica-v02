---
id: S05
parent: M004
milestone: M004
provides:
  - The adjacent runtime now treats canonical `id` / `user_id` as the live auth/session identity seam, while audit/admin/docs/frontend-adjacent surfaces and the S01 residue guard all reflect the post-Firebase runtime honestly.
requires:
  - slice: S02
    provides: Canonical backend login, restore, verify-session, and logout behavior centered on `user_id`.
  - slice: S03
    provides: Official frontend auth/session flows already running on the session-first contract.
affects:
  - S06
key_files:
  - backend-hormonia/app/core/redis_manager/session_cache.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/app/api/v2/user_cache_shared.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/dependencies/auth_user_adapter.py
  - backend-hormonia/app/services/audit/audit_service.py
  - backend-hormonia/app/api/v2/routers/admin_extensions/utils.py
  - backend-hormonia/app/api/v2/routers/docs/data_providers.py
  - frontend-hormonia/src/types/api.ts
  - frontend-hormonia/src/types/rbac.ts
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
key_decisions:
  - Keep the live session/cache/login/runtime identity pivot on canonical `user_id`; any Firebase-era fields can survive only as passive compatibility data outside the happy path.
  - Sanitize stale shared cache/session payloads before emitting runtime auth state instead of preserving `firebase_uid` in restore/login/websocket-adjacent flows.
  - Treat audit/admin/docs output and adjacent frontend type barrels as part of the live auth contract, so they must stop advertising Firebase or manual session-header semantics.
  - Republish the S01 residue boundary immediately after cleanup so remaining verifier hits mean passive compatibility/rejection bookkeeping only, not live runtime dependence.
patterns_established:
  - Slice-proof for runtime cleanup works best as focused packs by seam: core auth/cache identity, adjacent audit/docs/admin surfaces, adjacent frontend types/build, then residue republication.
  - A residue guard is trustworthy only when cleaned hotspots are removed from the allowlist and protected by focused tests instead of stale approvals.
  - Login/session restore and websocket-adjacent checks should assert both canonical success and absence of `firebase_uid` in emitted runtime payloads.
observability_surfaces:
  - `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
  - `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
  - `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
  - `cd frontend-hormonia && npm run build`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
drill_down_paths:
  - .gsd/milestones/M004/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/milestones/M004/slices/S05/tasks/T04-SUMMARY.md
  - .gsd/milestones/M004/slices/S05/tasks/T05-SUMMARY.md
duration: ~6h12m
verification_result: passed
completed_at: 2026-03-14T18:46:45-03:00
---

# S05: Resíduo funcional de Firebase removido do runtime adjacente

**The remaining live Firebase semantics were cut out of the adjacent runtime: Redis/session/cache/login payloads, shared adapters, audit/admin/docs output, frontend-adjacent types, and the S01 residue boundary now all describe the canonical cookie-backed `user_id` contract instead of a Firebase-shaped system.**

## What Happened

S05 finished the runtime cleanup that S02–S04 set up. The first pass repaired the broken auth dependency seam and moved the deepest remaining runtime identity pivot to canonical `user_id`. `auth_session_contract.py`, `auth_session_cache.py`, `auth_dependencies.py`, and `backend-hormonia/app/core/redis_manager/session_cache.py` now compile cleanly again, Redis session creation/listing/bulk invalidation no longer key staff identity through `firebase_uid`, and fallback rehydration only tolerates Firebase-era data as passive compatibility when canonical IDs are absent.

The second pass removed `firebase_uid` from the shared runtime adapters that kept reintroducing it after the core session pivot. Shared restore/cache helpers, login-written session payloads, and websocket-adjacent auth proof now stay on canonical `id` / `user_id` semantics only. Stale cached payloads are sanitized before they are emitted back into runtime auth state, so restore/login/websocket flows no longer echo Firebase identity even when old data is encountered.

The third pass converged the adjacent operational surfaces that still told the wrong story. HIPAA audit extraction and persistence now refresh canonical `request.state.user_id` / `session_id` and strip `firebase_uid` from emitted runtime metadata; admin audit serialization/export no longer exposes `firebase_uid`; and routed operator docs/examples now describe cookie-backed session handling instead of Firebase or `X-Session-ID` guidance.

The fourth pass cleaned the adjacent frontend type story so it matches the runtime that already ships. Canonical frontend/shared user types no longer expose `firebase_uid`, dead provider-era enums were removed from RBAC/admin barrels, and medico validation helpers now describe generic session/user context instead of Firebase claims. Focused type-level tests and the production build pin that narrower contract.

The final pass republished S01 so the guardrail tells the truth again. The runtime residue allowlist dropped the cleaned shared-auth/Redis/auth-user-adapter hotspots, retargeted the surviving anchors that changed meaning, and rewrote the readable S01 handoff so S06 inherits a smaller boundary: only passive compatibility/rejection bookkeeping remains approved, frontend residue is at zero, S06 owns the assembled-stack replay, and M005 owns schema/migration debt.

## Verification

Full slice closeout was replayed after the task work and passed:

- `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
  - Passed with no output.
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
  - Passed; canonical auth/cache/login/websocket proof stayed green on the `user_id` runtime contract.
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
  - Passed; audit/admin/docs output stayed aligned to cookie-backed canonical runtime semantics.
- `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
  - Passed: 91 tests.
- `cd frontend-hormonia && npm run build`
  - Passed; production bundle built successfully.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
  - Passed; backend shows only the reduced approved categories and frontend reports no approved residue.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - Passed; allowlist and code agree on the post-S05 boundary.

The backend pytest replays still emit the existing `pytest_asyncio` loop-scope deprecation warning. It is unchanged and non-blocking.

## Requirements Advanced

- R047 — Advanced the no-Firebase runtime cut by removing the remaining adjacent Firebase semantics from session/cache/login payloads, audit/admin/docs output, frontend-adjacent types, and the published residue boundary; only the assembled local stack replay remains before validation.

## Requirements Validated

- R049 — Validated by the combined S02+S05 proof: Redis/session identity, shared auth/cache restore, login-written payloads, websocket-adjacent auth, audit/admin/docs serialization, adjacent frontend types, and the green S01 residue guard all now stay on canonical `id` / `user_id` semantics without `firebase_uid` as a live runtime pivot.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- none

## Known Limitations

- S05 is contract proof, not assembled-stack proof. S06 still has to boot the local stack with Firebase Auth envs blank and replay `/login`, `/dashboard`, `/admin`, and `/whatsapp` in the mounted runtime.
- Approved backend residue still exists in explicit compatibility/rejection bookkeeping such as `auth_dependencies.py`, `auth_legacy_firebase.py`, `auth_session_cache.py`, `auth_session_contract.py`, `app/api/websockets.py`, and admin helper seams. Those are now boundary-owned leftovers, not live canonical runtime pivots.
- Schema/model Firebase residue still belongs to M005. S05 deliberately avoided physical schema cleanup or migration churn.

## Follow-ups

- S06: run the assembled local no-Firebase stack replay against the reduced post-S05 runtime boundary and critical routed surfaces.
- M005: remove the remaining structural Firebase/schema debt that no longer participates in the runtime contract.

## Files Created/Modified

- `backend-hormonia/app/core/redis_manager/session_cache.py` — moved core Redis session creation/listing/invalidation to canonical `user_id` semantics.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — restored canonical rehydration helpers and kept Firebase-era identity outside the live pivot.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — removed shared `firebase_uid` fallback/serialization from session restore.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — sanitized stale cached user payloads and narrowed runtime cache state to canonical identity.
- `backend-hormonia/app/api/v2/routers/auth.py` — removed login-time `firebase_uid` injection from canonical session writes.
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — stopped emitting `firebase_uid` from shared runtime serialization.
- `backend-hormonia/app/services/audit/audit_service.py` — removed Firebase-shaped runtime audit context and sanitized emitted metadata.
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` — removed `firebase_uid` from admin audit serialization and nested metadata.
- `backend-hormonia/app/api/v2/routers/docs/data_providers.py` — rewrote routed operator guidance/examples around cookie-backed sessions.
- `frontend-hormonia/src/types/api.ts` — removed `firebase_uid` from the canonical frontend `User` surface.
- `frontend-hormonia/src/types/rbac.ts` — removed dead provider-era enums from the RBAC barrel.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — republished the reduced post-S05 residue boundary.
- `.gsd/milestones/M004/slices/S05/S05-UAT.md` — published the slice replay tailored to the adjacent-runtime Firebase cleanup.

## Forward Intelligence

### What the next slice should know
- The remaining verifier hits are smaller and more honest now: if S06 sees new `firebase_uid` hotspots in shared auth/cache/login/audit/docs/frontend-adjacent code, that is a fresh regression, not tolerated transition residue.
- The contract is clean enough that mounted-stack failures in S06 are more likely to be environment/bootstrap/regression issues than hidden Firebase pivots in the official runtime path.
- Keep the ownership split straight: S06 proves the reduced runtime boundary in a live stack; M005 removes structural/schema residue.

### What's fragile
- `backend-hormonia/app/dependencies/auth_dependencies.py` lazy legacy seam and the surviving compatibility readers — they still mention Firebase-era state, so cleanup must distinguish passive compatibility from live runtime dependence before deleting them.
- Websocket/session restore diagnostics — the runtime cut stays trustworthy only while the tests keep proving canonical success plus rejection of stale/Firebase-shaped payload behavior.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — the fastest trustworthy signal that the published post-S05 boundary still matches the code.
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py` — the tightest proof for canonical `user_id` auth/cache/login/websocket identity.
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py` — the authoritative check for adjacent runtime narrative/serialization drift.
- `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts && npm run build` — the fastest proof that frontend-adjacent type surfaces did not reintroduce Firebase semantics.

### What assumptions changed
- "If the core backend login/session flow is canonical, adjacent surfaces can keep Firebase-shaped metadata harmlessly" — false; shared cache payloads, audit/admin/docs output, and frontend-adjacent type barrels were still teaching the wrong runtime until S05 removed or sanitized them.
- "The S01 residue verifier already tells the full Firebase story" — false; S05 needed focused proof packs for adjacent runtime surfaces and then a published allowlist/handoff update before the verifier became honest again.
