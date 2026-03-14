---
id: T01
parent: S02
milestone: M004
provides:
  - Red helper-level proof for canonical `user_id`-first auth/session identity across cache, shared V2 helpers, and override-sensitive request-state behavior.
key_files:
  - backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py
  - backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py
  - backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py
key_decisions:
  - Freeze S02 at the hidden helper seams (`auth_session_cache` and `user_cache_shared`) where canonical `user_id` still loses to `firebase_uid` cache fallback, instead of broadening the proof into route-level churn.
patterns_established:
  - Add mixed green/red proof packs that keep existing top-level auth routes green while isolating helper drift to explicit canonical-identity test names.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
duration: 1h35m
verification_result: partial
completed_at: 2026-03-14T09:13:20-03:00
blocker_discovered: false
---

# T01: Add failing canonical-identity proof for backend auth helpers

**Added the focused red proof pack for canonical helper identity drift, while keeping the existing route-level auth/session acceptance pack green.**

## What Happened

Created the two planned proof files and extended the override-sensitive contract suite.

- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`
  - pins embedded canonical-session hydration without `firebase_uid`
  - pins DB fallback + cache rehydration around canonical `user_id`
  - pins explicit `firebase_uid` fallback only when canonical identity is absent
  - adds a red assertion showing `auth_session_cache.resolve_session_user_data()` still accepts stale `firebase_uid` cache data before exhausting the canonical `user_id` path
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`
  - pins shared-helper precedence for Authorization → `X-Session-ID` → cookie → query
  - proves adjacent V2 consumers (`messages.helpers` and `tasks.dependencies`) still work with canonical embedded session payloads
  - adds a red assertion showing `user_cache_shared.get_or_cache_user_data()` still accepts stale `firebase_uid` cache data before the canonical `user_id` DB path
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`
  - extends the override contract so mapping-style session payloads still carry `request.state.session_id`, `request.state.user_id`, and `request.state.user_role`
  - adds a direct `auth_session_contract.resolve_authenticated_session_user()` proof that canonical mapping payloads still enrich request state without `firebase_uid`

Must-have coverage from this task:
- canonical `id` / `user_id` resolution is now explicitly proven through embedded payload, fallback rehydration, and compatibility-only `firebase_uid` fallback paths
- the shared-helper proof hits adjacent V2 consumers and shared precedence rules, not just `/api/v2/auth/*`
- override-sensitive behavior now explicitly covers mapping payloads plus `request.state.session_id` / `user_id` / `user_role`
- the first red run failed only on the intended dual-identity drift in `auth_session_cache` and `user_cache_shared`
- all new fixtures use synthetic UUIDs, emails, and session labels only; no secret-bearing tokens, cookies, or passwords are asserted

## Verification

Ran:
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_local_login.py tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

Results:
- focused proof pack: **red by design** with 2 failures
  - `test_resolve_session_user_data_prefers_db_lookup_by_user_id_before_firebase_uid_cache_fallback`
  - `test_user_cache_shared_prefers_db_lookup_by_user_id_before_firebase_uid_cache_when_canonical_id_present`
- existing backend auth/session acceptance pack: **passed**
- runtime residue report/check: **passed**

The first failures were attributable to the real S02 gap: both helper families still allow stale `firebase_uid` cache data to win even when canonical `user_id` is present.

## Diagnostics

Use the focused proof pack to localize drift:
- `test_auth_session_cache_canonical_identity.py` -> canonical cache hydration, fallback rehydration, and `auth_session_cache` lookup order
- `test_auth_session_shared_canonical_identity.py` -> shared helper precedence, adjacent V2 consumer behavior, and `user_cache_shared` lookup order
- `test_auth_dependency_override_contract.py` -> mapping-style session payloads plus `request.state.session_id` / `user_id` / `user_role`

The current red surface is narrow:
- canonical route/websocket/integration acceptance remains green
- only the helper-level `firebase_uid`-before-`user_id` drift is failing

## Deviations

- None.

## Known Issues

- The new focused proof pack is intentionally red until T02 changes `backend-hormonia/app/dependencies/auth_session_cache.py` and `backend-hormonia/app/api/v2/user_cache_shared.py` so canonical `user_id` resolution exhausts cache/DB paths before consulting `firebase_uid` compatibility cache.
- Pytest still emits the existing `pytest_asyncio` loop-scope deprecation warning; it did not affect this task’s failure attribution.

## Files Created/Modified

- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — focused canonical cache/session hydration proof with one intentional red test for `firebase_uid` cache drift.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — shared-helper and adjacent V2 consumer proof with one intentional red test for `user_cache_shared` dual-identity drift.
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py` — extended override/request-state proof for mapping payloads and canonical session state side effects.
- `.gsd/milestones/M004/slices/S02/tasks/T01-SUMMARY.md` — recorded the red-first proof outcome and next diagnostic surfaces.
- `.gsd/milestones/M004/slices/S02/S02-PLAN.md` — marked T01 complete.
- `.gsd/STATE.md` — moved the slice state forward to T02.
