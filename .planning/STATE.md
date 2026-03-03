---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: WuzAPI Migration
status: in_progress
stopped_at: Completed 38-04-PLAN.md
last_updated: "2026-03-03T14:35:27.570Z"
progress:
  total_phases: 12
  completed_phases: 12
  total_plans: 50
  completed_plans: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** v1.6 WuzAPI Migration — Phase 38: Tests and CI Validation

## Current Position

Phase: 38 of 39 (Tests and CI Validation)
Plan: 04 of 04 (completed)
Status: Complete
Last activity: 2026-03-03 — Completed 38-04 service-level send guard validation for TEST-04

Progress: [██████████] 100% (4/4 plans in phase 38 completed)

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
| Phase 33 P01 | 12min | 2 tasks | 6 files |
| Phase 33-new-provider-foundation P02 | 9 min | 2 tasks | 6 files |
| Phase 33 P03 | 10m | 2 tasks | 5 files |
| Phase 34-webhook-handler P01 | 8 min | 2 tasks | 3 files |
| Phase 34 P02 | 8 min | 2 tasks | 3 files |
| Phase 34 P03 | 26 min | 2 tasks | 5 files |
| Phase 35 P01 | 5 min | 2 tasks | 3 files |
| Phase 35 P02 | 5 min | 2 tasks | 7 files |
| Phase 36 P02 | 6 min | 2 tasks | 2 files |
| Phase 36 P03 | 6 min | 2 tasks | 3 files |
| Phase 37 P01 | 14 min | 2 tasks | 15 files |
| Phase 37 P02 | 15 min | 2 tasks | 21 files |
| Phase 37 P03 | 10min | 2 tasks | 4 files |
| Phase 37-evolution-cleanup P04 | 10 min | 2 tasks | 5 files |
| Phase 38 P01 | 9 min | 2 tasks | 1 files |
| Phase 38 P02 | 11 min | 2 tasks | 4 files |
| Phase 38 P03 | 9 min | 2 tasks | 5 files |
| Phase 38-tests-ci-validation P04 | 12 min | 2 tasks | 1 files |

## Accumulated Context

### Decisions

- [v1.6]: WuzAPIClient uses aiohttp (not httpx) for consistency with existing EvolutionAPIClient pattern and 2x perf advantage at high concurrency
- [v1.6]: Hard cut — no dual-provider mode, no feature toggles; Evolution tombstoned in single commit after Phase 36 passes
- [v1.6]: Phase 37 tombstone must come AFTER Phase 36 (IdempotentMessageSender updated) to avoid Celery worker ImportError on startup
- [v1.6]: LID (@lid) senders routed to DLQ from day one — never silently dropped (LGPD Art. 18 risk)
- [v1.6]: HMAC: read raw body bytes first, then json.loads separately — consuming request.json() first makes HMAC validation impossible
- [Phase 33]: Use Authorization header with raw token value (no Bearer prefix) in WuzAPI client defaults.
- [Phase 33]: Retry policy gives up on 4xx except 429 while retrying 5xx/429 up to three attempts.
- [Phase 33-new-provider-foundation]: Centralized media endpoint/field maps in models.py and consumed by client.send_media.
- [Phase 33-new-provider-foundation]: Enforced 16 MB limit during stream accumulation instead of post-download size checks.
- [Phase 33]: WuzAPIClient now wraps request execution with RedisCircuitBreaker(name="wuzapi") using 5/60/3 thresholds.
- [Phase 33]: WuzAPI package now exposes get_wuzapi_client() with WHATSAPP_WUZAPI_USE_MOCK=true switching to MockWuzAPIClient.
- [Phase 34-webhook-handler]: Reuse WebhookHMACValidator for WuzAPI webhook signature checks.
- [Phase 34-webhook-handler]: Process webhook raw bytes before JSON parsing to preserve HMAC integrity.
- [Phase 34-webhook-handler]: Use deterministic body-hash fallback event IDs when Info.ID is missing.
- [Phase 34]: Add MessageStatus.PLAYED to represent whatsmeow played receipts explicitly.
- [Phase 34]: WuzAPI extractor accepts wrapped and flat payloads with explicit empty-string delivered mapping.
- [Phase 34]: WuzAPI webhook now uses AtomicWebhookIdempotency fail-open checks and returns HTTP 200 duplicate payloads for repeated event IDs.
- [Phase 34]: Opt-out keywords STOP/PARAR/CANCELAR are processed through PhoneNormalizer phone-hash lookup and async handle_opt_out path.
- [Phase 34]: LID sender events are routed to DLQ and WuzAPI webhook is registered at /api/v2/webhooks/wuzapi via external router prefix.
- [Phase 35]: Keep WHATSAPP_EVOLUTION_* fields in settings until Phase 37 cleanup to avoid breaking imports.
- [Phase 35]: Validate WHATSAPP_WUZAPI_TOKEN via IntegrationsSettings model_validator with test-environment exemptions.
- [Phase 35]: Monitoring session endpoints should fail-open with structured error payloads (`connected/logged_in` or `qr` plus `error`) instead of raising API errors.
- [Phase 35]: Lifespan startup keeps `_initialize_evolution_api` and adds `_initialize_wuzapi_session` in parallel, with status-first idempotent connect and warning-only failures.
- [Phase 36]: UnifiedWhatsAppService now uses `get_wuzapi_client()`/`WuzAPIClient` for direct and queue-backed outbound flows with circuit breaker key `wuzapi`.
- [Phase 36]: Direct send path writes `whatsapp_id` from `response.data.Id` and encodes media via `fetch_and_encode_media` before `send_media`.
- [Phase 36]: WhatsApp queue and idempotent senders now call WuzAPI directly while preserving existing queue/idempotency flows
- [Phase 36]: sync_contacts now raises NotImplementedError because WuzAPI has no contacts API; removal deferred to Phase 37
- [Phase 36]: Keep Evolution DI only for instance-management endpoints in routes.py; migrate outbound message DI path to WuzAPI now.
- [Phase 36]: Remove explicit EvolutionClient construction from IdempotentMessageSender callers and rely on lazy WuzAPI initialization.
- [Phase 37]: Use full tombstone replacement for all 8 app.integrations.evolution modules with identical package-level ImportError message.
- [Phase 37]: Keep verification-time environment overrides scoped to commands instead of editing env files.
- [Phase 37]: Removed all remaining Stack B LID/Evolution paths and standardized webhook secret references on WHATSAPP_WUZAPI_WEBHOOK_SECRET.
- [Phase 37]: Monitoring/validation defaults now use WuzAPI token and instance identifiers, eliminating Evolution settings dependencies.
- [Phase 37]: Use validate_and_format_phone(request.to, strict=False) with 3-tuple unpacking in message_service send path.
- [Phase 37]: Remove WHATSAPP_EVOLUTION instance fallback and rely on resolved/default instance handling in UnifiedWhatsAppService.
- [Phase 37-evolution-cleanup]: Keep unauthorized response path as log-only no-op after Evolution removal to avoid reintroducing non-clinical outbound behavior.
- [Phase 37-evolution-cleanup]: Use WuzAPIError.status checks as drop-in queue failure categorization for RATE_LIMIT and API_ERROR.
- [Phase 38]: Reuse existing webhook integration harness and add only targeted gap tests for unknown event + missing HMAC header.
- [Phase 38]: Treat Task 2 as verification-only regression gate with no code delta when all tests pass.
- [Phase 38]: Scan app/ only in check_evolution_imports.py to match existing CI guard scope and avoid test-only false positives
- [Phase 38]: Keep tombstoned unit test modules collectable as skipped by retaining a placeholder test under module-level pytest skip
- [Phase 38]: Keep inline synthetic helper tests and add fixture-backed JSON tests in parallel for TEST-02 realism coverage.
- [Phase 38]: Reuse shared WuzAPI fixture payload files across webhook and extractor tests to enforce schema consistency.
- [Phase 38-tests-ci-validation]: Use UnifiedWhatsAppService.send_message runtime invocation to verify opt-out guard behavior for TEST-04
- [Phase 38-tests-ci-validation]: Patch patient loading/send path in tests to isolate guard outcomes without external transport side effects

### Pending Todos

None.

### Blockers/Concerns

- LID resolution mechanism in WuzAPI not fully documented — spike needed if @lid senders appear in staging during Phase 34
- Brazilian 9th-digit JID resolution at patient-cohort scale — rate limits for POST /user/check not documented; batch design needed before Phase 36

## Session Continuity

**Last session:** 2026-03-03T14:35:27.532Z
**Stopped At:** Completed 38-04-PLAN.md
**Resume File:** None
