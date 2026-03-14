---
id: T02
parent: S02
milestone: M004
provides:
  - Green canonical helper convergence for backend auth/session identity, with `id` / `user_id` normalized ahead of any `firebase_uid` compatibility fallback across the main and shared helper families.
key_files:
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/app/api/v2/user_cache_shared.py
  - backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py
  - backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py
key_decisions:
  - Normalize canonical identity at helper boundaries and preserve the existing transport-precedence/public dependency surface instead of changing `auth_dependencies.py`.
patterns_established:
  - Resolve embedded session identity through a single canonical-id alias step (`id` or `user_id`) before cache/DB lookup, then quarantine `firebase_uid` to explicit compatibility-only fallback.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
  - Focused request-state assertions over `request.state.session_id`, `request.state.user_id`, `request.state.user_role` plus websocket auth error codes `AUTH_WEBSOCKET_SESSION_INVALID` / `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`
duration: 10m
verification_result: passed
completed_at: 2026-03-14T09:23:08-03:00
blocker_discovered: false
---

# T02: Converge session/cache/shared helpers on user_id-first identity

**Made the canonical and shared backend auth helpers resolve `id` / `user_id` first, leaving `firebase_uid` as compatibility-only fallback while keeping request-state and transport precedence behavior intact.**

## What Happened

Updated the main helper seam in `backend-hormonia/app/dependencies/auth_session_cache.py` to normalize canonical user identity from either `id` or `user_id`, use that canonical ID for embedded session hydration and session-cache rehydration, and stop consulting `firebase_uid` cache when a canonical ID is already present but its cache key misses. That closes the exact red path T01 pinned: stale compatibility cache data no longer wins over canonical DB lookup.

Aligned the shared V2 helper family the same way in `backend-hormonia/app/api/v2/auth_session_shared.py` and `backend-hormonia/app/api/v2/user_cache_shared.py`. Embedded session payloads now accept either canonical ID alias, adjacent V2 consumers keep the same Authorization → `X-Session-ID` → cookie → query precedence, and shared cache/DB lookup order now matches the main dependency path instead of falling back to `firebase_uid` too early.

Added two focused regression proofs for `id`-shaped embedded session payloads so the slice now proves `id` / `user_id` alias handling explicitly, not just `user_id`-only payloads.

`backend-hormonia/app/dependencies/auth_session_contract.py` and `backend-hormonia/app/dependencies/auth_dependencies.py` did not need code changes: the public dependency surface, mapping-style payload behavior, and `request.state.session_id` / `user_id` / `user_role` side effects remained stable once the helper seams were converged underneath them.

## Verification

Ran:
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

Results:
- focused helper proof pack: passed
- existing local-login/session-priority/websocket/integration pack: passed
- backend runtime residue report: passed
- backend runtime residue check: passed

Confirmed must-haves:
- canonical cache-hit and cache-miss paths now stay on `id` / `user_id` before any `firebase_uid` compatibility lookup
- shared V2 helper paths follow the same canonical identity rules as the main dependency seam
- mapping-style payloads and request-state enrichment remain stable through the green override contract proof
- accepted session transports and precedence did not change behavior during this task

## Diagnostics

To inspect this work later:
- rerun the focused proof pack to isolate canonical helper drift from route-level auth behavior
- rerun the acceptance pack to confirm local login, session precedence, websocket auth, and end-to-end local auth flow still hold
- use `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` to compare remaining intentional compatibility residue before T03 shrinks the boundary

The failure surface remains explicit:
- helper-level canonical identity regressions fail in the focused proof pack
- request-state regressions fail in `tests/api/v2/test_auth_dependency_override_contract.py`
- websocket/session regressions surface through stable websocket auth error-code assertions

## Deviations

- None.

## Known Issues

- The backend residue boundary still contains the intentional compatibility hotspots tracked by the S01 guard; T03 still needs to update the allowlist/handoff artifacts for any boundary shrink this helper convergence enables.
- Pytest still emits the existing `pytest_asyncio` loop-scope deprecation warning; it did not affect verification outcomes.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_cache.py` — normalized canonical ID extraction, kept fallback rehydration on canonical IDs, and quarantined `firebase_uid` lookup to compatibility-only paths.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — aligned shared embedded-session extraction and canonical ID alias handling with the main dependency seam.
- `backend-hormonia/app/api/v2/user_cache_shared.py` — changed shared cache/DB lookup order to exhaust canonical `user_id` before any `firebase_uid` compatibility lookup.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — added green proof for `id`-alias embedded session payloads alongside the canonical lookup-order proof.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — added shared-helper proof for `id`-alias embedded sessions and verified the shared lookup-order fix.
- `.gsd/DECISIONS.md` — recorded the helper-boundary canonical-identity decision for downstream slices.
- `.gsd/milestones/M004/slices/S02/tasks/T02-SUMMARY.md` — recorded implementation details, verification, and the T03 handoff.
- `.gsd/milestones/M004/slices/S02/S02-PLAN.md` — marked T02 complete.
- `.gsd/STATE.md` — advanced the slice state to T03.
