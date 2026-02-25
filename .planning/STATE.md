---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Flow Health & Cleanup
status: unknown
last_updated: "2026-02-25T17:36:36.837Z"
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 15
  completed_plans: 15
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** Phase 17 — Flow Core Splits

## Current Position

Phase: 17 of 19 — v1.3 active (Flow Core Splits)
Plan: 17-04 complete (4/4) — phase complete
Status: Phase 17 complete
Last activity: 2026-02-25 — completed 17-04 test-schema guard + full-suite blocker refresh

Progress: v1.0 ██████████ 100% | v1.1 ██████████ 100% | v1.2 ██████████ 100% | v1.3 ██████████ 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 46 (v1.0: 13, v1.1: 10, v1.2: 16, v1.3: 8)
- Total execution time: 3 days (v1.0: 1 day, v1.1: 1 day, v1.2: 1 day)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| v1.0 (phases 1-5) | 13 | 1 day | - |
| v1.1 (phases 6-9) | 10 | 1 day | - |
| v1.2 (phases 10-13) | 16 | 1 day | ~8 min |
| Phase 14 P01 | 9 min | 2 tasks | 4 files |
| Phase 14 P02 | 1 min | 2 tasks | 3 files |
| Phase 14 P03 | 10 min | 2 tasks | 5 files |
| Phase 15-data-integrity-fixes P02 | 3 min | 2 tasks | 3 files |
| Phase 15 P01 | 3 min | 2 tasks | 4 files |
| Phase 15 P03 | 7 min | 2 tasks | 4 files |
| Phase 15-data-integrity-fixes P05 | 5 min | 2 tasks | 3 files |
| Phase 15-data-integrity-fixes P04 | 19 min | 2 tasks | 3 files |
| Phase 16 P01 | 22 min | 2 tasks | 3 files |
| Phase 16 P02 | 15 min | 2 tasks | 9 files |
| Phase 16 P03 | 26 min | 2 tasks | 16 files |
| Phase 17 P01 | 8 min | 2 tasks | 6 files |
| Phase 17 P02 | 5 min | 2 tasks | 7 files |
| Phase 17-flow-core-splits P03 | 9 min | 2 tasks | 8 files |
| Phase 17-flow-core-splits P04 | 5 min | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
All v1.2 decisions archived in milestones/v1.2-ROADMAP.md.

Recent decisions affecting v1.3:
- Phase 15 before 17: FIX-05 (constants consolidation) must complete before SPLIT-06 (flow_core split uses those constants)
- Phase 16 before 17: dead imports cleared before core layer refactor to avoid re-exporting tombstoned paths
- Shim pattern mandatory for all splits: old paths kept as re-export shims for backward compat
- [Phase 14]: Pause detection contract standardized on state_data.paused across flow services and daily processor
- [Phase 14]: Re-pausing an already paused flow is idempotent and refreshes auto_resume_at when duration is provided
- [Phase 14]: Auto-resume query now requires state_data.auto_resume_at and expired timestamp instead of updated_at age
- [Phase 14]: resume_paused_flows uses FlowManagementService.resume_patient_flow to keep state_data pause semantics consistent
- [Phase 14]: Cancel overrides paused state directly and finalizes the current flow instance by setting completed_at.
- [Phase 14]: Cancellation revokes queued Celery tasks from message metadata and marks pending/scheduled outbound messages as cancelled.
- [Phase 15-data-integrity-fixes]: Quiz template resolution in trigger flow now fails soft (fallback metadata + warning log) instead of raising.
- [Phase 15-data-integrity-fixes]: Monthly quiz link integration validates template existence before link creation and returns graceful fallback payload when missing.
- [Phase 15]: Cycle arithmetic centralized in flow_coordinator constants via compute_cycle_number
- [Phase 15]: QuizTriggerPolicy monthly cycle now delegates to canonical compute_cycle_number
- [Phase 15]: TemplateVariableProcessor uses canonical monthly constants imports instead of class-local copies
- [Phase 15]: Use existing FailureReason enum values (MAX_RETRIES_EXCEEDED/UNKNOWN) to avoid DB enum drift.
- [Phase 15]: Keep DLQ routing non-fatal so delivery-task failure reporting remains deterministic.
- [Phase 15-data-integrity-fixes]: HiveMindIntegrationService LangGraph routing now delegates flow/day boundaries to canonical resolve_flow_type_and_day.
- [Phase 15-data-integrity-fixes]: ManualCorrectionService monthly reset path now derives cycle/day via canonical compute_cycle_number and shared phase constants.
- [Phase 15-data-integrity-fixes]: Missing-template fallback now sends a no-link patient WhatsApp message through existing unified messaging infrastructure.
- [Phase 15-data-integrity-fixes]: Quiz trigger template-missing path now returns success with continue_flow marker to avoid terminal error classification.
- [Phase 16]: Use Phase 12 ImportError tombstone sentinel pattern for dead flow modules
- [Phase 16]: Keep pre-existing flow package import interception deferred to avoid widening 16-01 scope
- [Phase 16]: Kept flow analytics package as ImportError tombstones to preserve migration guidance while removing dead runtime code.
- [Phase 16]: Tombstoned analytics test modules with module-level skips and placeholder tests so pytest reports explicit skips.
- [Phase 16]: Tombstoned flow templates and flow monitoring with ImportError sentinels while preserving migration guidance in-module.
- [Phase 16]: Guarded FlowTemplateValidator-specific version-standardization tests with skipif so non-template version compatibility checks continue post-tombstone.
- [Phase 17]: Kept _flow_functions.py as a strict compatibility shim with explicit __all__ to preserve legacy imports.
- [Phase 17]: Centralized shared state validation, thread-id checks, send-mode parsing, and context mismatch helpers in _flow_orchestration_utils.py.
- [Phase 17]: FlowCore now composes three responsibility-specific mixins behind app.services.flow.core.service
- [Phase 17]: Legacy app.services.flow_core remains a re-export shim for FlowCore, exceptions, and block constants
- [Phase 17-flow-core-splits]: Composed FlowManagementService through state/advancement/pause-resume mixins under app.services.flow.management.service
- [Phase 17-flow-core-splits]: Preserved app.services.flow_management shim patch hooks (EnhancedFlowEngine and now_sao_paulo) for lifecycle regression compatibility
- [Phase 17-flow-core-splits]: Apply non-destructive fixture-time Postgres schema patching (ALTER TABLE ... IF NOT EXISTS) instead of table rebuilds
- [Phase 17-flow-core-splits]: Treat new AssertionError (422 vs 403) as the next deferred blocker after removing the original UndefinedColumn failure

### Pending Todos

None.

### Blockers/Concerns

Carried tech debt (not v1.3-scoped):
- Full AsyncSession migration (42+ remaining methods) — hot paths cover ~80% throughput
- Physician availability hours model — hardcoded defaults
- PromptedOutput validation confidence against gemini-2.5-flash is MEDIUM
- 60+ files >500 lines total; v1.3 addresses 10 of them
- Full backend suite currently fails in tests/api/critical/test_patient_security_fixes.py::TestPatientSecurityFixes::test_idempotency_rbac_denies_other_doctor with AssertionError (422 != 403); schema-missing-column path is fixed and next blocker is AsyncSession query mismatch in validation path.

## Session Continuity

Last session: 2026-02-25
Stopped at: Completed 17-flow-core-splits-04-PLAN.md
Resume file: None
