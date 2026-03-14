---
estimated_steps: 4
estimated_files: 7
---

# T01: Restore auth dependency hygiene and canonicalize the core Redis session contract

**Slice:** S05 — Resíduo funcional de Firebase removido do runtime adjacente
**Milestone:** M004

## Description

Repair the auth dependency baseline before any semantic cleanup and remove `firebase_uid` from the deepest live session/cache pivot. This task closes the highest-risk blocker first: until the dependency files compile cleanly and Redis session state is canonicalized around `user_id`, every later claim about “Firebase removed from runtime” is still resting on broken ground.

## Steps

1. Resolve the committed merge markers in `auth_session_contract.py`, `auth_session_cache.py`, `auth_dependencies.py`, and `dependencies/__init__.py` without reopening the S04 cookie-only transport contract.
2. Narrow the core Redis session contract in `session_cache.py` and `auth_session_cache.py` so session creation, rehydration, listing, and invalidation key off canonical `id` / `user_id` rather than `firebase_uid`.
3. Keep any unavoidable Firebase-era fields out of the live identity pivot, limiting them to passive compatibility data only if a focused assertion still requires them.
4. Extend the unit proof so py-compile, session helper behavior, and Redis session operations all pin the post-cut canonical contract explicitly.

## Must-Haves

- [ ] `auth_session_contract.py`, `auth_session_cache.py`, `auth_dependencies.py`, and `dependencies/__init__.py` are syntactically valid again.
- [ ] `SessionCache` no longer needs `firebase_uid` to create, read, list, or bulk-invalidate staff sessions.
- [ ] The dependency/helper unit proof distinguishes canonical `user_id` behavior from any leftover passive compatibility metadata.
- [ ] No change in this task revives header, bearer, or websocket query session transport.

## Verification

- `python3 -m py_compile backend-hormonia/app/dependencies/auth_session_contract.py backend-hormonia/app/dependencies/auth_session_cache.py backend-hormonia/app/dependencies/auth_dependencies.py backend-hormonia/app/dependencies/__init__.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/unit/test_session_cache.py`

## Observability Impact

- Signals added/changed: py-compile becomes a trustworthy syntax gate again, and unit assertions expose whether failure is in dependency-module hygiene, session payload storage, or Redis bulk invalidation semantics.
- How a future agent inspects this: rerun the py-compile command plus the two unit files to localize breakage to syntax, helper hydration, or Redis session contract drift.
- Failure state exposed: stale merge markers, `firebase_uid`-based invalidation/listing, or canonical `user_id` regressions fail with targeted assertions instead of surfacing later as vague auth/runtime breakage.

## Inputs

- `backend-hormonia/app/dependencies/auth_session_cache.py` — the main canonical session helper still contains the live cache/rehydration seam and the reported merge-marker blocker.
- `backend-hormonia/app/core/redis_manager/session_cache.py` — the deepest runtime session payload contract still stores and matches `firebase_uid`.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — existing focused proof for canonical helper lookup order after S02.
- S02/S04 handoff: the official contract is already cookie-only at the transport layer, so this task must preserve that while removing the remaining runtime identity pivot.

## Expected Output

- `backend-hormonia/app/dependencies/auth_session_contract.py` — syntax-restored canonical request-state contract consistent with S04.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — core auth/session helper no longer pivots on `firebase_uid` for live identity resolution.
- `backend-hormonia/app/core/redis_manager/session_cache.py` — Redis session creation, listing, and invalidation contract centered on canonical `user_id`.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — focused proof updated for the post-cut core helper semantics.
- `backend-hormonia/tests/unit/test_session_cache.py` — unit proof that Redis session storage and invalidation no longer depend on `firebase_uid`.
