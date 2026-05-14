---
estimated_steps: 8
estimated_files: 5
skills_used: []
---

# T05: Run final all-seam proof and persist closure matrix

Why: M015 is not complete until the final entrypoint exercises all seams, generates/validates the matrix, preserves only redaction-safe evidence, and tears down cleanly.
Do:
1. Run the full static/regression gate for runner, matrix, S01-S04 seam contracts, and M014 regressions.
2. Run `./scripts/security/verify-m015-runtime-security.sh` with no seam filter to execute all seams and final matrix validation.
3. Fix any red signals discovered by the all-seam pass; do not document failures as green.
4. Confirm durable matrix JSON/MD and all seam evidence record passed/fixed/non-goal statuses.
5. Confirm no active M015 runtime containers or bound ports remain.
Done when: the full S05 gate exits 0 and durable matrix artifacts validate redaction-clean with all required rows present.

## Inputs

- `scripts/security/verify-m015-runtime-security.sh`
- `backend-hormonia/docs/reports/security/m015/*-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`

## Expected Output

- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md`
- `scripts/security/m015-runtime/evidence/`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && PYTHONPATH=backend-hormonia:scripts/security/m015-runtime pytest scripts/security/m015-runtime/tests/test_runner_contract.py backend-hormonia/tests/security/test_m015_runtime_harness.py backend-hormonia/tests/security/test_m015_final_matrix_contract.py backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py -q && ./scripts/security/verify-m015-runtime-security.sh && python3 scripts/security/m015-runtime/evidence_matrix.py --input-dir backend-hormonia/docs/reports/security/m015 --output-dir backend-hormonia/docs/reports/security/m015 --validate && (docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'm015-runtime|18080|15432' && exit 1 || true)

## Observability Impact

Produces final all-run output, matrix validator status, seam correlations, and clean teardown evidence for milestone validation.
