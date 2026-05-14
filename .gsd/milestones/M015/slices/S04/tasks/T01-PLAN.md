---
estimated_steps: 8
estimated_files: 5
skills_used: []
---

# T01: Register artifact seam and static runtime contract

Why: S04 needs to become a first-class runner seam before runtime probes can be trusted; the contract must prevent false green results and define the synthetic fixture/evidence schema up front.

Do:
1. Add `artifact` to runner seam listing/help/validation without weakening omitted/unknown seam fail-closed behavior.
2. Add artifact evidence paths and an artifact probe service in Compose, isolated from project `.env`, production volumes, live providers, and accidental private-root public mounts.
3. Add/update static tests so `artifact` is listed, a genuinely bogus seam still fails closed, Compose has the artifact probe, and evidence paths are repo-local/sanitized.
4. Define the artifact evidence schema and redaction denylist expectations before any runtime proof writes artifacts.
5. Document `--seam artifact` usage and non-goals in the M015 runtime README.

Done when: static runner/Compose contracts pass and `artifact` cannot be reported green without an implemented probe.

## Inputs

- ``.gsd/milestones/M015/slices/S01/S01-SUMMARY.md``
- ``.gsd/milestones/M015/slices/S02/S02-SUMMARY.md``
- ``.gsd/milestones/M015/slices/S03/S03-SUMMARY.md``
- ``scripts/security/verify-m015-runtime-security.sh``
- ``scripts/security/m015-runtime/docker-compose.yml``
- ``scripts/security/m015-runtime/redaction.py``
- ``backend-hormonia/tests/security/test_m015_runtime_harness.py``
- ``scripts/security/m015-runtime/tests/test_runner_contract.py``

## Expected Output

- ``scripts/security/verify-m015-runtime-security.sh` — artifact seam registration, evidence paths, and fail-closed validation updates.`
- ``scripts/security/m015-runtime/docker-compose.yml` — artifact probe service/profile and safe mounts.`
- ``scripts/security/m015-runtime/README.md` — artifact seam usage and non-goals.`
- ``backend-hormonia/tests/security/test_m015_runtime_harness.py` — backend static harness assertions for artifact seam.`
- ``scripts/security/m015-runtime/tests/test_runner_contract.py` — root runner contract updates for artifact seam and bogus seam denial.`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh && ./scripts/security/verify-m015-runtime-security.sh --list-seams && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q

## Observability Impact

Adds artifact seam phase names, evidence destinations, failure classes, and static guardrails so later runtime failures localize to setup/compose/readiness/probe/evidence/redaction/teardown.
