---
id: S02
parent: M004
milestone: M004
provides:
  - Backend auth/session helpers and the public dependency surface now converge on one canonical `user_id`-first contract, with the S01 backend residue handoff republished to isolate the remaining transport and compatibility seams honestly.
requires:
  - slice: S01
    provides: Executable runtime-residue boundary and verifier used to reconcile the post-convergence backend map.
affects:
  - M004/S03
  - M004/S04
  - M004/S05
key_files:
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/app/api/v2/user_cache_shared.py
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S02/S02-UAT.md
key_decisions:
  - Canonical backend session identity resolves `id` / `user_id` first across both helper families; `firebase_uid` survives only as explicit compatibility fallback or passthrough metadata.
  - The S01 residue guard is a living boundary contract: after S02, semantic boundary shrinkage must update allowlist descriptions and handoff artifacts even when raw backend residue counts stay flat.
patterns_established:
  - Prove backend canonicalization with a focused helper proof pack plus an acceptance pack, then reconcile the residue verifier and slice handoff against the same live backend report before closeout.
  - Describe remaining auth/session residue only with the verifier's category ids (`firebase_uid`, `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, `firebase_narrative`) so later slices inherit one vocabulary.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
  - `request.state.session_id` / `user_id` / `user_role` assertions in `tests/api/v2/test_auth_dependency_override_contract.py`
  - websocket auth error-code assertions `AUTH_WEBSOCKET_SESSION_INVALID` / `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`
drill_down_paths:
  - .gsd/milestones/M004/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S02/tasks/T03-SUMMARY.md
duration: ~1h15m
verification_result: passed
completed_at: 2026-03-14T10:12:00-03:00
---

# S02: Backend auth/sessão convergido para identidade canônica

**The backend official auth/session path now resolves authenticated identity through canonical `user_id` first, while the republished residue boundary makes the remaining legacy transport and compatibility seams explicit for S03/S04/S05.**

## What Happened

S02 started by proving the real risk surface instead of trusting the already-green route contract. T01 added focused red proof around the hidden helper seams in `auth_session_cache.py`, `auth_session_shared.py`, `user_cache_shared.py`, and the override-sensitive request-state contract. That isolated the remaining backend drift to one problem: `firebase_uid` still won too early in helper/cache fallback paths even though the visible `/api/v2/auth/*` contract was already close to canonical.

T02 converged those helper seams on one canonical identity rule. The main dependency path in `backend-hormonia/app/dependencies/auth_session_cache.py` now resolves embedded payloads and fallback lookups through `id` / `user_id` first, only consulting `firebase_uid` cache/DB paths when canonical IDs are absent. The shared V2 helper family in `backend-hormonia/app/api/v2/auth_session_shared.py` and `backend-hormonia/app/api/v2/user_cache_shared.py` now follows the same rule, so adjacent official-runtime consumers inherit the canonical contract instead of a quieter Firebase-shaped fallback order. The public dependency surface, request-state side effects, and accepted transport precedence stayed stable underneath that change.

T03 closed the slice by reconciling the live S01 residue boundary with the converged runtime and publishing the handoff. The raw backend report did **not** shrink numerically: it still reports `firebase_uid` in 14 files / 133 matching lines, `root_legacy_session` in 2 / 8, `x_session_id` in 16 / 28, `session_bearer_fallback` in 8 / 11, `websocket_session_id_query` in 1 / 4, and `firebase_narrative` in 1 / 29. That flat count is real, not drift. The important change is semantic: the canonical helper-family `firebase_uid` hits now describe compatibility-only fallback or passthrough behavior, not happy-path identity resolution. The transport-heavy legacy work left for later slices is now explicit instead of blurred together with the helper convergence that already landed.

The S01 allowlist and handoff were updated to use that post-S02 meaning directly. The `firebase_uid` category description now describes compatibility-oriented residue, and the backend helper anchors that survived the convergence were relabeled as compatibility fallback/passthrough hotspots. `S01-RESEARCH.md`, `S01-SUMMARY.md`, and `S01-UAT.md` now tell the same story as the verifier and this slice handoff: S02 is done, S03/S04 still own transport retirement, and S05 still owns the remaining adjacent/admin Firebase residue.

## Verification

Passed on slice closeout rerun:

- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

Observability/diagnostic surfaces confirmed on rerun:

- The focused helper proof still distinguishes embedded canonical payload handling, cache/DB lookup order, and request-state side effects.
- The acceptance pack still covers local login, verify-session, logout, session precedence, websocket auth, and the local auth core flow.
- `--report backend` still emits the live backend residue map by category/file/count.
- `--check backend` stays green on the republished boundary and would still fail on `unexpected_file=` or `moved_hotspot=` drift.

## Requirements Advanced

- R047 — The official runtime boundary is now truthful after backend canonical convergence, so later slices inherit a live map of what legacy auth/session residue still remains.
- R048 — Backend auth/session helper families now share one canonical `user_id`-first identity contract without changing the public request-state or transport-precedence surface.
- R049 — The backend happy path no longer needs `firebase_uid` to resolve authenticated identity; remaining `firebase_uid` hits are now explicit compatibility residue instead of hidden canonical blockers.

## Requirements Validated

- none — frontend cutover, transport retirement, adjacent Firebase cleanup, and assembled-stack proof still belong to later slices.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

None.

## Known Limitations

- The backend residue report still contains the same raw `firebase_uid` file/line count after S02 because the verifier measures surviving literals, not semantic lookup order. Read the handoff before assuming the flat count means no backend shrink happened.
- The official frontend still emits `X-Session-ID`, `Authorization: Bearer <session_id>`, and websocket `session_id` query fallback; backend acceptance of those transports remains live by design until S03/S04.
- The root `/session/*` router island and backend Firebase narrative in `backend-hormonia/app/routers/auth_session.py` are still live and intentionally visible in the residue guard.
- Adjacent/backend-helper/admin compatibility residue around `firebase_uid` still remains for S05 after transport retirement is complete.
- `backend-hormonia` pytest still emits the existing `pytest_asyncio` loop-scope deprecation warning. It did not affect the pass/fail result.

## Follow-ups

- S03 should remove official frontend emission of `X-Session-ID`, session-as-Bearer, and websocket `session_id` query fallback while keeping backend acceptance stable enough for a controlled cutover.
- S04 should retire the root `/session/*` island and backend acceptance of `X-Session-ID`, session-as-Bearer, and websocket query fallback, then collapse the backend Firebase narrative as part of that retirement.
- S05 should remove the remaining fallback-only helper/admin `firebase_uid` residue and the frontend/admin Firebase narrative that survive after the transport cut.
- Any later slice that removes or relocates approved residue must update `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M004/slices/S01/S01-UAT.md`, and the current slice handoff in the same change.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_cache.py` — canonicalized session/cache helper lookup order on `id` / `user_id` before any `firebase_uid` compatibility fallback.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — aligned the shared V2 session helper family to the same canonical identity semantics while preserving current transport precedence.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — made shared cache/DB lookups exhaust canonical `user_id` before consulting `firebase_uid` compatibility paths.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — focused proof for canonical embedded session hydration, canonical lookup order, and compatibility-only `firebase_uid` fallback.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — focused proof for shared-helper canonical identity behavior and adjacent V2 consumer expectations.
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` — request-state and mapping-style payload proof for the public dependency surface.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — updated the `firebase_uid` category description and helper-anchor labels to describe post-S02 compatibility-only residue honestly.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — updated the backend residue interpretation and cut ownership after helper convergence.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — updated the condensed guardrail handoff for the post-S02 backend boundary.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — updated reviewer guidance for interpreting flat backend residue counts after semantic helper shrinkage.
- `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` — condensed backend slice handoff with converged contract, live residue map, and next-slice ownership.
- `.gsd/milestones/M004/slices/S02/S02-UAT.md` — reviewer checklist for replaying the slice proof and spotting stale residue bookkeeping later.

## Forward Intelligence

### What the next slice should know
- The backend residue map is transport-heavy now. If you see `firebase_uid` in the canonical helper family after S02, treat it as compatibility-only until the focused proof pack says otherwise.
- The report/check gate and the slice handoff now intentionally separate finished backend identity convergence from later transport retirement. Do not collapse those concerns back together.
- S03 can cut frontend emission without reopening backend helper design, but it still needs the backend acceptance paths left intact long enough to prove the frontend transition cleanly.

### What's fragile
- `auth_dependencies.get_current_user()` still only enters the session-first branch when a cookie or `X-Session-ID` is present. If frontend/header changes race ahead of backend transport retirement work, some callers can still fall through into legacy compatibility behavior.
- The root `/session/*` island in `backend-hormonia/app/routers/auth_session.py` still mixes live compatibility behavior, Firebase narrative, and old transport assumptions; it is the highest-risk backend file for S04.
- Flat residue counts can hide real semantic boundary changes. Later slices need both the focused proof pack and the residue verifier, not just one of them.

### Authoritative diagnostics
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py` — trusted proof for backend canonical identity behavior plus acceptance-level auth/session regressions.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` — live backend inventory surface for what residue remains approved after S02.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` — fastest way to catch stale allowlist/docs bookkeeping or newly introduced runtime residue.
- `.gsd/milestones/M004/slices/S02/S02-UAT.md` — replay checklist that ties the proof commands to the published residue story.

### What assumptions changed
- "Backend residue shrink will obviously show up as fewer `firebase_uid` hits in the report" — not true; S02 mostly changed lookup order and semantics, so the report stayed flat while the helper meaning narrowed.
- "The public auth dependency surface needed a visible refactor to land canonical identity" — not true; converging the helper seams underneath `auth_dependencies.py` and `auth_session_contract.py` was enough to keep the outward contract stable.
