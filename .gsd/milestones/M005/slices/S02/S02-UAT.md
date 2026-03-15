# S02: Legado Firebase isolado como histórico explícito — UAT

**Milestone:** M005
**Written:** 2026-03-15

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S02 changes schema/history boundaries, canonical API payload contracts, and session/audit compatibility seams. These are best proven by deterministic migration/service/API tests against local Postgres rather than manual UI walkthroughs.

## Preconditions

- Local Postgres test instance is reachable at `postgresql://postgres:postgres@localhost:55432/hormonia_test`.
- Python dependencies for `backend-hormonia` are installed.
- Run commands from the repository root.
- No other migration suite is using the same `TEST_DATABASE_URL` at the same time; the migration proof resets `public` and must be run serially on a shared local database.

## Smoke Test

Run:

```bash
cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'
```

Expected:
- The command passes.
- No assertion emits `sync_history_surface ...` or `named_failure ...`.
- This confirms the historical sync table is explicit and the shared audit fixture guards are not reviving Firebase residue.

## Test Cases

### 1. Existing-db upgrade preserves the explicit Firebase sync history surface

1. Run:
   ```bash
   cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k sync_history_surface
   ```
2. Observe the existing-db branch in `test_sync_history_named_failure_preserves_rows_on_existing_db_upgrade`.
3. **Expected:**
   - `firebase_sync_history` exists after upgrade.
   - `user_sync_log` no longer exists.
   - Preserved legacy rows survive the rename/backfill path.
   - The clean replay branch lands on `m005_s02_t01_publish_firebase_history_boundary` without schema ambiguity.

### 2. Canonical audit writes quarantine `firebase_uid`

1. Run:
   ```bash
   cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py -k 'audit_contract or legacy_writer or login_success_helper'
   ```
2. Observe the audit writer assertions.
3. **Expected:**
   - Canonical audit writes persist with `firebase_uid=None`.
   - Any legacy `firebase_uid` input is stripped from canonical metadata.
   - The test names/localized failures stay under the `audit_contract` or `legacy_writer` buckets.

### 3. Official users/admin/physicians payloads no longer expose `firebase_uid`

1. Run:
   ```bash
   cd backend-hormonia && pytest -q tests/api/v2/test_firebase_boundary_contracts.py -k 'audit or canonical_payload'
   ```
2. Observe the payload contract assertions.
3. **Expected:**
   - `/api/v2/users/me` returns sanitized payloads even when stale cache data still contains `firebase_uid`.
   - Admin user payloads do not publish `firebase_uid`.
   - Physician payloads do not publish `firebase_uid`.
   - Historical audit export filtering stays explicit and read-only.

### 4. `user_id`-first session compatibility still works without reviving Firebase identity

1. Run:
   ```bash
   cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py
   ```
2. Observe the named session/cache compatibility assertions.
3. **Expected:**
   - Canonical embedded sessions and cache/db lookups resolve by `user_id` first.
   - Cookie/shared helper paths stay green.
   - The quarantined fallback compat path still works without turning `firebase_uid` back into the live contract.
   - Failures, if any, are localized under `canonical_identity`.

### 5. Full slice proof pack stays green end-to-end

1. Run:
   ```bash
   cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure' && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py
   ```
2. Let the command finish without running any other migration suite against the same DB in parallel.
3. **Expected:**
   - All four proof segments pass.
   - The slice remains green across migration replay, append-only history writes, canonical payload narrowing, and `user_id`-first compat fallback.

## Edge Cases

### Stale `/users/me` cache still carries pre-slice `firebase_uid`

1. Run:
   ```bash
   cd backend-hormonia && pytest -q tests/api/v2/test_firebase_boundary_contracts.py -k canonical_payload
   ```
2. **Expected:**
   - The returned payload is sanitized.
   - The cleaned payload is rewritten back to cache.
   - No official user payload republishes `firebase_uid`.

### Shared test fixtures run against a stripped `audit_logs` table

1. Run:
   ```bash
   cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k named_failure
   ```
2. **Expected:**
   - Shared and critical conftest guards add only live audit columns.
   - Neither guard recreates `audit_logs.firebase_uid`.
   - Neither guard recreates `idx_audit_firebase_time`.

### Append-only sync history write fails internally

1. Run:
   ```bash
   cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py
   ```
2. **Expected:**
   - The history writer remains append-only.
   - Failure handling rolls back the history write path cleanly without reclassifying the surface as live domain state.

## Failure Signals

- `sync_history_surface ...` — clean replay or existing-db history-boundary regression.
- `named_failure ... resurrected_historical_audit_firebase_*` — shared fixture drift recreated historical audit residue.
- `audit_contract ...` — canonical audit writer/export leaked `firebase_uid` back into the live contract.
- `canonical_payload ...` — users/admin/physicians payloads or cache sanitization regressed.
- `canonical_identity ...` — `user_id`-first session/cache compatibility broke or the fallback boundary revived Firebase semantics.
- Migration tests failing only under concurrent execution against the same `TEST_DATABASE_URL` — likely a harness race on `DROP SCHEMA public CASCADE`, not necessarily a slice regression.

## Requirements Proved By This UAT

- R051 — proves that the live contract no longer treats Firebase sync rows or `firebase_uid` as active schema/API/session identity seams in the S02 scope; preserved residue is explicit and historical.

## Not Proven By This UAT

- Final clean-vs-existing schema convergence to one canonical head; that belongs to S03.
- Mounted backend proof on the final canonical head; that belongs to S04.
- Repo-wide removal of all remaining dead code or compatibility islands; that belongs to M006/R052.

## Notes for Tester

- Run the migration commands serially if you use the shared local Postgres test database; parallel destructive runs can manufacture false negatives.
- The expected result of this slice is not “Firebase data disappears.” The expected result is “preserved Firebase data is explicit historical residue and no longer part of the canonical live contract.”
- Ignore the current `pytest-asyncio` deprecation warning about `asyncio_default_fixture_loop_scope`; it does not indicate an S02 regression.
