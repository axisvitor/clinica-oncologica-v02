# Roadmap: Clinica Oncologica — Refinamento para Producao

## Milestones

- ✅ **v1.0 Foundations** — Phases 1-5 (shipped 2026-02-22)
- ✅ **v1.1 Architecture & Observability** — Phases 6-9 (shipped 2026-02-23)
- ✅ **v1.2 AI Framework Migration** — Phases 10-13 (shipped 2026-02-24)
- 🚧 **v1.3 Flow Health & Cleanup** — Phases 14-19 (in progress)

## Phases

<details>
<summary>✅ v1.0 Foundations (Phases 1-5) — SHIPPED 2026-02-22</summary>

- [x] Phase 1: Security Hardening (3/3 plans) — completed 2026-02-22
- [x] Phase 2: LGPD Compliance (3/3 plans) — completed 2026-02-22
- [x] Phase 3: Operational Stability (3/3 plans) — completed 2026-02-22
- [x] Phase 4: AI Reliability (2/2 plans) — completed 2026-02-22
- [x] Phase 5: Flow Consolidation (2/2 plans) — completed 2026-02-22

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Architecture & Observability (Phases 6-9) — SHIPPED 2026-02-23</summary>

- [x] Phase 6: Async Hot Path Migration (4/4 plans) — completed 2026-02-23
- [x] Phase 7: LGPD Key Rotation (1/1 plan) — completed 2026-02-23
- [x] Phase 8: AI Rationalization (2/2 plans) — completed 2026-02-23
- [x] Phase 9: Observability (3/3 plans) — completed 2026-02-23

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 AI Framework Migration (Phases 10-13) — SHIPPED 2026-02-24</summary>

- [x] Phase 10: Preparation & Scope (4/4 plans) — completed 2026-02-24
- [x] Phase 11: Agent Implementation (4/4 plans) — completed 2026-02-24
- [x] Phase 12: Flow Orchestration Replacement (3/3 plans) — completed 2026-02-24
- [x] Phase 13: SDK Migration & Cleanup (5/5 plans) — completed 2026-02-24

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

### 🚧 v1.3 Flow Health & Cleanup (In Progress)

**Milestone Goal:** Fix 7 critical functional gaps in patient flow control, remove ~4,550 LOC of dead code from unused packages, and split 10 oversized files (500-1,141 LOC each) into focused modules for long-term maintainability.

- [x] **Phase 14: Flow Control Fixes** - Fix pause detection, auto-resume, and cancel flow end-to-end
 (completed 2026-02-24)
- [x] **Phase 15: Data Integrity Fixes** - Fix quiz crash, consolidate constants, align cycle calculation, wire DLQ
 (completed 2026-02-25)
- [ ] **Phase 16: Dead Code Removal** - Tombstone 5 unused packages/files (~4,550 LOC)
- [ ] **Phase 17: Flow Core Splits** - Split _flow_functions, flow_core, flow_management into focused modules
- [ ] **Phase 18: Flow Service Splits** - Split sequential_message_handler, enhanced_flow_engine, flow_dashboard, flow_monitoring
- [ ] **Phase 19: Saga & Integrity Splits** - Split saga orchestrator, saga compensation, and flow_integrity

## Phase Details

### Phase 14: Flow Control Fixes
**Goal**: Patient flow pause, auto-resume, and cancel operations work correctly and consistently across all system components.
**Depends on**: Phase 13 (v1.2 complete baseline)
**Requirements**: FIX-01, FIX-02, FIX-03
**Success Criteria** (what must be TRUE):
  1. A paused patient flow stays paused: the daily processor reads `state_data.paused` and skips the patient, not a different field
  2. A patient whose pause window has expired is automatically resumed by the Celery Beat job without manual intervention
  3. A cancelled flow clears all pending messages and resets state so no follow-up messages are sent after cancellation
  4. The flow management service exposes a working cancel endpoint that a doctor can call and receive confirmation
**Plans**: 5 plans

Plans:
- [x] 14-01-PLAN.md — Standardize pause detection to state_data.paused across daily processor, FlowCore, and FlowManagementService
- [x] 14-02-PLAN.md — Rewrite auto-resume Beat job to check auto_resume_at timestamps instead of blanket 48h heuristic
- [x] 14-03-PLAN.md — Implement cancel flow with pending message cleanup, Celery task revocation, and API endpoint

### Phase 15: Data Integrity Fixes
**Goal**: Quiz links never crash on missing templates, all phase constants come from one canonical source, cycle calculation is consistent, and failed messages reach the DLQ.
**Depends on**: Phase 14
**Requirements**: FIX-04, FIX-05, FIX-06, FIX-07
**Success Criteria** (what must be TRUE):
  1. A patient without an associated quiz template receives a WhatsApp message without a quiz link instead of the server raising a ValueError
  2. All flow phase constants resolve to the same values regardless of which module imports them (no divergence between flow_coordinator and sequential_message_handler)
  3. The monthly quiz cycle number computed by flow_coordinator and sequential_message_handler is identical for every input date
  4. A flow message that fails delivery is visible in the DLQ monitoring dashboard and retried automatically
**Plans**: 5 plans

Plans:
- [x] 15-01-PLAN.md — Consolidate phase constants and cycle calculation to canonical source (FIX-05, FIX-06)
- [x] 15-02-PLAN.md — Add graceful fallback for missing quiz templates (FIX-04)
- [x] 15-03-PLAN.md — Wire failed flow messages to DLQ with retry and monitoring (FIX-07)
- [x] 15-04-PLAN.md — Close missing-template fallback gap by sending no-link message and returning continue/success semantics (FIX-04, FIX-07)
- [x] 15-05-PLAN.md — Remove remaining hardcoded phase/cycle arithmetic in production services using canonical helpers (FIX-05, FIX-06)

### Phase 16: Dead Code Removal
**Goal**: Five unused code packages and files are tombstoned, reducing the active codebase by ~4,550 LOC and eliminating future confusion about which modules are in use.
**Depends on**: Phase 15 (constants consolidated before tombstoning dependent files)
**Requirements**: DEAD-01, DEAD-02, DEAD-03, DEAD-04, DEAD-05
**Success Criteria** (what must be TRUE):
  1. Importing from `flow/constants.py`, `flow/template_lookup.py`, `flow/analytics/`, `flow/templates/`, or `flow/monitoring/` raises an ImportError with a clear migration message
  2. No production code path imports from any of the five tombstoned locations (verified by grep/CI check)
  3. The repository is ~4,550 LOC lighter with no functional regression in existing tests
**Plans**: 3 plans

Plans:
- [ ] 16-01-PLAN.md — Tombstone flow/constants.py (208 LOC) and flow/template_lookup.py (18 LOC)
- [ ] 16-02-PLAN.md — Tombstone flow/analytics/ package (5 files, 2,259 LOC) and its test files
- [ ] 16-03-PLAN.md — Tombstone flow/templates/ (4 files, 1,972 LOC) and flow/monitoring/ (2 files, 93 LOC), clean flow/__init__.py

### Phase 17: Flow Core Splits
**Goal**: The three largest core flow files (_flow_functions, flow_core, flow_management) are decomposed into focused modules under 500 lines each, with all imports updated and tests passing.
**Depends on**: Phase 15 (canonical constants in place), Phase 16 (dead imports cleared)
**Requirements**: SPLIT-05, SPLIT-06, SPLIT-07
**Success Criteria** (what must be TRUE):
  1. No single file in the flow core layer exceeds 500 lines
  2. Each new module has a single clear responsibility (e.g., phase transitions do not live in the same module as template binding)
  3. All existing callers of `_flow_functions`, `flow_core`, and `flow_management` continue to work via re-export shims at the original paths
  4. The full test suite passes after the split with no new failures
**Plans**: TBD

Plans:
- [ ] 17-01: Split `_flow_functions.py` into message flow + response flow + orchestration utils
- [ ] 17-02: Split `flow_core.py` into base operations + phase transitions + template binding
- [ ] 17-03: Split `flow_management.py` into state management + advancement + pause/resume

### Phase 18: Flow Service Splits
**Goal**: The four oversized flow service files (sequential_message_handler, enhanced_flow_engine, flow_dashboard, flow_monitoring) are split into focused modules, each under 500 lines.
**Depends on**: Phase 17 (core layer stabilized before service layer refactor)
**Requirements**: SPLIT-01, SPLIT-02, SPLIT-03, SPLIT-04
**Success Criteria** (what must be TRUE):
  1. No single file in the flow service layer exceeds 500 lines
  2. AI orchestration, conversation memory, and response processing in enhanced_flow_engine are separated into distinct modules
  3. Dashboard analytics, trend analysis, and risk detection in flow_dashboard are separated into distinct modules
  4. All callers of the four original files continue to work via re-export shims at the original paths
**Plans**: TBD

Plans:
- [ ] 18-01: Split `sequential_message_handler.py` into message sequencing + state tracking + quiz handling
- [ ] 18-02: Split `enhanced_flow_engine.py` into AI orchestration + conversation memory + response processing
- [ ] 18-03: Split `flow_dashboard.py` into dashboard analytics + trend analysis + risk detection
- [ ] 18-04: Split `flow_monitoring.py` into metrics + health checks + recovery

### Phase 19: Saga & Integrity Splits
**Goal**: The three saga and integrity files (saga/orchestrator, saga/compensation, flow_integrity) are split into focused modules, completing the full file-split milestone across all oversized flow files.
**Depends on**: Phase 18
**Requirements**: SPLIT-08, SPLIT-09, SPLIT-10
**Success Criteria** (what must be TRUE):
  1. No single file in the saga or integrity layer exceeds 500 lines
  2. The saga orchestrator, step executor, and metrics are in separate modules
  3. Compensation chain logic and step handlers are in separate modules
  4. Corruption detection and recovery actions in flow_integrity are separated into distinct modules
  5. All callers of the three original files continue to work via re-export shims at the original paths
**Plans**: TBD

Plans:
- [ ] 19-01: Split `saga/orchestrator.py` into main orchestrator + step executor + metrics
- [ ] 19-02: Split `saga/compensation.py` into compensation chain + step handlers
- [ ] 19-03: Split `flow_integrity.py` into corruption detection + recovery actions

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Security Hardening | v1.0 | 3/3 | Complete | 2026-02-22 |
| 2. LGPD Compliance | v1.0 | 3/3 | Complete | 2026-02-22 |
| 3. Operational Stability | v1.0 | 3/3 | Complete | 2026-02-22 |
| 4. AI Reliability | v1.0 | 2/2 | Complete | 2026-02-22 |
| 5. Flow Consolidation | v1.0 | 2/2 | Complete | 2026-02-22 |
| 6. Async Hot Path Migration | v1.1 | 4/4 | Complete | 2026-02-23 |
| 7. LGPD Key Rotation | v1.1 | 1/1 | Complete | 2026-02-23 |
| 8. AI Rationalization | v1.1 | 2/2 | Complete | 2026-02-23 |
| 9. Observability | v1.1 | 3/3 | Complete | 2026-02-23 |
| 10. Preparation & Scope | v1.2 | 4/4 | Complete | 2026-02-24 |
| 11. Agent Implementation | v1.2 | 4/4 | Complete | 2026-02-24 |
| 12. Flow Orchestration Replacement | v1.2 | 3/3 | Complete | 2026-02-24 |
| 13. SDK Migration & Cleanup | v1.2 | 5/5 | Complete | 2026-02-24 |
| 14. Flow Control Fixes | v1.3 | 3/3 | Complete | 2026-02-24 |
| 15. Data Integrity Fixes | v1.3 | Complete    | 2026-02-25 | 2026-02-25 |
| 16. Dead Code Removal | v1.3 | 0/3 | Not started | - |
| 17. Flow Core Splits | v1.3 | 0/3 | Not started | - |
| 18. Flow Service Splits | v1.3 | 0/4 | Not started | - |
| 19. Saga & Integrity Splits | v1.3 | 0/3 | Not started | - |

---
*Roadmap created: 2026-02-22*
*Last updated: 2026-02-25 — Phase 15 complete (5/5)*
