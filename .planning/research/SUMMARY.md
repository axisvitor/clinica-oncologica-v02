# Project Research Summary

**Project:** Clinica Oncologica v1.6 — WhatsApp Provider Migration (Evolution API to WuzAPI)
**Domain:** Healthcare WhatsApp backend — provider hard-cut migration
**Researched:** 2026-03-01
**Confidence:** HIGH (WuzAPI API shape and authentication verified from official docs + codebase), MEDIUM (webhook payload structure inferred from Go source inspection), HIGH (pitfall scenarios grounded in codebase evidence and verified third-party sources)

---

## Executive Summary

This is a provider replacement milestone, not a new product or a greenfield build. The oncology backend already delivers a working WhatsApp messaging layer through Evolution API (Baileys-based, two client stacks coexisting) for outbound patient follow-up messages and inbound patient replies. The goal is to replace Evolution API entirely with WuzAPI (Go + whatsmeow, direct WebSocket to WhatsApp) in a single hard-cut, with no dual-provider mode, no feature toggles, and simultaneous tombstoning of both Evolution client stacks (Stack A httpx + Stack B aiohttp) once WuzAPI is verified working. The existing `UnifiedWhatsAppService` facade, Redis message queue, DLQ, circuit breaker, Celery task pipeline, and WebSocket pub/sub are all unchanged by this migration — only the outbound client and inbound webhook parser are replaced.

The recommended approach is a 6-phase build order that respects import dependencies: create the new WuzAPI package and client first (zero impact on existing code), add the new webhook endpoint in parallel, update settings with new environment variables, migrate the outbound send path, tombstone all Evolution files in one commit, then validate with tests and CI. The key technical differences requiring careful handling are: WuzAPI uses a user/token model rather than a named instance model; inbound webhook payloads have a completely different structure from Evolution's Baileys JSON; media sends require base64 data URIs rather than URL strings; and the HMAC header name changes from Evolution's custom header to `x-hmac-signature`. No new Python packages are needed — the existing aiohttp, httpx, backoff, pydantic, and phonenumbers stack is fully sufficient.

The primary risks are clinical in nature, not technical. Silent data loss from webhook payload mismatches (STOP/opt-out commands not processed = LGPD Art. 18 violation), Brazilian 9th-digit JID resolution failures (oncology patients in SP/RJ never receive messages), and LID addressing from newer WhatsApp clients (opt-out silently dropped) are all pitfalls that produce no exception — they return HTTP 200 while the clinical operation fails. All three must be addressed in Phase 1 before any production cutover, not deferred to post-migration cleanup. The existing `WebhookHMACValidator` and phone normalization utilities are reusable with minor adaptation; the `EvolutionAPIClient` client logic, webhook parser, and Pydantic models must be fully replaced, not adapted.

---

## Key Findings

### Recommended Stack

The stack decision is clear and requires zero new Python packages. WuzAPI is a Go binary running as a Railway sidecar that exposes a plain REST+JSON API over HTTP. The existing `aiohttp>=3.10.0` client (already present for `EvolutionAPIClient`) is the correct HTTP client for `WuzAPIClient` — it outperforms httpx 2x+ at high concurrency and is already tuned with a `TCPConnector(limit=100, limit_per_host=30)` for this workload. The existing `backoff>=2.2.1`, `pydantic>=2.12.5`, `phonenumbers>=8.13.0`, and `aiobreaker>=1.2.0` packages all carry forward unchanged.

The only infrastructure addition is the WuzAPI Docker sidecar (`asternic/wuzapi`) deployed on Railway, configured with PostgreSQL (using the existing AWS RDS instance with a dedicated `wuzapi` database) to avoid session loss on container restarts. Three new environment variables are required on the Python backend (`WUZAPI_BASE_URL`, `WUZAPI_TOKEN`, `WUZAPI_WEBHOOK_SECRET`); three existing Evolution API env vars are deprecated and removed after tombstoning. The WuzAPI sidecar requires its own set of env vars including `WUZAPI_ADMIN_TOKEN`, `WUZAPI_GLOBAL_ENCRYPTION_KEY`, `WUZAPI_GLOBAL_HMAC_KEY`, `WEBHOOK_FORMAT=json` (critical — default is form-encoded), and PostgreSQL connection details.

Note: FEATURES.md states `WuzAPIClient` should use `httpx.AsyncClient`, but STACK.md and ARCHITECTURE.md both recommend keeping `aiohttp` for consistency with the canonical `EvolutionAPIClient` pattern. The aiohttp recommendation is adopted here as it aligns with the existing codebase pattern, avoids creating an inconsistency, and is faster for high-concurrency async.

**Core technologies (unchanged):**
- `aiohttp>=3.10.0`: WuzAPIClient HTTP transport — same as EvolutionAPIClient, no change
- `backoff>=2.2.1`: Retry on 429/5xx from WuzAPI — same decorator pattern, no change
- `pydantic>=2.12.5`: New WuzAPI request/response Pydantic models — no version change
- `phonenumbers>=8.13.0`: E.164 normalization — existing `normalize_phone()` produces correct WuzAPI format already
- `aiobreaker>=1.2.0`: Circuit breaker wrapping WuzAPIClient — rename breaker from `"evolution_api"` to `"wuzapi"`

**New infrastructure (sidecar, not Python):**
- WuzAPI Docker sidecar: `asternic/wuzapi` — Go + whatsmeow, direct WebSocket to WhatsApp
- PostgreSQL backend for WuzAPI: existing AWS RDS, dedicated `wuzapi` database

**New Python files (no new packages):**
- `app/integrations/wuzapi/client.py`: `WuzAPIClient` with aiohttp + backoff + rate limiter
- `app/integrations/wuzapi/models.py`: `WuzAPISendTextRequest`, `WuzAPIResponse`, `WuzAPISessionStatus`
- `app/integrations/wuzapi/errors.py`: `WuzAPIError` exception hierarchy
- `app/integrations/wuzapi/mock_wuzapi.py`: test double
- `app/integrations/wuzapi/api/webhooks.py`: webhook router at `/webhooks/wuzapi`
- `app/services/webhook/utils/wuzapi_message_extractor.py`: pure-function parser for WuzAPI event JSON

**Tombstoned (after migration):**
- `app/integrations/evolution/client.py` (Stack A, httpx)
- `app/integrations/evolution/message_sender.py`, `request_handler.py`, `webhook_handler.py`
- `app/integrations/whatsapp/services/evolution_client.py` (Stack B, aiohttp)
- `app/integrations/whatsapp/services/mock_evolution.py`
- `app/integrations/whatsapp/api/webhooks.py` (Evolution webhook handler)
- `app/services/webhook/utils/message_extractor.py` (Evolution Baileys parser)

### Expected Features

The feature mapping between Evolution API and WuzAPI has clear tiers. All table-stakes features have direct equivalents in WuzAPI, though several require payload structure adaptation. The most significant technical adaptation is media sending: WuzAPI requires base64 data URIs where Evolution accepted URLs, requiring a new `fetch_and_encode_media()` utility.

**Must have (table stakes — migration is broken without these):**
- Send text message (`POST /chat/send/text`) — field rename only; response ID at `data.Id` not `message.key.id`
- Send media (image/audio/document/video) — requires base64 data URI; new `fetch_and_encode_media()` utility with 16 MB guard
- Inbound message webhook — completely different payload structure; new `WuzAPIMessageExtractor` required
- ReadReceipt webhook — `type=ReadReceipt` replaces `MESSAGES_UPDATE`; `Receipt.Type` maps to `MessageStatus`
- HMAC webhook validation — header changes to `x-hmac-signature`; existing `WebhookHMACValidator` logic unchanged
- Session management (connect, disconnect, logout, status, QR) — adapted to WuzAPI session model
- WhatsApp number check (`POST /user/check`) — replaces `POST /chat/whatsappNumbers/{instance}`
- LGPD opt-out handler (STOP/PARAR) — same logic, different extraction path in new payload parser
- Idempotency (Redis SET NX) — keyed on `event.Info.ID` instead of `data.messages[0].key.id`
- Environment variable migration — add `WHATSAPP_WUZAPI_*`, remove `WHATSAPP_EVOLUTION_*`
- Evolution API code tombstoned — both Stack A and Stack B simultaneously

**Should have (post-v1.6 validation):**
- `POST /chat/markread` — mark patient messages read after opt-out processing (minor UX)
- S3 media delivery for inbound patient media — only if patients send images/audio at scale
- LID resolution — only if `@lid` JIDs appear in production payloads

**Defer to v2+:**
- PairPhone authentication (`POST /session/pairphone`) — QR-less automated session setup
- RabbitMQ event queue integration — only if HTTP webhook delivery proves unreliable at scale
- Multi-user WuzAPI support — only if clinic expands to multiple WhatsApp numbers

**Not buildable in WuzAPI (broken upstream):**
- Interactive button messages — deprecated by WhatsApp in 2022; whatsmeow cannot send them despite route existing; keep existing TEXT fallback (already production behavior)
- Interactive list messages — same issue as buttons; keep existing TEXT fallback

### Architecture Approach

The architecture follows a hard provider replace pattern, not an abstraction layer. `UnifiedWhatsAppService` is the preserved facade — it continues to route to direct-API mode and queue mode, with `EvolutionAPIClient` swapped for `WuzAPIClient` internally. The existing circuit breaker, Redis message queue, DLQ, Celery pipeline, and WebSocket pub/sub are untouched. The Evolution webhook endpoint (`/webhooks/whatsapp/*`) is tombstoned and replaced with a clean `/webhooks/wuzapi` endpoint that dispatches on `payload["type"]` rather than URL-path-based event routing.

The six-phase build order from ARCHITECTURE.md is the canonical implementation plan: Phase 1 creates the new WuzAPI package without touching any existing files; Phase 2 adds the webhook handler in parallel; Phase 3 updates settings; Phase 4 migrates outbound send path; Phase 5 tombstones all Evolution files; Phase 6 runs tests and CI validation. This order ensures no existing functionality is broken until WuzAPIClient is fully tested, and enables rollback at any point before Phase 5.

**Major components:**
1. `WuzAPIClient` (`app/integrations/wuzapi/client.py`) — HTTP client for all WuzAPI REST calls; aiohttp + backoff + rate limiter; `Authorization: {token}` header
2. `WuzAPIWebhookHandler` (`app/integrations/wuzapi/api/webhooks.py`) — single endpoint `/webhooks/wuzapi`; dispatches on `type` field; reuses `WebhookHMACValidator` and idempotency pattern
3. `WuzAPIMessageExtractor` (`app/services/webhook/utils/wuzapi_message_extractor.py`) — pure-function parser for `type=Message` and `type=ReadReceipt` payloads; replaces Evolution Baileys parser
4. `UnifiedWhatsAppService` (modified) — swap `EvolutionAPIClient` reference to `WuzAPIClient`; rename circuit breaker; update health check to call `GET /session/status`
5. `IntegrationsSettings` (modified) — add `WHATSAPP_WUZAPI_*` fields; deprecate and remove `WHATSAPP_EVOLUTION_*` fields
6. Evolution stacks (tombstoned) — Stack A (`app/integrations/evolution/`) and Stack B (`app/integrations/whatsapp/services/evolution_client.py`) both raised to `ImportError` in Phase 5

### Critical Pitfalls

1. **Webhook payload structure completely different — silent data loss:** WuzAPI payloads use whatsmeow-native Go struct naming. Existing Evolution handler accessing `data.messages[0].message.conversation` on a WuzAPI payload gets `None`, returns HTTP 200, and WuzAPI never retries. Patient STOP/opt-out commands are silently dropped (LGPD Art. 18 violation). Prevention: capture at least 10 real WuzAPI webhook payloads as fixtures BEFORE writing any handler code; build WuzAPI-specific Pydantic models; add schema validation logging at handler entry permanently in staging.

2. **Brazilian 9th-digit split — silent delivery failures for SP/RJ patients:** Oncology patients in DDD 11-19, 21, 22, 24, 27-28 may have WhatsApp accounts bound to old 8-digit JIDs. Sending to the 9-digit JID produces silent failure or error 479. Prevention: add `POST /user/check` call before first send to each patient; cache resolved JID in `patient.whatsapp_jid`; wire existing `build_br_phone_variants()` into JID resolution; run one-time Celery task to resolve JIDs for all existing patients at cutover.

3. **HMAC header name and signing body mismatch — all webhooks return 403:** WuzAPI uses `x-hmac-signature` (lowercase, no prefix) against raw request bytes. Reading `await request.json()` before HMAC validation consumes the body and makes raw-byte signing impossible. The existing HMAC_FAILURE_BLOCK threshold of 5 failures will block WuzAPI's IP within seconds. Prevention: read `body = await request.body()` once at handler entry, then `json.loads(body)` separately; update header lookup from Evolution's custom header to `x-hmac-signature`; verify HMAC key is at least 32 characters; write test: wrong signature → 403, correct signature → 200.

4. **Message ID format difference breaks idempotency and status tracking:** WuzAPI returns `response["data"]["Id"]`; Evolution returned `response["message"]["key"]["id"]`. If the wrong field path is used, `message.whatsapp_id` is NULL in the database. ReadReceipt events find no matching record, DELIVERED/READ statuses never update. Prevention: log full send response body in dev mode; write assertion test that `whatsapp_id` is non-null after every send; in ReadReceipt handler, log WARNING when no matching record is found.

5. **LID addressing — LGPD opt-out failure risk:** WhatsApp's 2025 LID privacy feature means some patients' WhatsApp clients send `sender@lid` instead of `phone@s.whatsapp.net`. All patient lookups fail silently. A patient sending STOP with a LID address is not opted out — LGPD Art. 18 violation in a healthcare context. Prevention: add LID detection in message extractor from day one; call WuzAPI contact/user endpoint to resolve LID; route unresolvable LIDs to DLQ for manual processing; never drop silently; log every `@lid` sender at WARNING.

6. **Session persistence — QR required after every Railway restart:** WuzAPI default SQLite storage is lost on container restart; Railway containers are ephemeral without persistent volumes. Prevention: configure WuzAPI with PostgreSQL (existing RDS, dedicated `wuzapi` schema); test a stop/start cycle in staging before production cutover; add health check alert if session shows disconnected for more than 5 minutes.

---

## Implications for Roadmap

Based on combined research, the 6-phase structure from ARCHITECTURE.md is the canonical roadmap. The ordering is dictated by import dependencies — nothing can be tombstoned until all its callers are updated; the new WuzAPI infrastructure must be fully tested before any Evolution code is removed.

### Phase 1: New Provider Foundation

**Rationale:** Create the entire WuzAPI package (`client.py`, `models.py`, `errors.py`, `mock_wuzapi.py`) with zero modifications to existing files. This phase can be reviewed and tested in isolation with no risk to production. It also includes the critical non-code prerequisites: capture real WuzAPI webhook payloads as test fixtures, and complete the environment variable audit (`grep -r "WHATSAPP_EVOLUTION"`) before any migration code is written. Rate limiter must be included in `WuzAPIClient` from the first implementation, not added later.
**Delivers:** Working `WuzAPIClient` with aiohttp + backoff + rate limiter; Pydantic models for all WuzAPI request/response types; `WuzAPIError` exception hierarchy; mock client for test isolation; real captured WuzAPI webhook JSON fixtures stored in `tests/fixtures/wuzapi/`; unit tests against mock HTTP.
**Addresses:** Text send, media send (with `fetch_and_encode_media()` utility), session management endpoints, WhatsApp number check, auth header migration, rate limiting.
**Avoids:** Auth header error (Pitfall 3), missing rate limiter (Pitfall 10 from PITFALLS.md), wrong response ID extraction (Pitfall 4).

### Phase 2: Webhook Handler

**Rationale:** The new webhook endpoint can be registered alongside the existing Evolution endpoint temporarily, allowing real WuzAPI events to be tested before the outbound path is migrated. Phase 2 must include LID resolution and 9th-digit JID handling from day one — these cannot be deferred because a patient sending STOP with a LID address and not being opted out is an immediate LGPD compliance failure.
**Delivers:** `/webhooks/wuzapi` endpoint with HMAC validation, idempotency, and event dispatch; `WuzAPIMessageExtractor` with LID detection and `@lid` DLQ routing; `StatusWebhookHandler` updated with WuzAPI `ReadReceipt` mapping (`"read"` → `MessageStatus.READ`); `phone_normalizer.py` updated to remove LID resolution methods (which call Evolution endpoints that will no longer exist); integration tests using real captured WuzAPI payloads as fixtures.
**Uses:** Existing `WebhookHMACValidator` (header name updated to `x-hmac-signature`); existing idempotency pattern (Redis SET NX, extraction path updated to `event.Info.ID`); existing opt-out handler (phone extraction path updated to `event.Info.Chat.User`).
**Avoids:** Webhook payload silent data loss (Pitfall 1), LID opt-out failure LGPD risk (Pitfall 6), HMAC validation failures (Pitfall 5), status event mapping gaps (Pitfall 8).

### Phase 3: Settings and Environment Variables

**Rationale:** New environment variables must be available in settings before any outbound code references them. This phase also marks Evolution env vars as deprecated in their field descriptions. `.env.example` is updated to add WuzAPI vars and comment out Evolution vars with migration instructions.
**Delivers:** `IntegrationsSettings` with `WHATSAPP_WUZAPI_BASE_URL`, `WHATSAPP_WUZAPI_TOKEN`, `WHATSAPP_WUZAPI_TIMEOUT_SECONDS`, `WHATSAPP_WUZAPI_WEBHOOK_SECRET`, `WHATSAPP_WUZAPI_USE_MOCK` fields; startup validation that refuses to start if `WUZAPI_TOKEN` is absent in non-development environments (fails fast with clear error, not silent fallback); `.env.example` updated; Railway staging env vars updated.
**Avoids:** Instance vs session env var mismatch silent misconfiguration (Pitfall 7), application silently falling back to `"default"` session identifier.

### Phase 4: Migrate Outbound Path

**Rationale:** All outbound messaging is routed through `WuzAPIClient`. This phase updates the three callers of Evolution clients: `UnifiedWhatsAppService` (Stack B via facade), `WhatsAppMessageService` (Stack B via queue worker), and `IdempotentMessageSender` (Stack A directly). `IdempotentMessageSender` must be updated before Stack A is tombstoned in Phase 5 — tombstoning Stack A first raises `ImportError` at Celery worker startup, breaking all task processing.
**Delivers:** `UnifiedWhatsAppService` using `WuzAPIClient`; circuit breaker renamed to `"wuzapi"`; health check calling `GET /session/status`; `instance_name` removed from `MessageRequest`; `WhatsAppMessageService` accepting `WuzAPIClient` by constructor injection; `IdempotentMessageSender` importing `WuzAPIClient`; `whatsapp_id` extracted from `response.data["Id"]`; JID resolution added to send path for first-send to each patient.
**Avoids:** Import dependency ordering violation (Anti-Pattern 4 from ARCHITECTURE.md), `instance_name` in WuzAPI requests (Anti-Pattern 5), stale circuit breaker key name confusion during incidents.

### Phase 5: Tombstone Evolution Code

**Rationale:** All Evolution files are raised to `ImportError` in a single commit after Phase 4 tests pass. A single commit is important — partial tombstoning creates a window where some callers are updated and some are not, making the `ImportError` harder to diagnose. This phase also removes deprecated `WHATSAPP_EVOLUTION_*` fields from settings and deregisters the Evolution webhook router.
**Delivers:** 8 tombstoned files (Stack A: 4 files in `app/integrations/evolution/`; Stack B: 3 files in `app/integrations/whatsapp/services/` and `api/`; Evolution payload parser: 1 file); deprecated Evolution settings removed; `grep -r "evolution" backend-hormonia/app/ --include="*.py" -i` returns only tombstone docstrings; Evolution webhook router deregistered; Evolution env vars confirmed absent from Railway staging.
**Avoids:** Dual-stack maintenance burden (Anti-Pattern 1 from ARCHITECTURE.md), Evolution webhook URL reuse with incompatible payload format (Anti-Pattern 2).

### Phase 6: Tests and CI Validation

**Rationale:** Full regression validation before production cutover. This phase is a gate, not an afterthought. The specific acceptance criteria from PITFALLS.md "Looks Done But Isn't" checklist must all pass.
**Delivers:** All test fixtures updated to use `MockWuzAPIClient`; end-to-end webhook tests with real captured WuzAPI JSON; HMAC validation test (wrong signature → 403, correct signature → 200); ReadReceipt status transition test (`Receipt.Type: "read"` → `MessageStatus.READ`); JID resolution test for DDD 11 and DDD 21 numbers; opt-out end-to-end test (send "STOP" → `patient.messaging_stopped_at` set → no further sends); session persistence test (stop/start WuzAPI → reconnect without QR); rate limiter load test (70 sends/minute → no ban signal); CI scripts pass (`check_async_isolation.py`, `check_agent_run_calls.py`); PII not logged in new webhook handler output.

### Phase Ordering Rationale

- Phase 1 before Phase 4: `WuzAPIClient` must exist and be unit-tested before it can replace `EvolutionAPIClient` in the service layer.
- Phase 2 in parallel with Phase 1: The webhook handler has no dependency on the outbound client; parallel development reduces total wall time.
- Phase 3 before Phase 4: Settings fields must exist before the code that reads them is committed.
- Phase 4 before Phase 5: `IdempotentMessageSender` must import `WuzAPIClient` before Stack A is tombstoned; tombstoning first causes Celery worker startup `ImportError`.
- Phase 5 as single commit: All Evolution tombstones in one commit eliminates partial-tombstone diagnostic confusion.
- Phase 6 as gate: Production cutover is blocked until all checklist items pass — especially opt-out, HMAC, and JID resolution.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (WuzAPI client — real payload capture):** WuzAPI webhook payload structure is MEDIUM confidence (inferred from Go source inspection, not from official JSON schema documentation). Real payload capture BEFORE writing parsers is mandatory, not optional. The difference between actual and inferred structure in wmiau.go Go structs has led to silent bugs in similar migrations.
- **Phase 2 (LID resolution):** WuzAPI LID→JID resolution via contact/user endpoints is not fully documented in API.md. The resolution mechanism for `@lid` senders in whatsmeow's internal store may require consulting whatsmeow issues directly. This needs a dedicated spike if LID senders appear in staging during Phase 2 validation.
- **Phase 4 (JID 9th-digit resolution at scale):** The one-time Celery task to resolve JIDs for all existing patients needs careful design — calling `POST /user/check` for each patient at WuzAPI rate limits could take hours for large patient cohorts. Batching and progress checkpointing need to be designed before Phase 4 begins.

Phases with standard patterns (research-phase not needed):
- **Phase 3:** Settings field additions and deprecations are deterministic, fully documented in existing research with exact field names and types.
- **Phase 5:** Tombstone pattern is well-established in this codebase (18+ files tombstoned in prior milestones). No novel patterns required.
- **Phase 6:** Test and CI validation patterns are documented in PITFALLS.md "Looks Done But Isn't" checklist with explicit pass/fail criteria.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | WuzAPI API shape verified from official API.md (fetched directly). aiohttp recommendation consistent across STACK.md and ARCHITECTURE.md. Zero new Python packages confirmed. Docker image verified on Docker Hub. RDS PostgreSQL backend recommendation is straightforward infrastructure decision. |
| Features | HIGH (send) / MEDIUM (inbound) | Send endpoints: HIGH (verified from API.md with explicit request/response examples). Inbound webhook payload structure: MEDIUM (inferred from wmiau.go Go source inspection, not official JSON schema). Button/list deprecation: HIGH (verified from whatsmeow maintainer statement and DEV.to article). Base64 media requirement: HIGH (confirmed from API.md). |
| Architecture | HIGH | Full codebase read of all affected files confirms exact change set. Six-phase build order respects all import dependencies. Component boundary decisions (keep facade, replace client, tombstone both stacks simultaneously) are well-grounded. Anti-patterns are identified with specific code evidence. |
| Pitfalls | HIGH | All critical pitfalls grounded in codebase analysis (Evolution payload paths grep-verified, HMAC validator logic read, LID resolution code confirmed). Brazilian 9th-digit issue verified from two WhatsApp BSP sources (Zoko, Gupshup). LID behavior verified from whatsmeow issues. LGPD violation scenarios mapped to specific articles (Art. 18, Art. 46, Art. 48). |

**Overall confidence:** HIGH

### Gaps to Address

- **WuzAPI webhook payload JSON schema:** The exact structure of WuzAPI webhook payloads is MEDIUM confidence (inferred from Go source, not official JSON docs). Real payload capture must happen before any Phase 2 parser code is written. If actual payloads differ from the inferred structure (especially for media messages and ReadReceipt events), parser logic in `WuzAPIMessageExtractor` must be revised. Risk: low if capture is done first; high if parsers are written from documentation assumptions.

- **LID resolution mechanism in WuzAPI:** The whatsmeow library resolves `@lid` JIDs internally via a local contact store populated by conversations. If a patient with a LID-mode WhatsApp sends STOP before they have any previous conversation in the WuzAPI session, the LID cannot be resolved from the local store. The research recommends DLQ routing for unresolvable LIDs, but the latency and retry window for this case is not fully characterized. This needs validation in staging against a real newer WhatsApp client before production cutover.

- **Brazilian 9th-digit JID resolution at patient-cohort scale:** The `POST /user/check` endpoint call per patient during the one-time JID resolution task is the correct approach, but the WuzAPI rate limits for this endpoint are not documented. If the clinic has hundreds or thousands of patients, the resolution task could take hours or trigger WhatsApp account-level throttling. Batch size and rate limit behavior should be tested against the staging WuzAPI instance before running in production.

- **WuzAPI HMAC with `WEBHOOK_FORMAT=json`:** The HMAC is computed over the raw request body. With `WEBHOOK_FORMAT=json`, the raw body is a JSON string. The signing and verification must be byte-exact. The existing `WebhookHMACValidator` should work unchanged if raw bytes are read first (before any JSON parsing), but this exact combination has not been integration-tested in this codebase. First Phase 2 task should be a HMAC test fixture test before any other webhook handler code.

- **aiohttp vs httpx inconsistency between FEATURES.md and other research files:** FEATURES.md recommends `httpx.AsyncClient` for `WuzAPIClient`; STACK.md and ARCHITECTURE.md recommend `aiohttp` for consistency with `EvolutionAPIClient`. This summary adopts the aiohttp recommendation, but the rationale should be documented explicitly in the implementation story's architecture decision section so the team is aligned before Phase 1 begins.

---

## Sources

### Primary (HIGH confidence)
- WuzAPI API.md — all endpoints, request/response schemas, phone format, HMAC details: https://github.com/asternic/wuzapi/blob/main/API.md
- WuzAPI README.md — authentication model, session vs instance, HMAC configuration, Docker deployment: https://github.com/asternic/wuzapi/blob/main/README.md
- whatsmeow events package — `events.Message` and `events.Receipt` Go struct definitions: https://pkg.go.dev/go.mau.fi/whatsmeow/types/events
- whatsmeow discussion #534 — buttons deprecated, cannot be sent via unofficial libraries: https://github.com/tulir/whatsmeow/discussions/534
- DEV.to — buttons and lists deprecated timeline (Aug 2021, Apr 2022, May 2022 final block): https://dev.to/purpshell/buttons-and-lists-get-deprecated-by-many-libraries-54h
- aiohttp PyPI — 3.13.x supports Python 3.13: https://pypi.org/project/aiohttp/
- Codebase analysis (all affected files read directly) — `evolution_client.py`, `webhooks.py`, `unified_whatsapp_service.py`, `hmac_validator.py`, `message_extractor.py`, `phone_normalizer.py`, `idempotent_sender.py`, `status_handler.py`, `integrations.py` settings, `message.py` models

### Secondary (MEDIUM confidence)
- WuzAPI wmiau.go — webhook event dispatch, postmap structure for Message and ReadReceipt events (inferred from Go source): https://github.com/asternic/wuzapi/blob/main/wmiau.go
- WuzAPI routes.go — complete route list including /chat/send/buttons and /chat/send/list: https://github.com/asternic/wuzapi/blob/main/routes.go
- WuzAPI issue #160 + #232 — token field removed from webhook payloads for security: https://github.com/asternic/wuzapi/issues/160
- Brazil 9th-digit WhatsApp JID inconsistency (Zoko): https://www.zoko.io/learning-article/whatsapp-id-brazil-mexico
- Brazil 9th-digit inconsistency (Gupshup): https://support.gupshup.io/hc/en-us/articles/4407840924953
- whatsmeow LID issue #859 — LID error 479: https://github.com/tulir/whatsmeow/issues/859
- LID/JID transition explanation (SprintHub): https://docs.sprinthub.com/en/news/behind-the-scenes-change-on-whatsapp-the-era-of-lid-and-jid-and-the-end-of-exposing-the-cell-phone-n
- aiohttp vs httpx benchmarks — aiohttp 2x+ faster for high-concurrency async: https://miguel-mendez-ai.com/2024/10/20/aiohttp-vs-httpx

### Tertiary (informational)
- WuzAPI Docker Hub — `asternic/wuzapi` image: https://hub.docker.com/r/asternic/wuzapi
- whatsmeow ban risk discussion #567 — WhatsApp account behavior with unofficial APIs: https://github.com/tulir/whatsmeow/discussions/567
- Baileys v7 LID migration docs — covers LID handling in whatsmeow-equivalent library: https://baileys.wiki/docs/migration/to-v7.0.0/

---
*Research completed: 2026-03-01*
*Ready for roadmap: yes*
