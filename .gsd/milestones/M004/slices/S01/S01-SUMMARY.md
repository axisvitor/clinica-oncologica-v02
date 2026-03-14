---
id: S01
parent: M004
milestone: M004
provides:
  - Executable guardrails for official-runtime auth/session residue; after S05 the live verifier boundary excludes cleaned shared-auth/Redis/audit/docs/frontend type hotspots and reports only backend passive compatibility/rejection residue plus zero-approved frontend guards.
requires: []
affects:
  - M004/S04
  - M004/S05
  - M004/S06
  - M005
key_files:
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
  - backend-hormonia/tests/unit/test_runtime_residue_guard.py
  - backend-hormonia/tests/auth/test_session_validation.py
  - backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py
  - backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py
  - backend-hormonia/tests/services/audit/test_audit_service.py
  - frontend-hormonia/tests/unit/types/type-consistency.test.ts
key_decisions:
  - The S01 verifier remains the durable guard for surviving runtime residue, but cleaned S05 surfaces are proved by focused backend/frontend packs rather than kept as approved debt.
  - Surviving post-S05 `firebase_uid` hits are treated as passive compatibility, sanitization, or adjacent admin-helper residue only; they must not regain canonical session/cache/login/audit/docs/frontend meaning.
  - M005 owns excluded schema/model debt only; S06 owns assembled-stack replay against this reduced boundary.
patterns_established:
  - Shrink the live boundary by deleting stale approvals and retargeting anchors, not by relaxing scopes; keep the roots hot so reintroductions fail.
  - Boundary republication after runtime cleanup moves allowlist, research, summary, and UAT together and is checked against focused proof packs for the surfaces that left the verifier.
  - Empty frontend approvals remain valid steady state and keep reintroduction visible.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all
  - cd backend-hormonia && pytest -q tests/auth/test_session_validation.py
  - python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py
  - cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py
  - cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py
  - cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts
  - cd frontend-hormonia && npm run build
duration: ~3h40m
verification_result: passed
completed_at: 2026-03-14T18:39:31-03:00
---

# S01: Guardrails do corte canônico de runtime

**Scoped runtime-residue guardrails now freeze the post-S05 boundary: the verifier no longer approves cleaned shared-auth/Redis/auth-user-adapter `firebase_uid` hotspots, the remaining backend inventory is a smaller passive compatibility/rejection surface (`firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`), and the `frontend` scope still reports `no approved residue`.**

## What Happened

S01 turned the runtime-cut discussion into an executable boundary, and later slices kept republishing that boundary instead of leaving it frozen in an outdated state. The slice added `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` as the machine-readable contract for the auth/session residue classes that matter to the official runtime, plus `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`, which reports approved residue by scope/category/file/count and fails on drift with diagnostics like `unexpected_file=` and `moved_hotspot=`.

S03 already completed the frontend side of the story: the official frontend loop no longer emits `X-Session-ID`, `Authorization: Bearer <session_id>`, websocket `session_id` query fallback, browser `session_id` storage/rehydration, or Firebase-shaped auth/admin narrative baggage. The `frontend` scope therefore stays in the allowlist with empty approved sets so any reintroduction fails loudly instead of being silently lost.

S04 then tightened the backend boundary again. The old root `/session/*` compatibility island was rewritten as an explicit 410 tombstone, so that surface no longer belongs in the residue verifier. It is now guarded by `backend-hormonia/tests/auth/test_session_validation.py`.

S05 reduced the live boundary one more time. Shared auth/cache restore, login-written session payloads, core Redis session storage, audit/admin/docs surfaces, and adjacent frontend type/narrative surfaces were converged on the canonical cookie-backed `user_id` contract. The S01 republish removed stale approvals for `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/core/redis_manager/session_cache.py`, and `backend-hormonia/app/dependencies/auth_user_adapter.py`, and retargeted the surviving `backend-hormonia/app/api/v2/routers/auth.py` and `backend-hormonia/app/api/v2/user_cache_shared.py` approvals to the post-S05 comment/sanitizer anchors that still exist.

## Verification

Latest republish reruns confirmed the post-S05 boundary state:

- `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py tests/api/v2/test_admin_extensions.py tests/api/v2/test_docs.py`
- `cd frontend-hormonia && npx vitest run src/lib/api-client/__tests__/normalizers.test.ts tests/unit/types/admin-types.test.ts tests/unit/types/type-consistency.test.ts`
- `cd frontend-hormonia && npm run build`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

Expected diagnostic surfaces remain authoritative:

- `tests/auth/test_session_validation.py` proves `/session/*` stays an explicit 410 tombstone with `AUTH_LEGACY_SESSION_ROUTE_RETIRED` instead of reviving or disappearing.
- `--report all` lists only approved backend rows for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`, while `frontend` still prints `no approved residue`.
- `--check all` fails if new live residue appears, stale approvals linger, or approved anchors drift.
- The S05 backend/frontend proof packs tell you whether drift re-entered the core auth/session seam, shared login/websocket payload path, audit/admin/docs serialization, or adjacent frontend types.
- The subprocess pytest harness remains the trusted failure-path proof for `unexpected_file=` and `moved_hotspot=` behavior.

## Requirements Advanced

- R047 — The official-runtime Firebase residue boundary is still executable and now excludes the cleaned S05 shared-auth/Redis/audit/docs/frontend hotspots from the live residue inventory.
- R048 — Legacy auth/session surfaces inside the official runtime are now split honestly between live residue guarded by the verifier, focused post-S05 proof packs for cleaned adjacent surfaces, and focused `/session/*` retirement proof.
- R049 — Remaining `firebase_uid` hotspots in the official runtime are now clearly passive backend compatibility/sanitization/admin-helper residue instead of core canonical runtime behavior.
- R050 — The official frontend residue boundary remains proven clean inside the scoped runtime guard.

## Requirements Validated

- none — S01 still proves the boundary and guardrails, not the full milestone behavior.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

None. This republish is the intended way S01 stays truthful as later slices shrink the live boundary.

## Known Limitations

- Approved residue is still live by design. After S05, it is concentrated in backend compatibility/rejection seams plus a small adjacent admin/auth/cache sanitizer trio.
- `backend-hormonia` pytest still emits the existing `pytest_asyncio` loop-scope deprecation warning during the guard suite. It is unchanged and non-blocking.
- `backend-hormonia/app/api/v2/routers/admin/utils.py` still serializes `firebase_uid` in a generic admin helper even though the audited/admin-extensions surface is already canonical.

## Follow-ups

- S06 should replay the assembled no-Firebase stack across the critical routed surfaces against this reduced verifier boundary.
- M005 should clean excluded schema/model Firebase debt only; do not treat it as the owner of these remaining runtime verifier hits.
- Any later slice that removes or relocates approved residue must update `runtime-residue-allowlist.json`, `S01-RESEARCH.md`, this summary, `S01-UAT.md`, and the current-slice handoff in the same change.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — machine-readable boundary for approved live residue classes, roots, and anchors after the post-S05 shrink.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — executable `--report` / `--check` guard for the still-live residue inventory.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — black-box regression harness for approved residue, unexpected residue, scope handling, and moved hotspots.
- `backend-hormonia/tests/auth/test_session_validation.py` — focused proof for explicit `/session/*` retirement after the route left the live residue inventory.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — readable hotspot map aligned to the post-S05 live verifier output and focused proof-pack split.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — reviewer script for the reduced boundary, zero-approved frontend guard, and focused post-S05 proof packs.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — condensed guardrail handoff updated for the post-S05 boundary.

## Forward Intelligence

### What the next slice should know
- The verifier is already scoped tightly enough to be actionable. Do not broaden it repo-wide; shrink the backend allowlist further only when the code actually stops containing the approved strings.
- Root `/session/*` is no longer verifier debt. If it regresses, start with `tests/auth/test_session_validation.py`, not the allowlist.
- `firebase_uid` in the report no longer means live session/login/audit/docs/frontend emission. It now mostly means passive compatibility/sanitization/admin-helper residue in backend code.
- S06 should consume both surfaces together: the reduced allowlist boundary and the focused proof packs that keep cleaned adjacent surfaces honest.

### What’s fragile
- Backend `firebase_uid` compatibility seams in `auth_dependencies.py`, `auth_session_cache.py`, `auth_legacy_firebase.py`, `auth_session_contract.py`, and `auth_role_dependencies.py`.
- `backend-hormonia/app/api/websockets.py`, where legacy query/header text still exists for diagnostics.
- The distinction between official-runtime scope and out-of-scope schema/history strings — broadening scans casually will create noise and weaken the guard.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` — source of truth for what residue is still approved right now.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — fastest way to catch new live residue or stale hotspot bookkeeping.
- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py` — fastest way to confirm `/session/*` remains an explicit tombstone.
- The S05 py_compile/pytest/vitest/build commands — fastest way to localize regressions to cleaned session/cache/login, audit/admin/docs, or adjacent frontend type surfaces.

### What assumptions changed
- "The verifier should still approve shared auth/cache/login/Redis `firebase_uid` writers" — no longer true after S05; those approvals were removed because the runtime path is now canonical there.
- "`firebase_uid` in the report means canonical runtime behavior is still Firebase-shaped" — no longer true; after S05 it means a smaller passive compatibility/rejection-adjacent boundary.
- "M005 will clean whatever runtime residue remains" — false; M005 owns excluded schema/model debt, while S06 owns assembled-stack proof against the reduced runtime boundary.
