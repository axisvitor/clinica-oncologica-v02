---
id: T02
parent: S03
milestone: M005
provides:
  - Verified the canonical S03 schema head on real Postgres and fixed the shared Postgres runtime harness so the existing T02 migration/runtime proofs pass against the real Alembic head instead of a broken ORM-DDL schema bootstrap.
key_files:
  - backend-hormonia/alembic/versions/m005_s03_t02_align_audit_history_head.py
  - backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py
  - backend-hormonia/tests/services/audit/test_audit_service.py
  - backend-hormonia/tests/conftest.py
key_decisions:
  - Keep the published S03 head contract as-is: no live `audit_logs.firebase_uid`, and preserved sync transition residue stays archival under `firebase_sync_history.changes.historical_shape`.
  - When `TEST_DATABASE_URL` is set, shared Postgres runtime tests should provision via `alembic upgrade head` rather than `Base.metadata.create_all()`.
patterns_established:
  - Provision shared Postgres test schemas from the real Alembic head and reserve ORM `create_all()` for fallback paths only.
  - If legacy model metadata still carries duplicate index names, dedupe by database name before fallback ORM DDL so test bootstraps fail less opaquely.
observability_surfaces:
  - backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py
  - backend-hormonia/tests/services/audit/test_audit_service.py
  - scrubbed `python3 -m alembic -c alembic.ini current` output on the upgraded head
  - backend-hormonia/tests/conftest.py provisioning logs for Postgres test-schema bootstrap
duration: ~2h
verification_result: passed
completed_at: 2026-03-15T12:34:00-03:00
blocker_discovered: false
---

# T02: Alinhar audit/history e provar convergência clean+existing no mesmo head

**Closed the remaining T02 blocker by validating the already-landed S03 head-alignment work and fixing the shared Postgres test harness so the migration/runtime proofs now pass end-to-end on the real Alembic head.**

## What Happened

The branch already contained the intended T02 schema/model/test surfaces when this unit resumed: the final linear revision `m005_s03_t02_align_audit_history_head.py`, the enum-backed `AuditLog` contract, the archival-only `firebase_sync_history` ORM shape, and the real-Postgres convergence proof in `tests/migrations/test_canonical_schema_head_convergence.py`. I read those surfaces first, then ran the task verification pack to see what was still actually broken.

The migration proofs passed, but the runtime proofs did not. Both `tests/services/audit/test_audit_service.py` and `tests/api/v2/test_canonical_user_profile_contracts.py` were failing before the application logic under test ran because the shared Postgres `test_engine` fixture in `backend-hormonia/tests/conftest.py` was using `Base.metadata.create_all()` and silently booting an empty schema on failure. The concrete root cause was duplicated `patients` index objects already present in metadata (`ix_patients_email_hash`, `ix_patients_phone_hash`, `ix_patients_idempotency_key`): Postgres rejected the duplicate DDL, rolled the transaction back, and left later runtime fixtures querying tables that did not exist.

I fixed that at the harness boundary instead of papering over individual tests. `tests/conftest.py` now dedupes metadata indexes by database name before fallback ORM DDL, and—more importantly for this slice—when `TEST_DATABASE_URL` is set it resets the shared local Postgres schema and provisions it via `alembic upgrade head`. That makes the runtime suites boot against the actual canonical S03 head that T02 is supposed to prove, rather than against a partial ORM-generated approximation.

With that harness fix in place, the already-landed T02 proof surfaces now run green as written: the migration convergence suite proves `base -> head` and `m005_s02_t01_publish_firebase_history_boundary -> head` land on the same fingerprint, the audit runtime suite proves the live contract stays enum-backed and Firebase-free at the ORM boundary, and the canonical user/profile runtime suite proves the official user/auth/physician surfaces still match the canonical head story.

## Verification

Passed task-level verification:

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py tests/migrations/test_canonical_schema_head_convergence.py`
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py -k 'canonical or historical or enum'`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/services/audit/test_audit_service.py`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/api/v2/test_canonical_user_profile_contracts.py -k 'canonical_profile or canonical_preferences'`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/services/audit/test_audit_service.py && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current`
  - `current` reported `m005_s03_t02_align_audit_history_head (head)`.

Notes:

- I initially triggered a false migration failure by running multiple suites in parallel against the same single Postgres database. Rerunning the migration pack serially confirmed the code was fine and the interference was purely from shared-DB concurrency.

## Diagnostics

Fastest inspection surfaces for what now proves T02 cleanly:

- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — real-Postgres structural fingerprint proof with named `canonical_head`, `phase`, `head`, `enum_missing`, and `fingerprint_diff` failures.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` — archival-shape proof for `firebase_sync_history`, including historical residue preserved under `changes.historical_shape`.
- `backend-hormonia/tests/services/audit/test_audit_service.py` — explicit `audit_contract surface=...` assertions that the live ORM/runtime contract does not expose `firebase_uid` and still uses `audit_event_type`.
- `backend-hormonia/tests/conftest.py` — shared Postgres bootstrap now logs metadata-index dedupe and `alembic upgrade head` provisioning when `TEST_DATABASE_URL` is used.
- Scrubbed Alembic current output — `m005_s03_t02_align_audit_history_head (head)` after the runtime pass leaves the database upgraded.

## Deviations

- The written task expected implementation work across the T02 schema/model/test bundle, but those changes were already present on this slice branch when the unit resumed. The only remaining code change required in this unit was the shared Postgres runtime-harness fix needed to make the planned verification pass honestly.
- The slice plan lists a direct scrubbed `alembic current` check. Because the migration suites intentionally reset `public` during teardown, I ran `current` after a head-provisioning runtime pass so the command would report meaningful head state instead of an empty schema.

## Known Issues

- none

## Files Created/Modified

- `backend-hormonia/tests/conftest.py` — shared Postgres runtime harness now provisions from Alembic head under `TEST_DATABASE_URL` and dedupes duplicate metadata index names before fallback ORM DDL.
- `.gsd/DECISIONS.md` — recorded the shared Postgres runtime test provisioning decision.
- `.gsd/milestones/M005/slices/S03/S03-PLAN.md` — added the missing diagnostic verification step and marked T02 complete.
- `.gsd/milestones/M005/slices/S03/tasks/T02-SUMMARY.md` — recorded what actually shipped and what was verified in this unit.
- `.gsd/STATE.md` — created the quick-glance state file and moved the next action to S04 planning/execution.
