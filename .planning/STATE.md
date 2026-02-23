# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** Milestone v1.1 — Architecture & Observability (defining requirements)

## Current Position

Phase: 06-async-hot-path-migration
Plan: 05 (next after 06-02 complete)
Status: In progress — 06-01, 06-02, 06-03, 06-04 complete, 06-05 remaining
Last activity: 2026-02-23 — Completed 06-02: FlowCore AsyncSession migration (7 TODOs in flow_core.py + flows router DI update)

Progress: [████████░░] ~80% (4 of ~5 phase-06 plans complete)

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
v1.0 key decisions preserved in PROJECT.md and milestone archive.

**Phase 06 decisions (2026-02-22):**
- Named stmt variables for complex async queries (join + filter + options) before passing to await self.db.execute(stmt)
- selectinload for one-to-many relationships; joinedload for many-to-one — prevents cartesian product with AsyncSession
- Delete loop: per-row await self.db.delete(obj) required; bulk query.delete() not supported same way in async
- Count queries: select(func.count()).select_from(stmt.subquery()) — only async-compatible count pattern

**Phase 06-01 decisions (2026-02-23):**
- Inline FlowStateRepository.get_active_flow() as direct select() query to avoid converting the entire sync repository
- Convert _set_flow_progress() from sync def to async def when it calls await self.db.commit()
- coordinator.py and hive_mind_integration.py Hive-Mind agent paths keep sync Session with documented comments for follow-up
- Add Session import back to webhooks.py alongside AsyncSession for non-migrated handler signatures to avoid NameError
- [Phase 06-async-hot-path-migration]: SagaCompensator/SagaStepExecutor db typed as Any to accept both sync/async sessions; PatientRepository methods inlined as async select() for AsyncSession compat; SagaOrchestrator direct sync calls documented as known gap per ASYNC-05 scope

**Phase 06-02 decisions (2026-02-23):**
- Dual-session DI pattern: async_db (AsyncSession) for FlowCore/EnhancedFlowEngine hot paths, sync db for FlowManagementService and FlowStateRepository (avoids MissingGreenlet on legacy .query() ORM calls)
- Shared EnhancedFlowEngine(async_db) passed to both FlowService and FlowManagementService so FlowCore inherited async methods work from both callers
- FlowManagementService sync commit: replaced calls to now-async _commit_flow_state_with_lock with direct self.db.commit() + version increment
- EnhancedFlowEngine cascade fix: process_patient_response, generate_flow_message, _get_flow_type_from_state (now async), _get_conversation_history, _get_recent_interactions all converted to await self.db.execute(select()) pattern

### Pending Todos

None.

### Blockers/Concerns

Carried forward from v1.0 (relevant to v1.1):
- [Research flag] Phase 9: WebSocket multi-instance gap between redis_pubsub_manager.py and WebSocket connection manager not fully characterized
- [Research gap] Phase 9: Physician availability slots model (what constitutes an available slot) is not documented in codebase

RESOLVED (2026-02-22):
- enhanced_quiz_service.py (8 TODOs) — DONE in 06-03
- saga_orchestrator/compensation.py (5 TODOs) + steps.py (3 TODOs) — DONE in 06-04 (ASYNC-05)

RESOLVED (2026-02-23):
- sequential_message_handler.py (12 TODOs) — DONE in 06-01
- flow_core.py (7 TODOs) + flows router DI — DONE in 06-02 (ASYNC-02)

## Session Continuity

Last session: 2026-02-23
Stopped at: Completed 06-02-PLAN.md (FlowCore AsyncSession migration — all 7 TODO sites resolved)
Resume file: /gsd:execute-phase 06 (next plan: 06-05 if any remaining)
