---
estimated_steps: 33
estimated_files: 3
skills_used: []
---

# T03: Enforce base report patient and download ownership

---
estimated_steps: 7
estimated_files: 1
skills_used:
  - api-design
  - security-review
  - verify-before-complete
---

Why: `/api/v2/reports/generate` currently accepts foreign patient_ids and `/api/v2/reports/{report_id}/download` returns report data to any authenticated UUID holder.

Files:
- `backend-hormonia/app/api/v2/routers/reports.py`

Do:
1. Parse `patient_ids` once into a sanitized `List[UUID]`; reject malformed values with the existing generic 400.
2. Before creating a report, call the shared report/patient access guard so non-admin doctors cannot generate report metadata for foreign patients.
3. Persist parsed patient IDs in every raw cached report state (`pending`, `generating`, `completed`, `failed`) alongside `generated_by`; update `_generate_report_async` signature/calls to preserve this metadata.
4. Add `db: AsyncSession = Depends(get_async_db)` to `download_report` and call the shared raw report access guard immediately after the report cache record is loaded and before status details, data extraction, or format conversion.
5. Preserve legitimate owner/admin downloads for JSON/CSV/Excel/PDF and keep filenames non-identifying (`report_{report_id}.ext`).
6. Keep all denial details generic; do not log patient IDs in message text, report payloads, private filesystem paths, or download URLs.
7. Keep existing list/schedule behavior compatible unless directly required by tests; if touched, retain non-admin filtering by raw owner/patient assignment.

Failure Modes (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| Redis report cache | existing missing report path remains 404 | request timeout applies | malformed owner/patient metadata fails closed before bytes are returned |
| DB patient assignment | fail closed/generic 403 for foreign or unprovable patient assignment | request timeout applies | malformed patient_ids returns 400 at generate or 403 for cached malformed metadata |

Load Profile (Q6):
- Shared resources: Redis report cache and DB patient ownership query.
- Per-operation cost: one cache lookup, one narrow patient assignment query when patient IDs exist, then existing formatting cost.
- 10x breakpoint: PDF/Excel formatting remains heavier than auth; auth query must happen before formatting to reduce abuse amplification.

Negative Tests (Q7):
- Malformed inputs: invalid patient_ids query and malformed cached patient_ids.
- Error paths: foreign doctor generation/download, missing user ID, missing ownership metadata.
- Boundary conditions: owner, admin, no patient_ids but generated_by owner, one of multiple patients foreign.

Done when: Base report generation/download portions of `test_report_ownership_closure.py` pass and unauthorized users cannot trigger report data formatting or receive status/data details for report IDs they do not own.

## Inputs

- `backend-hormonia/app/services/reporting/report_access.py`
- `backend-hormonia/app/api/v2/routers/reports.py`
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
- `backend-hormonia/app/schemas/v2/reports.py`
- `backend-hormonia/app/models/patient.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/reports.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "base_report or generate" -q

## Observability Impact

Moves base report denial ahead of expensive formatting and emits PHI-safe report access denial reasons tied to report_id/user_id instead of leaking status/data or patient identifiers.
