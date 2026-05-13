---
id: T02
parent: S06
milestone: M013
key_files:
  - backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md
  - tests/tasks/test_reports_tasks.py
key_decisions:
  - The T02 matrix records expected Fresh S06 evidence fields without claiming the integrated proof has already run; T03 remains responsible for appending actual full-suite evidence.
  - A root-cwd compatibility wrapper is acceptable for automated gates, but it delegates to the canonical backend report task suite and explicitly marks async tests so bare root pytest does not skip coroutine tests.
duration: 
verification_result: passed
completed_at: 2026-05-13T03:17:03.917Z
blocker_discovered: false
---

# T02: Created the M013 F-01..F-11 evidence matrix and fixed the root report-task verification gate used by automation.

**Created the M013 F-01..F-11 evidence matrix and fixed the root report-task verification gate used by automation.**

## What Happened

Read the M013 requirements, context, roadmap, completed S01-S05 summaries, S06/T01 summary, and reusable security boundary helper to assemble a standalone reviewer-facing matrix at `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`. The document includes the required scope statement, one row for each F-01 through F-11 with requirement mappings, controls, test files, command classes, expected Fresh S06 evidence fields for T03, and PHI-safe negative-test notes. It also adds the reusable R010 helper/suite section, the R011 diagnostics contract, and explicit deferred/non-goal coverage for R012-R018 without placeholder language or unsafe sentinel examples.

The prior verification gate failed because automation invoked `pytest tests/tasks/test_reports_tasks.py -q` from the repository root while the canonical tests live under `backend-hormonia/tests/tasks/test_reports_tasks.py`. To make that gate exercise the canonical suite instead of failing collection, I added `tests/tasks/test_reports_tasks.py` as a root-cwd compatibility wrapper. The wrapper loads backend environment defaults, imports the canonical backend test file, re-exports test functions, and marks re-exported coroutine tests with `pytest.mark.asyncio` so the bare root pytest invocation runs the async tests rather than skipping them.

## Verification

Verified the evidence matrix with the task-plan Python assertion: all F-01..F-11 IDs are present, R001-R014 are present, at least eleven `| F-` rows exist, and the forbidden placeholder/sentinel strings are absent. Re-ran the previously failing root report-task gate and it passed through the new compatibility wrapper with 13 tests passing. Also ran the canonical backend report task suite with the backend pytest config and PYTHONPATH to confirm the wrapper did not mask backend behavior; it passed with the canonical 13-test suite.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python - <<'PY'
from pathlib import Path
p = Path('backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md')
text = p.read_text(encoding='utf-8')
assert all(f'F-{i:02d}' in text for i in range(1, 12))
for rid in [f'R{i:03d}' for i in range(1, 15)]:
    assert rid in text, rid
for forbidden in ['TODO', 'TBD', 'patient-name', 'jane-doe', 'secret-token']:
    assert forbidden.lower() not in text.lower(), forbidden
assert text.count('| F-') >= 11
PY` | 0 | ✅ pass | 64ms |
| 2 | `pytest tests/tasks/test_reports_tasks.py -q` | 0 | ✅ pass | 33167ms |
| 3 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/tasks/test_reports_tasks.py -q` | 0 | ✅ pass | 36279ms |

## Deviations

Added `tests/tasks/test_reports_tasks.py`, a root-cwd compatibility wrapper, because the automated verification gate invoked that root-relative path and failed collection. The canonical backend test implementation remains under `backend-hormonia/tests/tasks/test_reports_tasks.py`.

## Known Issues

The pytest runs still emit existing non-blocking deprecation warnings from pytest-asyncio/Pydantic; they did not affect pass/fail status. T03 still needs to run the full integrated S06 security proof and replace the matrix's expected Fresh S06 evidence fields with real command evidence.

## Files Created/Modified

- `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`
- `tests/tasks/test_reports_tasks.py`
