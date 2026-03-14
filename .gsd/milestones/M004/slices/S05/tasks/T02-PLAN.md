---
estimated_steps: 4
estimated_files: 7
---

# T02: Remove `firebase_uid` from shared auth/cache adapters and login-written session payloads

**Slice:** S05 — Resíduo funcional de Firebase removido do runtime adjacente
**Milestone:** M004

## Description

Finish the runtime identity cut at the shared adapter layer. S02 already made canonical `user_id` win lookup order, but shared helpers, login writers, and websocket-adjacent adapters still serialize `firebase_uid` into live session/cache payloads. This task removes that runtime residue so adjacent consumers inherit the canonical contract instead of a quieter Firebase-shaped payload.

## Steps

1. Update `auth_session_shared.py` and `user_cache_shared.py` so shared restore/cache helpers consume canonical `user_id` payloads only and stop reading/writing `firebase_uid` as a live session identifier.
2. Remove `firebase_uid` injection from `api/v2/routers/auth.py` and `dependencies/auth_user_adapter.py` when building session/cache-ready user payloads.
3. Preserve the S04 cookie-only transport cut and the pinned websocket auth failure codes while aligning websocket-adjacent consumers to the new payload contract.
4. Extend the focused shared-helper/login/websocket proof so it asserts absence of `firebase_uid` runtime payload writing, not just happy-path auth success.

## Must-Haves

- [ ] Shared auth/cache helpers no longer require or emit `firebase_uid` in the live session/cache payload path.
- [ ] Local login and the shared user adapter stop writing `firebase_uid` into Redis/session-ready user payloads.
- [ ] Websocket-adjacent auth consumers keep the S04 transport boundary and stable diagnostics intact.
- [ ] Focused proof catches reintroduction of `firebase_uid` payload writing or fallback lookup in these seams.

## Verification

- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py`
- Confirm the updated assertions check for canonical payload shape / absence of `firebase_uid`, not only successful login and websocket auth behavior.

## Observability Impact

- Signals added/changed: shared-helper and login tests expose whether `firebase_uid` is still being written into runtime payloads, while websocket tests keep the stable auth error-code surface pinned.
- How a future agent inspects this: rerun the focused pytest pack and inspect whether the failure is in shared cache lookup, login payload serialization, or websocket-adjacent consumption.
- Failure state exposed: the proof distinguishes “canonical auth still works” from “Firebase-shaped runtime metadata is still being written underneath it.”

## Inputs

- `backend-hormonia/app/api/v2/auth_session_shared.py` — shared helper path consumed by adjacent runtime surfaces including websocket auth.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — shared cache helper still mirrors dual-key behavior from the research handoff.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical local login still writes a session payload and is the official runtime entrypoint for staff login.
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — shared adapter still emits Firebase-era cache/session fields.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — existing proof pack for the shared helper family after S02.
- T01 output: canonical core session/cache contract is now trustworthy and ready for adjacent helper cleanup.

## Expected Output

- `backend-hormonia/app/api/v2/auth_session_shared.py` — shared auth/session helper aligned to `user_id`-only runtime payloads.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — shared cache helper without `firebase_uid` runtime serialization or lookup pivots.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical login no longer injects `firebase_uid` into Redis/session payloads.
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — shared user/session adapter emits canonical runtime payloads only.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — focused proof for the shared post-cut contract.
- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — login proof asserting the new payload shape.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — websocket proof still green on the S04 transport boundary while consuming the canonical payload.
