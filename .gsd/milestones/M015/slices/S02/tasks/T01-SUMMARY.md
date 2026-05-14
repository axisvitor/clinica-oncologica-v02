---
id: T01
parent: S02
milestone: M015
key_files:
  - backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py
  - backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py
key_decisions:
  - PostgreSQL session rows are authoritative for both Redis cache hits and misses; Redis payloads are cache hints only.
duration: 
verification_result: passed
completed_at: 2026-05-14T07:52:30.773Z
blocker_discovered: false
---

# T01: Made PostgreSQL session state authoritative for staff-session Redis cache hits and misses, with fail-closed DB outage handling and direct-helper parity.

**Made PostgreSQL session state authoritative for staff-session Redis cache hits and misses, with fail-closed DB outage handling and direct-helper parity.**

## What Happened

Added M015/S02 security contract tests covering cache-hit DB validation, cache-miss DB fallback/rehydration, revoked/expired DB denial through stale Redis payloads, Redis timeout/error fallback, DB timeout/error fail-closed 503, inactive user denial, legacy Bearer/X-Session-ID rejection without a cookie, and direct V2 helper parity. Refactored auth_session_cache.resolve_session_user_data so every accepted session calls the DB session validator before trusting identity, while Redis misses/errors use the same DB path and rehydrate Redis best-effort. Brought app.api.v2.auth_session_shared.get_user_data_from_session to parity by querying the active/unrevoked/unexpired DB session row for both cache hits and misses, returning DB-derived canonical user data, and using sanitized diagnostic failure classes rather than raw exception values. Updated canonical identity regression tests so they still prove canonical user_id behavior and firebase_uid-cache avoidance under the new DB-authoritative session contract.

## Verification

Ran the required verification command from the task plan after the final code edits: `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q`. It passed with 30 tests (`.............................. [100%]`). A prior red run of the new security contract failed before implementation, confirming the tests pinned the intended behavior.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py -q` | 1 | ✅ expected red before implementation (10 failures pinning stale Redis trust/cache-miss denial) | 29295ms |
| 2 | `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py -q` | 0 | ✅ pass after DB-authoritative helper changes | 20220ms |
| 3 | `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` | 1 | ✅ expected regression signal before updating old canonical identity tests to new DB-authoritative contract | 30846ms |
| 4 | `cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q` | 0 | ✅ pass final verification (30 tests) | 22349ms |

## Deviations

Did not edit auth_session_contract.py or auth_dependencies.py directly because cookie-only transport was already enforced there and the existing dependency wiring already passed load_user_from_db_by_session into auth_session_cache; changing auth_session_cache made that wiring DB-authoritative for both cache hits and misses.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py`
- `backend-hormonia/app/dependencies/auth_session_cache.py`
- `backend-hormonia/app/api/v2/auth_session_shared.py`
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py`
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py`
