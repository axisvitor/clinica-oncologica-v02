# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** Milestone v1.1 — Architecture & Observability (defining requirements)

## Current Position

Phase: 06-async-hot-path-migration
Plan: 01 complete (ASYNC-01 done)
Status: In progress — 06-01 and 06-03 complete, 06-02/05 remaining
Last activity: 2026-02-23 — Completed 06-01: SequentialMessageHandler AsyncSession migration (12 TODOs)

Progress: [████░░░░░░] ~50% (2 of ~4 phase-06 plans complete)

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

### Pending Todos

None.

### Blockers/Concerns

Carried forward from v1.0 (relevant to v1.1):
- [Research flag] Phase 6: AsyncSession migration for flow_core.py (7 TODOs) — plan 06-02 pending
- [Research flag] Phase 6: Saga orchestrator compensation+steps (ASYNC-05) — plan 06-05 pending
- [Research flag] Phase 9: WebSocket multi-instance gap between redis_pubsub_manager.py and WebSocket connection manager not fully characterized
- [Research gap] Phase 9: Physician availability slots model (what constitutes an available slot) is not documented in codebase

RESOLVED (2026-02-22):
- enhanced_quiz_service.py (8 TODOs) — DONE in 06-03

RESOLVED (2026-02-23):
- sequential_message_handler.py (12 TODOs) — DONE in 06-01

## Session Continuity

Last session: 2026-02-23
Stopped at: Completed 06-01-PLAN.md (SequentialMessageHandler AsyncSession migration)
Resume file: /gsd:execute-phase 06 (next plan: 06-02 flow_core.py or 06-05 saga orchestrator)
