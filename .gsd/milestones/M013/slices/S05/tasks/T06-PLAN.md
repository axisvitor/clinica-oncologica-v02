---
estimated_steps: 31
estimated_files: 5
skills_used: []
---

# T06: Run integrated report ownership proof suite

---
estimated_steps: 5
estimated_files: 0
skills_used:
  - verify-before-complete
  - test
  - security-review
---

Why: S05 closes a security boundary only if the new negative matrix and prior S04/enhanced report compatibility suites pass together.

Files:
- No source files should be modified by this verification-only task unless a failure reveals a regression that must be fixed in the owning task files.

Do:
1. Run the focused S05 ownership suite.
2. Run enhanced reports compatibility and report service compatibility suites to prove legitimate owner/admin flows remain compatible.
3. Re-run S04 private upload/report serving and Taskiq report artifact tests to prove S05 did not reintroduce public private-file URLs or PHI-unsafe report artifact behavior.
4. If tests fail, fix the owning implementation/test fixture file rather than weakening assertions; rerun the smallest failing command first, then the final combined command.
5. Record final verification evidence in the task completion summary with command, exit code, and duration.

Failure Modes (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| pytest/test DB | inspect first failing test and keep DB fixture isolation | rerun focused subset; do not mark complete without fresh output | N/A |
| Redis/cache mocks | fix fixture incompatibility, not production fail-open behavior | N/A | malformed metadata tests must remain fail-closed |

Load Profile (Q6):
- Shared resources: test DB setup, mocked Redis, pytest process.
- Per-operation cost: full focused integration subset only; no live external services.
- 10x breakpoint: total test runtime; keep final command focused to S05/S04 compatibility rather than full repo.

Negative Tests (Q7):
- Malformed inputs: covered by `test_report_ownership_closure.py`.
- Error paths: anonymous/foreign/missing/malformed ownership and private URL leak checks.
- Boundary conditions: owner/admin success across base/enhanced/export/private report paths.

Done when: The final combined verification command exits 0 with fresh output from this task and no completion claim relies on stale earlier test runs.

## Inputs

- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`
- `backend-hormonia/tests/services/test_report_service_task_compat.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
- `backend-hormonia/tests/tasks/test_reports_tasks.py`
- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`
- `backend-hormonia/app/services/reporting/report_access.py`

## Expected Output

- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`
- `backend-hormonia/tests/services/test_report_service_task_compat.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
- `backend-hormonia/tests/tasks/test_reports_tasks.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py -q

## Observability Impact

Produces the slice-level verification evidence future S06 can cite when assembling the F-09/R008 and R010/R011 evidence matrix.
