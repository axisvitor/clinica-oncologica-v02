---
estimated_steps: 5
estimated_files: 3
---

# T01: Add failing canonical-identity proof for backend auth helpers

**Slice:** S02 — Backend auth/sessão convergido para identidade canônica
**Milestone:** M004

## Description

Freeze the hidden backend identity contract before changing the helper substrate. This task adds focused proof around the two helper families (`auth_session_cache` / `auth_session_contract` and `auth_session_shared` / `user_cache_shared`) plus the override-sensitive dependency surface, so S02 has to close the real `user_id`-first gap instead of merely preserving already-green top-level routes.

## Steps

1. Add `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` to pin canonical embedded-user hydration, DB fallback by `user_id`, cache rehydration, and explicit `firebase_uid` fallback only when canonical IDs are absent.
2. Add `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` to pin the shared helper family used by adjacent V2 consumers, including session lookup semantics that official-runtime callers and websocket/session paths still rely on.
3. Extend `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` where needed so mapping-style session payloads and `request.state.session_id` / `user_id` / `user_role` remain part of the proven contract during convergence.
4. Run the new proof pack red-first and confirm the first failures point at current helper dual-identity drift or missing canonicalization, not fixture/setup instability.
5. Tighten fixtures or assertions only enough to express the real contract; do not relax the slice boundary to accommodate today’s `firebase_uid`-centric behavior.

## Must-Haves

- [ ] The new tests prove canonical `id` / `user_id` resolution through cache-hit and cache-miss paths without requiring `firebase_uid` on the happy path.
- [ ] The shared helper proof covers adjacent V2/helper consumers rather than only `/api/v2/auth/*` routes.
- [ ] Override-sensitive behavior still pins mapping-style payloads and `request.state` side effects.
- [ ] The initial failures are attributable to real contract gaps, not unrelated environment noise.
- [ ] No test fixtures expose real session tokens, cookies, passwords, or other secret-bearing values.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py`

## Observability Impact

- Signals added/changed: the slice gains focused failures for cache hydration, shared-helper resolution, and request-state/override regressions instead of relying on indirect route failures.
- How a future agent inspects this: run the new pytest files directly to see whether drift lives in canonical cache hydration, shared helper behavior, or the public dependency surface.
- Failure state exposed: test names and assertions should make it obvious whether the regression is missing canonical IDs, accidental `firebase_uid` dependence, or lost `request.state` side effects.

## Inputs

- `.gsd/milestones/M004/slices/S02/S02-RESEARCH.md` — defines the helper-layer drift, the preserved transport constraints, and the slice boundary.
- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — current route-level happy-path proof to keep as the acceptance baseline rather than rewriting the public contract.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — current backend residue map showing where `firebase_uid` and transport compatibility still live.

## Expected Output

- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — focused proof for canonical cache/session hydration behavior.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — focused proof for the shared helper family and its adjacent-runtime contract.
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` — updated override-sensitive proof that remains valid during the convergence.
