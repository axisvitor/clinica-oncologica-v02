---
id: T05
parent: S05
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/routers/enhanced_reports.py
  - backend-hormonia/app/services/reporting/enhanced_reports_service.py
  - backend-hormonia/tests/api/v2/test_enhanced_reports.py
  - backend-hormonia/tests/api/v2/test_report_ownership_closure.py
key_decisions:
  - Persist export access evidence under both legacy and service export cache keys so status/download authorization can use raw metadata before normalization.
  - Withhold unsafe legacy private artifact URLs from export status responses and fail closed before redirecting downloads that point at /uploads, file, data, or javascript URLs.
duration: 
verification_result: passed
completed_at: 2026-05-13T02:26:18.847Z
blocker_discovered: false
---

# T05: Authorized enhanced export status/download by raw export metadata, persisted export ownership evidence, and blocked unsafe private artifact URL leakage.

**Authorized enhanced export status/download by raw export metadata, persisted export ownership evidence, and blocked unsafe private artifact URL leakage.**

## What Happened

Implemented export ownership closure for the enhanced reports export_id surfaces. EnhancedReportsService.export_multi_format now persists raw export metadata under both legacy router and service export cache keys, including created_by/generated_by, report_id, formats, status, file metadata, and timestamps. The export status route now authorizes raw export metadata before normalization and sanitizes download_urls so legacy /uploads private artifact URLs are withheld from status responses. The export download route authorizes before readiness checks or redirects, rejects malformed download_urls, blocks unsafe /uploads/file/data/javascript artifact URLs with PHI-safe structured diagnostics, preserves the inline completed-format fallback when no artifact URL exists, and only redirects safe cached URLs after authorization. Tests were updated to assert raw export metadata persistence, owner/admin behavior, foreign-user denial without Location leakage, status URL sanitization, and owner fail-closed behavior for legacy private artifact URLs. The previous auto-fix failure was also verified as a command working-directory issue by rerunning the same pytest subset from backend-hormonia.

## Verification

Ran the targeted export ownership regression, reran the previously failing builder/sharing/public_link/history/restore subset from the backend directory, ran the full report ownership closure suite, and ran the complete T05 verification command covering export ownership plus enhanced report compatibility and report service task compatibility. All commands passed. Pytest still emits an existing pytest-asyncio loop-scope deprecation warning, but no test failures or task-specific runtime warnings remain.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "export" -q` | 0 | ✅ pass | 25466ms |
| 2 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "builder or sharing or public_link or history or restore" -q` | 0 | ✅ pass | 24929ms |
| 3 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -q` | 0 | ✅ pass | 24883ms |
| 4 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "export" -q && pytest tests/api/v2/test_enhanced_reports.py tests/services/test_report_service_task_compat.py -q` | 0 | ✅ pass | 49997ms |

## Deviations

None.

## Known Issues

Pytest emits an existing pytest-asyncio configuration deprecation warning about asyncio_default_fixture_loop_scope being unset; this task did not change that project-level test setting.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
