# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** Milestone v1.1 — Architecture & Observability (defining requirements)

## Current Position

Phase: 08-ai-rationalization
Plan: 02 complete (2 of 2 phase-08 plans complete)
Status: Phase 08 complete — 08-01 and 08-02 done
Last activity: 2026-02-23 — Completed 08-02: Circuit breaker exception type fix (FeatureNotAvailableError on circuit-open in GeminiClient, 4 unit tests, AI-04 satisfied)

Progress: [██████████] 100% (2 of 2 phase-08 plans complete)

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

**Phase 07-01 decisions (2026-02-23):**
- Secrets never as Celery task args — env var names passed as args, values read inside task body via os.environ (prevents PHI appearing in broker/backend logs)
- has_more detection via last_batch_size == chunk_size after while loop exits — handles max_patients exact-boundary edge case
- Per-patient errors counted/logged but do not abort batch — allows partial success and safe resume
- rotate_encryption_key() only updates in-memory keys, explicitly delegates DB re-encryption to lgpd.batch_reencrypt_patients Celery task

**Phase 08-02 decisions (2026-02-23):**
- Import FeatureNotAvailableError from app.core.exceptions (not re-defined locally) — single source of truth
- Positional args for FeatureNotAvailableError constructor: (message, graph_name='gemini', operation='generate_content') — matches __init__ signature
- Test uses GeminiClient.__new__() with minimal manual init to avoid real API/Redis calls in unit tests
- Monkeypatch call_gemini on circuit breaker instance (not class) to isolate the exact used_fallback=True path
- Stale .pyc files from 08-01 caused router ImportError — cleared bytecode cache to unblock tests (no source change needed)

## Session Continuity

Last session: 2026-02-23
Stopped at: Completed 08-02-PLAN.md (Circuit breaker exception type fix — AI-04 satisfied)
Resume file: /gsd:execute-phase 09 (if next phase exists)
