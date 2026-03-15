---
estimated_steps: 4
estimated_files: 6
---

# T03: Make the proof pack and fixtures tell the new truth

**Slice:** S02 — Legado Firebase isolado como histórico explícito
**Milestone:** M005

## Description

Finish the slice by making the test harness and focused proof reflect the new historical boundary, so fixtures stop resurrecting Firebase residue as live schema and the compatibility tests keep proving `user_id` remains the only canonical identity.

## Steps

1. Remove fixture defaults that recreate `audit_logs.firebase_uid` and `idx_audit_firebase_time` as live-schema assumptions in shared test setup.
2. Finalize the slice-focused migration/API/service tests with named failures for sync history, canonical audit writes, and sanitized payloads.
3. Rerun the existing `user_id`-first session compatibility tests to prove Firebase identity survives only as quarantined fallback compat.
4. Close the loop by rerunning the full S02 verification pack, including the reused S01 Alembic operability guard.

## Must-Haves

- [ ] Shared test fixtures stop lying about Firebase residue being part of the live canonical schema.
- [ ] The final verification pack distinguishes historical-boundary regressions from canonical-identity compatibility regressions.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py`
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`

## Observability Impact

- Signals added/changed: final proof names for `sync_history_surface`, `audit_contract`, `canonical_payload`, and canonical-identity fallback compatibility.
- How a future agent inspects this: run the full slice verification commands and read the named failing test blocks instead of diffing the whole repo.
- Failure state exposed: whether a failure comes from migration replay, fixture drift, canonical serialization, or fallback identity handling.

## Inputs

- `backend-hormonia/tests/conftest.py` and `backend-hormonia/tests/api/critical/conftest.py` — fixtures currently recreating legacy audit assumptions.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` and `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — compatibility proof that must remain green.
- Outputs from T01 and T02 — historical sync boundary plus narrowed canonical payload surfaces.
- S01 summary insight — `tests/migrations/test_alembic_operability.py` is the cheapest trustworthy regression gate and should stay in the slice closeout pack.

## Expected Output

- `backend-hormonia/tests/conftest.py` and `backend-hormonia/tests/api/critical/conftest.py` — fixtures aligned with the historical boundary instead of live Firebase residue.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` and `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py` — finalized named proof pack for the slice.
- Green reruns of the full S02 verification commands — evidence that the historical boundary and canonical identity contract now tell the same story.
