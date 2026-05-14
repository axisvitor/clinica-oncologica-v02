---
id: T03
parent: S02
milestone: M015
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/m015_session_security_taskiq.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/m015-runtime/tests/test_runner_contract.py
  - tests/api/v2/test_auth.py
key_decisions:
  - The M015 session seam is now an implemented runner seam alongside DB while all other seams continue to fail closed before setup.
  - The session Taskiq worker proof returns only sanitized outcome fields and hashes; PostgreSQL session rows remain the hard authorization source.
  - Root-level verification shims load backend pytest plugins instead of duplicating backend fixture logic.
duration: 
verification_result: passed
completed_at: 2026-05-14T08:55:03.666Z
blocker_discovered: false
---

# T03: Wired the M015 session seam runner path, harness-only Taskiq session task, Compose worker/probe mounts, and root verification shim so session contracts and auth regression gates pass.

**Wired the M015 session seam runner path, harness-only Taskiq session task, Compose worker/probe mounts, and root verification shim so session contracts and auth regression gates pass.**

## What Happened

Implemented the session seam as an implemented runner target alongside the existing DB seam. The runner now lists/accepts `session`, keeps omitted/unknown seams fail-closed before setup, routes common setup/readiness into either `run_db_probe` or `run_session_probe`, records session evidence paths, updates teardown status for DB or session artifacts, and sanitizes Cookie/Set-Cookie headers in subprocess logs. Added `scripts/security/m015-runtime/m015_session_security_taskiq.py`, a harness-only Taskiq module registered on `app.taskiq_broker.broker`; it accepts synthetic session IDs via the queue, can wait on a Dragonfly gate key, re-reads PostgreSQL session state at execution time, and returns sanitized allowed/reason/hash/timestamp/worker-boundary fields. Extended Compose so the worker explicitly imports `app.tasks.m015_session_security_taskiq`, mounts the harness module into the worker and session probe, and defines a `session-probe` tool service with synthetic env/evidence mounts and no live provider/project `.env` wiring. Updated static harness tests for session seam listing, session-probe/worker import contracts, evidence mounts, and cookie redaction. Added a root `tests/api/v2/test_auth.py` shim that loads the canonical backend auth tests plus backend pytest fixtures so the automated root-level gate no longer fails due a missing path or missing fixtures.

## Verification

Ran the final timeout-recovery verification command covering shell syntax, Compose config, Python compilation for the new module/shim, backend static harness tests, runner contract tests, and the previously failing root-level S02 gate. All checks passed: the final combined command exited 0; the task static harness suite reported 23 passing checks, and the S02 auth/session gate reported 99 passed with warnings only.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && python -m py_compile scripts/security/m015-runtime/m015_session_security_taskiq.py tests/api/v2/test_auth.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py -q && cd .. && python scripts/security/m015-runtime/tests/test_runner_contract.py && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/api/v2/test_auth.py -q` | 0 | ✅ pass | 42837ms |
| 2 | `PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/api/v2/test_auth.py -q` | 0 | ✅ pass (99 passed, warnings only) | 21480ms |
| 3 | `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && python -m py_compile scripts/security/m015-runtime/m015_session_security_taskiq.py tests/api/v2/test_auth.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py -q && cd .. && python scripts/security/m015-runtime/tests/test_runner_contract.py` | 0 | ✅ pass (23 static harness/contract checks) | 21413ms |

## Deviations

Added `tests/api/v2/test_auth.py` as a root-path shim to satisfy the automated verification gate, because the gate referenced the root path while the canonical auth test lives under `backend-hormonia/tests/api/v2/test_auth.py`.

## Known Issues

Full Docker runtime execution of `./scripts/security/verify-m015-runtime-security.sh --seam session` was not run in this timeout-recovery pass; the task-specified static/contract verification and the previously failing S02 gate both pass.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/m015_session_security_taskiq.py`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`
- `tests/api/v2/test_auth.py`
