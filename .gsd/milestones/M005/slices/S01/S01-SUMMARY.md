---
id: S01
parent: M005
milestone: M005
provides:
  - Settings-free Alembic control plane: `history`, `heads`, `upgrade head`, and `current` now work with only database configuration.
  - Migration-owned helper/import seams for historical revisions and LGPD backfills, so graph traversal no longer boots `app.config.settings` or unrelated secrets.
  - A real-Postgres operability pack with named `db_url_resolution`, `graph-load`, `upgrade`, and `current` failures plus masked database URLs.
requires: []
affects:
  - S02: can isolate Firebase historical data on top of a working, scrubbed Alembic control plane instead of debugging bootstrap side effects.
  - S03: can reuse the operability harness to prove clean and existing databases converge to the same head.
key_files:
  - backend-hormonia/app/db/base.py
  - backend-hormonia/app/db/migrations.py
  - backend-hormonia/alembic/env.py
  - backend-hormonia/alembic/runtime_helpers.py
  - backend-hormonia/alembic_runtime_helpers.py
  - backend-hormonia/alembic/versions/020_encrypt_cpf_lgpd.py
  - backend-hormonia/alembic/versions/029_migrate_email_phone_to_encrypted.py
  - backend-hormonia/alembic/versions/73a9d4d7cf05_align_patient_lgpd_encryption.py
  - backend-hormonia/alembic/versions/lgpd03_add_ai_audit_event_types.py
  - backend-hormonia/tests/migrations/test_alembic_operability.py
  - .gsd/milestones/M005/slices/S01/S01-UAT.md
key_decisions:
  - Alembic metadata/bootstrap helpers live in settings-free `app.db` modules; runtime engine/session bootstrap stays in `app.database`.
  - Historical revisions import migration-owned helpers through `backend-hormonia/alembic_runtime_helpers.py` instead of `app.utils` or `alembic.*`.
  - Runtime-coupled backfills must prove pending rows before importing app services, and clean-replay alignment revisions may guard missing legacy-only DB objects instead of failing the whole upgrade path.
patterns_established:
  - Keep migration control-plane imports self-contained and push package-level runtime side effects behind lazy exports.
  - Prove operability with scrubbed-env subprocess checks plus a real Postgres replay, and make failures name command/phase/revision/import path with masked URLs.
observability_surfaces:
  - `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py`
  - `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini history`
  - `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini heads`
  - `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini upgrade head`
  - `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current`
drill_down_paths:
  - .gsd/milestones/M005/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S01/tasks/T03-SUMMARY.md
duration: 3h45m
verification_result: passed
completed_at: 2026-03-14T16:09:58-03:00
blocker_discovered: false
---

# S01: Alembic operável sem segredos de runtime

**What was actually shipped:** a self-contained Alembic control plane that can load the graph, inspect heads/history, and replay a clean Postgres to head/current with only database configuration, without WuzAPI/Firebase secrets or `app.config.settings` imports.

## What Happened

- T01 moved declarative metadata and migration bootstrap into settings-free `app.db` modules, kept runtime engine/session setup in `app.database`, and exposed named bootstrap failures for DB URL resolution and graph loading.
- That work also exposed package-level import side effects outside Alembic itself, so `app.utils` and `app.integrations*` exports were made lazy to stop deep model imports from bootstrapping unrelated runtime settings.
- T02 replaced the remaining historical `app.utils` dependencies with migration-owned helpers for timezone and JSON-schema validation, published them through `backend-hormonia/alembic_runtime_helpers.py`, and extended the operability pack so graph-walk regressions report `command`, `offending_revision`, and `offending_import_path` instead of a generic settings cascade.
- T03 guarded the LGPD backfill revisions so they only import `app.services.encryption` after proving there is real work to do, then fixed the clean replay path in `lgpd03_add_ai_audit_event_types` by tolerating a missing legacy-only enum on the historical path.
- For slice closeout, I reran the full written verification set plus the direct scrubbed `upgrade head`/`current` CLI probes against the same local Postgres URL used in T03 because `TEST_DATABASE_URL` was not exported in the agent shell.

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py` — **PASS**
- `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k db_url_resolution` — **PASS**
- `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k missing_source_has_named_failure` — **PASS**
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini history` — **PASS**
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini heads` — **PASS**
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini upgrade head` — **PASS**
- `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current` — **PASS**

Observed evidence:
- `pytest -q tests/migrations/test_alembic_operability.py` stayed green with the real-Postgres path and the named failure-phase harness intact.
- `alembic history` printed the full graph from `<base>` through `lgpd03_add_ai_audit_event_types` under scrubbed env.
- `alembic heads` reported a single head: `lgpd03_add_ai_audit_event_types (head)`.
- The direct scrubbed `upgrade head && current` replay reached the same head without any WuzAPI/Firebase settings in the environment.

## Requirements Advanced

- `R051` — S01 proved the Alembic control plane can load, traverse, and replay on real Postgres with only DB config; final schema convergence and historical-boundary cleanup remain for S02–S04.
- `R053` — S01 added real migration-plane replay evidence to the broader integrated closeout chain, even though the requirement was already validated earlier by mounted runtime proof.

## Requirements Validated

- No additional requirement reached fully validated status in this slice; S01 advances operability but does not yet prove final schema convergence on its own.

## Deviations

- T01 pulled lazy-export cleanup for `app.utils` and `app.integrations*` into scope because deep model imports were still bootstrapping runtime settings even after moving `Base`.
- T03 also touched `backend-hormonia/alembic/versions/lgpd03_add_ai_audit_event_types.py` after the first clean replay exposed an undocumented assumption about the legacy `audit_event_type` enum.

## Known Limitations

- The clean replay now reaches head, but the historical path still leaves `audit_logs.event_type` as `varchar`; canonical schema convergence remains a later-slice problem.
- S01 does not yet decide what Firebase-era data stays archival versus live in `users`, `audit_logs`, and `user_sync_log`; that boundary is still owned by S02.

## Follow-ups

- Use this operability harness in S02 while publishing the explicit Firebase historical boundary so archival decisions do not reintroduce runtime-coupled imports.
- Reuse the same scrubbed replay contract in S03 for both clean and existing/stamped databases to prove convergence on one honest head.

## Files Created/Modified

- `backend-hormonia/app/db/base.py` — declarative `Base` moved into a settings-free module.
- `backend-hormonia/app/db/migrations.py` — migration bootstrap/DB URL helpers with named failures.
- `backend-hormonia/alembic/env.py` — Alembic now uses the settings-free bootstrap path.
- `backend-hormonia/alembic/runtime_helpers.py` — migration-only timezone and schema-validation helpers.
- `backend-hormonia/alembic_runtime_helpers.py` — import shim that keeps helper ownership local without shadowing upstream Alembic.
- `backend-hormonia/alembic/versions/016_validate_patient_metadata.py` — removed runtime helper dependency.
- `backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py` — removed runtime helper dependency.
- `backend-hormonia/alembic/versions/019_seed_welcome_message_template.py` — removed runtime helper dependency.
- `backend-hormonia/alembic/versions/c9a6d2f7b3e1_ensure_message_templates_table.py` — removed runtime helper dependency.
- `backend-hormonia/alembic/versions/020_encrypt_cpf_lgpd.py` — runtime encryption import delayed until work exists.
- `backend-hormonia/alembic/versions/029_migrate_email_phone_to_encrypted.py` — runtime encryption import delayed until work exists.
- `backend-hormonia/alembic/versions/73a9d4d7cf05_align_patient_lgpd_encryption.py` — runtime encryption import delayed until work exists.
- `backend-hormonia/alembic/versions/lgpd03_add_ai_audit_event_types.py` — clean replay now guards missing legacy enum.
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — final operability pack for graph load, history, heads, upgrade, and current.
- `.gsd/milestones/M005/slices/S01/S01-UAT.md` — concrete replay/UAT script for the slice.

## Forward Intelligence

### What the next slice should know
- The cheapest trustworthy regression gate is `pytest -q tests/migrations/test_alembic_operability.py`; it already exercises scrubbed graph load, history/heads, clean upgrade, and current.
- If `TEST_DATABASE_URL` is missing in the shell, the same proof can be replayed with an explicit local URL; slice closeout used `postgresql://postgres:postgres@localhost:55432/hormonia_test`.

### What's fragile
- Operability is now green, but the clean historical path still carries non-canonical scars like `audit_logs.event_type` staying `varchar`; do not confuse operability with convergence.
- Any future historical revision that imports `app.utils`, `app.database`, `app.config`, or runtime services at module-import time can break graph traversal again.

### Authoritative diagnostics
- `backend-hormonia/tests/migrations/test_alembic_operability.py` — fastest source of truth because it names `db_url_resolution`, `graph-load`, `upgrade`, and `current` and masks DB credentials.
- `env -i ... alembic history|heads|upgrade head|current` — direct CLI proof that the migration control plane works outside the app runtime.

### What assumptions changed
- The clean replay path did not have the legacy `audit_event_type` enum available before `lgpd03_add_ai_audit_event_types`, so the migration had to guard that object instead of assuming prior creation.
- `history`/`heads` were blocked not only by `Base` placement but also by package `__init__` side effects; lazy package exports were necessary to make deep model imports safe.
