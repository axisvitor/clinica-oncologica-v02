# S06: Integrated Security Proof

**Goal:** Produce the final integrated proof for M013 critical/high security remediation: close the remaining R007 generated-report artifact/log leakage gap, map F-01..F-11 to fresh passing evidence, and explicitly carry medium/proof-gap/runtime follow-ups forward.
**Demo:** A consolidated evidence matrix shows F-01..F-11 mapped to passing commands/tests and explicitly lists deferred medium/proof-gap follow-ups.

## Must-Haves

- R007 is no longer active: Taskiq-generated patient report artifact filenames are opaque/non-identifying, remain under the private report root, and task diagnostics do not emit raw or merely sanitized free-form `report_type` values.
- The evidence matrix at `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md` maps every finding F-01..F-11 to requirements R001..R011, fixed controls, test files/commands, PHI-safe diagnostic notes, and fresh S06 proof evidence.
- The matrix explicitly lists deferred R012, R013, and R014 follow-ups and calls out R015-R018 as out-of-scope/non-goals without reopening completed critical/high work.
- Fresh integrated verification from `backend-hormonia` passes for the WhatsApp auth, WuzAPI SSRF, patient/message/flow, quiz, private upload/report, report ownership, report task, enhanced report, and compatibility suites.
- Executable documentation validation proves the evidence matrix contains F-01..F-11, R001..R014, no `TODO`/`TBD` placeholders, and no unsafe sentinel values.
- No pytest/test code reads `.gsd/`, `.planning/`, `.audits/`, or other gitignored planning/audit paths.

## Proof Level

- This slice proves: Final-assembly proof. This slice proves critical/high remediation at contract/integration-test level using real backend pytest suites and executable document assertions. No live provider, production runtime, browser UAT, or manual human UAT is required; production-like runtime harness gaps are deferred as R014.

## Integration Closure

Consumes completed S01-S05 controls and tests: WhatsApp management auth, WuzAPI SSRF guard, shared patient ownership helper, quiz token/session validator, private upload/report serving boundary, and report ownership guard. S06 introduces only the R007 report artifact/log tightening and a tracked evidence matrix. After the integrated command and matrix validation pass, M013 critical/high code remediation is ready for milestone validation; remaining medium hardening/proof gaps/runtime harness work stays explicitly deferred.

## Verification

- S06 consolidates PHI-safe failure visibility across the milestone. R007 removes or allowlists report-type diagnostics so future agents can still inspect task/report IDs, status, reason, and failure type without exposing patient names, phones, raw tokens, private paths, URLs, cookies, message bodies, quiz answers, or secrets. The final matrix becomes the inspection surface for what command proves each boundary.

## Tasks

- [x] **T01: Close R007 generated report artifact and task diagnostic leakage** `est:1.5h`
  Expected executor skills/frontmatter: `estimated_steps: 7`, `estimated_files: 3`, `skills_used: [tdd, security-review, observability, verify-before-complete]`.
  - Files: `backend-hormonia/app/tasks/helpers/reports_helpers.py`, `backend-hormonia/app/tasks/reports_taskiq.py`, `backend-hormonia/tests/tasks/test_reports_tasks.py`
  - Verify: cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q

- [x] **T02: Assemble the F-01..F-11 critical/high evidence matrix** `est:1h`
  Expected executor skills/frontmatter: `estimated_steps: 6`, `estimated_files: 1`, `skills_used: [write-docs, security-review, verify-before-complete]`.
  - Files: `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`
  - Verify: python - <<'PY'
from pathlib import Path
p = Path('backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md')
text = p.read_text(encoding='utf-8')
assert all(f'F-{i:02d}' in text for i in range(1, 12))
for rid in [f'R{i:03d}' for i in range(1, 15)]:
    assert rid in text, rid
for forbidden in ['TODO', 'TBD', 'patient-name', 'jane-doe', 'secret-token']:
    assert forbidden.lower() not in text.lower(), forbidden
assert text.count('| F-') >= 11
PY

- [x] **T03: Run the integrated S06 security proof and update the matrix with fresh evidence** `est:1.5h`
  Expected executor skills/frontmatter: `estimated_steps: 6`, `estimated_files: 1`, `skills_used: [test, verify-before-complete, security-review]`.
  - Files: `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`
  - Verify: cd backend-hormonia && pytest tests/integration/whatsapp/test_whatsapp_management_auth.py tests/integrations/wuzapi/test_ssrf_guard.py tests/integrations/wuzapi/test_wuzapi_media.py tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q
python - <<'PY'
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
PY

## Files Likely Touched

- backend-hormonia/app/tasks/helpers/reports_helpers.py
- backend-hormonia/app/tasks/reports_taskiq.py
- backend-hormonia/tests/tasks/test_reports_tasks.py
- backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md
