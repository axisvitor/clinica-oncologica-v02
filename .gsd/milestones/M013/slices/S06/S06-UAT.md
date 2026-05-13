# S06: Integrated Security Proof — UAT

**Milestone:** M013
**Written:** 2026-05-13T03:28:44.484Z

## UAT Type

Executable security proof / reviewer UAT. No live WhatsApp provider, browser session, production runtime, or manual human patient-flow UAT is required for S06.

## Preconditions

1. Work from the repository root.
2. Backend test dependencies are installed and the backend pytest configuration can run under `backend-hormonia`.
3. The evidence matrix exists at `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`.

## Steps

1. Run the focused report-task proof:
   `cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q`
2. Confirm the output exits 0 and the report-task tests cover opaque `{report_id}.pdf` artifacts plus PHI-safe Taskiq diagnostics.
3. Run the integrated S06 proof:
   `cd backend-hormonia && pytest tests/integration/whatsapp/test_whatsapp_management_auth.py tests/integrations/wuzapi/test_ssrf_guard.py tests/integrations/wuzapi/test_wuzapi_media.py tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q`
4. Confirm the integrated run exits 0; one skip for disabled rate limiting is acceptable in this test environment.
5. Open the evidence matrix and verify every F-01..F-11 row references Fresh S06 exit-0 evidence, maps to the relevant R001..R011 requirement(s), and includes PHI-safe diagnostic notes.
6. Run the matrix validation script from the S06 plan and confirm it exits 0, including R012/R013/R014 deferral markers and absence of `TODO`, `TBD`, `patient-name`, `jane-doe`, and `secret-token`.
7. Confirm the S06 proof tests/root wrapper do not contain `.gsd`, `.planning`, or `.audits` path literals.

## Expected Outcomes

- Anonymous WhatsApp management, SSRF media vectors, cross-doctor/patient IDOR attempts, forged/expired/mismatched quiz sessions, public private-file access, and report ownership bypasses fail closed under tests.
- Legitimate admin/assigned-doctor/patient-compatible paths covered by the selected suites still pass.
- Generated report artifacts remain private and opaque, and report-task diagnostics provide failure visibility without PHI, token, path, URL, cookie, message-body, quiz-answer, secret, or free-form `report_type` leakage.
- The matrix gives a single downstream inspection surface for F-01..F-11, Fresh S06 evidence, R007 closure, R010/R011 coverage, and deferred R012/R013/R014 follow-ups.

## Edge Cases to Inspect

- `report_type` values shaped like traversal paths, patient-identifying text, phone/token fragments, or other unsafe free-form input must not appear in output paths or task diagnostics.
- Quiz submissions with forged raw session IDs, wrong patient/token binding, expired links, revoked links, or mismatched state must fail while the valid fixture flow still completes.
- Direct UUID/report ID downloads, exports, shares, history, and restore paths must reject foreign users/doctors before returning data or URLs.
- Private upload/report static paths must deny anonymous/public access; authorized gated downloads remain functional.

## Operational Readiness

- Health signal: focused and integrated pytest commands plus matrix validation exit 0.
- Failure signal: pytest assertions fail on any boundary regression, unsafe artifact/log leakage, missing Fresh S06 evidence, placeholder text, or unsafe sentinel values.
- Recovery procedure: rerun the focused report-task suite to isolate R007 regressions, rerun the integrated S06 command for cross-slice regressions, then inspect PHI-safe Taskiq diagnostics by report_id/task_name/status/reason/failure_type.
- Monitoring gaps: production-like runtime harness, live provider behavior, and browser/manual UAT are intentionally not proven here and remain deferred under R014; medium follow-ups R012/R013 remain outside this critical/high closure.

## Not Proven By This UAT

- Live WhatsApp/WuzAPI provider behavior outside mocked/test seams.
- Production deployment, storage permissions, CDN/static server configuration, or runtime file-system enforcement beyond the backend contract tests.
- Browser UI flows and manual clinical-user acceptance.
- Deferred medium/proof-gap/runtime items R012, R013, and R014, and non-goal items R015-R018.
