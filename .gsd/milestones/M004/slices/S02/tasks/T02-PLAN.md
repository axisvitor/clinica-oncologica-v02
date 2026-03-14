---
estimated_steps: 5
estimated_files: 7
---

# T02: Converge session/cache/shared helpers on user_id-first identity

**Slice:** S02 — Backend auth/sessão convergido para identidade canônica
**Milestone:** M004

## Description

Close the actual runtime gap by making the canonical and shared auth helper families resolve authenticated identity through `id` / `user_id` first. This task narrows `firebase_uid` to an explicit compatibility fallback, keeps request-state and mapping-style payload contracts intact, and preserves the current accepted session transports and precedence so S03/S04 can retire them intentionally instead of inheriting accidental drift.

## Steps

1. Update `backend-hormonia/app/dependencies/auth_session_cache.py` and `auth_session_contract.py` so embedded canonical session fields and DB/cache rehydration resolve identity by `id` / `user_id` first while preserving mapping-style payloads plus `request.state.session_id` / `user_id` / `user_role` side effects.
2. Update `backend-hormonia/app/api/v2/auth_session_shared.py` and `user_cache_shared.py` so adjacent V2 consumers and websocket/session paths inherit the same canonical identity semantics instead of their own `firebase_uid`-shaped fallback behavior.
3. Adjust `backend-hormonia/app/dependencies/auth_dependencies.py` only as needed to keep the public dependency surface stable while routing canonical session lookups through the converged helper behavior.
4. Preserve the current accepted session transports and deliberate precedence rules; do not retire root `/session/*`, `X-Session-ID`, session-as-Bearer, or websocket query fallback in this task.
5. Rerun the focused proof pack plus the existing local-login, session-priority, websocket, and integration suites until any remaining failures are real contract regressions rather than helper drift.

## Must-Haves

- [ ] Canonical cache-hit and cache-miss paths resolve staff identity via `id` / `user_id` before any `firebase_uid` compatibility lookup.
- [ ] The shared helper family used outside `/api/v2/auth/*` follows the same canonical identity rules as the main dependency path.
- [ ] Mapping-style payloads, override compatibility, and `request.state` side effects remain stable for downstream callers.
- [ ] Current accepted session transports and precedence remain unchanged in behavior during this slice.
- [ ] `firebase_uid` survives only as an explicit compatibility fallback when canonical IDs are absent, not as the happy-path pivot.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`

## Observability Impact

- Signals added/changed: canonical auth helper failures should stay visible as stable 401/403/503 responses, request-state assertions, and websocket auth diagnostics instead of falling through into ambiguous Firebase-shaped behavior.
- How a future agent inspects this: run the focused suites above, then inspect the converged helper modules plus any backend residue drift via `verify-runtime-residue.sh --report backend`.
- Failure state exposed: the proof should distinguish precedence regressions, lost request-state enrichment, shared-helper divergence, and hidden `firebase_uid` dependence.

## Inputs

- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — failing proof created in T01 for canonical cache/session hydration.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — failing proof created in T01 for the shared helper family.
- `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/app/dependencies/auth_dependencies.py` — the runtime seams that currently allow hidden dual-identity behavior.

## Expected Output

- `backend-hormonia/app/dependencies/auth_session_cache.py` and `backend-hormonia/app/dependencies/auth_session_contract.py` — converged canonical helper behavior with `user_id`-first identity resolution.
- `backend-hormonia/app/api/v2/auth_session_shared.py` and `backend-hormonia/app/api/v2/user_cache_shared.py` — adjacent-runtime helper behavior aligned to the same canonical identity contract.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — stable public surface delegating to the converged helper semantics without transport-retirement drift.
