---
phase: 16-dead-code-removal
plan: 03
subsystem: api
tags: [dead-code, tombstone, flow, templates, monitoring, pytest]

requires:
  - phase: 16-02
    provides: flow analytics tombstones and test tombstone pattern baseline
provides:
  - tombstoned flow templates and monitoring packages with migration ImportErrors
  - cleaned flow package exports limited to config and types
  - tombstoned template-oriented test modules with module-level skips
affects: [phase-17-flow-core-splits, flow-import-surface, test-collection]

tech-stack:
  added: []
  patterns: [importerror-tombstone-sentinel, module-level-pytest-skip-for-tombstoned-tests]

key-files:
  created:
    - .planning/phases/16-dead-code-removal/deferred-items.md
  modified:
    - backend-hormonia/app/services/flow/__init__.py
    - backend-hormonia/app/services/flow/templates/__init__.py
    - backend-hormonia/app/services/flow/templates/manager.py
    - backend-hormonia/app/services/flow/templates/validator.py
    - backend-hormonia/app/services/flow/templates/repository.py
    - backend-hormonia/app/services/flow/monitoring/__init__.py
    - backend-hormonia/app/services/flow/monitoring/dashboard.py
    - backend-hormonia/tests/services/flow/templates/test_validator_graph.py
    - backend-hormonia/tests/services/flow/templates/test_validator_transitions.py
    - backend-hormonia/tests/services/flow/templates/test_manager.py
    - backend-hormonia/tests/services/flow/templates/test_repository.py
    - backend-hormonia/tests/services/flow/templates/_template_test_utils.py
    - backend-hormonia/tests/unit/services/flow/templates/test_template_validator.py
    - backend-hormonia/tests/unit/services/flow/templates/test_template_repository.py
    - backend-hormonia/tests/services/test_version_standardization.py

key-decisions:
  - "Tombstoned flow templates and flow monitoring using phase-specific ImportError sentinel modules rather than file deletion."
  - "Kept non-template version-standardization tests active by conditionally skipping only FlowTemplateValidator assertions when tombstone imports are unavailable."

patterns-established:
  - "When decommissioning a package, convert dependent test modules to module-level pytest skips to avoid collection-time ImportError noise."

requirements-completed: [DEAD-04, DEAD-05]

duration: 26 min
completed: 2026-02-25
---

# Phase 16 Plan 03: Templates + Monitoring Tombstone Summary

**Flow templates and flow monitoring packages were fully tombstoned with migration ImportErrors while `app.services.flow` exports were reduced to config/types and dependent template test suites were safely skipped.**

## Performance

- **Duration:** 26 min
- **Started:** 2026-02-25T02:19:50Z
- **Completed:** 2026-02-25T02:46:32Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments
- Replaced all 4 `app/services/flow/templates/` modules and 2 `app/services/flow/monitoring/` modules with tombstone ImportError sentinels and migration guidance.
- Cleaned `app/services/flow/__init__.py` to remove analytics/templates re-export imports and dead `__all__` symbols, preserving only config/types public surface.
- Tombstoned 7 template test modules and guarded `tests/services/test_version_standardization.py` so non-template version checks continue while validator-specific tests auto-skip.
- Verified fixed-string grep checks report zero production imports of all five tombstoned locations.

## Task Commits

Each task was committed atomically:

1. **Task 1: Tombstone templates + monitoring source packages and clean flow exports** - `ff1d3eb2` (fix)
2. **Task 2: Tombstone template test modules and patch version-standardization imports** - `f71934a4` (test)

**Plan metadata:** pending

## Files Created/Modified
- `backend-hormonia/app/services/flow/templates/__init__.py` - package tombstone with migration path to `template_loader_pkg` and `flow_template`.
- `backend-hormonia/app/services/flow/templates/manager.py` - module tombstone sentinel.
- `backend-hormonia/app/services/flow/templates/validator.py` - module tombstone sentinel.
- `backend-hormonia/app/services/flow/templates/repository.py` - module tombstone sentinel.
- `backend-hormonia/app/services/flow/monitoring/__init__.py` - package tombstone redirecting to `app.services.flow_monitoring`.
- `backend-hormonia/app/services/flow/monitoring/dashboard.py` - module tombstone sentinel.
- `backend-hormonia/app/services/flow/__init__.py` - removed analytics/template imports and exports.
- `backend-hormonia/tests/services/flow/templates/test_validator_graph.py` - module-level skip for tombstoned package.
- `backend-hormonia/tests/services/flow/templates/test_validator_transitions.py` - module-level skip for tombstoned package.
- `backend-hormonia/tests/services/flow/templates/test_manager.py` - module-level skip for tombstoned package.
- `backend-hormonia/tests/services/flow/templates/test_repository.py` - module-level skip for tombstoned package.
- `backend-hormonia/tests/services/flow/templates/_template_test_utils.py` - module-level skip for tombstoned package.
- `backend-hormonia/tests/unit/services/flow/templates/test_template_validator.py` - module-level skip for tombstoned package.
- `backend-hormonia/tests/unit/services/flow/templates/test_template_repository.py` - module-level skip for tombstoned package.
- `backend-hormonia/tests/services/test_version_standardization.py` - import guard + class-level skip for validator tests.
- `.planning/phases/16-dead-code-removal/deferred-items.md` - out-of-scope failing full-suite item logged.

## Decisions Made
- Maintained tombstone files in place instead of deletion for discoverable migration guidance on direct imports.
- Used class-level `skipif` in version-standardization tests to keep loader compatibility checks running while template-validator-specific assertions are skipped post-tombstone.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected tombstoned import verification to fixed-string matching**
- **Found during:** Task 2 (cross-cutting production-import verification)
- **Issue:** Regex-style `grep` check treated dots as wildcards and falsely matched `app.services.flow_monitoring` as `app.services.flow.monitoring`.
- **Fix:** Re-ran verification with fixed-string matching (`grep -F`) to validate actual import paths.
- **Files modified:** None (execution-only fix)
- **Verification:** Fixed-string check passed with zero production imports for all five tombstoned paths.
- **Committed in:** N/A (no file change)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Verification was tightened to avoid false positives; planned code scope and deliverables remained unchanged.

## Issues Encountered
- Full `pytest` run failed outside this plan scope due test DB schema drift (`patients.messaging_stopped_at` missing) in `tests/api/critical/test_patient_security_fixes.py`; logged to `.planning/phases/16-dead-code-removal/deferred-items.md` and not modified in this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 16 tombstoned import surface is complete across constants, template lookup, analytics, templates, and monitoring.
- `app.services.flow` public API no longer re-exports dead analytics/templates symbols, clearing prerequisite import hygiene for Phase 17 splits.

---
*Phase: 16-dead-code-removal*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: `.planning/phases/16-dead-code-removal/16-03-SUMMARY.md`
- FOUND: `ff1d3eb2`
- FOUND: `f71934a4`
