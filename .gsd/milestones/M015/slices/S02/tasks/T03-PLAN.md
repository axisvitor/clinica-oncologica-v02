---
estimated_steps: 14
estimated_files: 5
skills_used: []
---

# T03: Wire the session seam runner, Compose service, and explicit Taskiq task module

Why: S01 proves worker liveness only. S02 must expose a `session` seam, mount a harness-only Taskiq module, and force the worker to import it so queue proof crosses the real broker/worker boundary.

Expected executor skills_used frontmatter: `tdd`, `observability`, `verify-before-complete`.
Estimated scope: about 8 steps / 5 files.

Do:
1. Update `verify-m015-runtime-security.sh` help/list/validation so `db` and `session` are implemented; omitted/unknown seams still fail before setup.
2. Refactor runner dispatch so common setup/teardown/readiness can run `run_db_probe` or `run_session_probe`, with stable session evidence paths.
3. Extend `sanitize_stream` to redact `Cookie:` and `Set-Cookie:` headers.
4. Add `scripts/security/m015-runtime/m015_session_security_taskiq.py`, registered on `app.taskiq_broker.broker`, that receives synthetic session IDs only through the queue, optionally waits on a Dragonfly gate key, re-reads PostgreSQL session state at execution time, and returns sanitized `allowed/reason/session_id_hash/checked_at/worker_boundary` fields.
5. Update `docker-compose.yml`: mount the task module into `/app/app/tasks/m015_session_security_taskiq.py` for `worker` and `session-probe`, change worker command to explicitly import `app.tasks.m015_session_security_taskiq`, and add `session-probe` with synthetic env/redaction/evidence mounts.
6. Update `test_m015_runtime_harness.py` and `scripts/security/m015-runtime/tests/test_runner_contract.py` for session seam listing, evidence paths, `session-probe`, explicit worker module import, cookie redaction, and continued absence of live WuzAPI/Gemini/project `.env` wiring.
7. Do not add tests that inspect `.gsd/`, `.planning/`, `.audits/`, or generated `.m015-runtime/` scratch.

Failure Modes (Q5): unknown seam -> non-zero before setup; task import failure -> worker/probe failure; broker unavailable -> probe failure; teardown failure -> evidence teardown status records sanitized failure; malformed Compose -> config/static test failure.
Load Profile (Q6): one worker, one Taskiq queue, one Redis result backend, one probe; at 10x parallel runs Docker resources/project/port/queue isolation break first.
Negative Tests (Q7): provider seam rejected, session seam listed, cookie headers sanitized, worker command requires explicit module, provider service names remain absent, and paths remain repo-relative.

## Inputs

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/redaction.py`
- `backend-hormonia/app/taskiq_broker.py`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`

## Expected Output

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/m015_session_security_taskiq.py`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py -q && cd .. && python scripts/security/m015-runtime/tests/test_runner_contract.py

## Observability Impact

Extends runner/Compose diagnostics so session probe, worker import, broker dispatch, and teardown failures surface with correlation IDs and sanitized logs.
