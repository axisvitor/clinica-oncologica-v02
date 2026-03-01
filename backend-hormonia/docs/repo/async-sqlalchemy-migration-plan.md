# Async SQLAlchemy Migration Plan

Date: 2026-02-09
Owner: Backend
Status: In progress

## Goal

Eliminate event-loop blocking caused by synchronous SQLAlchemy access inside async code paths.

## Scope

This plan targets modules with explicit `TODO(async-migration)` markers and runtime-critical paths.

## Priority Backlog

| Priority | File | TODO(async-migration) count | Notes |
|---|---|---:|---|
| P0 | `app/services/flow/sequential_message_handler.py` | 12 | High-throughput message path |
| P0 | `app/services/enhanced_quiz_service.py` | 8 | User-facing quiz interactions |
| P0 | `app/services/flow_core.py` | 7 | Core flow orchestration |
| P1 | `app/services/flow_alerts.py` | 5 | Alert delivery reliability |
| P1 | `app/services/firebase_user_sync_service.py` | 5 | Sync job path |
| P1 | `app/services/data_integrity_monitoring.py` | 5 | Monitoring worker path |
| P1 | `app/orchestration/saga_orchestrator/compensation.py` | 5 | Compensation flow |
| P1 | `app/services/flow_dashboard.py` | 4 | Dashboard reads |
| P1 | `app/orchestration/saga_orchestrator/steps.py` | 3 | Saga execution path |

## Migration Strategy

1. Introduce async repository interfaces for each bounded context.
2. Keep router/service API stable while replacing internals incrementally.
3. Use dual-path adapters during migration:
   - async implementation as default
   - sync fallback only where needed
4. Remove fallback path after parity tests pass.

## Execution Phases

### Phase 1: Foundation

- Standardize async session dependency usage (`get_async_db`).
- Create per-domain repository protocols with async signatures.
- Add tracing around DB calls (latency and blocking indicators).

### Phase 2: P0 Services

- Migrate `sequential_message_handler`, `enhanced_quiz_service`, `flow_core`.
- Replace sync `.query()/.execute()/.commit()` calls with async equivalents.
- Add regression tests for:
  - success path
  - retry/error path
  - concurrent request behavior

### Phase 3: P1 Services

- Migrate alert, dashboard, saga, integrity monitoring, and firebase sync modules.
- Remove `TODO(async-migration)` markers as each file is completed.

### Phase 4: Hardening

- Run performance baseline before/after.
- Ensure no sync DB calls remain in async methods.
- Add CI check to fail on new `TODO(async-migration)` in production code.

## Definition of Done

- Zero `TODO(async-migration)` in `app/`.
- No sync SQLAlchemy usage inside async functions in migrated modules.
- Targeted tests pass for each migrated module.
- No P0/P1 regression in latency and error rate.

