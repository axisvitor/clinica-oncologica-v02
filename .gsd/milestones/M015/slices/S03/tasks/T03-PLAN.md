---
estimated_steps: 8
estimated_files: 5
skills_used: []
---

# T03: Wire the provider seam into the runner, Compose stack, and static contracts

Why: The runner currently implements only `db` and `session`; provider proof must be a fail-closed first-class seam with Compose services and static contracts before any runtime claim is made.

Steps:
1. Extend `verify-m015-runtime-security.sh` with `provider` evidence paths, seam listing, CLI validation, sanitized setup/env generation, and teardown evidence updates.
2. Add provider-stub and provider-probe services to the M015 Compose file; configure the API and worker to use local WuzAPI/Gemini stub URLs and synthetic provider tokens/keys only.
3. Mount provider stub/probe/task files explicitly and keep worker task imports explicit rather than relying on broad Taskiq discovery.
4. Extend backend and root runner-contract tests for seam listing, fail-closed unknown seam behavior, Compose isolation/no live provider service, provider stub/probe mounts, sanitized Cookie/Authorization handling, and provider evidence paths.
5. Ensure `docker compose config --quiet` remains green and does not depend on project `.env` values.

Done when the provider seam is statically wired and listed, but runtime provider proof can still be implemented in T04/T05.

## Inputs

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`
- `.gsd/milestones/M015/slices/S02/S02-SUMMARY.md`

## Expected Output

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py -q && cd .. && PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_runner_contract.py -q

## Observability Impact

Adds provider seam phase routing, evidence path registration, and sanitized runner diagnostics for provider-specific setup and teardown failures.
