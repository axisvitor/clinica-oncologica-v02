# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** Phase 15 — Data Integrity Fixes

## Current Position

Phase: 15 of 19 — v1.3 active (Data Integrity Fixes)
Plan: In progress (2/3 complete) — remaining 15-03-PLAN.md
Status: Phase 15 in progress
Last activity: 2026-02-24 — completed 15-01 constants consolidation and cycle canonicalization

Progress: v1.0 ██████████ 100% | v1.1 ██████████ 100% | v1.2 ██████████ 100% | v1.3 ██░░░░░░░░ 25%

## Performance Metrics

**Velocity:**
- Total plans completed: 41 (v1.0: 13, v1.1: 10, v1.2: 16, v1.3: 3)
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

### Pending Todos

None.

### Blockers/Concerns

Carried tech debt (not v1.3-scoped):
- Full AsyncSession migration (42+ remaining methods) — hot paths cover ~80% throughput
- Physician availability hours model — hardcoded defaults
- PromptedOutput validation confidence against gemini-2.5-flash is MEDIUM
- 60+ files >500 lines total; v1.3 addresses 10 of them

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 15-01-PLAN.md
Resume file: None
