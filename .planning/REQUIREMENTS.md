# Requirements: Clinica Oncologica

**Defined:** 2026-02-24
**Core Value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## v1.3 Requirements

Requirements for v1.3 Flow Health & Cleanup. Each maps to roadmap phases.

### Critical Fixes

- [x] **FIX-01**: Pause detection uses `state_data.paused` consistently across daily processor and flow management
- [x] **FIX-02**: Auto-resume Celery Beat job checks `auto_resume_at` timestamps and resumes expired pauses
- [ ] **FIX-03**: Cancel flow implemented in flow_management with cleanup of pending messages and state reset
- [ ] **FIX-04**: Quiz template missing triggers graceful fallback (skip quiz link, send message without it) instead of ValueError
- [ ] **FIX-05**: Phase constants consolidated to single canonical source (`flow_coordinator/constants.py`), all duplicates removed
- [ ] **FIX-06**: Quiz mensal cycle calculation consolidated to single algorithm used by both flow_coordinator and sequential_message_handler
- [ ] **FIX-07**: Failed flow messages routed to DLQ with retry and monitoring integration

### Dead Code Removal

- [ ] **DEAD-01**: `flow/constants.py` tombstoned (208 LOC, 0 external imports)
- [ ] **DEAD-02**: `flow/template_lookup.py` tombstoned (18 LOC, 0 external imports)
- [ ] **DEAD-03**: `flow/analytics/` package tombstoned (4 files, 2,259 LOC, 0 production callers)
- [ ] **DEAD-04**: `flow/templates/` package tombstoned (4 files, 1,972 LOC, 0 production callers)
- [ ] **DEAD-05**: `flow/monitoring/` package tombstoned (2 files, 93 LOC, 0 production callers)

### File Splits

- [ ] **SPLIT-01**: `sequential_message_handler.py` (1,135 LOC) split into focused modules
- [ ] **SPLIT-02**: `enhanced_flow_engine.py` (1,141 LOC) split into AI orchestration + conversation memory + response processing
- [ ] **SPLIT-03**: `flow_dashboard.py` (946 LOC) split into dashboard analytics + trend analysis + risk detection
- [ ] **SPLIT-04**: `flow_monitoring.py` (923 LOC) split into metrics + health checks + recovery
- [ ] **SPLIT-05**: `_flow_functions.py` (887 LOC) split into message flow + response flow + orchestration utils
- [ ] **SPLIT-06**: `flow_core.py` (882 LOC) split into base operations + phase transitions + template binding
- [ ] **SPLIT-07**: `flow_management.py` (694 LOC) split into state management + advancement + pause/resume
- [ ] **SPLIT-08**: `saga/orchestrator.py` (645 LOC) split into main orchestrator + step executor + metrics
- [ ] **SPLIT-09**: `saga/compensation.py` (573 LOC) split into compensation chain + step handlers
- [ ] **SPLIT-10**: `flow_integrity.py` (559 LOC) split into corruption detection + recovery actions

## Future Requirements

### Deferred

- **ASYNC-01**: Full AsyncSession migration for remaining 42+ sync-in-async methods
- **PHYS-01**: Physician availability hours preferences model (replace hardcoded Mon-Fri 08-17)
- **ADK-01**: Google ADK integration (pending dependency conflict resolution)

## Out of Scope

| Feature | Reason |
|---------|--------|
| New flow types | v1.3 is cleanup, not new capabilities |
| Frontend changes | Backend-only milestone |
| WhatsApp provider migration | Evolution API integration is stable |
| Database schema changes | No new models needed for cleanup work |
| Full async migration | Too large (42+ methods, 65+ files); hot paths already covered |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FIX-01 | Phase 14 | Complete |
| FIX-02 | Phase 14 | Complete |
| FIX-03 | Phase 14 | Pending |
| FIX-04 | Phase 15 | Pending |
| FIX-05 | Phase 15 | Pending |
| FIX-06 | Phase 15 | Pending |
| FIX-07 | Phase 15 | Pending |
| DEAD-01 | Phase 16 | Pending |
| DEAD-02 | Phase 16 | Pending |
| DEAD-03 | Phase 16 | Pending |
| DEAD-04 | Phase 16 | Pending |
| DEAD-05 | Phase 16 | Pending |
| SPLIT-05 | Phase 17 | Pending |
| SPLIT-06 | Phase 17 | Pending |
| SPLIT-07 | Phase 17 | Pending |
| SPLIT-01 | Phase 18 | Pending |
| SPLIT-02 | Phase 18 | Pending |
| SPLIT-03 | Phase 18 | Pending |
| SPLIT-04 | Phase 18 | Pending |
| SPLIT-08 | Phase 19 | Pending |
| SPLIT-09 | Phase 19 | Pending |
| SPLIT-10 | Phase 19 | Pending |

**Coverage:**
- v1.3 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 — traceability mapped to phases 14-19*
