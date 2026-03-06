# Roadmap: Clinica Oncologica — Refinamento para Producao

## Milestones

- ✅ **v1.0 Foundations** — Phases 1-5 (shipped 2026-02-22)
- ✅ **v1.1 Architecture & Observability** — Phases 6-9 (shipped 2026-02-23)
- ✅ **v1.2 AI Framework Migration** — Phases 10-13 (shipped 2026-02-24)
- ✅ **v1.3 Flow Health & Cleanup** — Phases 14-19 (shipped 2026-02-26)
- ✅ **v1.4 AsyncSession & Test Stability** — Phases 20-28 (shipped 2026-02-28)
- ✅ **v1.5 Saga Orchestrator Deep Dive** — Phases 29-32 (shipped 2026-03-01)
- ✅ **v1.6 WuzAPI Migration** — Phases 33-39 (shipped 2026-03-03)
- ✅ **v1.7 Frontend Quality & ADK Integration** — Phases 40-43 (shipped 2026-03-05)
- ✅ **v1.8 ADK Stability & Error Hardening** — Phases 44-49 (shipped 2026-03-06)
- **v1.9 Bulletproof Flow Pipeline** — Phases 50-53 (in progress)

## Phases

<details>
<summary>v1.0-v1.8 (Phases 1-49) — SHIPPED</summary>

- [x] Phases 1-5 archived — `.planning/milestones/v1.0-ROADMAP.md`
- [x] Phases 6-9 archived — `.planning/milestones/v1.1-ROADMAP.md`
- [x] Phases 10-13 archived — `.planning/milestones/v1.2-ROADMAP.md`
- [x] Phases 14-19 archived — `.planning/milestones/v1.3-ROADMAP.md`
- [x] Phases 20-28 archived — `.planning/milestones/v1.4-ROADMAP.md`
- [x] Phases 29-32 archived — `.planning/milestones/v1.5-ROADMAP.md`
- [x] Phases 33-39 archived — `.planning/milestones/v1.6-ROADMAP.md`
- [x] Phases 40-43 archived — `.planning/milestones/v1.7-ROADMAP.md`
- [x] Phases 44-49 archived — `.planning/milestones/v1.8-ROADMAP.md`

</details>

### v1.9 Bulletproof Flow Pipeline

**Milestone Goal:** Make the WhatsApp flow pipeline operationally bulletproof -- every silent failure becomes either an automatic recovery or a visible alert, and the entire chain is verified by integration tests.

**Phase Numbering:**
- Integer phases (50, 51, 52, 53): Planned milestone work
- Decimal phases (50.1, 50.2): Urgent insertions if needed (marked with INSERTED)

- [x] **Phase 50: Pipeline Reliability** - Fix silent failures in sequential gate, message sends, follow-ups, day advancement, and config validation
- [x] **Phase 51: Flow Recovery** - Detect stuck flows automatically and provide manual + automatic recovery paths (completed 2026-03-06)
- [ ] **Phase 52: Flow Observability** - Surface pipeline health, stall alerts, AI fallback rates, and correlation tracing
- [ ] **Phase 53: Pipeline Verification** - Integration tests proving end-to-end pipeline, recovery, and retry paths

## Phase Details

### Phase 50: Pipeline Reliability
**Goal**: Patients never get silently stuck due to infrastructure failures in the flow pipeline -- every failure is either automatically recovered or surfaced with a clear error
**Depends on**: Nothing (first phase of v1.9)
**Requirements**: FLOW-01, FLOW-02, FLOW-03, FLOW-04, FLOW-05
**Success Criteria** (what must be TRUE):
  1. When sequential gate encounters a context mismatch, the patient flow retries with corrected context or resets state instead of waiting silently forever
  2. When an outbound WhatsApp message send fails, the system retries up to 3 times with exponential backoff before marking the send as permanently failed
  3. When a deferred follow-up send fails, it is re-queued via Celery task instead of being silently dropped
  4. When day advancement fails after day_complete, the failure is detected and the flow does not silently skip to a broken state
  5. When a flow starts with malformed or missing template day_config, it fails immediately with a clear error and alert instead of proceeding with broken config
**Plans**: 4 plans

Plans:
- [x] 50-01: Sequential gate context mismatch recovery
- [x] 50-02: Outbound message send retry via Celery with exponential backoff
- [x] 50-03: Deferred follow-up retry and atomic day advancement
- [x] 50-04: Template day_config validation at flow start

### Phase 51: Flow Recovery
**Goal**: Stuck patient flows are automatically detected and recovered, and operators have manual tools to intervene when auto-recovery is insufficient
**Depends on**: Phase 50
**Requirements**: RECV-01, RECV-02, RECV-03, RECV-04
**Success Criteria** (what must be TRUE):
  1. A periodic Celery Beat task scans for flows stuck in awaiting_response longer than a configurable threshold and flags them as stalled
  2. Stalled flows are automatically recovered by re-sending the last prompt or advancing the day, based on analysis of current flow state
  3. An admin can reset, advance, or unstick a specific patient flow via a dedicated API endpoint
  4. Failed flow operations (gate blocks, send failures, recovery failures) are visible in the admin interface via a queryable surface (DLQ or dedicated query)
**Plans**: 2 plans

Plans:
- [x] 51-01-PLAN.md — Stuck flow detection service, auto-recovery logic, and Celery Beat task
- [x] 51-02-PLAN.md — Admin flow control API and failed flow operations visibility

### Phase 52: Flow Observability
**Goal**: Operators can see real-time pipeline health and get alerted when patients are stuck, with full traceability from webhook to send
**Depends on**: Phase 50
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04
**Success Criteria** (what must be TRUE):
  1. A flow health API endpoint returns current counts of active, stalled, failed, and completed flows
  2. A stall alert fires (structured log + optional webhook) when any patient has not progressed in a configurable time window
  3. AI personalization fallback rate is tracked via Prometheus counter (ai_personalization_fallback_total) that increments each time deterministic fallback is used instead of AI
  4. A correlation ID is generated at webhook entry and propagated through every processing step (handler -> gate -> continuation -> send), visible in structured logs
**Plans**: 2 plans

Plans:
- [ ] 52-01-PLAN.md -- Flow health endpoint and stall alerting
- [ ] 52-02-PLAN.md -- AI fallback metrics and correlation ID propagation

### Phase 53: Pipeline Verification
**Goal**: Integration tests prove the full pipeline works end-to-end under both success and failure conditions
**Depends on**: Phase 50, Phase 51, Phase 52
**Requirements**: TEST-01, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. Integration tests exercise the full pipeline from webhook arrival through sequential gate, continuation, and next question send -- and all tests pass
  2. Integration tests exercise stuck flow detection triggering auto-recovery and verify the patient flow progresses -- and all tests pass
  3. Integration tests exercise failed outbound sends triggering Celery retry mechanics and verify eventual delivery or proper failure surfacing -- and all tests pass
**Plans**: 2 plans

Plans:
- [ ] 53-01: End-to-end pipeline integration tests
- [ ] 53-02: Recovery and retry integration tests

## Progress

**Execution Order:**
Phases execute in numeric order: 50 -> 51 -> 52 -> 53
(Phase 51 and 52 both depend on 50 but are independent of each other; 53 depends on all three.)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-5 | v1.0 | 13/13 | Complete | 2026-02-22 |
| 6-9 | v1.1 | 10/10 | Complete | 2026-02-23 |
| 10-13 | v1.2 | 16/16 | Complete | 2026-02-24 |
| 14-19 | v1.3 | 31/31 | Complete | 2026-02-26 |
| 20-28 | v1.4 | 54/54 | Complete | 2026-02-28 |
| 29-32 | v1.5 | 14/14 | Complete | 2026-03-01 |
| 33-39 | v1.6 | 21/21 | Complete | 2026-03-03 |
| 40-43 | v1.7 | 20/20 | Complete | 2026-03-05 |
| 44-49 | v1.8 | 11/11 | Complete | 2026-03-06 |
| 50. Pipeline Reliability | v1.9 | 4/4 | Complete | 2026-03-06 |
| 51. Flow Recovery | v1.9 | 2/2 | Complete | 2026-03-06 |
| 52. Flow Observability | v1.9 | 0/2 | Not started | - |
| 53. Pipeline Verification | v1.9 | 0/2 | Not started | - |

---

_Roadmap created: 2026-02-22_
_Last updated: 2026-03-06 -- Phase 52 planned (2 plans in 1 wave)_
