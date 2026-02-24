# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-23)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** v1.2 AI Framework Migration — Phase 12: Flow Orchestration Replacement

## Current Position

Phase: 12 of 13 (Flow Orchestration Replacement)
Plan: 0 of 3 in current phase
Status: In progress
Last activity: 2026-02-24 - Completed 11-04 GeminiDomainClient AI_FRAMEWORK shim and 50-scenario regression suite

Progress: v1.0 ██████████ 100% | v1.1 ██████████ 100% | v1.2 █████░░░░░ 50%

## Performance Metrics

**Velocity:**
- Total plans completed: 19 (v1.0: 13, v1.1: 10 — but v1.1 had overlap)
- Average duration: tracking (latest: 17 min)
- Total execution time: 2 days + active v1.2

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
| Phase 10 P01 | 4 min | 2 tasks | 2 files |
| Phase 10 P03 | 7 min | 2 tasks | 12 files |
| Phase 10 P04 | 4 min | 2 tasks | 7 files |
| Phase 11 P01 | 7 min | 3 tasks | 4 files |
| Phase 11 P02 | 2 min | 1 tasks | 2 files |
| Phase 11 P03 | 5 min | 2 tasks | 6 files |
| Phase 11 P04 | 17 min | 2 tasks | 6 files |

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
- [Phase 10]: Keep LangGraph and pydantic-ai-slim coexisting during migration phases 10-12.
- [Phase 10]: Pin pydantic-ai-slim below 2.0.0 to avoid planned April 2026 breaking changes.
- [Phase 10]: Use identical one-line DDD scope annotation text across all 12 target files for consistent migration signaling.
- [Phase 10]: Place scope annotation after __future__ imports when present to preserve import ordering conventions.
- [Phase 10]: Use no-LLM annotation wording for communication support modules and package initializers.
- [Phase 10]: Use composer-specific scope annotation explicitly documenting GeminiClient.generate_content() delegation.
- [Phase 11]: Use PIISafeAgent as the only sanctioned agent.run() entrypoint enforced by CI lint.
- [Phase 11]: Inject GoogleModel per call from AIDeps to avoid global API key coupling at import time.
- [Phase 11]: Use PromptedOutput(SentimentResult) with defer_model_check=True so SentimentAgent keeps runtime model injection through AIDeps.
- [Phase 11]: Raise ModelRetry inside SentimentAgent output_validator for banned pattern/prompt leak violations to trigger pydantic-ai regeneration.
- [Phase 11]: Keep guardrails duplicated as per-agent output_validator decorators using ModelRetry for re-ask behavior.
- [Phase 11]: Place the 88% similarity check after _safe_run in VariationAgent and fallback deterministically instead of validator retry loops.
- [Phase 11]: Use app.ai.agents.helpers as the only import surface to isolate Phase 12 langgraph tombstoning.
- [Phase 11]: Keep AI_FRAMEWORK default as legacy to preserve production behavior until explicit opt-in.
- [Phase 11]: Convert SentimentAgent output to dict in GeminiDomainClient shim for backward-compatible caller signatures.

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
Stopped at: Completed 11-04-PLAN.md
Resume file: None
