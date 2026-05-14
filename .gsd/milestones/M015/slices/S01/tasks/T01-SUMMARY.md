---
id: T01
parent: S01
milestone: M015
key_files:
  - .gitignore
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/postgres-init/001-roles.sh
  - scripts/security/m015-runtime/README.md
  - scripts/security/m015-runtime/tests/test_runner_contract.py
key_decisions:
  - Use ignored `.m015-runtime/` for generated env/certs/log scratch while keeping committed harness assets under `scripts/security/m015-runtime/`.
  - Fail closed for all non-`db` seams and for missing seam selection before setup/service startup.
  - Keep evidence sanitized and correlation-id/phase-scoped so future DB proof tasks can extend it without leaking DSNs, secrets, PHI, or provider data.
duration: 
verification_result: passed
completed_at: 2026-05-14T04:35:57.458Z
blocker_discovered: false
---

# T01: Added the fail-closed M015 DB runtime harness with isolated Compose services, generated TLS/env scratch, Postgres synthetic roles, sanitized diagnostics, and static contract tests.

**Added the fail-closed M015 DB runtime harness with isolated Compose services, generated TLS/env scratch, Postgres synthetic roles, sanitized diagnostics, and static contract tests.**

## What Happened

Created the root runner `scripts/security/verify-m015-runtime-security.sh` with strict shell mode, `--seam db`, `--help`, `--list-seams`, unknown/missing seam rejection before startup, configurable ports/project name, idempotent teardown, generated local-only env/certs under ignored `.m015-runtime/`, phase-stamped sanitized logging, and evidence hooks. Added the isolated M015 Compose stack with Postgres TLS, Dragonfly, API, worker, and db-probe services; it avoids `env_file`, production volumes, WuzAPI/live provider services, and backend `.env` reuse. Added the Postgres init script that creates non-superuser `hormonia_app` and `m015_rls_denied` roles from generated synthetic passwords. Added README usage/non-goals/failure-class documentation and a tracked contract test covering fail-closed CLI behavior plus static Compose/ignore invariants.

## Verification

Fresh verification after the final edits passed: shell syntax validation succeeded, Docker Compose rendered the M015 stack configuration successfully, the Python contract tests passed 6/6, and the prescribed combined gate (`bash -n ... && docker compose ... config --quiet`) exited 0. Full live `--seam db` startup, Alembic migration proof, and RLS allow/deny proof remain deferred to later S01 tasks per the slice/task boundaries.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh` | 0 | ✅ pass | 141ms |
| 2 | `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet` | 0 | ✅ pass | 814ms |
| 3 | `python3 scripts/security/m015-runtime/tests/test_runner_contract.py` | 0 | ✅ pass (6 tests) | 264ms |
| 4 | `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet` | 0 | ✅ pass | 761ms |

## Deviations

Added `scripts/security/m015-runtime/tests/test_runner_contract.py` beyond the expected output list to satisfy the task's test requirement. Full live DB seam startup was not run because the T01 verification contract is static shell/Compose validation; later S01 tasks own migration/RLS proof.

## Known Issues

None.

## Files Created/Modified

- `.gitignore`
- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/postgres-init/001-roles.sh`
- `scripts/security/m015-runtime/README.md`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`
