---
id: T01
parent: S04
milestone: M015
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/m015-runtime/README.md
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/m015-runtime/tests/test_runner_contract.py
key_decisions:
  - Register `artifact` as a first-class seam now, but keep `run_artifact_probe` fail-closed with `artifact-probe-not-implemented` until the runtime probe/evidence are implemented in later S04 tasks.
  - Use a profile-scoped `artifact-probe` Compose service that consumes the existing FastAPI/PostgreSQL/Dragonfly/worker substrate and writes to the same repo-local M015 evidence mount.
  - Update runner and static contracts to use a bogus `not-a-seam` value for unknown-seam checks now that `artifact` is registered.
duration: 
verification_result: passed
completed_at: 2026-05-14T16:28:28.955Z
blocker_discovered: false
---

# T01: Registered the M015 `artifact` seam and static Compose/runner contracts while keeping runtime execution fail-closed until the artifact probe is implemented.

**Registered the M015 `artifact` seam and static Compose/runner contracts while keeping runtime execution fail-closed until the artifact probe is implemented.**

## What Happened

Registered `artifact` in the M015 runner help, seam list, parser, evidence path setup, teardown result dispatch, and selected-seam switch. The runtime branch currently calls `run_artifact_probe`, which intentionally fails with `artifact-probe-not-implemented` so the seam cannot report green until T02-T05 implement and run the proof. Added an `artifact-probe` service to the tools profile in Docker Compose with the existing backend build, synthetic runtime environment, M015 evidence mount, redaction helper mount, and session helper mount. Rewrote the M015 runtime README so it reflects DB/session/provider as completed seams and artifact as an S04 registered-but-not-yet-green seam with planned proof scope and non-goals. Updated backend and root static contract tests so `--list-seams` expects `db`, `session`, `provider`, `artifact`, unknown seam checks use `not-a-seam`, Compose assertions include `artifact-probe`, and runner assertions include artifact evidence paths and fail-closed stub behavior.

## Verification

Fresh T01 verification passed after the last edit: `bash -n scripts/security/verify-m015-runtime-security.sh && ./scripts/security/verify-m015-runtime-security.sh --list-seams && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q`. The seam list printed `db`, `session`, `provider`, `artifact`, Docker Compose config exited 0, and pytest reported `......................................... [100%]` for 41 static contract tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh && ./scripts/security/verify-m015-runtime-security.sh --list-seams && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q` | 0 | ✅ pass — seams listed db/session/provider/artifact, Compose config passed, and 41 static contract tests reached 100% | 25300ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/README.md`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`
