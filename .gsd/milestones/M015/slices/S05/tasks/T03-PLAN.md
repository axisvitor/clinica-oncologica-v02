---
estimated_steps: 8
estimated_files: 5
skills_used: []
---

# T03: Generate redaction-safe M015 evidence matrix

Why: S05's central artifact is the evidence matrix, not another seam log; the generator must consolidate prior seam evidence into explicit requirement/deferred-item rows.
Do:
1. Implement a matrix helper script/module under `scripts/security/m015-runtime/` that reads DB/session/provider/artifact evidence and summaries.
2. Emit `m015-evidence-matrix.json` and `m015-evidence-matrix.md` under `backend-hormonia/docs/reports/security/m015/`.
3. Populate rows with requirement IDs, source seam, evidence path, correlation ID, result, proof class, non-goal/fixed-outcome status, and redaction verdict.
4. Include the S04-discovered upload schema/auth fixes as fixed outcomes, and the upload quota warning as an explicit warning-policy item for validator review.
5. Validate outputs with existing redaction denylist helpers.
Done when: the generator creates matrix artifacts from current seam evidence without Docker and contract tests pass.

## Inputs

- `backend-hormonia/docs/reports/security/m015/db-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json`

## Expected Output

- `scripts/security/m015-runtime/evidence_matrix.py`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md`

## Verification

python3 -m py_compile scripts/security/m015-runtime/evidence_matrix.py && python3 scripts/security/m015-runtime/evidence_matrix.py --input-dir backend-hormonia/docs/reports/security/m015 --output-dir backend-hormonia/docs/reports/security/m015 && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py -q

## Observability Impact

Creates row-level matrix diagnostics with evidence path, correlation ID, result, status, and failure-policy fields.
