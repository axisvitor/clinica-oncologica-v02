---
estimated_steps: 15
estimated_files: 1
skills_used: []
---

# T03: Run the integrated S06 security proof and update the matrix with fresh evidence

Expected executor skills/frontmatter: `estimated_steps: 6`, `estimated_files: 1`, `skills_used: [test, verify-before-complete, security-review]`.

Why: S06 must provide fresh final-assembly proof that S01-S05 boundaries still pass together after the R007 tightening, not merely cite historical summaries.

Files: update `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md` with the fresh S06 command, exit code, high-level result, and `gsd_exec` ID or equivalent persisted evidence identifier.

Do:
1. Run the integrated pytest command from the repository root with `cd backend-hormonia && ...`; do not add any test that reads `.gsd/`, `.planning/`, or `.audits/`.
2. Include all critical/high proof suites in one command: WhatsApp management auth, WuzAPI SSRF guard/media, patient helper and ownership boundary, messages/RBAC/phase25 regression, quiz link/session/compat/extensions, private upload serving, report tasks, report ownership closure, enhanced reports, and report service compatibility.
3. If the integrated command fails because of the R007 report task changes, fix T01 scope and rerun the full command; do not mark S06 complete with only a focused subset.
4. Update every matrix row's S06 evidence field or a shared evidence legend with the fresh command and exit 0 result. Historical S01-S05 `gsd_exec` IDs may remain as supporting evidence, but the matrix must clearly show the new S06 run.
5. Run the executable matrix validation from T02 after updating evidence.
6. Perform a final security-proof self-audit: all F-01..F-11 rows have controls/tests/evidence; R010/R011 are explicitly covered; R012/R013/R014 are deferred; R007 is no longer described as active; no PHI/token/private-path examples were copied into the doc.

Threat Surface (Q3): integration verification exercises auth bypass, SSRF, IDOR/BOLA, forged quiz state, public private-file exposure, report-export URL leakage, and diagnostic redaction boundaries.

Requirement Impact (Q4): re-verifies R001-R011 in one final command and records R012-R014 as follow-ups. Decisions revisited: D013 only.

Failure Modes (Q5): test DB/schema drift, Redis/cache fakes, async loop warnings, or fixture coupling can fail the suite; handle by fixing real regression or test isolation, not by removing boundary tests. Known pytest-asyncio loop-scope warnings are non-blocking if exit code remains 0.

Load Profile (Q6): final proof is local pytest integration load, not production traffic. Main shared resources are test DB/session fixtures, in-memory cache/fake Redis seams, and filesystem temp dirs.

Negative Tests (Q7): the included suites cover anonymous/non-admin auth, private/loopback/metadata SSRF URLs and redirects, cross-doctor/patient resource IDs, forged/expired/mismatched quiz tokens/cookies, public static denial, unsafe/private report redirect URLs, missing/malformed ownership evidence, and unsafe/PHI-like report labels.

## Inputs

- `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`
- `backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py`
- `backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py`
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`
- `backend-hormonia/tests/unit/api/v2/test_patient_access_helpers.py`
- `backend-hormonia/tests/api/v2/test_patient_ownership_boundary.py`
- `backend-hormonia/tests/api/v2/test_messages.py`
- `backend-hormonia/tests/api/v2/test_patients_rbac_impl.py`
- `backend-hormonia/tests/api/v2/test_phase25_messages_quiz_async.py`
- `backend-hormonia/tests/api/v2/test_quiz_link_session_boundary.py`
- `backend-hormonia/tests/api/v2/test_monthly_quiz_compatibility.py`
- `backend-hormonia/tests/api/v2/test_quiz_extensions.py`
- `backend-hormonia/tests/api/v2/test_private_upload_serving.py`
- `backend-hormonia/tests/tasks/test_reports_tasks.py`
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`
- `backend-hormonia/tests/services/test_report_service_task_compat.py`

## Expected Output

- `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`

## Verification

cd backend-hormonia && pytest tests/integration/whatsapp/test_whatsapp_management_auth.py tests/integrations/wuzapi/test_ssrf_guard.py tests/integrations/wuzapi/test_wuzapi_media.py tests/unit/api/v2/test_patient_access_helpers.py tests/api/v2/test_patient_ownership_boundary.py tests/api/v2/test_messages.py tests/api/v2/test_patients_rbac_impl.py tests/api/v2/test_phase25_messages_quiz_async.py tests/api/v2/test_quiz_link_session_boundary.py tests/api/v2/test_monthly_quiz_compatibility.py tests/api/v2/test_quiz_extensions.py tests/api/v2/test_private_upload_serving.py tests/tasks/test_reports_tasks.py tests/api/v2/test_report_ownership_closure.py tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q
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

## Observability Impact

The matrix becomes the final operational index for future agents: each boundary has the exact proof command/evidence ID plus safe failure-diagnostic constraints.
