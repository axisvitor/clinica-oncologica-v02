---
estimated_steps: 3
estimated_files: 6
skills_used: []
---

# T02: Write M014 evidence matrix and validator

Why: R013/R018 require no medium/proof-gap item to disappear; a reviewer-facing matrix is the durable inspection surface.
Do: Create `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md` using the M013 matrix pattern and S01-S04/S05 evidence. Add `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py` to validate all R012/R013/R018-relevant rows, S01-S05 command references, closed/not-applicable/deferred statuses, R014/M015 deferral language, and absence of TODO/TBD/unsafe PHI/secret/path sentinel values.
Done when: The matrix exists, cites exact command classes/evidence IDs available from summaries, and the validator fails on missing required rows or unsafe placeholders.

## Inputs

- `.gsd/milestones/M014/slices/S01/S01-SUMMARY.md`
- `.gsd/milestones/M014/slices/S02/S02-SUMMARY.md`
- `.gsd/milestones/M014/slices/S03/S03-SUMMARY.md`
- `.gsd/milestones/M014/slices/S04/S04-SUMMARY.md`
- `.gsd/milestones/M014/slices/S05/S05-RESEARCH.md`
- `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`
- `.gsd/REQUIREMENTS.md`

## Expected Output

- `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`
- `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py

## Observability Impact

Creates the reviewer/future-agent map from requirement/finding to command evidence, plus a mechanical validator for missing coverage and unsafe documentation content.
