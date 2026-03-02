# Roadmap: Clinica Oncologica — Refinamento para Producao

## Milestones

- ✅ **v1.0 Foundations** — Phases 1-5 (shipped 2026-02-22)
- ✅ **v1.1 Architecture & Observability** — Phases 6-9 (shipped 2026-02-23)
- ✅ **v1.2 AI Framework Migration** — Phases 10-13 (shipped 2026-02-24)
- ✅ **v1.3 Flow Health & Cleanup** — Phases 14-19 (shipped 2026-02-26)
- ✅ **v1.4 AsyncSession & Test Stability** — Phases 20-28 (shipped 2026-02-28)
- ✅ **v1.5 Saga Orchestrator Deep Dive** — Phases 29-32 (shipped 2026-03-01)
- 🚧 **v1.6 WuzAPI Migration** — Phases 33-38 (in progress)

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

<details>
<summary>✅ v1.3 Flow Health & Cleanup (Phases 14-19) — SHIPPED 2026-02-26</summary>

- [x] Phases 14-19 archived — full details: `.planning/milestones/v1.3-ROADMAP.md`

</details>

<details>
<summary>✅ v1.4 AsyncSession & Test Stability (Phases 20-28) — SHIPPED 2026-02-28</summary>

- [x] Phase 20: Schema Fix (1/1 plan) — completed 2026-02-26
- [x] Phase 21: Async Foundation (5/5 plans) — completed 2026-02-26
- [x] Phase 22: Critical Async Fixes (3/3 plans) — completed 2026-02-27
- [x] Phase 23: Service Migration (9/9 plans) — completed 2026-02-27
- [x] Phase 24: API Routers — Auth / Patients / Flow (7/7 plans) — completed 2026-02-27
- [x] Phase 25: API Routers — Messages / Quiz (5/5 plans) — completed 2026-02-27
- [x] Phase 26: API Routers — Analytics / Admin / System / Remaining (16/16 plans) — completed 2026-02-27
- [x] Phase 27: Test Stability (6/6 plans) — completed 2026-02-28
- [x] Phase 28: Async Session Gap Closure (2/2 plans) — completed 2026-02-28

Full details: `.planning/milestones/v1.4-ROADMAP.md`

</details>

<details>
<summary>✅ v1.5 Saga Orchestrator Deep Dive (Phases 29-32) — SHIPPED 2026-03-01</summary>

- [x] Phase 29: Saga Module Audit (3/3 plans) — completed 2026-02-28
- [x] Phase 30: Flow Integration Trace (4/4 plans) — completed 2026-03-01
- [x] Phase 31: Compensation Integrity (2/2 plans) — completed 2026-03-01
- [x] Phase 32: Test Coverage (5/5 plans) — completed 2026-03-01

Full details: `.planning/milestones/v1.5-ROADMAP.md`

</details>

### 🚧 v1.6 WuzAPI Migration (In Progress)

**Milestone Goal:** Replace Evolution API with WuzAPI as the WhatsApp provider — hard cut, no dual-provider mode. All outbound messages routed through WuzAPIClient, all inbound webhooks parsed by WuzAPI-native handler, all Evolution code tombstoned.

- [x] **Phase 33: New Provider Foundation** - WuzAPIClient package with aiohttp, retry, rate limiter, mock client, and media utility (completed 2026-03-02)
- [ ] **Phase 34: Webhook Handler** - New /webhooks/wuzapi endpoint with HMAC validation, idempotency, LID detection, and opt-out routing
- [ ] **Phase 35: Configuration and Session** - New env vars, startup validation, .env.example update, and session management endpoints
- [ ] **Phase 36: Outbound Migration** - Wire WuzAPIClient into all three outbound callers before any Evolution code is removed
- [ ] **Phase 37: Evolution Cleanup** - Tombstone all Evolution files in one atomic commit after outbound is verified
- [ ] **Phase 38: Tests and CI Validation** - Full regression gate: HMAC, opt-out E2E, JID resolution, source-level import guards

## Phase Details

### Phase 33: New Provider Foundation
**Goal**: WuzAPIClient exists, is unit-tested, and can send text and media messages to WuzAPI — without modifying any existing file
**Depends on**: Phase 32 (v1.5 complete)
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06
**Success Criteria** (what must be TRUE):
  1. WuzAPIClient sends a text message to WuzAPI via `POST /chat/send/text` with `Authorization: {token}` header and receives a non-null `data.Id` in response
  2. WuzAPIClient sends image, audio, video, and document messages using base64-encoded data URIs to their respective type endpoints
  3. WuzAPIClient retries automatically on 5xx and 429 responses (up to 3 attempts) and the circuit breaker key is named `wuzapi`
  4. MockWuzAPIClient is activated by `WHATSAPP_WUZAPI_USE_MOCK=true` and satisfies the same interface as WuzAPIClient
  5. `fetch_and_encode_media()` downloads a media URL and returns a base64 data URI, rejecting files larger than 16 MB with a clear error
**Plans**: 3 plans in 2 waves

Plans:
- [ ] 33-01-PLAN.md — WuzAPIClient core: aiohttp transport, token auth, text send, response parsing, rate limiter, backoff retry (Wave 1)
- [ ] 33-02-PLAN.md — Media send: image/audio/video/document endpoints, base64 data URI encoding, fetch_and_encode_media utility (Wave 2, depends on 33-01)
- [ ] 33-03-PLAN.md — Resilience and mock: circuit breaker wiring (key="wuzapi"), MockWuzAPIClient, factory function (Wave 2, depends on 33-01)

### Phase 34: Webhook Handler
**Goal**: A new `/webhooks/wuzapi` endpoint receives WuzAPI events, validates HMAC with `x-hmac-signature`, deduplicates by `event.Info.ID`, and correctly routes Message and ReadReceipt events — including LID sender detection and opt-out keyword processing
**Depends on**: Phase 33
**Requirements**: WH-01, WH-02, WH-03, WH-04, WH-05, WH-06
**Success Criteria** (what must be TRUE):
  1. A POST to `/webhooks/wuzapi` with a valid WuzAPI Message payload and correct HMAC returns 200; an invalid HMAC returns 403
  2. Inbound Message events yield the correct sender phone, message text, and message ID extracted by `WuzAPIMessageExtractor`
  3. ReadReceipt events map `Receipt.Type` values to the correct `MessageStatus` (SENT, DELIVERED, READ, PLAYED)
  4. A repeated event with the same `event.Info.ID` is deduplicated via Redis SET NX and processed only once
  5. An inbound message containing STOP, PARAR, or CANCELAR triggers the opt-out handler and sets `patient.messaging_stopped_at`; senders with `@lid` addresses are routed to DLQ rather than silently dropped
**Plans**: 3 plans in 2 waves

Plans:
- [ ] 34-01-PLAN.md — Webhook endpoint and HMAC validation: POST /webhooks/wuzapi, raw body read, x-hmac-signature, event type routing stubs (Wave 1)
- [ ] 34-02-PLAN.md — WuzAPIMessageExtractor: Message parser, ReadReceipt mapper, LID detection, PLAYED enum, RECEIPT_TYPE_TO_STATUS (Wave 1, parallel with 34-01)
- [ ] 34-03-PLAN.md — Idempotency, opt-out, LID DLQ wiring: Redis SET NX dedup, STOP/PARAR/CANCELAR handler, LID DLQ routing, router registration (Wave 2, depends on 34-01 + 34-02)

### Phase 35: Configuration and Session
**Goal**: All WuzAPI environment variables exist in settings, application refuses to start without the token, `.env.example` is updated, and session management (connect, status, QR) is exposed through the monitoring API
**Depends on**: Phase 33
**Requirements**: CFG-01, CFG-02, CFG-03, SESS-01, SESS-02, SESS-03
**Success Criteria** (what must be TRUE):
  1. Starting the application with `WHATSAPP_WUZAPI_TOKEN` absent causes an immediate startup failure with a clear error message — not a silent fallback
  2. `WHATSAPP_WUZAPI_BASE_URL`, `WHATSAPP_WUZAPI_TOKEN`, and `WHATSAPP_WUZAPI_WEBHOOK_SECRET` are valid settings fields readable by the WuzAPIClient at startup
  3. `.env.example` contains all three WuzAPI variables and has removed Evolution API variable entries
  4. The monitoring API exposes the WuzAPI session connection state via `GET /session/status` so operators can observe whether WhatsApp is connected
  5. The QR code endpoint returns a base64 QR string usable to pair a new WhatsApp session
**Plans**: TBD

Plans:
- [ ] 35-01: IntegrationsSettings update (add WHATSAPP_WUZAPI_* fields, startup validator, .env.example update)
- [ ] 35-02: Session management endpoints (connect on startup, status monitoring endpoint, QR endpoint wired to WuzAPIClient)

### Phase 36: Outbound Migration
**Goal**: All outbound WhatsApp messages flow through WuzAPIClient — UnifiedWhatsAppService, WhatsAppMessageService queue pipeline, and IdempotentMessageSender are all updated before any Evolution file is removed
**Depends on**: Phase 35 (env vars must exist before callers reference them)
**Requirements**: OUT-01, OUT-02, OUT-03, OUT-04
**Success Criteria** (what must be TRUE):
  1. A patient follow-up message sent via `UnifiedWhatsAppService` is delivered using WuzAPIClient with `Authorization: {token}` header — no Evolution client is called
  2. The queue pipeline in `WhatsAppMessageService` routes outbound messages through WuzAPIClient by constructor injection
  3. `IdempotentMessageSender` imports and uses WuzAPIClient; `whatsapp_id` in the database is populated from `response.data["Id"]` after each send
  4. Phone numbers are sent to WuzAPI as raw digits (no `@s.whatsapp.net` suffix) and the circuit breaker key is `wuzapi`
**Plans**: TBD

Plans:
- [ ] 36-01: UnifiedWhatsAppService migration (swap EvolutionAPIClient for WuzAPIClient, rename circuit breaker to wuzapi, update health check to GET /session/status)
- [ ] 36-02: Queue pipeline and IdempotentMessageSender migration (WhatsAppMessageService constructor injection, IdempotentMessageSender import update, whatsapp_id extraction from response.data.Id)

### Phase 37: Evolution Cleanup
**Goal**: All Evolution API code is tombstoned in a single commit — both Stack A and Stack B clients, the Evolution webhook handler, the Baileys message parser, LID resolution methods, and deprecated env vars are all removed from the active runtime
**Depends on**: Phase 36 (all callers must be updated before tombstoning)
**Requirements**: CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04, CLEAN-05, CLEAN-06
**Success Criteria** (what must be TRUE):
  1. Importing anything from `app/integrations/evolution/` raises `ImportError` with a tombstone message — Stack A is dead
  2. Importing `evolution_client.py` or `mock_evolution.py` from `app/integrations/whatsapp/services/` raises `ImportError` — Stack B is dead
  3. The Evolution webhook router (`/webhooks/whatsapp/*`) is deregistered; requests to that path return 404
  4. `grep -r "EvolutionAPIClient\|EvolutionClient" backend-hormonia/app/ --include="*.py" -i` returns no matches outside tombstone docstrings
  5. `WHATSAPP_EVOLUTION_*` env vars are absent from settings and `.env.example`; LID resolution methods that called Evolution endpoints are removed from `phone_normalizer.py`
**Plans**: TBD

Plans:
- [ ] 37-01: Stack A tombstone (app/integrations/evolution/: client, message_sender, request_handler, webhook_handler, rate_limiter, validators)
- [ ] 37-02: Stack B tombstone and cleanup (evolution_client.py, mock_evolution.py, Evolution webhook deregistration, message_extractor.py tombstone, phone_normalizer.py LID methods removal, WHATSAPP_EVOLUTION_* vars removal)

### Phase 38: Tests and CI Validation
**Goal**: The full test suite passes with WuzAPI contracts, all LGPD-critical paths (opt-out, HMAC, idempotency) are covered by tests, and CI source-level guards confirm zero Evolution imports outside tombstone files
**Depends on**: Phase 37
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):
  1. WuzAPIClient unit tests pass for text send, all media types, auth header correctness, 5xx retry behavior, and rate limiting — using MockWuzAPIClient or a mock HTTP server
  2. Webhook handler tests using real captured WuzAPI JSON fixture payloads pass for Message events, ReadReceipt events, and unknown event types
  3. HMAC validation tests confirm: valid `x-hmac-signature` returns 200; tampered payload returns 403; missing header returns 403
  4. The opt-out end-to-end test confirms: sending "STOP" → `patient.messaging_stopped_at` is set → subsequent sends are blocked by the send guard
  5. `scripts/check_async_isolation.py` passes and a source-level regression test confirms zero imports of `EvolutionClient` or `EvolutionAPIClient` in any non-tombstone file
**Plans**: TBD

Plans:
- [ ] 38-01: WuzAPIClient unit tests (text, media, auth, retry, rate limit)
- [ ] 38-02: Webhook tests with real WuzAPI fixture payloads (Message, ReadReceipt, unknown type, HMAC accept/reject)
- [ ] 38-03: E2E opt-out test and source-level Evolution import regression guard

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-5. Foundations | v1.0 | 13/13 | Complete | 2026-02-22 |
| 6-9. Architecture & Observability | v1.1 | 10/10 | Complete | 2026-02-23 |
| 10-13. AI Framework Migration | v1.2 | 16/16 | Complete | 2026-02-24 |
| 14-19. Flow Health & Cleanup | v1.3 | 31/31 | Complete | 2026-02-26 |
| 20-28. AsyncSession & Test Stability | v1.4 | 54/54 | Complete | 2026-02-28 |
| 29-32. Saga Orchestrator Deep Dive | v1.5 | 14/14 | Complete | 2026-03-01 |
| 33. New Provider Foundation | 3/3 | Complete    | 2026-03-02 | - |
| 34. Webhook Handler | 2/3 | In Progress|  | - |
| 35. Configuration and Session | v1.6 | 0/2 | Not started | - |
| 36. Outbound Migration | v1.6 | 0/2 | Not started | - |
| 37. Evolution Cleanup | v1.6 | 0/2 | Not started | - |
| 38. Tests and CI Validation | v1.6 | 0/3 | Not started | - |

---
*Roadmap created: 2026-02-22*
*Last updated: 2026-03-01 — v1.6 roadmap added (Phases 33-38)*
