---
estimated_steps: 36
estimated_files: 4
skills_used: []
---

# T04: Guard enhanced builder, sharing, and history routes before normalization

---
estimated_steps: 9
estimated_files: 2
skills_used:
  - api-design
  - security-review
  - verify-before-complete
---

Why: Enhanced report builder, sharing, public-link, share-listing, history, and restore paths currently rely on a permissive `_check_report_access()` or no check, and builder normalization can default missing `created_by` to the requester.

Files:
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`

Do:
1. Replace the router-level synchronous `_check_report_access()` boolean with an async raw-metadata guard that resolves the report record from router cache/service cache/DB fallback before normalization.
2. In `get_builder_report()` and `download_builder_report()`, load raw cached/service data, authorize it with the shared helper, then normalize/format only after access is proven.
3. In `create_visualization()`, `create_delivery_schedule()`, `share_report()`, `create_public_link()`, `list_report_shares()`, `get_report_history()`, and `restore_report_version()`, authorize the referenced report_id via the async guard before invoking service methods or returning mock lists.
4. Update `EnhancedReportsService` to use an async shared assertion instead of the permissive service `_check_report_access()` in share/public-link/history/restore and other report-id methods it owns.
5. Make `build_custom_report()` persist raw owner metadata (`created_by`) in a cache key that follow-up get/download/share/export checks can resolve, without relying on normalized defaults.
6. Preserve admin behavior for existing reports; preserve owner behavior for valid cached/service builder records.
7. For absent resources, keep existing 404-style behavior where the resource truly does not exist; for existing resources with foreign or missing evidence, return generic 403.
8. Do not include patient names, raw data rows, private paths, tokens, or download URLs in denial messages/logs.
9. Keep existing route response models and public API shapes stable for legitimate callers.

Failure Modes (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|-----------------------|
| Enhanced report cache/service lookup | missing report remains 404; existing report with no access proof is 403 | request timeout applies | missing/malformed created_by fails closed, not requester-defaulted |
| DB fallback | fail closed/generic denial when patient assignment cannot be proven | request timeout applies | malformed DB/cache IDs fail closed |

Load Profile (Q6):
- Shared resources: Redis cache and DB session through `EnhancedReportsService`.
- Per-operation cost: one or two cache lookups plus optional DB fallback/patient query before service work.
- 10x breakpoint: cache/DB lookup pressure on report-id endpoints; authorization must short-circuit before report/export work.

Negative Tests (Q7):
- Malformed inputs: missing `created_by`, invalid owner UUID, missing report metadata.
- Error paths: foreign doctor for builder get/download/share/history/restore/public-link/list shares.
- Boundary conditions: owner/admin success, absent report 404, existing report without evidence 403.

Done when: Enhanced builder/sharing/history portions of the S05 regression tests pass and normalization can no longer launder missing owner metadata into access.

## Inputs

- `backend-hormonia/app/services/reporting/report_access.py`
- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`
- `backend-hormonia/tests/api/v2/test_report_ownership_closure.py`
- `backend-hormonia/tests/api/v2/test_enhanced_reports.py`
- `backend-hormonia/app/schemas/v2/enhanced_reports.py`

## Expected Output

- `backend-hormonia/app/api/v2/routers/enhanced_reports.py`
- `backend-hormonia/app/services/reporting/enhanced_reports_service.py`

## Verification

cd backend-hormonia && pytest tests/api/v2/test_report_ownership_closure.py -k "builder or sharing or public_link or history or restore" -q

## Observability Impact

Denials for enhanced report operations become attributable to report_id/user_id/role/reason before service work or normalization, making missing-owner and foreign-owner failures inspectable without PHI leakage.
