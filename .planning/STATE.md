---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: WuzAPI Migration
current_phase: 33
current_phase_name: New Provider Foundation
current_plan: none
status: ready_to_plan
stopped_at: null
last_updated: "2026-03-01T23:45:00.000Z"
last_activity: 2026-03-01
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 15
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** v1.6 WuzAPI Migration — Phase 33: New Provider Foundation

## Current Position

Phase: 33 of 38 (New Provider Foundation)
Plan: — (not started)
Status: Ready to plan
Last activity: 2026-03-01 — Roadmap created, v1.6 phases 33-38 defined

Progress: [░░░░░░░░░░] 0% (0/15 plans)

## Performance Metrics

| Milestone | Phases | Plans | Timeline |
|-----------|--------|-------|----------|
| v1.0 Foundations | 5 | 13 | 1 day (2026-02-22) |
| v1.1 Architecture & Observability | 4 | 10 | 1 day (2026-02-23) |
| v1.2 AI Framework Migration | 4 | 16 | 1 day (2026-02-24) |
| v1.3 Flow Health & Cleanup | 6 | 31 | 2 days (2026-02-24 → 2026-02-26) |
| v1.4 AsyncSession & Test Stability | 9 | 54 | 3 days (2026-02-26 → 2026-02-28) |
| v1.5 Saga Orchestrator Deep Dive | 4 | 14 | 2 days (2026-02-28 → 2026-03-01) |
| v1.6 WuzAPI Migration | 6 | 15 est. | Started 2026-03-01 |
| **Cumulative (shipped)** | **32 phases** | **138 plans** | **8 days** |

## Accumulated Context

### Decisions

- [v1.6]: WuzAPIClient uses aiohttp (not httpx) for consistency with existing EvolutionAPIClient pattern and 2x perf advantage at high concurrency
- [v1.6]: Hard cut — no dual-provider mode, no feature toggles; Evolution tombstoned in single commit after Phase 36 passes
- [v1.6]: Phase 37 tombstone must come AFTER Phase 36 (IdempotentMessageSender updated) to avoid Celery worker ImportError on startup
- [v1.6]: LID (@lid) senders routed to DLQ from day one — never silently dropped (LGPD Art. 18 risk)
- [v1.6]: HMAC: read raw body bytes first, then json.loads separately — consuming request.json() first makes HMAC validation impossible

### Pending Todos

None.

### Blockers/Concerns

- WuzAPI webhook payload JSON schema is MEDIUM confidence (inferred from Go source) — real payload capture required before Phase 34 parser code is written
- LID resolution mechanism in WuzAPI not fully documented — spike needed if @lid senders appear in staging during Phase 34
- Brazilian 9th-digit JID resolution at patient-cohort scale — rate limits for POST /user/check not documented; batch design needed before Phase 36

## Session Continuity

**Last session:** 2026-03-01
**Stopped At:** Roadmap created — Phase 33 ready to plan
**Resume File:** None — start with `/gsd:plan-phase 33`
