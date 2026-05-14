# S05: Unified Runner, Evidence Matrix, and Strict Closure Gate — UAT

**Milestone:** M015
**Written:** 2026-05-14T18:21:52.364Z

# UAT — M015/S05 Unified Runner, Evidence Matrix, and Strict Closure Gate

## Scenario
Run M015 with no seam filter and verify it executes all seams, validates the final evidence matrix, and tears down cleanly.

## Command
```bash
bash -n scripts/security/verify-m015-runtime-security.sh && \
docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && \
PYTHONPATH=backend-hormonia:scripts/security/m015-runtime pytest \
  scripts/security/m015-runtime/tests/test_runner_contract.py \
  backend-hormonia/tests/security/test_m015_runtime_harness.py \
  backend-hormonia/tests/security/test_m015_final_matrix_contract.py \
  backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py \
  backend-hormonia/tests/api/v2/test_private_upload_serving.py \
  backend-hormonia/tests/api/v2/test_report_ownership_closure.py \
  backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py \
  backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py -q && \
./scripts/security/verify-m015-runtime-security.sh && \
python3 scripts/security/m015-runtime/evidence_matrix.py \
  --input-dir backend-hormonia/docs/reports/security/m015 \
  --output-dir backend-hormonia/docs/reports/security/m015 \
  --validate && \
(docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'm015-runtime|18080|15432' && exit 1 || true)
```

## Expected Results
- 118 scoped tests pass.
- No-filter runner executes `db`, `session`, `provider`, and `artifact` in order.
- Parent correlation is `m015-20260514T181125Z-2167622` with child seam correlations suffixed by seam.
- Matrix generation/validation prints `M015 evidence matrix validated: backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`.
- Matrix JSON records `result: passed`, required runtime rows, R012/R013/R014/R015/R017/R018, classified warnings, validator `passed`, and explicit non-goals.
- Post-teardown check finds no active M015 runtime containers or `18080`/`15432` bound ports.

## Actual Result
Passed on the final run. All seams completed, matrix validation passed, and cleanup left no M015 runtime containers or bound ports.
