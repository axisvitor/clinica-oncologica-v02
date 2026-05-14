---
id: T03
parent: S05
milestone: M015
key_files:
  - scripts/security/m015-runtime/evidence_matrix.py
  - backend-hormonia/tests/security/test_m015_final_matrix_contract.py
  - backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json
  - backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md
key_decisions:
  - Matrix rows use stable runtime item IDs rather than prose-only rows so S05 can mechanically detect omissions.
  - DB evidence without a top-level `result` is normalized as passed when it has a correlation ID and no failed phase events, preserving S01's existing evidence shape.
  - The known upload quota AsyncSession/query runtime warning is classified explicitly instead of being ignored.
duration: 
verification_result: passed
completed_at: 2026-05-14T17:57:37.726Z
blocker_discovered: false
---

# T03: Generated the redaction-safe M015 evidence matrix from the four seam evidence artifacts.

**Generated the redaction-safe M015 evidence matrix from the four seam evidence artifacts.**

## What Happened

Implemented the matrix helper so it reads DB/session/provider/artifact evidence from `backend-hormonia/docs/reports/security/m015`, validates each seam artifact with the existing redaction denylist, normalizes seam pass status, and writes `m015-evidence-matrix.json` plus `m015-evidence-matrix.md`. The generated matrix includes required requirement IDs R012/R013/R014/R015/R017/R018, required runtime rows, evidence paths, correlation IDs, redaction booleans, non-goals, validator failure classes, and a classified warning for the non-fatal upload quota runtime log.

## Verification

Fresh verification passed: `python3 -m py_compile scripts/security/m015-runtime/evidence_matrix.py` succeeded; matrix generation printed `M015 evidence matrix validated: backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`; 9 matrix contract tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile scripts/security/m015-runtime/evidence_matrix.py && python3 scripts/security/m015-runtime/evidence_matrix.py --input-dir backend-hormonia/docs/reports/security/m015 --output-dir backend-hormonia/docs/reports/security/m015 && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py -q` | 0 | ✅ pass | 22700ms |

## Deviations

The initial placeholder validator flagged its own `placeholder_text` failure-class name; narrowed placeholder scanning to evidence narrative strings while excluding validator taxonomy fields.

## Known Issues

The validator has basic strict checks now, but T04 still needs focused negative tests/mutations to prove each false-green class is rejected.

## Files Created/Modified

- `scripts/security/m015-runtime/evidence_matrix.py`
- `backend-hormonia/tests/security/test_m015_final_matrix_contract.py`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md`
