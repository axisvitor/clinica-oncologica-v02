# S05: Report Ownership Closure — UAT

**Milestone:** M013
**Written:** 2026-05-13T02:40:39.595Z

## UAT Type

Automated security regression / API contract UAT for report ownership boundaries. Human browser UAT is not required for this slice.

## Preconditions

1. Repository checkout is at `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`.
2. Backend test dependencies and the project test environment are available.
3. Run commands from the repository root exactly as written so the backend test root is selected with `cd backend-hormonia`.

## Steps and Expected Outcomes

1. Run focused ownership proof:
   ```bash
   cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -q
   ```
   Expected: command exits 0 and all focused report ownership tests pass.

2. Run integrated report/private-artifact proof:
   ```bash
   cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py -q
   ```
   Expected: command exits 0 and report ownership, enhanced report compatibility, report service task compatibility, private upload serving, and report task regressions pass together.

3. In the focused test fixture, exercise base report generation/download with owner doctor/admin users and assigned patients.
   Expected: legitimate owner/admin/assigned-patient flows succeed, generated report state carries raw owner and parsed patient evidence, and no public deterministic private-report URL is required.

4. In the same fixture, submit foreign or malformed `patient_ids`, direct-download a foreign report ID, and request a report with missing/invalid raw ownership evidence.
   Expected: requests are denied before report creation, cache/status disclosure, report payload extraction, or formatting. Denial bodies/logs expose only generic status/reason-style diagnostics and do not contain patient names, patient IDs in messages, private filesystem paths, raw report data, tokens, or private download URLs.

5. Exercise enhanced builder, sharing/public-link/share listing, history, restore, delivery/visualization, and report-ID routes with owner/admin and foreign-doctor identities.
   Expected: owner/admin paths remain functional; foreign or anonymous access is denied before normalization, service work, response shaping, or redirects.

6. Exercise export status and export download with owner/admin and foreign users, including legacy cached download URLs and unsafe `/uploads`, `file:`, `data:`, or `javascript:` destinations.
   Expected: authorized users can observe/download safe exports; unauthorized users cannot obtain `download_url`, private paths, patient identifiers, tokens, or redirects; unsafe private artifact URLs are withheld or rejected even for legacy metadata.

7. Exercise S04 private upload/report serving regressions as part of the integrated command.
   Expected: private report artifacts remain inaccessible through unauthenticated `/uploads`, and authorized gated access continues to work.

## Edge Cases Covered

- UUID/report_id/export_id enumeration and replay attempts.
- Cross-doctor and cross-patient ownership mismatches.
- Anonymous access to report-ID surfaces.
- Missing, malformed, or laundering-prone `generated_by`/`created_by`/owner metadata.
- Malformed or foreign `patient_ids` during generation.
- Legacy cache keys versus service cache keys for builder/report/export evidence.
- Export download URL leakage and unsafe redirect schemes/paths.
- PHI-safe denial diagnostics.

## Operational Readiness (Q8)

- Health signal: focused and integrated pytest suites provide repeatable closeout health for S05 report ownership boundaries.
- Denial signal: route denials and helper logs use report/export IDs, user role/status/reason-style fields, and avoid PHI/private paths/tokens.
- Recovery procedure: if a regression appears, rerun the focused command first, inspect `tests/api/v2/test_report_ownership_closure.py` case names to identify the affected base/enhanced/export surface, then fix the route to invoke `report_access` before normalization/redirect/data disclosure.
- Monitoring gaps: runtime server telemetry and SIEM dashboards were not added in S05; S06 should consolidate evidence and list any milestone-wide observability gaps.

## Not Proven By This UAT

- Live deployed server behavior, browser flows, real Redis/object storage, or human clinical workflow validation.
- Medium/proof-gap findings outside S05 scope.
- The final F-01..F-11 milestone evidence matrix; that is S06's responsibility.
- R007's remaining opaque/allowlisted generated filename follow-up noted in requirements.
