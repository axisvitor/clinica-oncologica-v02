# Stack Research

**Domain:** Healthcare WhatsApp backend — WuzAPI provider migration (Evolution API → WuzAPI)
**Researched:** 2026-03-01
**Confidence:** HIGH (WuzAPI API shape verified from official docs), MEDIUM (Docker resource numbers — no official specs), HIGH (Python HTTP client decisions — based on existing requirements)

---

## Executive Verdict: What to Add, Remove, or Change

| Component | Status | Action | Rationale |
|-----------|--------|--------|-----------|
| `aiohttp>=3.10.0` | KEEP | No change — WuzAPIClient uses aiohttp same as EvolutionAPIClient | WuzAPI is REST+JSON; aiohttp is already present and outperforms httpx for high-concurrency async |
| `backoff>=2.2.1` | KEEP | No change | Retry logic pattern stays; WuzAPI returns 429/5xx same as Evolution |
| `httpx>=0.28.1` | KEEP | No change — OTel instrumentation uses httpx | Not used for WhatsApp client; keep for OpenTelemetry |
| `aiohttp` OTel | ADD consideration | `opentelemetry-instrumentation-aiohttp-client` | If tracing WuzAPI calls matters; currently only `httpx` instrumented |
| `EvolutionAPIClient` | TOMBSTONE | Convert to ImportError stub after WuzAPIClient is wired | Both legacy httpx-based and canonical aiohttp-based stacks |
| `mock_evolution.py` | TOMBSTONE | Test double replaced by mock for WuzAPIClient | |
| New env vars | ADD | `WUZAPI_BASE_URL`, `WUZAPI_TOKEN`, `WUZAPI_WEBHOOK_SECRET` | Replace `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_API_INSTANCE` |
| `WEBHOOK_FORMAT=json` | CONFIGURE | Set on WuzAPI sidecar | Default is `form`; JSON mode needed for easy FastAPI parsing |

**No new Python packages are required.** The WuzAPI integration is a pure client-side rewrite using the existing aiohttp stack.

---

## WuzAPI: What It Is

WuzAPI (github.com/asternic/wuzapi) is a Go binary that wraps the `whatsmeow` library (tulir/whatsmeow) and exposes WhatsApp functionality as a REST API. It connects directly to WhatsApp's WebSocket servers — no Puppeteer, no Android emulator — making it significantly lighter than browser-based solutions.

**Architecture difference from Evolution API:**

| Aspect | Evolution API | WuzAPI |
|--------|--------------|--------|
| Model | Instance-per-number (instanceName in URL path) | User-per-token (Authorization header selects session) |
| Auth header | `apikey: <key>` | `Authorization: <user_token>` |
| Phone format in request | `"5491155554444"` (E.164 digits only) | `"5491155554444"` (E.164 digits only; JID `@s.whatsapp.net` appears only in responses) |
| Send text endpoint | `POST /message/sendText/{instanceName}` | `POST /chat/send/text` |
| Send image endpoint | `POST /message/sendMedia/{instanceName}` | `POST /chat/send/image` |
| Webhook HMAC header | `x-evolution-signature` (SHA-256) | `x-hmac-signature` (SHA-256) |
| Webhook payload type | `application/json` always | `application/json` or `application/x-www-form-urlencoded` (env-controlled) |
| Session state | Instance-level (create/restart/delete) | Session-level (connect/disconnect/logout) |
| Health check | `GET /instance/connectionState/{name}` | `GET /session/status` |
| Instance management | Per-instance CRUD | Per-user session lifecycle |

---

## Recommended Stack

### Core Technologies (unchanged)

| Technology | Version (existing) | Purpose | Change? |
|------------|-------------------|---------|---------|
| Python | 3.13 | Runtime | No |
| FastAPI | >=0.128.0,<0.200.0 | API framework | No |
| aiohttp | >=3.10.0,<4.0.0 | WuzAPI HTTP client | No — already present |
| backoff | >=2.2.1,<3.0.0 | Retry with exponential backoff | No |
| pydantic | >=2.12.5,<3.0.0 | Request/response models | No |
| SQLAlchemy (AsyncSession) | >=2.0.45,<2.1.0 | ORM for API paths | No |
| Celery + Dragonfly | celery>=5.6.2 | Task queue | No |

### Supporting Libraries (unchanged — already in requirements.txt)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `backoff` | >=2.2.1,<3.0.0 | Exponential backoff on 429/5xx | Keep existing `@backoff.on_exception` decorator |
| `aiobreaker` | >=1.2.0,<2.0.0 | Circuit breaker wrapping WuzAPI calls | Keep; wraps WuzAPIClient at service layer |
| `tenacity` | >=8.2.3,<9.0.0 | Alternative retry primitives | Keep for pydantic-ai; not needed for WuzAPI client directly |
| `cryptography` | >=43.0.0,<45.0.0 | Fernet encryption | Keep for LGPD key rotation; unrelated to WuzAPI |
| `phonenumbers` | >=8.13.0,<9.0.0 | Phone number formatting | Keep; normalize to E.164 digits before sending to WuzAPI |

### New Dependencies: NONE

WuzAPI uses plain REST+JSON over HTTP. The existing `aiohttp` client is identical in capability to what `EvolutionAPIClient` already uses. No new Python packages are needed.

**Why NOT httpx for WuzAPIClient:**
The existing canonical `EvolutionAPIClient` already uses `aiohttp`. Benchmarks consistently show aiohttp is 2x+ faster than httpx for high-concurrency async workloads. The existing `TCPConnector` with `limit=100, limit_per_host=30` is already tuned for this use case. Switching to httpx for WuzAPI would create an inconsistency with no upside. httpx stays in requirements only for OpenTelemetry instrumentation (`opentelemetry-instrumentation-httpx`).

---

## WuzAPI API Reference (Verified)

### Authentication

```
Authorization: <user_token>
```

Admin endpoints use the admin token (`WUZAPI_ADMIN_TOKEN`). Per-session endpoints use the per-user token created via `POST /admin/users`. The legacy `Token` header is also accepted.

**Evolution API comparison:** Evolution used `apikey: <key>` as a flat header — a different header name, same concept.

### Session Management (replaces instance management)

| Operation | WuzAPI Endpoint | Evolution API Equivalent |
|-----------|-----------------|-------------------------|
| Connect/pair QR | `POST /session/connect` | `POST /instance/create` |
| Check status | `GET /session/status` | `GET /instance/connectionState/{name}` |
| Get QR code | `GET /session/qr` | `GET /instance/qrcode/{name}` |
| Disconnect (keep session) | `POST /session/disconnect` | `PUT /instance/restart/{name}` |
| Logout (clear session) | `POST /session/logout` | `DELETE /instance/logout/{name}` |

Session connect payload:
```json
{
  "Subscribe": ["Message", "ReadReceipt", "HistorySync", "ChatPresence"],
  "Immediate": false
}
```

### Sending Messages

**Send text:**
```
POST /chat/send/text
Authorization: <token>
Content-Type: application/json

{
  "Phone": "5511999887766",
  "Body": "Olá, como você está se sentindo?",
  "Id": "optional-client-message-id"
}
```

Response (HTTP 200):
```json
{
  "code": 200,
  "data": { "Id": "whatsapp-message-id-from-server" },
  "success": true
}
```

**Send image:**
```
POST /chat/send/image
Authorization: <token>
Content-Type: application/json

{
  "Phone": "5511999887766",
  "Image": "https://example.com/image.jpg",
  "Caption": "Optional caption"
}
```

**Send document:**
```
POST /chat/send/document
Authorization: <token>
Content-Type: application/json

{
  "Phone": "5511999887766",
  "Document": "https://example.com/file.pdf",
  "FileName": "relatorio.pdf"
}
```

**Phone format:** E.164 digits only, no `+`, no spaces, no `@s.whatsapp.net`. The `@s.whatsapp.net` JID suffix appears only in webhook event payloads and contact responses, NOT in send requests. The existing `normalize_br_phone()` already produces correct format — just strip non-digits and ensure country code prefix `55`.

### Webhook Configuration

```
POST /webhook
Authorization: <token>
Content-Type: application/json

{
  "webhookUrl": "https://your-api.railway.app/webhooks/whatsapp",
  "webhookEvents": "Message,ReadReceipt"
}
```

HMAC configuration:
```
POST /session/hmac/config
Authorization: <token>
Content-Type: application/json

{
  "key": "your-minimum-32-char-hmac-secret-key"
}
```

### Webhook Payload Format

**Critical:** Set `WEBHOOK_FORMAT=json` on the WuzAPI sidecar. The default `form` format requires URL-decoding a `jsonData` field, which adds complexity. With `WEBHOOK_FORMAT=json`, WuzAPI posts:

```
POST <webhook_url>
Content-Type: application/json
x-hmac-signature: <sha256-hex-of-raw-body>

{
  "type": "Message",
  "event": {
    "Info": {
      "ID": "3EB0C767D097B7C84C5A",
      "Timestamp": "2026-03-01T10:30:00-03:00",
      "FromMe": false,
      "Type": "textMessage",
      "Sender": "5511999887766@s.whatsapp.net",
      "Chat": "5511999887766@s.whatsapp.net"
    },
    "Message": {
      "Conversation": "Patient response text here"
    }
  }
}
```

ReadReceipt event:
```json
{
  "type": "ReadReceipt",
  "event": {
    "Info": {
      "ID": "3EB0C767D097B7C84C5A",
      "Timestamp": "2026-03-01T10:31:00-03:00",
      "Type": "protocolMessage"
    }
  }
}
```

**HMAC signature:** The `x-hmac-signature` header contains the raw hex SHA-256 digest — no `sha256=` prefix. This differs from some other APIs. The existing `WebhookHMACValidator` already handles bare hex by defaulting to SHA-256 when no prefix is found (line 29-30 in `hmac_validator.py`). No change needed to the validator.

**Inbound sender extraction:** Sender JID is `event.Info.Sender` (format: `5511999887766@s.whatsapp.net`). Strip `@s.whatsapp.net` to get the phone number. The existing `contact_data.get("id", "").split("@")[0]` pattern in `EvolutionAPIClient.get_contacts()` already demonstrates this split.

### Supported Event Types

| Event | Subscribe Name | Replaces Evolution API Event |
|-------|---------------|------------------------------|
| Incoming/outgoing messages | `Message` | `MESSAGES_UPSERT` |
| Read receipts / delivery | `ReadReceipt` | `MESSAGES_UPDATE` |
| Typing presence | `ChatPresence` | `PRESENCE_UPDATE` |
| Message history sync | `HistorySync` | (no direct equivalent) |
| User presence | `Presence` | `PRESENCE_UPDATE` |

---

## WuzAPI Webhook Payload vs Evolution API Webhook Payload

The key structural difference:

| Field | Evolution API | WuzAPI (json format) |
|-------|--------------|----------------------|
| Top-level event type | `event` (e.g., `"MESSAGES_UPSERT"`) | `type` (e.g., `"Message"`) |
| Message body | `data.messages[0].message.conversation` | `event.Message.Conversation` |
| Sender JID | `data.key.remoteJid` | `event.Info.Sender` |
| Message ID | `data.key.id` | `event.Info.ID` |
| Timestamp | `data.messageTimestamp` (Unix int) | `event.Info.Timestamp` (ISO 8601) |
| Instance ID | URL path: `/{instanceName}/webhook` | `Authorization` header (user token) |

The existing `WebhookPayload` Pydantic model (in `models/message.py`) has `event: str` and `data: Union[Dict, List[Dict]]`. For WuzAPI, this needs to be replaced with:
```python
class WuzAPIWebhookPayload(BaseModel):
    type: str  # "Message" | "ReadReceipt" | "ChatPresence" | "HistorySync"
    event: Dict[str, Any]  # nested Info + Message/Receipt data
```

---

## Deployment: WuzAPI as Railway Sidecar

WuzAPI is a Go binary distributed as a Docker image (`asternic/wuzapi`). It must run alongside the Python backend.

**Docker image:** `asternic/wuzapi` (Docker Hub: hub.docker.com/r/asternic/wuzapi)

**Resource footprint:** Go + whatsmeow connects directly via WebSocket. No Chromium, no JVM, no Android emulator. Estimated: 50-150 MB RAM, <0.1 CPU at idle. This is the primary advantage over browser-based solutions.

**Database:** WuzAPI stores WhatsApp session keys and user token data. Two options:
- SQLite (default): fine for single-instance; file lives on disk inside container. On Railway, needs a persistent volume or sessions are lost on redeploy.
- PostgreSQL: set `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` env vars. WuzAPI can reuse the existing AWS RDS PostgreSQL instance with a separate `wuzapi` database/schema.

**Recommendation:** Use the existing AWS RDS PostgreSQL instance with a dedicated `wuzapi` database. This avoids volume management on Railway and session loss on redeploys. SQLite on Railway containers is ephemeral by default.

**Required environment variables for WuzAPI sidecar:**

```bash
WUZAPI_ADMIN_TOKEN=<32-char-random>          # Save immediately — auto-generated if omitted
WUZAPI_GLOBAL_ENCRYPTION_KEY=<32-byte-key>   # AES-256 for session key encryption
WUZAPI_GLOBAL_HMAC_KEY=<32-char-minimum>     # Global HMAC fallback (per-session can override)
WEBHOOK_FORMAT=json                           # CRITICAL: use json not form for FastAPI parsing
WUZAPI_GLOBAL_WEBHOOK=<your-fastapi-webhook-url>  # Optional: global fallback webhook
WUZAPI_PORT=8080                              # Default; expose on Railway internal port

# PostgreSQL (point to existing RDS)
DB_HOST=<rds-endpoint>
DB_USER=wuzapi
DB_PASSWORD=<password>
DB_NAME=wuzapi
DB_PORT=5432
DB_SSLMODE=require                            # RDS requires SSL

# Optional
TZ=America/Sao_Paulo
SESSION_DEVICE_NAME=HormoniaBot
```

**Required environment variables to ADD to Python backend (replacing Evolution API vars):**

```bash
WUZAPI_BASE_URL=http://wuzapi:8080          # Internal Railway service URL
WUZAPI_TOKEN=<user-token-for-this-session>  # Created via POST /admin/users on WuzAPI
WUZAPI_WEBHOOK_SECRET=<same-as-hmac-key>    # For validating incoming webhook signatures
```

---

## Alternatives Considered

### HTTP Client for WuzAPIClient

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|------------------------|
| `aiohttp` (keep existing) | `httpx.AsyncClient` | If the codebase migrates entirely to httpx (not planned); httpx has HTTP/2 support but 2x slower for high-concurrency async |
| `aiohttp` | `requests` (sync) | Never — all API paths are async; sync requests blocks the event loop |

### WuzAPI Database Backend

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|------------------------|
| PostgreSQL (existing RDS) | SQLite on Railway volume | Only if Railway persistent volumes are configured correctly; SQLite is zero-config but has Railway persistence caveats |
| PostgreSQL (existing RDS) | A separate PostgreSQL on Railway | Adds cost and management overhead; reusing existing RDS is simpler |

### Webhook Payload Format

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|------------------------|
| `WEBHOOK_FORMAT=json` | `WEBHOOK_FORMAT=form` (default) | Never — form format requires URL-decoding a `jsonData` field and re-parsing JSON inside the FastAPI handler; json mode gives direct `request.json()` access |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Any Python WuzAPI client library from PyPI | None exist (as of 2026-03); WuzAPI has no official Python SDK | Write `WuzAPIClient` directly using aiohttp — it is a simple REST API |
| SQLite for WuzAPI session storage on Railway | Railway containers are ephemeral without explicit volume mounts; SQLite file is lost on redeploy, requiring QR scan again | PostgreSQL via existing AWS RDS (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME) |
| `WEBHOOK_FORMAT=form` (WuzAPI default) | Form format wraps event JSON inside a `jsonData` URL-encoded field — extra parsing step with no benefit | Set `WEBHOOK_FORMAT=json` in WuzAPI sidecar environment |
| Dual-provider (Evolution + WuzAPI simultaneously) | Creates two code paths, double maintenance, confusion about which service is authoritative for message state | Hard-cut: tombstone both Evolution API stacks after WuzAPI is verified working |
| Keeping `WhatsAppInstance` DB model for WuzAPI | WuzAPI uses user/session model, not instance model; `WhatsAppInstance` table maps to Evolution API concepts | Assess whether instance tracking table needs adaptation or can be retired |
| `instanceName` in request payloads | WuzAPI selects session via `Authorization` header token, not a named instance in the URL | Pass user token in `Authorization` header; no instance name in payload or path |

---

## Version Compatibility

| Package | Current Version | WuzAPI Requires | Compatible? |
|---------|----------------|-----------------|-------------|
| `aiohttp` | >=3.10.0,<4.0.0 | (Python client; WuzAPI is Go) | YES — aiohttp 3.13.x supports Python 3.13 with pre-built wheels |
| `backoff` | >=2.2.1,<3.0.0 | N/A | YES |
| `pydantic` | >=2.12.5,<3.0.0 | N/A | YES — Pydantic models for WuzAPI request/response |
| Python | 3.13 | N/A (server is Go) | YES |
| WuzAPI Docker | `asternic/wuzapi:latest` | PostgreSQL 12+ or SQLite | YES — existing RDS is PostgreSQL 14+ |

---

## Integration Points in Existing Codebase

### Files to Tombstone

| File | Path | Action |
|------|------|--------|
| Legacy Evolution client (httpx) | Unknown — referenced in imports elsewhere | Find callers via Grep, tombstone after replacing |
| Canonical Evolution client (aiohttp) | `app/integrations/whatsapp/services/evolution_client.py` | Tombstone after `WuzAPIClient` verified |
| Evolution mock | `app/integrations/whatsapp/services/mock_evolution.py` | Tombstone; replace test double with mock of `WuzAPIClient` |

### Files to Create

| File | Path | Notes |
|------|------|-------|
| WuzAPI client | `app/integrations/whatsapp/services/wuzapi_client.py` | Direct rewrite of `EvolutionAPIClient` using same aiohttp + backoff patterns |
| WuzAPI Pydantic models | `app/integrations/whatsapp/models/wuzapi_message.py` | New payload models (`WuzAPIWebhookPayload`, `WuzAPISendTextRequest`, etc.) |

### Files to Modify

| File | Change |
|------|--------|
| `app/integrations/whatsapp/api/webhooks.py` | Rewrite event routing: `type: Message` vs `event: MESSAGES_UPSERT`; new sender extraction path |
| `app/integrations/whatsapp/security/hmac_validator.py` | No code change needed — existing bare-hex SHA-256 path already handles WuzAPI `x-hmac-signature` format |
| `app/services/unified_whatsapp_service.py` | Replace `EvolutionAPIClient` with `WuzAPIClient`; update constructor and send methods |
| `app/config.py` / `settings` | Add `WUZAPI_BASE_URL`, `WUZAPI_TOKEN`, `WUZAPI_WEBHOOK_SECRET`; deprecate `EVOLUTION_*` vars |
| `app/integrations/whatsapp/models/message.py` | Keep `MessageStatus`, `MessageType` enums (still valid); retire `InstanceStatus` or adapt to session model |
| `.env.example` | Add new vars, mark old ones deprecated |

### HMAC Validation: No Code Change Required

The existing `WebhookHMACValidator.validate_signature()` already handles bare hex (no `sha256=` prefix) by falling back to SHA-256:

```python
# hmac_validator.py line 28-29 — already correct for WuzAPI:
if len(signature) == 128:
    return "sha512", signature
return "sha256", signature  # WuzAPI sends 64-char hex (SHA-256 bare hex)
```

WuzAPI sends a 64-character hex string in `x-hmac-signature`. The validator will correctly interpret this as SHA-256 bare hex. The webhook handler only needs the **header name** updated from whatever Evolution used to `x-hmac-signature`, and the signed content is the raw JSON body (same as with `WEBHOOK_FORMAT=json`).

---

## Phone Number Adapter

WuzAPI expects `"5511999887766"` (E.164 digits, country code prefix, no `+`).

The existing `normalize_phone()` / `normalize_br_phone()` in `app/schemas/validators/phone.py` already handles this. The WuzAPIClient should use the same utility before sending:

```python
from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

def _to_wuzapi_phone(raw_phone: str) -> str:
    """Convert any phone format to WuzAPI E.164 digits."""
    normalized = normalize_phone(raw_phone, mode=PhoneValidationMode.STRICT)
    # normalize_phone returns +5511999887766; strip the leading +
    return normalized.lstrip("+")
```

No new library needed — `phonenumbers>=8.13.0` is already installed for E.164 formatting.

---

## Installation

No new packages. The diff from the existing `requirements.txt` is zero Python additions.

**WuzAPI sidecar (Railway service):**
```bash
# Docker image — no pip install; Go binary
docker pull asternic/wuzapi:latest

# Or pin to a commit SHA for reproducibility:
docker pull asternic/wuzapi:sha-898ed2e
```

**Env var changes in Python backend:**
```bash
# Add:
WUZAPI_BASE_URL=http://wuzapi:8080
WUZAPI_TOKEN=<user-token>
WUZAPI_WEBHOOK_SECRET=<hmac-key>

# Remove (after Evolution tombstoned):
# EVOLUTION_API_URL
# EVOLUTION_API_KEY
# EVOLUTION_API_INSTANCE
```

---

## Sources

- WuzAPI GitHub README — authentication, Docker, env vars, webhook format: https://github.com/asternic/wuzapi/blob/main/README.md (MEDIUM confidence — fetched from raw GitHub)
- WuzAPI API.md — all endpoints, request/response schemas, phone format, HMAC details: https://github.com/asternic/wuzapi/blob/main/API.md (HIGH confidence — official API reference)
- WuzAPI Docker Hub — image available at `asternic/wuzapi`: https://hub.docker.com/r/asternic/wuzapi (MEDIUM confidence — page content inaccessible, verified via SHA layer URLs)
- whatsmeow library — underlying Go library for direct WhatsApp WebSocket: https://github.com/tulir/whatsmeow (HIGH confidence)
- aiohttp PyPI — 3.13.x supports Python 3.13: https://pypi.org/project/aiohttp/ (HIGH confidence)
- httpx PyPI — 0.28.1 current stable, 1.0.dev3 in progress: https://pypi.org/project/httpx/ (HIGH confidence)
- httpx vs aiohttp benchmarks — aiohttp 2x+ faster for high-concurrency async: https://miguel-mendez-ai.com/2024/10/20/aiohttp-vs-httpx (MEDIUM confidence — benchmark sources vary)
- Existing `hmac_validator.py` — bare hex SHA-256 path already handles WuzAPI format: codebase analysis (HIGH confidence)
- Existing `requirements.txt` — current versions of all packages: codebase analysis (HIGH confidence)

---

*Stack research for: Healthcare WhatsApp backend — WuzAPI provider migration*
*Researched: 2026-03-01*
*Confidence: HIGH for API shape and integration points, MEDIUM for Docker resource numbers (Go/whatsmeow is lightweight by design but no official spec found)*
