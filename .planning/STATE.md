# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Médicos acompanham pacientes oncológicos continuamente entre consultas via WhatsApp, com questionários humanizados que coletam dados clínicos sem sobrecarregar o paciente.
**Current focus:** Phase 1 — Security Hardening

## Current Position

Phase: 1 of 9 (Security Hardening)
Plan: 3 of 3 in current phase
Status: Phase Complete — All 3 plans in Phase 1 executed
Last activity: 2026-02-22 — Plan 01-03 executed (debug flag startup guardrail)

Progress: [██░░░░░░░░] 11%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: ~6 min
- Total execution time: 0.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-security-hardening | 3/3 | ~18 min | ~6 min |

**Recent Trend:**
- Last 5 plans: 5 min, 7 min, 6 min
- Trend: consistent baseline established

*Updated after each plan completion*
| Phase 01-security-hardening P02 | 16 | 3 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 9 phases chosen for comprehensive depth — security/compliance first (1-4), architecture second (5-7), rationalization/observability last (8-9)
- [Roadmap]: Phases 2 and 3 both depend only on Phase 1 and can be worked in parallel
- [Roadmap]: Phase 8 (AI Rationalization) deferred after Phase 4 + 5 to avoid touching AI layer during critical infrastructure work
- [Research]: LangGraph stack retained — rationalize single-node graphs, keep multi-node routing graphs
- [Research]: AsyncSession migration targeted to hot paths only (ASYNC-V2 for full migration deferred to v2)
- [01-01]: Read monitoring endpoints (metrics, APM, DB, resources, business, anomalies, dashboard, alerts, performance) use get_current_active_user — admin + doctor roles can view monitoring data
- [01-01]: Admin-only endpoints are GET/PUT /config, POST /export/grafana/query, POST /actions/* — these mutate state or expose raw query execution
- [01-01]: /health and /export/prometheus remain unauthenticated for Railway probes and Prometheus scraping (OWASP standard: network-level protection)
- [01-02]: TEST_TOKEN_REGISTRY removed from all production app/ modules — test token bypass now restricted to test environment only (conftest fixtures)
- [01-03]: validate_debug_flag placed in BaseAppSettings (not SecuritySettings) so ALL Settings subclasses inherit the startup guard
- [01-03]: Both 'production'/'prod' and 'staging' are blocked — covers real-world CI/CD naming conventions
- [01-03]: Tests use direct BaseAppSettings import from base module to avoid triggering module-level Settings() instantiation in __init__.py
- [Phase 01-security-hardening]: Override get_admin_user in admin_token fixture - admin router depends on it directly, not get_current_user
- [Phase 01-security-hardening]: SEC-03 guardrail is severity-aware: RuntimeError in prod/staging, CRITICAL log only in development

### Pending Todos

None yet.

### Blockers/Concerns

- [Research flag] Phase 6: AsyncSession migration scope for sequential_message_handler.py (12 TODOs), flow_core.py (7 TODOs), enhanced_quiz_service.py (8 TODOs) needs file-by-file analysis during planning
- [Research flag] Phase 9: WebSocket multi-instance gap between redis_pubsub_manager.py and WebSocket connection manager not fully characterized — needs focused spike before story creation
- [Research gap] Phase 2: Patient data export endpoint (import_export.py) needs verification it works — LGPD Art. 18 portability requirement
- [Research gap] Phase 5: Physician availability slots model (what constitutes an available slot) is not documented in codebase — needs product clarification during story creation

## Session Continuity

Last session: 2026-02-22
Stopped at: Completed 01-02-PLAN.md (TEST_TOKEN_REGISTRY elimination + Firebase credential guardrail — 3 tasks, 6 files)
Resume file: .planning/phases/01-security-hardening/01-03-PLAN.md (Plan 03 next in Phase 1)
