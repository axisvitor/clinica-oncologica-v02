# S04: Private Artifact App-Route Runtime Proof — UAT

**Milestone:** M015
**Written:** 2026-05-14T17:34:00.235Z

# UAT — M015/S04 Private Artifact App-Route Runtime Proof

## Scenario
Run the artifact seam against the synthetic M015 Docker runtime and inspect the durable evidence.

## Command
```bash
bash -n scripts/security/verify-m015-runtime-security.sh && \
docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && \
PYTHONPATH=backend-hormonia:scripts/security/m015-runtime pytest \
  scripts/security/m015-runtime/tests/test_runner_contract.py \
  backend-hormonia/tests/security/test_m015_runtime_harness.py \
  backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py \
  backend-hormonia/tests/api/v2/test_private_upload_serving.py \
  backend-hormonia/tests/api/v2/test_report_ownership_closure.py \
  backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py \
  backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py -q && \
./scripts/security/verify-m015-runtime-security.sh --seam artifact && \
(docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'm015-runtime|18080|15432' && exit 1 || true)
```

## Expected Results
- Static/regression suite passes: 103 scoped tests.
- Artifact runtime seam exits 0.
- Evidence correlation is `m015-20260514T172743Z-2102411`.
- Private upload owner/admin downloads return 200 with expected body hash and safe attachment headers.
- Anonymous/foreign/private direct-static attempts fail closed without private bytes or path leakage.
- Base report/enhanced builder/enhanced export owner/admin/fallback routes pass, unsafe private/static export URL behavior is denied/withheld, and cross-owner/anonymous cases fail closed.
- `backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json` records `result: passed`, `redaction.validated: true`, and teardown `complete`.
- No active M015 runtime containers or `18080`/`15432` bound ports remain after teardown.

## Actual Result
Passed on the final post-change run. The runner recorded upload/report/evidence/redaction readiness phases and clean teardown for correlation `m015-20260514T172743Z-2102411`.
