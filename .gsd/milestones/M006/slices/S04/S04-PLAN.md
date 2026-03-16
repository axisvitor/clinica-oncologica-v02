# S04: Publicar o closeout final e provar o sistema montado pós-purga

**Goal:** Close M006 and validate R052 by fixing the last S02 blocker, replaying the full published proof topology on the post-purge state, and publishing a replayable closeout artifact.
**Demo:** `M006-VERIFY.json` exists with all phases green, and the published commands can be replayed to re-prove absence, schema convergence, and mounted stack health on the canonical post-purge head.

## Must-Haves

- The S02 caplog blocker (`test_get_current_user_from_session_db_timeout_logs_error` under `TEST_DATABASE_URL`) is fixed without changing production logging behavior.
- The full S02 verification list passes end to end.
- S01 residue guards (backend + frontend), S03 absence/build/typecheck scans, frontend import-boundary contract tests, and the final-schema proof (`--fresh` and `--existing`) all pass on the post-purge state.
- `.gsd/milestones/M006/M006-VERIFY.json` records each proof phase with command, status, and diagnostic pointer.
- `.gsd/milestones/M006/M006-SUMMARY.md` closes the milestone with requirement outcomes and forward guidance.
- R052 moves to validated in `REQUIREMENTS.md`.

## Proof Level

- This slice proves: final-assembly
- Real runtime required: yes (Postgres on port 55432, uvicorn on port 8000)
- Human/UAT required: no

## Verification

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error -vv`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_canonical_schema_head_convergence.py`
- `cd frontend-hormonia && npx vitest run tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`
- `python3 -c "import json; v=json.load(open('.gsd/milestones/M006/M006-VERIFY.json')); assert all(p.get('status')=='passed' for p in v['phases'].values()), 'not all phases passed'"`

## Observability / Diagnostics

- Runtime signals: per-phase status in `/tmp/gsd-m005-s04-final-schema-proof/*/status.json`; S01 residue guard `--report` output.
- Inspection surfaces: `M006-VERIFY.json` is the single top-level proof record; each phase entry has a `command` and `diagnostic` pointer.
- Failure visibility: each phase in M006-VERIFY.json records `status`, `command`, and a `diagnostic` path to log/output for localized inspection.
- Redaction constraints: none (no secrets in proof artifacts).

## Integration Closure

- Upstream surfaces consumed: S01 residue guard + allowlist, S02 focused backend packs + schema head, S03 absence scans + build/typecheck + frontend import-boundary contract, M005/S04 final-schema proof runner, M004/S06 mounted proof helper.
- New wiring introduced in this slice: none (reuse of all published runners).
- What remains before the milestone is truly usable end-to-end: nothing — S04 is the final slice.

## Tasks

- [x] **T01: Fix the S02 caplog blocker and confirm the full S02 verification list** `est:30m`
  - Why: The test `test_get_current_user_from_session_db_timeout_logs_error` fails under Postgres because `caplog` doesn't capture the expected log when the conftest provisions the schema via `alembic upgrade head` at session scope, which may reconfigure the module logger's handler/propagation chain. This blocks honest S02 closeout and the final-schema runner's pytest replay phase.
  - Files: `backend-hormonia/tests/api/v2/test_auth_timeout.py`
  - Do: Reproduce the failure under `TEST_DATABASE_URL`. Diagnose why caplog doesn't see the log (likely `propagate=False` or handler attachment during early Alembic imports). Fix the test's log capture — either set `propagate=True` on the target logger in the test, capture at root level and filter by logger name, or use `logging_plugin` instead of `caplog.set_level`. Do NOT change production logging in `auth_dependencies.py`. Rerun the full S02 verification list from the S02-PLAN to confirm everything passes.
  - Verify: `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/api/v2/test_auth_timeout.py -vv` — all 4 tests pass. Then the full S02 focused packs from S02-PLAN.md verification section.
  - Done when: All 4 auth_timeout tests pass under both default (SQLite) and Postgres harnesses, and the full S02 verification list is green.

- [ ] **T02: Replay the full proof topology and publish M006 closeout artifacts** `est:45m`
  - Why: S04's deliverable is a replayable closeout that combines all proof surfaces on the post-purge state. This task runs every published runner and records the results into a machine-readable M006-VERIFY.json and a human-readable M006-SUMMARY.md.
  - Files: `.gsd/milestones/M006/M006-VERIFY.json`, `.gsd/milestones/M006/M006-SUMMARY.md`, `.gsd/REQUIREMENTS.md`, `.gsd/STATE.md`, `.gsd/milestones/M006/M006-ROADMAP.md`
  - Do: Run proof phases in order: (1) S01 residue guards backend+frontend, (2) S02 focused backend packs under default harness, (3) S02 schema convergence under Postgres, (4) S03 absence scans for deleted files + env vars + manifests + workflows, (5) frontend import-boundary contract tests + typecheck + build, (6) final-schema proof `--fresh`, (7) final-schema proof `--existing`. Record each phase's command, status, and diagnostic pointer into M006-VERIFY.json following M003-VERIFY.json structure. Write M006-SUMMARY.md with milestone closeout. Move R052 to validated in REQUIREMENTS.md. Mark S04 complete in M006-ROADMAP.md. Update STATE.md.
  - Verify: `python3 -c "import json; v=json.load(open('.gsd/milestones/M006/M006-VERIFY.json')); assert all(p.get('status')=='passed' for p in v['phases'].values())"` and M006-SUMMARY.md exists with verification_result: passed.
  - Done when: M006-VERIFY.json has all phases green, M006-SUMMARY.md is published, R052 is validated in REQUIREMENTS.md, and STATE.md reflects M006 complete.

## Files Likely Touched

- `backend-hormonia/tests/api/v2/test_auth_timeout.py`
- `.gsd/milestones/M006/M006-VERIFY.json`
- `.gsd/milestones/M006/M006-SUMMARY.md`
- `.gsd/milestones/M006/M006-ROADMAP.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/STATE.md`
