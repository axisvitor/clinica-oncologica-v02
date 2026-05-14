---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T04: Enforce strict matrix validator and red-signal policy

Why: Final closure must be mechanically blocked on missing/stale/unsafe/failed evidence rather than relying on narrative review.
Do:
1. Add strict validation mode to the matrix helper or a companion validator.
2. Reject missing required rows/artifacts, non-passed seam results, stale/mismatched correlation references, placeholders/TODO text, raw sensitive shapes, raw download URLs/private paths/cookies/session IDs, unclassified warnings, and unresolved red signals.
3. Add negative tests using temporary mutated evidence/matrix fixtures.
4. Wire the validator into the runner's all-seam closeout path after matrix generation.
Done when: negative tests prove false greens are rejected and the current generated matrix validates cleanly.

## Inputs

- `scripts/security/m015-runtime/evidence_matrix.py`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md`

## Expected Output

- `scripts/security/m015-runtime/evidence_matrix.py`
- `backend-hormonia/tests/security/test_m015_final_matrix_contract.py`
- `scripts/security/verify-m015-runtime-security.sh`

## Verification

python3 scripts/security/m015-runtime/evidence_matrix.py --input-dir backend-hormonia/docs/reports/security/m015 --output-dir backend-hormonia/docs/reports/security/m015 --validate && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py tests/security/test_m015_runtime_harness.py -q

## Observability Impact

Validator emits explicit failure classes for missing rows, stale evidence, unsafe content, unresolved warnings, and failed seam results.
