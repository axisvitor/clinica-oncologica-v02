---
id: T03
parent: S06
milestone: M013
key_files:
  - backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md
key_decisions:
  - Use a shared Fresh S06 Integrated Evidence legend (`S06-T03-1`) plus per-row references so future reviewers can trace every F-01..F-11 row to the same durable full-suite proof without duplicating the long command in every row.
duration: 
verification_result: passed
completed_at: 2026-05-13T03:21:49.462Z
blocker_discovered: false
---

# T03: Ran the full integrated M013/S06 critical-high security proof and updated the evidence matrix with the fresh exit-0 `gsd_exec` evidence ID.

**Ran the full integrated M013/S06 critical-high security proof and updated the evidence matrix with the fresh exit-0 `gsd_exec` evidence ID.**

## What Happened

Executed the integrated backend pytest selection covering WhatsApp management auth, WuzAPI SSRF/media guards, patient ownership helpers and boundaries, messages/RBAC/phase25 regressions, quiz link/session/compat/extensions, private upload serving, report Taskiq tasks, report ownership closure, enhanced reports, and report service compatibility. The run passed with exit 0 and produced durable evidence under `gsd_exec 2664b28c-f06f-4a15-ad36-5781138c0677`. Updated `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md` by adding a Fresh S06 Integrated Evidence legend with the exact command, result, duration, persisted evidence ID, and high-level output note. Replaced all F-01 through F-11 placeholder evidence fields with concrete S06-T03-1 references. The matrix now explicitly states R007 is closed by S06/T01 plus the integrated proof, R010/R011 are covered by reusable negative isolation and PHI-safe diagnostics assertions, and R012/R013/R014 remain deferred follow-ups.

## Verification

Ran the required integrated pytest command from the repository root via `gsd_exec`; it exited 0 in 61152ms and reached pytest `[100%]` with one expected skip for the rate-limit-disabled test environment. Ran the task-plan executable matrix validation after updating the document; it exited 0. Ran an additional self-audit ensuring all eleven F-rows contain S06-T03-1 evidence, the fresh `gsd_exec` ID, and `exit 0`, while R010/R011 coverage, R012-R014 deferral, R007 closure, and forbidden placeholder/sentinel absence are all present.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/integration/whatsapp/test_whatsapp_management_auth.py tests/integrations/wuzapi/test_ssrf_guard.py tests/integrations/wuzapi/test_wuzapi_media.py tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q` | 0 | ✅ pass | 61152ms |
| 2 | `python - <<'PY'
from pathlib import Path
p = Path('backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md')
text = p.read_text(encoding='utf-8')
assert all(f'F-{i:02d}' in text for i in range(1, 12))
for rid in [f'R{i:03d}' for i in range(1, 15)]:
    assert rid in text, rid
for marker in ['fresh s06', 'exit 0', 'R012', 'R013', 'R014']:
    assert marker.lower() in text.lower(), marker
for forbidden in ['TODO', 'TBD', 'patient-name', 'jane-doe', 'secret-token']:
    assert forbidden.lower() not in text.lower(), forbidden
PY` | 0 | ✅ pass | 67ms |
| 3 | `python - <<'PY'
from pathlib import Path
p = Path('backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md')
text = p.read_text(encoding='utf-8')
rows = [line for line in text.splitlines() if line.startswith('| F-')]
assert len(rows) == 11, len(rows)
for i, row in enumerate(rows, 1):
    fid = f'F-{i:02d}'
    assert row.startswith(f'| {fid} '), fid
    assert 'backend-hormonia/tests/' in row or 'tests/tasks/test_reports_tasks.py' in row, fid
    assert 'S06-T03-1' in row, fid
    assert 'gsd_exec 2664b28c-f06f-4a15-ad36-5781138c0677' in row, fid
    assert '`exit 0`' in row, fid
for required in ['R010 and R011 are explicitly covered', 'R012, R013, and R014 remain deferred follow-ups', 'R007 generated-report artifact/log leakage is closed']:
    assert required in text, required
for forbidden in ['row should cite', 'Expected S06 fresh evidence field', 'TODO', 'TBD', 'patient-name', 'jane-doe', 'secret-token']:
    assert forbidden.lower() not in text.lower(), forbidden
print('self-audit ok: 11 rows, fresh evidence, R010/R011 covered, R012-R014 deferred, R007 closed')
PY` | 0 | ✅ pass | 78ms |

## Deviations

None.

## Known Issues

The integrated pytest stderr still contains the pre-existing pytest-asyncio loop-scope deprecation warning; the run exited 0. The integrated stdout reports one expected skip because rate limiting is disabled in the test environment.

## Files Created/Modified

- `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`
