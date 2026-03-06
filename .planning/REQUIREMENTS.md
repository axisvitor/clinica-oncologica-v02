# Requirements: Clinica Oncologica — v1.9 Bulletproof Flow Pipeline

**Defined:** 2026-03-06
**Core Value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## v1.9 Requirements

Requirements for bulletproof flow pipeline. Each maps to roadmap phases.

### Flow Reliability

- [ ] **FLOW-01**: Sequential gate recovers from context mismatches with explicit retry or state reset instead of silently waiting forever
- [ ] **FLOW-02**: Failed outbound message sends are automatically retried via Celery task with exponential backoff (max 3 attempts)
- [ ] **FLOW-03**: Deferred follow-up send failures are retried via task queue instead of being silently dropped
- [ ] **FLOW-04**: Day advancement after day_complete is atomic and verified — no silent skip when advance fails
- [ ] **FLOW-05**: Template day_config is validated at flow start; malformed or missing config fails fast with clear error and alert

### Flow Recovery

- [ ] **RECV-01**: Stuck flow detector runs as periodic Celery Beat task, identifying flows with awaiting_response > configurable hours
- [ ] **RECV-02**: Stuck flow auto-recovery attempts re-send of last prompt or day advance based on flow state analysis
- [ ] **RECV-03**: Admin can manually reset, advance, or unstick a patient flow via dedicated API endpoint
- [ ] **RECV-04**: Failed flow operations are visible in admin via DLQ or dedicated failed-flows query

### Flow Observability

- [ ] **OBS-01**: Flow health API endpoint returns counts of active, stalled, failed, and completed flows
- [ ] **OBS-02**: Flow stall alert fires (structured log + optional webhook) when patient hasn't progressed in configurable time
- [ ] **OBS-03**: AI personalization fallback rate is tracked via Prometheus counter (ai_personalization_fallback_total)
- [ ] **OBS-04**: Correlation ID is generated at webhook entry and propagated through handler -> gate -> continuation -> send chain

### Pipeline Verification

- [ ] **TEST-01**: Integration tests cover full pipeline: webhook arrival -> sequential gate -> continuation -> next question send
- [ ] **TEST-02**: Integration tests cover stuck flow detection -> auto-recovery path
- [ ] **TEST-03**: Integration tests cover retry mechanics for failed outbound sends

## Future Requirements

### ADK Operational Maturity (deferred from v1.8)

- **ADK-14**: Map ADK error taxonomy to standardized HTTP response envelope
- **ADK-15**: Define retryable/non-retryable policy with idempotency for ADK calls
- **ADK-OPS**: Close ADK operational stability criteria with runbook and minimum alerts

### Flow Intelligence (deferred to v2.0+)

- **FLOW-AI-01**: AI adapts next question based on patient's actual response content
- **FLOW-AI-02**: Dynamic question branching based on sentiment analysis of responses

## Out of Scope

| Feature | Reason |
|---------|--------|
| AI-driven dynamic question generation | Reliability first; template-driven pipeline must work before adding intelligence |
| WhatsApp live chat (doctor-patient) | Requires shared inbox product; different architecture |
| Full Celery async conversion | Workers sync Session is correct by design |
| Frontend admin flow management UI | Backend pipeline focus; admin API endpoints sufficient for v1.9 |
| WuzAPI live-provider verification | Deferred; requires staging environment with real WhatsApp |
| ADK error envelope / retry policy | Separate concern from flow pipeline; deferred to next milestone |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FLOW-01 | Phase 50 | Pending |
| FLOW-02 | Phase 50 | Pending |
| FLOW-03 | Phase 50 | Pending |
| FLOW-04 | Phase 50 | Pending |
| FLOW-05 | Phase 50 | Pending |
| RECV-01 | Phase 51 | Pending |
| RECV-02 | Phase 51 | Pending |
| RECV-03 | Phase 51 | Pending |
| RECV-04 | Phase 51 | Pending |
| OBS-01 | Phase 52 | Complete |
| OBS-02 | Phase 52 | Complete |
| OBS-03 | Phase 52 | Complete |
| OBS-04 | Phase 52 | Complete |
| TEST-01 | Phase 53 | Pending |
| TEST-02 | Phase 53 | Pending |
| TEST-03 | Phase 53 | Pending |

**Coverage:**
- v1.9 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-03-06*
*Last updated: 2026-03-06 -- Phase 52 traceability marked complete*
