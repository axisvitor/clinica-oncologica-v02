---
id: T02
parent: S05
milestone: M013
key_files:
  - backend-hormonia/app/services/reporting/report_access.py
key_decisions:
  - Centralize report access checks in a raw-metadata helper that fails closed before normalization/formatting/redirects and logs only PHI-safe denial diagnostics.
duration: 
verification_result: passed
completed_at: 2026-05-13T01:53:18.335Z
blocker_discovered: false
---

# T02: Added a shared raw report access guard with strict owner/patient metadata parsing, DB fallback evidence lookup, assignment checks, and PHI-safe denial logging.

**Added a shared raw report access guard with strict owner/patient metadata parsing, DB fallback evidence lookup, assignment checks, and PHI-safe denial logging.**

## What Happened

Created `backend-hormonia/app/services/reporting/report_access.py` as the centralized report authorization primitive for later base/enhanced route integration. The helper extracts raw owner evidence from `generated_by`, `created_by`, and `owner_id`, extracts patient evidence from scalar `patient_id` and list-like `patient_ids` across safe metadata/filter containers, and marks malformed UUIDs or scalar/list mismatches as fail-closed. It provides narrow DB fallback lookups for `Report` and `MedicalReport` rows without loading PHI-heavy content, async doctor assignment checks against `Patient.doctor_id`, and public assertion helpers for report/export metadata and patient ID scopes. Denial logging uses generic messages plus structured report/export/user/role/status/reason/count fields only.

## Verification

Ran the task py_compile check from `backend-hormonia`, reran the previous failing collect-only command from the correct backend directory, imported the helper and parsed owner evidence, and executed inline negative smoke checks for owner success, foreign owner denial, malformed owner UUID denial, and scalar/list patient metadata mismatch denial.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && python -m py_compile app/services/reporting/report_access.py` | 0 | ✅ pass | 79ms |
| 2 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py --collect-only -q` | 0 | ✅ pass | 24996ms |
| 3 | `cd backend-hormonia && python - <<'PY'
from app.services.reporting.report_access import ReportAccessEvidence, parse_report_access_metadata
print(ReportAccessEvidence.__name__)
print(parse_report_access_metadata({'generated_by': '00000000-0000-0000-0000-000000000001'}).owner_ids[0])
PY` | 0 | ✅ pass | 5216ms |
| 4 | `cd backend-hormonia && python - <<'PY'
import asyncio
from uuid import uuid4
from fastapi import HTTPException
from app.models.user import UserRole
from app.services.reporting.report_access import assert_report_access, parse_report_access_metadata
async def main():
    owner = uuid4()
    foreign = uuid4()
    evidence = parse_report_access_metadata({'generated_by': str(owner)})
    assert evidence.owner_ids == (owner,)
    await assert_report_access(None, role=UserRole.DOCTOR, user_id=owner, raw_metadata={'generated_by': str(owner)})
    for payload in ({'generated_by': str(owner)}, {'generated_by': 'not-a-uuid'}, {'patient_ids': str(uuid4())}):
        try:
            await assert_report_access(None, role=UserRole.DOCTOR, user_id=foreign, raw_metadata=payload)
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail == 'Access denied'
        else:
            raise AssertionError(f'expected denial for {payload}')
asyncio.run(main())
print('report_access smoke ok')
PY` | 0 | ✅ pass | 5180ms |

## Deviations

Added small helper APIs (`parse_patient_id_query` and `assert_patient_ids_access`) in the same planned module so T03 can reuse the same strict patient-scope primitive for report generation.

## Known Issues

Full route-level ownership enforcement is not wired yet; that remains planned for T03-T05. T02 verified the shared helper and test collection only.

## Files Created/Modified

- `backend-hormonia/app/services/reporting/report_access.py`
