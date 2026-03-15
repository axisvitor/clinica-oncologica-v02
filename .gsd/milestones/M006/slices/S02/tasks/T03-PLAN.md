---
estimated_steps: 3
estimated_files: 3
---

# T03: Drop the remaining Firebase-named `users` columns and replay the final-schema pack

**Slice:** S02 — Remover o resíduo de schema que ainda prende o runtime ao passado
**Milestone:** M006

## Description

After T01 and T02, the runtime should be able to live without the Firebase-prefixed `users` residue. This task makes that true at the schema level and republishes the integrated proof so fresh and existing histories both exercise the new head honestly.

## Steps

1. Add a new Alembic revision after `m005_s03_t02_align_audit_history_head` that drops the Firebase-prefixed `users` columns and `ix_users_firebase_uid`, while leaving `auth_provider` and `firebase_sync_history` intact.
2. Update the canonical head convergence test so both clean replay and existing-upgrade histories fingerprint the post-drop `users` table correctly and fail with explicit diffs if any removed column/index comes back.
3. Extend the published final-schema runner to replay the focused S02 runtime packs before mounted backend proof, then rerun both `--fresh` and `--existing` histories.

## Must-Haves

- [ ] The new head removes only the intended `users` schema residue and keeps the live/historical boundaries honest (`auth_provider`, `firebase_sync_history`).
- [ ] Both replay histories and the mounted backend proof pass against the post-drop head.

## Verification

- `cd backend-hormonia && pytest -q tests/migrations/test_canonical_schema_head_convergence.py`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`

## Observability Impact

- Signals added/changed: `canonical_head` fingerprint output and final-schema phase/status files should identify missing/extra `users` columns and per-phase replay failures directly.
- How a future agent inspects this: read `/tmp/gsd-m005-s04-final-schema-proof/*/status.json`, the convergence diff, and the runner log pointers to localize whether failure happened in schema prep, pytest replay, or mounted backend startup.
- Failure state exposed: reintroduced schema residue shows up as named fingerprint deltas instead of generic Alembic drift or backend import errors.

## Inputs

- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — current fresh/existing replay fingerprint harness for the canonical head.
- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — published integrated proof surface that already owns fresh/existing replay plus mounted backend proof.
- `backend-hormonia/alembic/versions/m005_s03_t02_align_audit_history_head.py` — current head the new drop revision must extend.

## Expected Output

- `backend-hormonia/alembic/versions/<new_s02_drop_users_firebase_residue>.py` — new post-M005 head without the Firebase-prefixed `users` residue.
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — updated convergence proof for the post-drop head.
- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — integrated runner that replays the S02-focused runtime packs on both fresh and existing histories.
