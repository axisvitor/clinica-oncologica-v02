---
id: S02
parent: M005
milestone: M005
provides:
  - Explicit Firebase historical boundaries across schema, audit, and API/session contracts without reviving `firebase_uid` as live runtime identity.
requires:
  - slice: S01
    provides: Alembic operability harness and settings-free migration control-plane replay on local Postgres.
affects:
  - S03
  - S04
key_files:
  - backend-hormonia/alembic/versions/m005_s02_t01_publish_firebase_history_boundary.py
  - backend-hormonia/app/models/user_sync_log.py
  - backend-hormonia/app/services/firebase_user_sync_service.py
  - backend-hormonia/app/models/audit_log.py
  - backend-hormonia/app/services/audit_log.py
  - backend-hormonia/app/api/v2/routers/users.py
  - backend-hormonia/app/api/v2/routers/admin/utils.py
  - backend-hormonia/app/api/v2/routers/physicians/crud.py
  - backend-hormonia/tests/migrations/test_firebase_historical_boundary.py
  - backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py
  - backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py
key_decisions:
  - Publish legacy sync residue as append-only `firebase_sync_history` instead of keeping the live-looking `user_sync_log` contract.
  - Keep `audit_logs.firebase_uid` only as historical residue while canonical writes and official serializers sanitize it away.
  - Shared Postgres fixture guards may patch only live `audit_logs` columns and must never recreate historical Firebase audit residue.
patterns_established:
  - Historical Firebase residue is preserved behind explicitly named archival tables and read-only filters instead of canonical ORM/API contracts.
  - Canonical payload boundaries sanitize stale cache entries and legacy-writer inputs before they can republish quarantined identity fields.
  - Focused migration/API/session proof uses named failure prefixes (`sync_history_surface`, `audit_contract`, `canonical_payload`, `canonical_identity`) to localize regressions.
observability_surfaces:
  - cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'
  - cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py -k 'audit_contract or legacy_writer or login_success_helper'
  - cd backend-hormonia && pytest -q tests/api/v2/test_firebase_boundary_contracts.py -k 'audit or canonical_payload'
  - cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py
drill_down_paths:
  - .gsd/milestones/M005/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S02/tasks/T03-SUMMARY.md
duration: ~3h10m
verification_result: passed
completed_at: 2026-03-15T10:41:37-03:00
---

# S02: Legado Firebase isolado como histórico explícito

**Firebase-era sync/audit residue now lives behind explicit historical seams while canonical users/admin/physicians/session surfaces stay `user_id`-first and `firebase_uid`-free.**

## What Happened

S02 closed the ambiguity around what Firebase residue is still intentionally preserved and what no longer belongs to the live contract.

First, the slice published the sync-history boundary honestly. The old live-looking `user_sync_log` surface became the explicit archival table `firebase_sync_history` through a dedicated Alembic revision, the ORM/export seam was renamed to match that archival meaning, and `FirebaseUserSyncService` was rewired to append history rows instead of writing through a model that looked like active domain state. The same task added migration proof for both clean replay and existing-db upgrade, so preserved rows survive the rename and the new boundary is visible in replayable Postgres state.

Second, the slice quarantined `firebase_uid` from the canonical write/read paths without erasing the chosen historical residue. `AuditLogService` now strips `firebase_uid` from canonical writes and metadata, leaving persisted canonical audit rows with `firebase_uid=None`. Official read surfaces for users, admin, and physicians no longer expose `firebase_uid`, while still-live Firebase-era profile fields stayed explicit instead of being prematurely classified as archival. Cached `/api/v2/users/me` and admin single-user responses were also handled honestly so stale cache entries cannot keep replaying the pre-slice contract.

Third, the slice made the proof pack tell the same story as the runtime. Shared Postgres fixture guards stopped silently recreating `audit_logs.firebase_uid` and `idx_audit_firebase_time`, and the migration proof now exercises those guards directly against a stripped audit table. Session compatibility coverage was tightened with named `canonical_identity` assertions so the remaining `user_id`-first fallback behavior stays distinct from the historical Firebase boundary work.

By the end of the slice, the preserved Firebase sync/audit residue is explicit and quarantined, while the canonical model/API/session story no longer treats `firebase_uid` as a live contract.

## Verification

Passed the full slice verification pack, run serially against the shared local Postgres test database:

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'`
- `cd backend-hormonia && pytest -q tests/unit/test_firebase_sync_history.py tests/services/audit/test_audit_service.py tests/api/v2/test_firebase_boundary_contracts.py`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`

Confirmed the published drill-down diagnostics replay cleanly:

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_firebase_historical_boundary.py -k 'sync_history_surface or named_failure'`
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py -k 'audit_contract or legacy_writer or login_success_helper'`
- `cd backend-hormonia && pytest -q tests/api/v2/test_firebase_boundary_contracts.py -k 'audit or canonical_payload'`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py`

Note: the migration tests reset `public` and should not be parallelized against the same `TEST_DATABASE_URL`; a parallel replay can create false negatives unrelated to slice behavior.

## Requirements Advanced

- R051 — S02 published the explicit historical/live Firebase boundary in sync history, audit writes, official serializers, and shared test harnesses, so the active schema/runtime contract now carries less Firebase residue as live structure.

## Requirements Validated

- none — final head convergence and mounted runtime proof still belong to S03/S04.

## New Requirements Surfaced

- none.

## Requirements Invalidated or Re-scoped

- none.

## Deviations

none.

## Known Limitations

- `audit_logs.firebase_uid` still exists as preserved historical residue; S03 still needs to decide what survives in the final canonical head versus what can be removed outright.
- `firebase_sync_history` is now explicit and honest, but S03 still has to prove clean and existing databases converge to the same final head after the historical/live split.
- Some Firebase-era profile fields remain live (`firebase_last_sign_in`, `firebase_display_name`, `firebase_photo_url`, `firebase_email_verified`) and were intentionally left for S03 instead of being reclassified blindly in S02.

## Follow-ups

- Converge clean replay and existing-db upgrade to one canonical head with the same live schema now that the historical boundary is explicit.
- Decide, with proof, which remaining Firebase-era columns stay operational in the final schema and which become removable historical residue in S03.
- Keep destructive migration proof serial when reusing a single local Postgres test database.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m005_s02_t01_publish_firebase_history_boundary.py` — published `firebase_sync_history` as the explicit archival sync table.
- `backend-hormonia/app/models/user_sync_log.py` — replaced the live-looking sync model with the explicit append-only `FirebaseSyncHistory` seam.
- `backend-hormonia/app/services/firebase_user_sync_service.py` — rewired sync logging to append archival history rows.
- `backend-hormonia/app/models/audit_log.py` — documented `firebase_uid` as historical-only audit residue.
- `backend-hormonia/app/services/audit_log.py` — sanitized legacy `firebase_uid` input out of canonical audit writes and metadata.
- `backend-hormonia/app/api/v2/routers/users.py` — sanitized stale cached `/users/me` payloads and rewrote cleaned cache entries.
- `backend-hormonia/app/api/v2/routers/admin/utils.py` — removed `firebase_uid` from official admin serialization and mapped `last_login` to the still-live sign-in field.
- `backend-hormonia/app/api/v2/routers/admin/users.py` — versioned the cached admin single-user payload seam to avoid stale contract replay.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — removed `firebase_uid` from physician payload assembly.
- `backend-hormonia/app/schemas/v2/admin.py` — dropped `firebase_uid` from the official admin response schema.
- `backend-hormonia/app/schemas/v2/physicians.py` — dropped `firebase_uid` from the physician schema while keeping still-live profile fields explicit.
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` — constrained the historical audit metadata filter surface.
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` — proved clean replay, existing-db preservation, and fixture-drift failures with named assertions.
- `backend-hormonia/tests/unit/test_firebase_sync_history.py` — proved append-only sync history writes and non-blocking failure behavior.
- `backend-hormonia/tests/services/audit/test_audit_service.py` — proved canonical audit null writes and metadata sanitization.
- `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py` — proved canonical payload narrowing across users/admin/physicians and audit export filtering.
- `backend-hormonia/tests/conftest.py` — stopped resurrecting historical Firebase audit residue in shared Postgres setup.
- `backend-hormonia/tests/api/critical/conftest.py` — matched the critical-suite audit schema guard to the live-only boundary.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` — added named `canonical_identity` assertions for `user_id`-first session/cache behavior.
- `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — added named `canonical_identity` assertions for shared auth/session helpers.
- `.gsd/REQUIREMENTS.md` — updated R051 mapping/notes to reflect S02 evidence.
- `.gsd/PROJECT.md` — refreshed current project state for the completed historical Firebase boundary.
- `.gsd/STATE.md` — moved the active slice to S03.
- `.gsd/milestones/M005/M005-ROADMAP.md` — marked S02 complete.

## Forward Intelligence

### What the next slice should know
- The clean replay path and the existing-db path now agree on the historical boundary: `firebase_sync_history` is the honest archival seam, and canonical API/session surfaces no longer advertise `firebase_uid`.
- The remaining hard work is schema convergence, not contract ambiguity. S03 should focus on making clean and upgraded databases land on the same canonical live schema after the historical split, especially around the remaining Firebase-era profile fields and any lingering one-way Alembic scars.
- If you reuse the same local Postgres database for migration proofs, run destructive migration commands serially. Parallel runs can race on `DROP SCHEMA public CASCADE` and create false migration failures.

### What's fragile
- Existing-db migration proof on a shared local database — destructive tests reset `public`, so concurrent runs can fake schema regressions.
- Remaining Firebase-era profile columns — they are still operationally live enough that reclassifying or dropping them without proof in S03 would be guesswork.

### Authoritative diagnostics
- `backend-hormonia/tests/migrations/test_firebase_historical_boundary.py` — this is the authoritative boundary proof for clean replay, existing-db preservation, and fixture drift.
- `backend-hormonia/tests/api/v2/test_firebase_boundary_contracts.py` — this catches canonical payload regressions for users/admin/physicians and filtered audit export behavior.
- `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` and `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — these are the fastest trustworthy signals that the `user_id`-first compat fallback still works without reviving `firebase_uid` as a live contract.

### What assumptions changed
- `user_sync_log` looked like an acceptable leftover compatibility seam — it was not; the slice proved it needed an explicit archival identity as `firebase_sync_history`.
- Preserving audit/session compatibility meant tolerating `firebase_uid` in canonical payloads or writers — it did not; sanitizing writes, caches, and serializers preserved compatibility while keeping the live contract narrow.
- Shared test fixtures were assumed to be neutral — they were not until T03; they were quietly rebuilding historical Firebase audit residue and now explicitly guard only live columns.
