---
estimated_steps: 15
estimated_files: 3
skills_used: []
---

# T01: Close R007 generated report artifact and task diagnostic leakage

Expected executor skills/frontmatter: `estimated_steps: 7`, `estimated_files: 3`, `skills_used: [tdd, security-review, observability, verify-before-complete]`.

Why: S06 research found the only live remediation risk: `reports_helpers._build_safe_report_path()` and `reports_taskiq.generate_patient_report()` treat sanitized free-form `report_type` as safe. Sanitization is not redaction because values such as patient names, phone fragments, path segments, or tokens can survive in private artifact filenames and structured logs.

Files: `backend-hormonia/app/tasks/helpers/reports_helpers.py`, `backend-hormonia/app/tasks/reports_taskiq.py`, `backend-hormonia/tests/tasks/test_reports_tasks.py`.

Do:
1. Extend `test_reports_tasks.py` first so it fails against the current implementation: use sentinel report types such as `medical/../../patient-name`, `Jane Doe +551199999999 secret-token`, and traversal-like strings, then assert those sentinel fragments do not appear in `Path(result["output_path"]).name`, `result["output_path"]`, or `caplog.text`.
2. Change report artifact path construction to use an opaque, report-id-only filename such as `{report_id}.pdf` under `get_private_report_artifact_root()`. Preserve the existing private-root traversal guard with `resolve(strict=False)` and `relative_to(...)`.
3. Remove raw/sanitized free-form `report_type` from `generate_patient_report` start, validation, error, and success diagnostics. If report-type diagnostic value is retained, it must be a strict non-PHI allowlist/category and unknown/free-form values must map to `other`; do not log a transformed version of attacker/patient-controlled text.
4. Preserve existing successful result shape (`status`, `report_id`, `output_path`) and invalid-patient failure shape (`{"status": "failed", "error": "invalid_patient_id"}`), but ensure neither includes patient identifiers or free-form report-type material beyond the private root and UUID report ID.
5. Keep scheduled report dispatch behavior compatible: `generate_scheduled_reports()` may pass the original type through for existing task API compatibility, but the generated filename/logging path must not expose it.
6. Run the focused task suite and update assertions that previously expected `{report_id}_{sanitized_report_type}.pdf`.

Threat Surface (Q3): attacker-controlled or user-entered report labels can contain PHI, path fragments, tokens, or misleading filenames. Data exposure risk is PHI leakage through private artifact names, task result paths, and logs. Input trust boundary is untrusted `report_type` reaching filesystem/logging code.

Requirement Impact (Q4): closes R007 and advances R011; re-verifies S04/S05 report task compatibility. Decision D013 applies: report artifacts use report-id-only filenames and only non-PHI diagnostics.

Failure Modes (Q5): if private root resolution fails, fail closed with `Invalid report output path`; if PDF generation fails, log generic `report_generation_failed` with task/report IDs and failure type only; if malformed patient ID is supplied, return the existing failed response without creating artifact directories.

Load Profile (Q6): per operation remains one DB/report generation flow plus one private file write; no new shared cache or network cost. At 10x load, existing report generation/PDF cost dominates, not filename classification.

Negative Tests (Q7): malformed UUID, traversal-like report types, PHI-like names/phones, token-like strings, unknown/free-form report types, and successful PDF write under the private root.

## Inputs

- `backend-hormonia/app/tasks/helpers/reports_helpers.py`
- `backend-hormonia/app/tasks/reports_taskiq.py`
- `backend-hormonia/tests/tasks/test_reports_tasks.py`

## Expected Output

- `backend-hormonia/app/tasks/helpers/reports_helpers.py`
- `backend-hormonia/app/tasks/reports_taskiq.py`
- `backend-hormonia/tests/tasks/test_reports_tasks.py`

## Verification

cd backend-hormonia && pytest tests/tasks/test_reports_tasks.py -q

## Observability Impact

Report task diagnostics stay useful through task_name/report_id/status/reason/failure_type while removing free-form report_type leakage from logs and result paths.
