---
id: S04
parent: M005
milestone: M005
provides:
  - Replayable final-schema proof that prepares fresh and existing database histories, replays the critical post-M004 backend packs on the canonical S03 head, and mounts a real uvicorn backend on that same schema for live readiness/config/session verification.
requires:
  - slice: S01
    provides: Alembic control-plane commands and upgrade replay work with database-only configuration.
  - slice: S02
    provides: Firebase-era sync/audit residue is isolated behind an explicit historical boundary.
  - slice: S03
    provides: Fresh and upgraded databases converge on the canonical head `m005_s03_t02_align_audit_history_head`.
affects:
  - M006
key_files:
  - .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh
  - .gsd/milestones/M004/slices/S06/run-mounted-proof.sh
  - backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py
  - .gsd/milestones/M005/slices/S04/S04-UAT.md
key_decisions:
  - Reuse the published S06 mounted-proof contract in a backend-only mode instead of building a second uvicorn launcher for S04.
  - Keep S04 as a thin serial orchestrator over one shared database with explicit phases `canonical_head -> pytest_replay -> mounted_backend -> live_auth_probe` and persisted status/log pointers.
patterns_established:
  - Publish layered final-assembly proof as canonical history prep, focused pytest replay, and live mounted backend probe on the same `DATABASE_URL`.
  - Keep live-uvicorn runtime tests fixture-free when they target an already-mounted backend so pytest import/setup side effects do not reprovision the shared schema.
observability_surfaces:
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/status.json
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/canonical-head.json
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/pytest-replay.log
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend/backend.log
  - /tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend/live-auth-probe.log
drill_down_paths:
  - .gsd/milestones/M005/slices/S04/tasks/T01-SUMMARY.md
duration: ~2h
verification_result: passed
completed_at: 2026-03-15T13:55:14-03:00
---

# S04: Prova integrada de upgrade e backend no schema final

**Closed M005 with one replayable runner that proves both canonical upgrade histories, replays the post-M004 critical backend packs on the final schema, and mounts a real backend on that same head for live readiness/config/session checks.**

## What Happened

S04 closed the last open risk in M005: not whether the schema could converge in theory, but whether the real backend still booted and behaved correctly on that converged head.

The slice reused the S03 convergence oracle and the published S06 mounted-proof contract instead of inventing a new runtime path. `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` now acquires a serial lock, prepares either `base -> head` (`--fresh`) or `m005_s02_t01_publish_firebase_history_boundary -> head` (`--existing`), writes a canonical fingerprint artifact, replays the three focused post-M004 packs through `TEST_DATABASE_URL`, then hands the same database to a backend-only mounted proof.

To keep the mounted contract truthful, `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` gained a backend-only mode instead of spawning a second independent launcher. That path boots uvicorn with Firebase blank, WuzAPI mock enabled, and test-mode env removed, reseeds the masked proof user on the live database, and runs `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py` against real HTTP surfaces. The live probe asserts `runtime_ready`, `runtime_config`, and `live_session_flow` across `/health/ready`, `/api/v2/system/config`, `login`, `verify-session`, `/users/me`, `logout`, and the expected post-logout `401`.

The closeout reran the full slice verifier pack. Both `--fresh` and `--existing` completed with `status=passed` and `phase=live_auth_probe`, and the published status/log surfaces under `/tmp/gsd-m005-s04-final-schema-proof` remained truthful.

## Verification

Passed the full slice verifier pack from `S04-PLAN.md`:

- `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' .venv/bin/python -m pytest -q tests/migrations/test_canonical_schema_head_convergence.py tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`
- `python3 - <<'PY' ...` status-surface verifier over `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/status.json`

All passed in this closeout run.

## Requirements Advanced

- R051 — S04 rechecked the validated canonical head under a real mounted backend entrypoint instead of leaving it as migration-only proof.

## Requirements Validated

- R053 — The converged post-M004/M005 state is now proven by an integrated final-schema runner that exercises both upgrade histories and a real backend on the consolidated head, not just static cleanup or TestClient-level proof.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

Instead of teaching the S04 runner to manage uvicorn directly, the slice extended the existing S06 mounted helper with a backend-only `--backend-proof` mode and kept S04 as the serial orchestrator above it.

## Known Limitations

The proof is intentionally serial when it shares one `TEST_DATABASE_URL`; concurrent runs against the same Postgres database remain a false-failure risk. Frontend/browser smoke is not re-executed here because S04’s unresolved risk was truthful backend startup on the final schema, not broader assembled-stack routing already covered in M004/S06.

## Follow-ups

- Use the S04 runner as the regression baseline while M006 removes remaining dead-code and compatibility residue.
- Keep future migration-adjacent runtime proof on the Alembic-provisioned shared Postgres path rather than falling back to ORM DDL.

## Files Created/Modified

- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — serial final-schema orchestrator for canonical history prep, focused pytest replay, and mounted backend proof.
- `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` — backend-only mounted proof mode reused by S04.
- `backend-hormonia/tests/runtime/test_mounted_final_schema_proof.py` — live uvicorn probe for readiness, public config, and cookie-session auth flow.
- `.gsd/milestones/M005/slices/S04/S04-SUMMARY.md` — compressed slice closeout.
- `.gsd/milestones/M005/slices/S04/S04-UAT.md` — concrete replay/UAT script for the final-schema proof.
- `.gsd/REQUIREMENTS.md` — updated R053 traceability to reflect S04 as the validating slice.
- `.gsd/DECISIONS.md` — appended the mounted-proof reuse and serial proof-topology decisions.
- `.gsd/PROJECT.md` — refreshed project current state after M005 closeout.
- `.gsd/STATE.md` — advanced state to M006 planning.
- `.gsd/milestones/M005/M005-ROADMAP.md` — marked S04 complete.

## Forward Intelligence

### What the next slice should know
- The trustworthy assembled proof path for the final schema is now `run-final-schema-proof.sh --fresh|--existing`; if that runner is green, migrations, critical auth loops, and mounted backend startup agree on one canonical head.
- The mounted backend probe intentionally avoids shared pytest fixtures. Reintroducing fixture-based DB setup into that live path will make the proof lie.

### What's fragile
- Shared `TEST_DATABASE_URL` concurrency — parallel runs can still reset `public` underneath another verifier and create false negatives.
- Port `8000` ownership — the mounted helper assumes it can bind a real backend there and will fail loudly if another process is already listening.

### Authoritative diagnostics
- `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/status.json` — fastest truth for history, phase, pass/fail state, and log pointers.
- `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend/backend.log` — fastest truth for real uvicorn startup/readiness failures.
- `/tmp/gsd-m005-s04-final-schema-proof/{fresh,existing}/mounted-backend/live-auth-probe.log` — fastest truth for public config or cookie-session flow regressions.

### What assumptions changed
- “S03 convergence proof is enough to close M005” — it was not; the missing risk was real backend startup and auth behavior on that converged head, which S04 now proves directly.
