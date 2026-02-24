# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-23)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** v1.2 AI Framework Migration — Phase 10: Preparation & Scope

## Current Position

Phase: 10 of 13 (Preparation & Scope)
Plan: 1 of 2 in current phase
Status: In progress
Last activity: 2026-02-24 - Completed 10-02 consensus deletion and DDD scope annotation

Progress: v1.0 ██████████ 100% | v1.1 ██████████ 100% | v1.2 █░░░░░░░░░ 8%

## Performance Metrics

**Velocity:**
- Total plans completed: 18 (v1.0: 13, v1.1: 10 — but v1.1 had overlap)
- Average duration: unknown (v1.2 not yet started)
- Total execution time: 2 days (v1.0 + v1.1)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| v1.0 (phases 1-5) | 13 | 1 day | - |
| v1.1 (phases 6-9) | 10 | 1 day | - |
| v1.2 (phases 10-13) | TBD | - | - |

**Recent Trend:**
- v1.1 completed in 1 day (30+ commits, 69 files)
- Trend: Stable

*Updated after each plan completion*
| Phase 10 P02 | 2 min | 2 tasks | 13 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting v1.2 work:

- google-adk DEFERRED to v1.3: irresolvable OTel cap conflict + Pydantic 2.11+ FastAPI schema failures + 300-400 MB GCP footprint; documented in research/SUMMARY.md
- pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0: correct variant (not full pydantic-ai); pin <2.0.0 (V2 planned April 2026 with breaking changes)
- PromptedOutput(SentimentResult) for SentimentAgent: Gemini cannot use tool-calling + native structured output simultaneously; PromptedOutput injects JSON schema into system prompt
- PIISafeAgent wrapper MANDATORY: only sanctioned way to call any agent; direct .run() calls blocked by CI lint rule; LGPD Art. 46 requirement
- Flow graphs replaced with direct async Python (not ADK): 10-15 lines each, identical runtime semantics, zero new dependencies
- GeminiClient preserved as execution backend throughout migration: cache, circuit breaker, rate limiter, PII redaction unchanged
- [Phase 10]: Consensus path removed entirely; FlowCoordinator now escalates directly to ALERT_ANALYZER_ID via critical message.
- [Phase 10]: Added one-line scope annotations across app/agents DDD services to prevent pydantic-ai migration confusion in Phase 11.

### Pending Todos

None.

### Blockers/Concerns

Carried from v1.1 (not in v1.2 scope):
- Full AsyncSession migration (42+ remaining methods) — hot paths cover ~80% throughput
- 60+ files >500 lines need splitting
- Physician availability hours model — hardcoded defaults

v1.2 risks to watch:
- PromptedOutput validation against gemini-2.5-flash: MEDIUM confidence; 1-day spike recommended as first Phase 11 task
- Celery async bridge: agent.run_sync() fix documented but not yet validated in this stack; 100-task load test is acceptance criterion in Phase 13
- LangGraph checkpoint PHI audit: sample existing keys before purge to determine LGPD documentation obligations

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 10-02-PLAN.md
Resume file: None
