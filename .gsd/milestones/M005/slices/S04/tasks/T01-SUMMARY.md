---
id: T01
parent: S04
milestone: M005
provides:
  - Serial final-schema proof runner covering fresh and existing histories, focused pytest replay, and mounted backend-only live auth/runtime verification on the canonical head.
key_files:
  - .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh
  - .gsd/milestones/M004/slices/S06/run-mounted-proof.sh
  - backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py
  - .gsd/milestones/M005/slices/S04/S04-UAT.md
key_decisions:
  - Reused the published S06 mounted-proof contract by adding a backend-only proof mode instead of building a second independent uvicorn runner.
  - Kept the S04 runner as a thin serial orchestrator with a DB lock, canonical-history prep, shared pytest replay, and mounted-backend proof phases on one status surface.
patterns_established:
  - Publish layered runtime proof as canonical_head -> pytest_replay -> mounted_backend/live_auth_probe with explicit per-phase logs and status.json pointers.
  - Keep mounted runtime tests fixture-free when they target live uvicorn so pytest import side effects do not reprovision the shared database.
observability_surfaces:
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/status.json
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/canonical-head.json
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/pytest-replay.log
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend/backend.log
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend/live-auth-probe.log
duration: ~2h
verification_result: passed
completed_at: 2026-03-15T13:39:23-03:00
blocker_discovered: false
---

# T01: Publicar o runner serial de prova final-schema e mounted backend

**Published a single S04 replay runner that prepares the canonical history, replays the post-M004 backend packs, then proves real uvicorn startup and cookie-session auth against the final schema for both `fresh` and `existing` histories.**

## What Happened

I fixed the flagged observability gap first by extending `.gsd/milestones/M005/slices/S04/S04-PLAN.md` with an explicit status-surface verification step, so the slice no longer relies only on green exits.

From there I implemented `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` as the S04 orchestrator. The runner now acquires a serial lock at `/tmp/gsd-m005-s04-final-schema-proof/serial.lock`, prepares the selected canonical history (`base -> head` for `--fresh`, `m005_s02_t01_publish_firebase_history_boundary -> head` for `--existing`) by reusing the oracle helpers from `tests/migrations/test_canonical_schema_head_convergence.py`, writes a `canonical-head.json` fingerprint artifact, replays the three focused post-M004 packs via `TEST_DATABASE_URL`, and then hands the same database to the mounted backend proof.

To avoid inventing a second mounted contract, I extended `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` with a backend-only `--backend-proof` mode. That path starts only uvicorn with Firebase blank and WuzAPI mock enabled, explicitly unsets `TESTING`/`PYTEST_CURRENT_TEST`, reseeds the masked proof user against the live database, and runs a new live runtime probe in `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py`. The runtime proof is intentionally thin and fixture-free: it asserts `runtime_ready`, `runtime_config`, and `live_session_flow` against real HTTP surfaces (`/health/ready`, `/api/v2/system/config`, `login -> verify-session -> /users/me -> logout -> verify-session(401)`) without letting pytest’s shared DB harness mutate the live server state.

I also published `.gsd/milestones/M005/slices/S04/S04-UAT.md` with the replay contract, artifact locations, and the explicit “serial only” database restriction.

One real bug surfaced during verification: the first `--fresh` run failed immediately because the new S04 runner rooted itself at `.gsd/` instead of the repo root, so it looked for `backend-hormonia/.venv` in the wrong place. I fixed the root path and reran the published command successfully for both histories.

## Verification

- `chmod +x .gsd/milestones/M004/slices/S06/run-mounted-proof.sh .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh .gsd/milestones/M004/slices/S06/seed-proof-user.py && bash -n .gsd/milestones/M004/slices/S06/run-mounted-proof.sh && bash -n .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — **PASS**
- `cd backend-hormonia && .venv/bin/python -m py_compile tests/runtime/test_mounted_final_schema_proof.py ../.gsd/milestones/M004/slices/S06/seed-proof-user.py` — **PASS**
- `cd backend-hormonia && .venv/bin/python -m pytest -q tests/runtime/test_mounted_final_schema_proof.py` — **PASS** (expected skips without `MOUNTED_PROOF_*` env)
- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' .venv/bin/python -m pytest -q tests/migrations/test_canonical_schema_head_convergence.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py` — **PASS**
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh` — **PASS**
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing` — **PASS**
- `python3 - <<'PY' ...` status-surface verifier over `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/status.json` — **PASS** (`s04 status surfaces verified`)

## Diagnostics

- S04 runner status: `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/status.json`
- Canonical history artifact: `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/canonical-head.json`
- Focused pytest replay log: `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/pytest-replay.log`
- Mounted helper stdout/stderr: `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend.log`
- Live backend log: `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend/backend.log`
- Live auth/runtime probe log: `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend/live-auth-probe.log`
- Masked proof-user artifact: `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/proof.env`

Failures are now explicit on both axes the task required: the top-level runner publishes `history` + `phase` (`canonical_head`, `pytest_replay`, `mounted_backend`, `live_auth_probe`), and the mounted proof keeps separate backend/probe logs without persisting plaintext credentials or reset tokens.

## Deviations

- Instead of teaching the S04 runner to manage uvicorn directly, I extended the existing S06 mounted helper with a backend-only `--backend-proof` mode and kept S04 as the serial orchestrator above it. This stayed within the task contract (“reutilizar ou estender minimamente”) and avoided splitting the no-Firebase mounted contract into two separate launchers.

## Known Issues

- None.

## Files Created/Modified

- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — new serial S04 orchestrator for canonical history prep, focused pytest replay, and mounted backend-only proof.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — added backend-only mounted proof mode, explicit live probe log path, and mounted-runtime startup that unsets test-mode env.
- `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py` — new live uvicorn proof for readiness, public config, and cookie-session auth flow.
- `.gsd/milestones/M005/slices/S04/S04-UAT.md` — published replay/UAT contract with commands, artifacts, and serial DB restriction.
- `.gsd/milestones/M005/slices/S04/S04-PLAN.md` — added explicit status-surface verification step and marked T01 complete.
- `.gsd/STATE.md` — updated next action so state no longer points at this completed task.
