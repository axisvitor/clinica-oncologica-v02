---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T01: Lock final matrix and no-filter runner contracts

Why: S05 must define the closeout contract before changing runner behavior; otherwise matrix generation can silently omit a deferred item.
Do:
1. Add static tests that define required all-seam behavior, matrix artifact names, required matrix rows, and validator failure cases.
2. Include contract rows for R012/R013/R014/R015/R017/R018 and M014-deferred DB/session/provider/artifact runtime items.
3. Assert matrix artifacts are written under `backend-hormonia/docs/reports/security/m015/` and use redaction validation.
4. Keep tests static/fast; do not start Docker in this task.
Done when: contract tests fail on the current no-filter behavior/missing matrix, and pass after later tasks implement it.

## Inputs

- `.gsd/milestones/M015/M015-ROADMAP.md`
- `backend-hormonia/docs/reports/security/m015/*-seam-evidence.json`
- `scripts/security/verify-m015-runtime-security.sh`

## Expected Output

- `backend-hormonia/tests/security/test_m015_final_matrix_contract.py`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`

## Verification

cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q

## Observability Impact

Defines the matrix fields and validator failure classes that later tasks must emit.
