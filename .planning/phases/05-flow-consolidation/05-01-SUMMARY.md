---
phase: 05-flow-consolidation
plan: 01
subsystem: api
tags: [flow, qw-021, dispatcher, feature-flags, patient-flow, enrollment]

# Dependency graph
requires:
  - phase: 04-ai-reliability
    provides: AI invocation wrapper and LangGraph reliability fixes (unblocks flow consolidation work)
provides:
  - FlowDispatcher facade at app/services/dispatcher.py routing enrollment to canonical production system
  - FlowFeatureFlags with patient-type routing fields (canonical_system, route_new/existing_patients_to_canonical, log_dispatcher_routing)
  - QW-021 package fully deleted (27 app files + 7 test files)
  - service_provider.flow_service returning FlowDispatcher instead of FlowManager
  - flow/__init__.py with production-relevant exports only (analytics, templates, types, config)
affects:
  - 05-02 (next plan in Phase 5 flow consolidation)
  - 06-async-migration (async patient flow operations now route through FlowDispatcher)
  - Any code calling services.flow_service (now gets FlowDispatcher, not FlowManager)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FlowDispatcher facade pattern: enrollment routing via thin facade, lazy imports, feature-flag-controlled logging"
    - "Full code deletion (not tombstone): QW-021 package deleted with git rm -r per user decision"
    - "service_provider lazy-import pattern: TYPE_CHECKING import for type hints, runtime import inside property"

key-files:
  created:
    - backend-hormonia/app/services/dispatcher.py
  modified:
    - backend-hormonia/app/services/flow/config.py
    - backend-hormonia/app/services/flow/__init__.py
    - backend-hormonia/app/service_provider.py
    - backend-hormonia/app/dependencies/service_dependencies.py
    - backend-hormonia/app/services/webhook/handlers/message_handler.py

key-decisions:
  - "Full code deletion (not tombstone) for QW-021: per user decision — zero callers outside package itself confirmed before deletion"
  - "FlowDispatcher is enrollment-only: does NOT wrap advance_flow, pause, resume — those go directly to production services"
  - "FlowFeatureFlags replaced percentage-based rollout with patient-type routing: route_new_patients_to_canonical / route_existing_patients_to_canonical"
  - "message_handler.py FlowEngine import was dead code: FlowEngine(db) set to self.flow_engine but never called — removed cleanly"
  - "FlowConfig.is_consolidated_enabled() replaced with is_canonical_system_production(): reflects post-QW-021 reality"

patterns-established:
  - "Pattern: FlowDispatcher facade — all new patient flow enrollment calls route through dispatcher.initialize_flow() not directly to PatientFlowService"
  - "Pattern: Lazy imports in FlowDispatcher methods — same as service_provider.py convention"

requirements-completed:
  - FLOW-01
  - FLOW-02

# Metrics
duration: 12min
completed: 2026-02-22
---

# Phase 5 Plan 01: Flow Consolidation — QW-021 Deletion Summary

**FlowDispatcher enrollment facade created, QW-021 package (27 app files, 7 test files, ~11,000 LOC) fully deleted via git rm, production flow system is sole canonical**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-22T21:53:56Z
- **Completed:** 2026-02-22T22:05:00Z
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 modified, 34 deleted)

## Accomplishments

- Created FlowDispatcher facade at `app/services/dispatcher.py` with patient-type routing, audit logging, and lazy imports
- Replaced FlowFeatureFlags percentage-based rollout with patient-type routing fields (4 fields: canonical_system, route_new, route_existing, log_dispatcher_routing)
- Deleted entire QW-021 package: 5 subdirectories (core, errors, execution, integrations, validation) + manager.py — 27 source files totaling ~10,992 LOC
- Deleted 7 QW-021 test files (tests/services/flow/core/, tests/services/flow/integrations/)
- Updated service_provider.py: flow_service now returns FlowDispatcher; TYPE_CHECKING import updated
- Fixed message_handler.py: removed dead FlowEngine import/assignment (QW-021 FlowEngine was imported but never actually called)
- Zero dangling imports verified: grep scans across entire app/ confirm no references to deleted modules

## Task Commits

Each task was committed atomically:

1. **Task 1: Create FlowDispatcher facade and update FlowFeatureFlags** - `c4fc9294` (feat)
2. **Task 2: Delete QW-021 package and update all callers** - `021aa4d6` (feat)

**Plan metadata:** (docs commit — see final_commit step)

## Files Created/Modified

- `backend-hormonia/app/services/dispatcher.py` - FlowDispatcher facade: initialize_flow(), is_new_patient(), feature-flag routing with audit logging
- `backend-hormonia/app/services/flow/config.py` - FlowFeatureFlags updated: percentage-based rollout removed, patient-type routing fields added; FlowConfig method updated
- `backend-hormonia/app/services/flow/__init__.py` - Rewrote: removed all QW-021 imports (FlowManager, FlowEngine, etc.), kept analytics/templates/types/config; updated docstring and version metadata
- `backend-hormonia/app/service_provider.py` - flow_service property returns FlowDispatcher; _flow_service type annotation updated; TYPE_CHECKING import updated
- `backend-hormonia/app/dependencies/service_dependencies.py` - get_flow_service() docstring updated to reference FlowDispatcher
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` - Removed dead FlowEngine import and unused self.flow_engine = FlowEngine(db) assignment

**Deleted (QW-021 application code — 27 files):**
- `backend-hormonia/app/services/flow/core/` (6 files: __init__, context, engine, lifecycle, manager, state_machine)
- `backend-hormonia/app/services/flow/errors/` (4 files: __init__, handler, recovery, retry)
- `backend-hormonia/app/services/flow/execution/` (5 files: __init__, conditions, executor, scheduler, transitions)
- `backend-hormonia/app/services/flow/integrations/` (6 files: __init__, ai_integration, base, manager, plugins, quiz_integration)
- `backend-hormonia/app/services/flow/validation/` (5 files: __init__, constraints, integrity, rules, validator)
- `backend-hormonia/app/services/flow/manager.py` (1 file — was shim to core.manager)

**Deleted (QW-021 test code — 7 files):**
- `backend-hormonia/tests/services/flow/core/` (3 files: __init__, test_engine, test_error_handler)
- `backend-hormonia/tests/services/flow/integrations/` (4 files: __init__, test_ai_integration, test_manager, test_quiz_integration)

## Decisions Made

- **Full deletion not tombstone:** User decision confirmed in plan. Zero production callers outside QW-021 package itself verified before deletion.
- **Dispatcher is enrollment-only:** FlowDispatcher wraps ONLY initialize_flow() and is_new_patient(). advance_flow, pause, resume, complete continue going directly to EnhancedFlowEngine / FlowManagementService. This keeps the facade lean.
- **FlowFeatureFlags redesign:** Dropped `use_consolidated_flows` + `consolidated_flows_rollout_percentage` + `should_use_consolidated_for_flow()`. Replaced with patient-type routing (new vs existing) and audit logging flag. Percentage-based rollout was designed for gradual QW-021 adoption; with QW-021 deleted it's meaningless.
- **message_handler.py FlowEngine fix:** The import `from app.services.flow import FlowEngine` and `self.flow_engine = FlowEngine(db)` were dead code — `self.flow_engine` was assigned but never called; all actual engine calls used `self.enhanced_flow_engine`. Removed cleanly (Rule 1 - Bug: dead import blocking deletion).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed dead FlowEngine import from message_handler.py**

- **Found during:** Task 2 (Delete QW-021 package and update all callers)
- **Issue:** `message_handler.py` imported `FlowEngine` from `app.services.flow` (QW-021 package) and assigned `self.flow_engine = FlowEngine(db)`, but `self.flow_engine` was never called anywhere in the handler — all actual flow engine operations used `self.enhanced_flow_engine`. The import would have raised `ImportError` after the QW-021 deletion.
- **Fix:** Removed the `from app.services.flow import FlowEngine` import line and the `self.flow_engine = FlowEngine(db)` assignment. The dead field `self.flow_engine` was never referenced anywhere else in the file.
- **Files modified:** `backend-hormonia/app/services/webhook/handlers/message_handler.py`
- **Verification:** `grep -rn "FlowEngine" app/ --include="*.py"` returns zero results for live imports; message_handler import verification passes.
- **Committed in:** `021aa4d6` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — dead import bug)
**Impact on plan:** The auto-fix was necessary to complete Task 2. The dead import would have caused an ImportError after deletion. No scope creep — fix is entirely contained in message_handler.py.

## Issues Encountered

- Pre-existing test failure `test_idempotency_rbac_denies_other_doctor` due to missing `messaging_stopped_at` column in test DB (added in Phase 2 LGPD migration, not applied to test env). Unrelated to this plan's changes. Flow-specific tests (analytics, templates) all pass: 151 passed.

## User Setup Required

None - no external service configuration required. All changes are internal code refactoring.

## Next Phase Readiness

- FlowDispatcher is ready to receive enrollment routing calls
- Production flow system (flow_core.py / EnhancedFlowEngine / PatientFlowService) is confirmed as sole canonical path
- Phase 5 Plan 02 can proceed: any remaining flow consolidation work (analytics refactor, monitoring, sequential_message_handler cleanup)
- Phase 6 (Async Migration) can proceed knowing flow enrollment is routed cleanly through FlowDispatcher

---
*Phase: 05-flow-consolidation*
*Completed: 2026-02-22*
