---
id: T01
parent: S05
milestone: M015
key_files:
  - backend-hormonia/tests/security/test_m015_final_matrix_contract.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/m015-runtime/tests/test_runner_contract.py
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/evidence_matrix.py
  - scripts/security/m015-runtime/README.md
key_decisions:
  - No-filter runner behavior is now a static contract for all-seam closeout; unknown seams remain fail-closed.
  - The final matrix contract requires rows for R012/R013/R014/R015/R017/R018 and the M014-deferred DB/session/provider/artifact runtime items.
  - The validator failure taxonomy is explicit: missing row/artifact, failed seam result, stale correlation, placeholder text, unsafe content, raw download URL/private path leakage, unclassified warning, and unresolved red signal.
duration: 
verification_result: passed
completed_at: 2026-05-14T17:54:21.566Z
blocker_discovered: false
---

# T01: Locked the S05 final matrix and no-filter all-seam runner contracts with fast static tests.

**Locked the S05 final matrix and no-filter all-seam runner contracts with fast static tests.**

## What Happened

Added `test_m015_final_matrix_contract.py` to define the S05 final matrix shape, required requirement/runtime rows, matrix artifact paths, validator failure classes, redaction-safe expected matrix shape, and existing seam evidence safety. Updated existing runtime harness and runner contract tests so no-filter behavior is treated as the all-seam closeout contract rather than missing-seam fail-closed behavior, while unknown seams still fail before setup. Added the initial `evidence_matrix.py` helper and runner/README static declarations needed for the contract suite to pass without starting Docker.

## Verification

Fresh verification passed after edits: `python3 -m py_compile scripts/security/m015-runtime/evidence_matrix.py backend-hormonia/tests/security/test_m015_final_matrix_contract.py backend-hormonia/tests/security/test_m015_runtime_harness.py scripts/security/m015-runtime/tests/test_runner_contract.py && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q` completed with 50 tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile scripts/security/m015-runtime/evidence_matrix.py backend-hormonia/tests/security/test_m015_final_matrix_contract.py backend-hormonia/tests/security/test_m015_runtime_harness.py scripts/security/m015-runtime/tests/test_runner_contract.py && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q` | 0 | ✅ pass | 22500ms |

## Deviations

Implemented the minimum static runner declarations and matrix helper skeleton while adding the contract tests so the T01 verification could be green instead of leaving a red test state for later tasks.

## Known Issues

T02-T04 still need to fully harden and exercise the all-seam runner/matrix validator beyond the static contract; T01 intentionally verifies only fast static behavior and existing evidence safety.

## Files Created/Modified

- `backend-hormonia/tests/security/test_m015_final_matrix_contract.py`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`
- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/evidence_matrix.py`
- `scripts/security/m015-runtime/README.md`
