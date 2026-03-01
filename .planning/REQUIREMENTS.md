# Requirements: Clinica Oncologica v1.6

**Defined:** 2026-03-01
**Core Value:** Medicos acompanham pacientes oncologicos continuamente entre consultas via WhatsApp, com questionarios humanizados que coletam dados clinicos sem sobrecarregar o paciente.

## v1.6 Requirements

Requirements for WuzAPI migration. Each maps to roadmap phases.

### Client Infrastructure

- [ ] **CLI-01**: WuzAPIClient sends text messages via `POST /chat/send/text` with Token auth header
- [ ] **CLI-02**: WuzAPIClient sends media messages (image, audio, video, document) via type-specific endpoints with base64 data URI encoding
- [ ] **CLI-03**: WuzAPIClient uses aiohttp with backoff retry (3 retries on 5xx/429/timeout) and sliding-window rate limiter
- [ ] **CLI-04**: Circuit breaker wraps WuzAPIClient calls (renamed from `evolution_api` to `wuzapi`)
- [ ] **CLI-05**: MockWuzAPIClient provides drop-in test double activated by `WHATSAPP_WUZAPI_USE_MOCK=true`
- [ ] **CLI-06**: `fetch_and_encode_media()` utility downloads media URLs and converts to base64 data URIs with 16MB size guard

### Webhook Handling

- [ ] **WH-01**: New webhook endpoint receives WuzAPI events at `/webhooks/wuzapi` and routes by `type` field (Message, ReadReceipt)
- [ ] **WH-02**: Inbound message parser extracts sender phone, message text, media info, and message ID from WuzAPI `Message` event payload
- [ ] **WH-03**: ReadReceipt parser maps WuzAPI receipt types to internal `MessageStatus` (SENT, DELIVERED, READ, PLAYED)
- [ ] **WH-04**: HMAC validation uses `x-hmac-signature` header with SHA-256 on raw request body bytes
- [ ] **WH-05**: LGPD opt-out handler detects STOP/PARAR/CANCELAR keywords in WuzAPI inbound message payloads
- [ ] **WH-06**: Webhook idempotency uses WuzAPI `event.Info.ID` as deduplication key in Redis SET NX

### Session Management

- [ ] **SESS-01**: Application startup calls `POST /session/connect` and verifies session is connected before accepting sends
- [ ] **SESS-02**: Session status endpoint (`GET /session/status`) exposes connection state via monitoring API
- [ ] **SESS-03**: QR code endpoint (`GET /session/qr`) returns base64 QR for WhatsApp pairing

### Configuration

- [ ] **CFG-01**: New env vars added: `WHATSAPP_WUZAPI_BASE_URL`, `WHATSAPP_WUZAPI_TOKEN`, `WHATSAPP_WUZAPI_WEBHOOK_SECRET`
- [ ] **CFG-02**: Startup validation refuses to start if `WHATSAPP_WUZAPI_TOKEN` is missing (hard fail)
- [ ] **CFG-03**: `.env.example` updated with all WuzAPI env vars and removed Evolution API vars

### Outbound Migration

- [ ] **OUT-01**: UnifiedWhatsAppService uses WuzAPIClient instead of EvolutionAPIClient for all outbound messages
- [ ] **OUT-02**: WhatsAppMessageService queue pipeline wired to WuzAPIClient
- [ ] **OUT-03**: IdempotentMessageSender updated to use WuzAPIClient instead of legacy EvolutionClient (Stack A)
- [ ] **OUT-04**: Phone format adapted: raw digits sent to WuzAPI (no `@s.whatsapp.net` suffix on send — WuzAPI accepts raw Phone field)

### Evolution Cleanup

- [ ] **CLEAN-01**: Stack A tombstoned: `app/integrations/evolution/` (client, message_sender, request_handler, webhook_handler, rate_limiter, validators) converted to ImportError sentinels
- [ ] **CLEAN-02**: Stack B tombstoned: `app/integrations/whatsapp/services/evolution_client.py` and `mock_evolution.py` converted to ImportError sentinels
- [ ] **CLEAN-03**: Evolution webhook handler tombstoned: `app/integrations/whatsapp/api/webhooks.py` deregistered from router
- [ ] **CLEAN-04**: Evolution message extractor tombstoned: `app/services/webhook/utils/message_extractor.py`
- [ ] **CLEAN-05**: LID resolution methods removed from `phone_normalizer.py` (WuzAPI/whatsmeow handles internally)
- [ ] **CLEAN-06**: `WHATSAPP_EVOLUTION_*` env vars removed from settings and `.env.example`

### Testing & Validation

- [ ] **TEST-01**: WuzAPIClient unit tests cover text send, media send (all types), auth header, retry on 5xx, rate limiting
- [ ] **TEST-02**: Webhook handler tests with real WuzAPI payload fixtures for Message, ReadReceipt, and unknown event types
- [ ] **TEST-03**: HMAC validation tests verify `x-hmac-signature` acceptance and rejection of tampered payloads
- [ ] **TEST-04**: Opt-out E2E test: inbound STOP message → patient.messaging_stopped_at set → send guard blocks future messages
- [ ] **TEST-05**: Source-level regression tests verify zero imports of `EvolutionClient` or `EvolutionAPIClient` outside tombstone files

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Enhanced WuzAPI Features

- **WUZAPI-01**: PairPhone authentication for QR-less automated session setup
- **WUZAPI-02**: S3 media delivery for inbound patient media (images/audio at scale)
- **WUZAPI-03**: RabbitMQ event integration (WuzAPI publishes to queue instead of webhooks)
- **WUZAPI-04**: Mark messages as read after processing (`POST /chat/markread`)
- **WUZAPI-05**: Message reactions for patient confirmation UX

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dual-provider mode (Evolution + WuzAPI) | Hard cut is cleaner; no feature toggle complexity |
| WuzAPI multi-session (multiple WhatsApp numbers) | Single clinic number is sufficient |
| WuzAPI group management | No group messaging in patient flow |
| WuzAPI S3 media storage | Defer unless patient media volume requires it |
| WhatsApp Business API (official) | WuzAPI is the chosen self-hosted solution |
| Button/list message migration | WhatsApp deprecated third-party interactive messages in 2022 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLI-01 | Phase 33 | Pending |
| CLI-02 | Phase 33 | Pending |
| CLI-03 | Phase 33 | Pending |
| CLI-04 | Phase 33 | Pending |
| CLI-05 | Phase 33 | Pending |
| CLI-06 | Phase 33 | Pending |
| WH-01 | Phase 34 | Pending |
| WH-02 | Phase 34 | Pending |
| WH-03 | Phase 34 | Pending |
| WH-04 | Phase 34 | Pending |
| WH-05 | Phase 34 | Pending |
| WH-06 | Phase 34 | Pending |
| SESS-01 | Phase 35 | Pending |
| SESS-02 | Phase 35 | Pending |
| SESS-03 | Phase 35 | Pending |
| CFG-01 | Phase 35 | Pending |
| CFG-02 | Phase 35 | Pending |
| CFG-03 | Phase 35 | Pending |
| OUT-01 | Phase 36 | Pending |
| OUT-02 | Phase 36 | Pending |
| OUT-03 | Phase 36 | Pending |
| OUT-04 | Phase 36 | Pending |
| CLEAN-01 | Phase 37 | Pending |
| CLEAN-02 | Phase 37 | Pending |
| CLEAN-03 | Phase 37 | Pending |
| CLEAN-04 | Phase 37 | Pending |
| CLEAN-05 | Phase 37 | Pending |
| CLEAN-06 | Phase 37 | Pending |
| TEST-01 | Phase 38 | Pending |
| TEST-02 | Phase 38 | Pending |
| TEST-03 | Phase 38 | Pending |
| TEST-04 | Phase 38 | Pending |
| TEST-05 | Phase 38 | Pending |

**Coverage:**
- v1.6 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 — traceability complete (33/33 mapped to Phases 33-38)*
