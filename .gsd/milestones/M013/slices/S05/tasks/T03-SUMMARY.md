---
id: T03
parent: S05
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/routers/reports.py
  - backend-hormonia/tests/api/v2/test_report_ownership_closure.py
key_decisions:
  - Use the shared raw report access guard at the route boundary before report creation, cache status disclosure, report payload extraction, or format conversion.
  - Preserve cache-level ownership evidence as list-like `patient_ids` in every base report state so malformed cached metadata fails closed.
duration: 
verification_result: passed
completed_at: 2026-05-13T02:01:17.866Z
blocker_discovered: false
---

# T03: Enforced base report generation and download ownership using raw owner/patient metadata before cache creation or report formatting.

**Enforced base report generation and download ownership using raw owner/patient metadata before cache creation or report formatting.**

## What Happened

Updated `backend-hormonia/app/api/v2/routers/reports.py` so `/api/v2/reports/generate` parses `patient_ids` once through the shared strict parser, rejects malformed query values with the existing 400 response, and calls the shared patient access guard before creating any report ID or cached report state. The pending, generating, completed, and failed raw cache states now preserve `generated_by` plus list-like `patient_ids`, and `_generate_report_async` receives the parsed IDs so background transitions cannot drop ownership evidence. Updated direct downloads to depend on the async DB session and call `assert_report_access` immediately after loading the raw cache record, before status details, data extraction, format override validation, CSV/Excel/PDF conversion, or response bytes. Owner/admin behavior and non-identifying `report_{report_id}.ext` filenames are preserved. While verifying, fixed local ownership test compatibility issues: the patient fixture now uses schema-valid empty `patient_data`, and the generic denial assertion allows the app's existing non-PHI `status_code` envelope field.

## Verification

Fresh verification after the final edit passed: py_compile succeeded for the shared access helper, base report router, and ownership test file; the task-plan targeted pytest command passed for generation/base-report selection; and a broader base-only pytest subset passed all six base generation/download ownership tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile backend-hormonia/app/services/reporting/report_access.py backend-hormonia/app/api/v2/routers/reports.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py` | 0 | ✅ pass | 226ms |
| 2 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "base_report or generate" -q` | 0 | ✅ pass | 25474ms |
| 3 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "base" -q` | 0 | ✅ pass | 26532ms |

## Deviations

The task plan expected only the base report router as output, but the existing route-level regression file needed two small compatibility fixes so the T03 gate could exercise the route logic under the current strict patient JSONB schema and generic error envelope.

## Known Issues

None for the T03 base report scope. Enhanced builder/share/history/export ownership remains scheduled for T04-T05.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
