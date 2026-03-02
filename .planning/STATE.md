---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: WuzAPI Migration
status: unknown
stopped_at: Completed 35-01-PLAN.md
last_updated: "2026-03-02T04:12:03.661Z"
progress:
  total_phases: 9
  completed_phases: 8
  total_plans: 39
  completed_plans: 38
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.
**Current focus:** v1.6 WuzAPI Migration — Phase 35: Configuration and Session

## Current Position

Phase: 35 of 39 (Configuration and Session)
Plan: 01 of 02 (35-01 completed, 35-02 pending)
Status: In Progress
Last activity: 2026-03-02 — Completed 35-01 WuzAPI settings, startup token validation, and env example updates

Progress: [█████░░░░░] 50% (1/2 plans in phase)

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

### Pending Todos

None.

### Blockers/Concerns

- LID resolution mechanism in WuzAPI not fully documented — spike needed if @lid senders appear in staging during Phase 34
- Brazilian 9th-digit JID resolution at patient-cohort scale — rate limits for POST /user/check not documented; batch design needed before Phase 36

## Session Continuity

**Last session:** 2026-03-02T04:12:03.632Z
**Stopped At:** Completed 35-01-PLAN.md
**Resume File:** None
