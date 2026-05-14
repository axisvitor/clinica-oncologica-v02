---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T05: Run artifact seam end to end and persist fresh evidence

Why: S04 is not complete until the root runner exercises the artifact seam through Docker, writes fresh redaction-validated evidence, keeps M014 regressions green, and tears down cleanly.

Do:
1. Wire the runner `artifact` branch to invoke the artifact probe service and collect evidence/summary paths.
2. Run the full layered gate: shell syntax, Compose config, M015 artifact/runtime contracts, M014 upload/report regressions, and `./scripts/security/verify-m015-runtime-security.sh --seam artifact`.
3. Fix any red signals instead of documenting them away as green.
4. Confirm post-teardown no active M015 runtime containers or M015 bound ports remain.
5. Record fresh artifact evidence and summary with correlation ID and explicit non-goals.

Done when: the full T05 command exits 0 and durable artifact evidence records passed, redaction validated, and teardown complete.

## Inputs

- ``scripts/security/verify-m015-runtime-security.sh``
- ``scripts/security/m015-runtime/docker-compose.yml``
- ``scripts/security/m015-runtime/artifact_seam.py``
- ``scripts/security/m015-runtime/redaction.py``
- ``backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py``
- ``backend-hormonia/tests/security/test_m015_runtime_harness.py``
- ``backend-hormonia/tests/api/v2/test_private_upload_serving.py``
- ``backend-hormonia/tests/api/v2/test_report_ownership_closure.py``
- ``backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py``
- ``backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py``

## Expected Output

- ``scripts/security/verify-m015-runtime-security.sh` — executable artifact seam branch and teardown/evidence integration.`
- ``backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json` — fresh runtime artifact seam evidence.`
- ``backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md` — fresh runtime artifact seam summary.`
- ``scripts/security/m015-runtime/evidence/` — sanitized per-run diagnostics.`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && PYTHONPATH=backend-hormonia:scripts/security/m015-runtime pytest scripts/security/m015-runtime/tests/test_runner_contract.py backend-hormonia/tests/security/test_m015_runtime_harness.py backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py -q && ./scripts/security/verify-m015-runtime-security.sh --seam artifact && (docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'm015-runtime|18080|15432' && exit 1 || true)

## Observability Impact

Verifies the final operational surfaces: runner phase logs, evidence/summary files, redaction status, teardown status, and post-teardown container/port cleanup.
