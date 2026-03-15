# S03: Head canônico de schema sem resíduo estrutural vivo — UAT

**Milestone:** M005
**Written:** 2026-03-15

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S03 changes the migration graph, canonical schema head, and runtime-adjacent API/model contracts. The honest acceptance surface is deterministic command/test proof against real Postgres rather than a manual UI walkthrough.

## Preconditions

- Local Postgres test instance is reachable at `postgresql://postgres:postgres@localhost:55432/hormonia_test`.
- Python dependencies for `backend-hormonia` are installed.
- The repo is at the S03-complete state.
- No runtime secrets beyond the database URL are required for the Alembic proof.
- Run commands from the repository root unless noted otherwise.

## Smoke Test

Run the canonical migration convergence pack:

1. `cd backend-hormonia`
2. `TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py tests/migrations/test_canonical_schema_head_convergence.py`
3. **Expected:** The suite passes with no failures. A failure here means S03 no longer proves that clean replay and upgraded databases converge to the same canonical head.

## Test Cases

### 1. Clean replay and upgraded replay converge to the same S03 head

1. `cd backend-hormonia`
2. Run `TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py tests/migrations/test_canonical_schema_head_convergence.py`
3. **Expected:** All tests pass. The convergence suite must not report `canonical_head`, `phase`, `head`, `enum_missing`, or `fingerprint_diff` failures. This proves both `base -> head` and `m005_s02_t01_publish_firebase_history_boundary -> head` land on the same structure.

### 2. Official user/auth/physician surfaces read and write the canonical `users` contract

1. `cd backend-hormonia`
2. Run `pytest -q tests/api/v2/test_canonical_user_profile_contracts.py`
3. **Expected:** The suite passes with no failures. The proven contract is canonical/neutral naming such as `last_login`, `photo_url`, and canonical preferences/profile storage rather than Firebase-shaped live fields or claims storage.

### 3. Focused canonical profile and preferences writes still hold on their own

1. `cd backend-hormonia`
2. Run `pytest -q tests/api/v2/test_canonical_user_profile_contracts.py -k 'canonical_profile or canonical_preferences'`
3. **Expected:** The focused subset passes. This isolates the live `users` storage change from unrelated router behavior and confirms the slice’s highest-risk payload/write surfaces remain canonical.

### 4. Scrubbed Alembic inspection still reports the canonical head without extra runtime env

1. `cd backend-hormonia`
2. Run `env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current`
3. **Expected:** Output includes exactly `m005_s03_t02_align_audit_history_head (head)`. No Firebase/WuzAPI/app-runtime secret should be required.

### 5. Audit contract remains enum-backed and Firebase-free at the live ORM/runtime boundary

1. `cd backend-hormonia`
2. Run `pytest -q tests/services/audit/test_audit_service.py -k 'canonical or historical or enum'`
3. **Expected:** The suite passes with no failures. The live audit contract must continue using `audit_event_type`, must not expect live `audit_logs.firebase_uid`, and must preserve only the explicit historical boundary already published in S02/S03.

### 6. Combined runtime-adjacent proof still passes after the head alignment

1. `cd backend-hormonia`
2. Run `pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/services/audit/test_audit_service.py`
3. **Expected:** Both suites pass together. This confirms the canonical `users` contract and the canonical `audit_logs` contract still coexist cleanly in the assembled runtime-adjacent test harness.

## Edge Cases

### Serial execution against one shared Postgres database

1. Run the migration/runtime commands one after another, not in parallel, when they share `postgresql://postgres:postgres@localhost:55432/hormonia_test`.
2. **Expected:** Suites pass consistently. Parallel runs against the same database are a known false-negative source because migration fixtures reset `public` during teardown.

### Historical sync residue remains archival, not structural

1. Run `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py`
2. **Expected:** The suite passes and preserved sync-era residue is verified under `firebase_sync_history.changes.historical_shape`, not as live columns like `supabase_user_id`, `sync_action`, or `sync_status` on the canonical head.

### Shared Postgres runtime harness uses Alembic head, not ORM bootstrap fiction

1. Run `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/services/audit/test_audit_service.py`
2. **Expected:** The suites pass without missing-table errors caused by `Base.metadata.create_all()`. If the harness silently falls back to broken ORM DDL, failures typically show up before application logic as missing tables after duplicate-index rollback.

## Failure Signals

- `canonical_head surface=...` failures in `tests/migrations/test_canonical_schema_head_convergence.py`
- `fingerprint_diff`, `enum_missing`, head mismatch, or missing/extra column/index diagnostics in the migration pack
- `audit_contract surface=...` failures in `tests/services/audit/test_audit_service.py`
- `canonical_profile` or `canonical_preferences` assertion failures in `tests/api/v2/test_canonical_user_profile_contracts.py`
- `alembic current` reporting anything other than `m005_s03_t02_align_audit_history_head (head)`
- Any command needing non-database runtime secrets to inspect or traverse the migration graph

## Requirements Proved By This UAT

- R051 — Proves the live schema/models/migration head now tell the canonical post-Firebase story and that clean + upgraded databases converge to the same honest head.

## Not Proven By This UAT

- R052 — This slice does not remove all remaining dead-code/compatibility residue across the repo.
- S04 scope — This UAT does not prove the real backend entrypoint booting on the final head or the full post-M004 critical-loop replay on assembled runtime state.

## Notes for Tester

- Treat the migration convergence pack as the primary acceptance gate for S03.
- Treat the scrubbed `alembic current` command as the fastest quick-check when you only need to know whether the local database is on the canonical S03 head.
- If a failure appears only when multiple verifier commands run at once, rerun them serially before assuming a code regression.
