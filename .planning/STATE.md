# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-22)

**Core value:** Médicos acompanham pacientes oncológicos continuamente entre consultas via WhatsApp, com questionários humanizados que coletam dados clínicos sem sobrecarregar o paciente.
**Current focus:** Phase 5 — Flow Consolidation (Plan 1 of 2 complete)

## Current Position

Phase: 5 of 9 (Flow Consolidation) — IN PROGRESS (1/2 plans done); Phase 4 complete (2/2 plans done)
Plan: 1 of 2 completed in Phase 5
Status: Phase 5 Plan 01 Complete — QW-021 package deleted, FlowDispatcher facade created, production flow system confirmed as sole canonical
Last activity: 2026-02-22 — Plan 05-01 executed (FlowDispatcher created; QW-021 ~11,000 LOC deleted; service_provider.flow_service returns FlowDispatcher; FLOW-01, FLOW-02 satisfied)

Progress: [██████░░░░] 30%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: ~8 min
- Total execution time: 0.80 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-security-hardening | 3/3 | ~18 min | ~6 min |
| 02-lgpd-compliance | 3/4 | ~25 min | ~8 min |

**Recent Trend:**
- Last 5 plans: 5 min, 7 min, 6 min, 12 min, 10 min
- Trend: LGPD plans slightly longer due to DB migration complexity

*Updated after each plan completion*
| Phase 01-security-hardening P02 | 16 | 3 tasks | 6 files |
| Phase 02-lgpd-compliance P01 | ~12 min | 2 tasks | 6 files |
| Phase 02-lgpd-compliance P02 | 10 | 2 tasks | 4 files |
| Phase 02-lgpd-compliance P03 | 3 | 2 tasks | 2 files |
| Phase 03-operational-stability P02 | 2 | 2 tasks | 1 files |
| Phase 03-operational-stability P03 | 2 | 2 tasks | 2 files |
| Phase 03-operational-stability P01 | 5 | 2 tasks | 2 files |
| Phase 04-ai-reliability P01 | 2 | 2 tasks | 2 files |
| Phase 04-ai-reliability P02 | 2 | 2 tasks | 4 files |
| Phase 05-flow-consolidation P01 | 12 | 2 tasks | 6 files |

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
- [02-01]: No FK from patient_deletion_audit to patients.id — audit row must survive even if patient is hard-deleted
- [02-01]: PostgreSQL RULE objects (not triggers) used for immutability — RULEs intercept at rewrite layer, cannot be bypassed by superusers
- [02-01]: Merge migration pattern (down_revision as tuple) used because codebase had two Alembic heads (015_rename_upload_metadata, a9c4e1d2b7f0)
- [02-01]: PatientDeletionAudit import inside delete_patient() body — avoids circular import risk
- [Phase 02-lgpd-compliance]: Opt-out interception placed after patient lookup and before flow advancement to prevent any outbound message post-revocation
- [Phase 02-lgpd-compliance]: Consent revocation is best-effort — messaging_stopped_at is persisted regardless, satisfying LGPD Art. 18 immediacy
- [Phase 02-lgpd-compliance]: OPT_OUT_KEYWORDS uses exact-match only to prevent false positives in medical conversations
- [Phase 02-lgpd-compliance]: Four AI enum values grouped under LGPD-03 comment in AuditEventType for compliance traceability (Art. 20 automated processing)
- [Phase 02-lgpd-compliance]: downgrade() for lgpd03 is intentionally a no-op — PostgreSQL cannot remove enum values, values are harmless if unused
- [Phase 03-operational-stability]: increment=True path uses Lua script (atomic); increment=False path uses pipeline (no mutation, no race)
- [Phase 03-operational-stability]: _sliding_window_script() called synchronously (no await) matching existing pipeline pattern in async check_rate_limit
- [Phase 03-operational-stability]: PyJWT jwt.encode/decode provides identical API to python-jose for HS256 - zero code changes needed beyond import line replacement
- [Phase 03-operational-stability]: python-jose 3.5.0 lingered in venv despite absence from requirements.txt - best-effort uninstall succeeded
- [Phase 03-operational-stability]: asyncio import retained in flow_tasks.py — process_daily_flows_async still uses Semaphore/gather/sleep/TimeoutError; only the sync entry point changed
- [Phase 03-operational-stability]: asyncio import removed from base.py — was used only in the deleted loop-detection block; no other code needed it
- [Phase 03-operational-stability]: async_to_sync is now the sole sync→async bridge pattern in app/tasks/ — matches established convention from 15+ existing task files
- [Phase 04-ai-reliability]: AI-01: _check_langgraph_available inspects only _LANGGRAPH_IMPORT_ERROR sentinel — no graph compilation at startup (graphs compiled lazily via @lru_cache)
- [Phase 04-ai-reliability]: AI-01: RuntimeError call placed before asyncio.gather() so it propagates — placing inside _initialize_ai_services() would be swallowed by return_exceptions=True
- [Phase 04-ai-reliability]: AI-01: FeatureNotAvailableError uses is_recoverable=True and error_code=FEATURE_NOT_AVAILABLE — callers can retry without cascading failure
- [Phase 04-ai-reliability]: AI-02: invoke_langgraph_graph() wrapper centralizes None validation — expect_dict=True for sentiment, False for strings
- [Phase 04-ai-reliability]: AI-02: humanization fallback uses message_template.base_content — patient always receives a message
- [Phase 04-ai-reliability]: AI-02: sentiment fallback confidence=0.0 not 0.5 — downstream threshold checks correctly treat as low-confidence
- [Phase 04-ai-reliability]: AI-02: sentry_sdk.capture_exception before fallback branch in enhanced_flow_engine.py — every AI failure visible in dashboards
- [Phase 05-flow-consolidation]: Full code deletion (not tombstone) for QW-021: zero callers outside package confirmed before deletion
- [Phase 05-flow-consolidation]: FlowDispatcher is enrollment-only: advance_flow/pause/resume go directly to EnhancedFlowEngine/FlowManagementService
- [Phase 05-flow-consolidation]: FlowFeatureFlags: dropped percentage-based rollout, replaced with patient-type routing (route_new/existing_patients_to_canonical)

### Pending Todos

None yet.

### Blockers/Concerns

- [Research flag] Phase 6: AsyncSession migration scope for sequential_message_handler.py (12 TODOs), flow_core.py (7 TODOs), enhanced_quiz_service.py (8 TODOs) needs file-by-file analysis during planning
- [Research flag] Phase 9: WebSocket multi-instance gap between redis_pubsub_manager.py and WebSocket connection manager not fully characterized — needs focused spike before story creation
- [Research gap] Phase 2: Patient data export endpoint (import_export.py) needs verification it works — LGPD Art. 18 portability requirement
- [Research gap] Phase 5: Physician availability slots model (what constitutes an available slot) is not documented in codebase — needs product clarification during story creation

## Session Continuity

Last session: 2026-02-22
Stopped at: Completed 05-01-PLAN.md (QW-021 deletion + FlowDispatcher facade, 2 tasks, 6 files; Phase 5 Plan 1 of 2 done)
Resume file: .planning/phases/05-flow-consolidation/ (Phase 5 Plan 02)
