---
id: S03
parent: M005
milestone: M005
provides:
  - Canonical S03 schema head where clean replay and existing-upgrade converge on the same Postgres fingerprint without live Firebase-shaped residue in `users`, `audit_logs`, or `firebase_sync_history`.
requires:
  - slice: S01
    provides: Alembic control-plane commands and replay work with only database configuration.
  - slice: S02
    provides: Firebase-era sync/audit residue is already isolated behind an explicit historical boundary.
affects:
  - S04
key_files:
  - backend-hormonia/alembic/versions/m005_s03_t01_republish_users_canonical_contract.py
  - backend-hormonia/alembic/versions/m005_s03_t02_align_audit_history_head.py
  - backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py
  - backend-hormonia/tests/conftest.py
key_decisions:
  - `users` canonical profile/settings columns are now the live source of truth; Firebase-named storage is mirrored only for explicit transition compatibility.
  - The canonical S03 head keeps `audit_logs` free of live `firebase_uid` and preserves remaining sync-era residue only under `firebase_sync_history.changes.historical_shape`.
  - Shared Postgres runtime tests must provision from `alembic upgrade head` when `TEST_DATABASE_URL` is set so runtime suites validate the real head, not ORM-generated DDL.
patterns_established:
  - Read canonical-first with legacy fallback at model/helper edges; write canonical-first and mirror legacy storage only where active readers still exist.
  - Compare clean replay and upgraded paths by structural fingerprint rather than by revision name alone.
  - Provision shared Postgres test schemas from Alembic head for migration-adjacent runtime proof.
observability_surfaces:
  - backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py
  - backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py
  - backend-hormonia/tests/services/audit/test_audit_service.py
  - env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current
  - backend-hormonia/tests/conftest.py Postgres provisioning path
drill_down_paths:
  - .gsd/milestones/M005/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S03/tasks/T02-SUMMARY.md
duration: ~4h
verification_result: passed
completed_at: 2026-03-15T12:44:55-03:00
---

# S03: Head canônico de schema sem resíduo estrutural vivo

**Republished the live `users` contract under neutral canonical storage, closed the remaining audit/history alignment at the head, and proved in real Postgres that clean and existing databases converge to the same honest S03 schema.**

## What Happened

S03 closed the structural part of M005.

T01 published neutral live storage for the still-active user profile/settings data in `users` (`last_login`, `display_name`, `photo_url`, `preferences`, physician/profile fields, and related canonical columns), backfilled it from the old Firebase-shaped columns/claims, and rewired the official user/auth/physician surfaces to read and write that canonical contract first. `firebase_uid` and `auth_provider` stayed only as explicit compatibility residue while active readers still exist, and `firebase_custom_claims` stopped acting as the live canonical store for profile/preferences data.

T02 then closed the rest of the head story around `audit_logs` and `firebase_sync_history`. The final S03 alignment revision and model/test bundle already existed on the branch when this unit resumed, so the remaining work was to validate that contract honestly and fix the shared Postgres test harness that was still booting runtime suites from `Base.metadata.create_all()`. That path was already invalid on Postgres because duplicate `patients` index metadata caused DDL rollback and left later suites querying missing tables. The harness now provisions the shared Postgres schema with `alembic upgrade head` whenever `TEST_DATABASE_URL` is set, deduping metadata indexes only for the fallback ORM path.

With that fix in place, the slice proof surfaces now tell one consistent story:

- `base -> head` and `m005_s02_t01_publish_firebase_history_boundary -> head` land on the same S03 fingerprint.
- `users` live fields are canonical/neutral at the model and API boundary.
- `audit_logs.event_type` is enum-backed at the live contract and no live `audit_logs.firebase_uid` is expected.
- `firebase_sync_history` remains explicit history only, with preserved transition residue held under `changes.historical_shape` rather than live structural columns.
- Scrubbed `alembic current` reports `m005_s03_t02_align_audit_history_head (head)`.

## Verification

Passed the full slice verifier pack from `S03-PLAN.md`:

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py tests/migrations/test_firebase_historical_boundary.py tests/migrations/test_canonical_schema_head_convergence.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/services/audit/test_audit_service.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py -k 'canonical_profile or canonical_preferences'`
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current`
- `cd backend-hormonia && pytest -q tests/services/audit/test_audit_service.py -k 'canonical or historical or enum'`

All passed in this closeout run. The scrubbed Alembic command reported `m005_s03_t02_align_audit_history_head (head)`.

## Requirements Advanced

- R053 — S03 added real-Postgres proof that the canonical schema head itself converges cleanly before S04 mounts the backend on that head.

## Requirements Validated

- R051 — Real Postgres proof now shows fresh and upgraded databases reaching the same canonical S03 head while official user/auth/physician and audit/history surfaces stop treating Firebase-shaped structure as live schema contract.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

The written T02 task expected implementation work across the final alignment revision/model/test bundle, but those schema/model/test changes were already present on the slice branch when this unit resumed. The only remaining code change needed to make the written verifier pass honestly was the shared Postgres harness fix in `tests/conftest.py`.

## Known Limitations

S04 still has to boot the real backend on this consolidated head and replay the post-M004 critical loops against both freshly bootstrapped and upgraded schemas. Legacy compatibility mirrors inside `users` also still exist until the remaining readers are proven removable in later work.

## Follow-ups

- Execute S04 against the same canonical head `m005_s03_t02_align_audit_history_head` and reuse the Alembic-based shared Postgres provisioning path.
- Keep migration/runtime verifier runs serial when they share the same `TEST_DATABASE_URL`; parallel runs against one database can create false failures.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m005_s03_t01_republish_users_canonical_contract.py` — published canonical `users` profile/settings storage and backfill.
- `backend-hormonia/alembic/versions/m005_s03_t02_align_audit_history_head.py` — final S03 head alignment for canonical audit/history schema.
- `backend-hormonia/app/models/user.py` — canonical-first profile/settings storage with explicit legacy mirroring.
- `backend-hormonia/app/models/audit_log.py` — live audit contract aligned to enum-backed canonical head without live `firebase_uid`.
- `backend-hormonia/app/models/user_sync_log.py` — explicit archival `firebase_sync_history` shape.
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — structural fingerprint proof for clean vs upgraded convergence.
- `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py` — canonical user/auth/physician contract proof.
- `backend-hormonia/tests/services/audit/test_audit_service.py` — focused proof for enum-backed audit contract and historical boundary.
- `backend-hormonia/tests/conftest.py` — shared Postgres runtime harness now provisions via Alembic head under `TEST_DATABASE_URL`.
- `.gsd/milestones/M005/slices/S03/S03-SUMMARY.md` — compressed slice closeout.
- `.gsd/milestones/M005/slices/S03/S03-UAT.md` — concrete slice UAT script.
- `.gsd/REQUIREMENTS.md` — promoted R051 to validated and updated S03 requirement traceability.
- `.gsd/DECISIONS.md` — published the S03 archival boundary decision.
- `.gsd/PROJECT.md` — refreshed current project state after S03 closeout.
- `.gsd/STATE.md` — advanced active slice to S04.
- `.gsd/milestones/M005/M005-ROADMAP.md` — marked S03 complete.

## Forward Intelligence

### What the next slice should know
- The shared Postgres runtime harness only tells the truth for migration-adjacent proof if `TEST_DATABASE_URL` is set and the schema is provisioned from Alembic head. Reverting to `Base.metadata.create_all()` will reintroduce false failures and schema drift.
- The clean/existing convergence proof is already in place. S04 should consume it rather than invent a new structural oracle.

### What's fragile
- Shared `TEST_DATABASE_URL` concurrency — running multiple migration/runtime suites in parallel against the same Postgres database can create false negatives by resetting `public` underneath another suite.
- Legacy user-field mirroring — canonical storage is authoritative now, but some compatibility mirrors remain and can confuse future cleanup if a reader still silently depends on them.

### Authoritative diagnostics
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — fastest truth for head/fingerprint drift and enum/index/column mismatch.
- `env -i ... python3 -m alembic -c alembic.ini current` — fastest truth for the scrubbed live head revision.
- `backend-hormonia/tests/services/audit/test_audit_service.py` — fastest truth for whether the live audit contract has accidentally regressed toward Firebase-shaped schema.

### What assumptions changed
- “T02 still needs substantial schema/model implementation” — the branch already had the intended alignment revision and proof surfaces; the real blocker was the shared Postgres provisioning path in `tests/conftest.py`.
