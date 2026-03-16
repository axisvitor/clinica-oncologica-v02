# S04: Publicar o closeout final e provar o sistema montado pós-purga — Research

**Date:** 2026-03-15

## Summary

S04 is a closeout slice. The structural purge work is done across S01–S03. What remains is fixing one isolated test blocker left by S02, replaying the full published verification surfaces on the post-purge state, and publishing a replayable M006 closeout artifact that proves the assembled system is honest.

The S02 recovery artifact left one known red edge: `tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error` fails under the real-Postgres `TEST_DATABASE_URL` harness because `caplog` does not capture the expected log record from `app.dependencies.auth_dependencies`. The 504 timeout behavior itself works — only the log observation assertion is broken. The root cause is likely that the test's `caplog.set_level(logging.ERROR, logger="app.dependencies.auth_dependencies")` does not propagate correctly when the Postgres harness provisions the test schema via `alembic upgrade head` during session setup, which triggers early imports that may reconfigure the module logger's handler chain. The fix is narrowly scoped: either adjust the test's caplog configuration to match the Postgres harness's logging state, or switch to a structurally equivalent assertion that does not depend on caplog propagation under that harness.

After that fix, the verification surface is entirely reuse of existing published runners: the S01 residue guard, the S02 focused backend packs, the S03 absence/build/typecheck scans, the M005 final-schema proof for `--fresh` and `--existing`, and the S03 frontend import-boundary tests. The closeout artifact should follow the M003-VERIFY.json model — a machine-readable JSON recording each proof phase's status, command, and result pointers.

## Recommendation

Execute S04 in three phases:

1. **Fix the S02 caplog blocker.** The test `test_get_current_user_from_session_db_timeout_logs_error` needs its log capture assertion made compatible with the Postgres harness. The simplest fix is to use `propagate=True` on the target logger in the test fixture or to capture at root level and filter by logger name. Do not change the production logging behavior — only the test's observation strategy. Rerun the full S02 plan verification list after the fix.

2. **Replay the full proof topology.** In order:
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` (S01 guard)
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` (S01 guard)
   - S02 focused backend packs (auth/session/profile/admin/schema convergence)
   - S03 absence scans (deleted files, `FIREBASE_SESSION_TTL_SECONDS`, `WHATSAPP_EVOLUTION_` in manifests, Firebase Admin in workflows)
   - Frontend import-boundary contract tests + typecheck + build
   - `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
   - `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`

3. **Publish the closeout artifact.** Write `.gsd/milestones/M006/M006-VERIFY.json` (following M003-VERIFY.json structure) recording each phase's command, status, and diagnostic pointer. Write M006-SUMMARY.md with requirement outcomes, milestone closeout, and forward guidance.

## Implementation Landscape

### Key Files

- `backend-hormonia/tests/api/v2/test_auth_timeout.py` — the S02 blocker. `test_get_current_user_from_session_db_timeout_logs_error` needs its caplog assertion fixed for the Postgres harness. The other 3 tests in this file pass fine.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — production code that emits the timeout log via `logger = logging.getLogger(__name__)` at module level (line 27). The `_get_user_from_db_by_user_id_async` function logs at WARNING (retry) and ERROR (final failure). No production changes needed.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — runtime residue guard. Reuse as-is for backend and frontend scopes.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — current residue contract. All backend auth/session categories already at `approved: []` with `proof_only` boundaries. No changes needed.
- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — final-schema proof runner. Already includes the S02 focused packs in its pytest replay phase. Reuse as-is for `--fresh` and `--existing`.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — mounted backend proof helper. Called internally by the final-schema runner. No changes needed.
- `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py` — mounted proof test suite. Exercises readiness, config, and live session flow against a real uvicorn. No changes needed.
- `backend-hormonia/tests/migrations/test_canonical_schema_head_convergence.py` — schema convergence proof. Head pinned to `m006_s02_t03_drop_users_firebase_residue`. No changes needed.
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — S03's absence guard for deleted frontend bridges. Reuse as-is.
- `.gsd/milestones/M003/M003-VERIFY.json` — model for the M006 closeout artifact structure.
- `.gsd/milestones/M006/slices/S02/S02-PLAN.md` — S02's full verification list that must be replayed green.

### Build Order

1. **Fix caplog blocker first.** This unblocks the entire S02 verification list and the final-schema proof runner (which includes the timeout test in its pytest replay phase).
2. **Run S02 verification list.** Confirms the schema drop and runtime republication are honest on the post-purge state.
3. **Run S01/S03 guards.** Confirms the residue boundary and absence scans still hold.
4. **Run final-schema proof `--fresh` and `--existing`.** This is the heaviest verification — it serializes canonical head preparation, focused pytest replay (which includes the timeout test), and mounted backend startup on the real schema.
5. **Publish closeout artifacts.** Write M006-VERIFY.json and M006-SUMMARY.md.

### Verification Approach

The slice verification is the milestone verification — it's a full replay of all published proof surfaces on the final state:

**Residue guards:**
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`

**S02 focused backend packs (must be green before final-schema runner):**
- `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_canonical_schema_head_convergence.py`

**S03 absence/build/typecheck:**
- `cd frontend-hormonia && npx vitest run tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- Absence scans: `session_service.py`, `auth_legacy_firebase.py`, `FIREBASE_SESSION_TTL_SECONDS` in app code, `WHATSAPP_EVOLUTION_` in manifests, `FIREBASE_ADMIN` in workflows

**Integrated final-schema replay (requires local Postgres on port 55432):**
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`

**Closeout artifact:**
- `.gsd/milestones/M006/M006-VERIFY.json` — machine-readable proof record
- `.gsd/milestones/M006/M006-SUMMARY.md` — milestone closeout

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Runtime residue drift | `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` + allowlist | Already distinguishes approved vs. proof-only vs. drift; M006 should replay it, not replace it |
| Schema + mounted backend proof | `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` | Already serializes `canonical_head -> pytest_replay -> mounted_backend -> live_auth_probe` with per-phase status |
| Frontend absence guard | `dead-compat-cleanup.contract.test.ts` | Already covers all 10 deleted bridge files plus 2 deleted directories |
| Closeout artifact model | `.gsd/milestones/M003/M003-VERIFY.json` | Already models phase-by-phase proof with commands and diagnostic pointers |

## Constraints

- The final-schema proof runner requires a local Postgres instance on port 55432 with database `hormonia_test`. This is the same requirement as M005/S04 — the runner handles schema reset internally.
- The mounted backend proof (called from the final-schema runner) starts a real uvicorn on port 8000. That port must be free.
- The S02 caplog fix must not change production logging behavior — only the test's observation mechanism.
- `FIREBASE_ADMIN_*` env vars intentionally remain in `.env.example` and production templates because `firebase_user_sync_service.py` still consumes them. S04 should not treat their presence as residue.
- The `/session/*` tombstone in `auth_session.py` is intentionally preserved as an explicit retirement contract, not dead code.

## Common Pitfalls

- **Widening the caplog fix into a logging refactor** — the fix is narrowly scoped to making one test's log observation work under Postgres. Do not restructure production logging or add new observability just to make the test pass.
- **Treating the closeout as a new round of cleanup** — S04 publishes proof of the post-purge state. If a new issue surfaces during replay, document it as a known limitation rather than expanding scope.
- **Running final-schema proof before the caplog fix** — the pytest replay phase inside `run-final-schema-proof.sh` includes `test_auth_timeout.py`, so it will fail until the blocker is resolved.

## Open Risks

- If the Postgres instance is unavailable or the `hormonia_test` database has stale state from prior runs, the final-schema proof may fail for infrastructure reasons rather than code issues. The runner handles schema reset, but port conflicts or stale Alembic stamps can still create noise.
- The mounted backend proof seeds a proof admin user and runs live HTTP assertions. If the seed/bootstrap helper has drift from S02/S03 changes, it may need minor adjustment.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — install with `npx skills add wshobson/agents@fastapi-templates` |
| Alembic / SQLAlchemy | `wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` | available — install with `npx skills add wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` |

## Sources

- S02 recovery summary identifies `test_get_current_user_from_session_db_timeout_logs_error` under `TEST_DATABASE_URL` as the single remaining blocker, with the 504 behavior itself still working. (source: `.gsd/milestones/M006/slices/S02/S02-SUMMARY.md`)
- S03 summary confirms all deleted surfaces absent, residue guard green, build/typecheck green, and `FIREBASE_ADMIN_*` intentionally retained in env templates. (source: `.gsd/milestones/M006/slices/S03/S03-SUMMARY.md`)
- M003-VERIFY.json provides the structural model for the M006 closeout artifact. (source: `.gsd/milestones/M003/M003-VERIFY.json`)
- The final-schema proof runner includes `test_auth_timeout.py` in its pytest replay phase. (source: `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`, lines 200–211)
- The module-level logger in `auth_dependencies.py` uses `logging.getLogger(__name__)` at line 27 and emits the timeout diagnostic at ERROR level from `_get_user_from_db_by_user_id_async`. (source: `backend-hormonia/app/dependencies/auth_dependencies.py`)
- The conftest's Postgres path provisions via `alembic upgrade head` at session scope, which may trigger early imports affecting logger state before individual test caplog captures. (source: `backend-hormonia/tests/conftest.py`, lines 1008–1027)
