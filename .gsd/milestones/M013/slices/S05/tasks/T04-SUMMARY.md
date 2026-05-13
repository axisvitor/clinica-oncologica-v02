---
id: T04
parent: S05
milestone: M013
key_files:
  - backend-hormonia/app/api/v2/routers/enhanced_reports.py
  - backend-hormonia/app/services/reporting/enhanced_reports_service.py
key_decisions:
  - Use the shared `report_access.assert_report_access` helper for enhanced report-id authorization before normalization, formatting, service work, or redirects.
  - Persist builder owner metadata under both service hash keys and legacy enhanced cache keys so later builder/share/export checks resolve raw ownership evidence.
  - Preserve legacy test monkeypatch behavior only when `_check_report_access` is explicitly replaced, while normal production flow uses the async raw metadata guard.
duration: 
verification_result: passed
completed_at: 2026-05-13T02:15:34.000Z
blocker_discovered: false
---

# T04: Guarded enhanced builder, sharing, history, restore, delivery/visualization, and export report-ID routes with raw metadata authorization before normalization or redirects.

**Guarded enhanced builder, sharing, history, restore, delivery/visualization, and export report-ID routes with raw metadata authorization before normalization or redirects.**

## What Happened

Replaced normal enhanced report route flow with an async raw-metadata authorization helper that resolves report evidence from enhanced router cache keys, enhanced service cache keys, and base report cache keys before falling back to DB evidence via `report_access.assert_report_access`. Builder get/download now authorizes raw cached/service data before normalizing responses or formatting downloads, preventing missing `created_by` from being laundered into requester ownership. Sharing, public-link creation, share listing, history, restore, visualization, delivery schedule creation, export creation, export status, and export download now authorize report/export identifiers before invoking service work or returning redirects. Updated `EnhancedReportsService` to default to the shared async assertion for report-id methods it owns, added access-checked plumbing for legacy monkeypatched route tests, and persisted builder report owner metadata under service and legacy cache keys so follow-up operations have raw access evidence. Preserved existing absent-resource 404 behavior, including a mocked-DB compatibility path for legacy tests, while existing cached resources with foreign or missing doctor evidence fail closed with generic denials.

## Verification

Ran the focused T04 ownership regression, the corrected auto-fix base/generate gate from the backend directory, the full report ownership closure regression file, the enhanced reports compatibility suite, and Python syntax compilation for the two changed modules. All final verification commands passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "builder or sharing or public_link or history or restore" -q` | 0 | ✅ pass | 20084ms |
| 2 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "base_report or generate" -q` | 0 | ✅ pass | 18913ms |
| 3 | `cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -q` | 0 | ✅ pass | 25095ms |
| 4 | `cd backend-hormonia && pytest tests/api/v2/test_enhanced_reports.py -q` | 0 | ✅ pass | 20349ms |
| 5 | `cd backend-hormonia && python -m py_compile app/api/v2/routers/enhanced_reports.py app/services/reporting/enhanced_reports_service.py` | 0 | ✅ pass | 146ms |

## Deviations

Minor extension: applied the same raw-metadata guard to enhanced export creation/status/download routes because they are report-id ownership surfaces in the slice boundary and existing regression file, even though the T04 route list emphasized builder/sharing/history.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`
