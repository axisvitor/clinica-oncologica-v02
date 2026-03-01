# Phase 33: New Provider Foundation - Research

**Researched:** 2026-03-01
**Domain:** WuzAPI HTTP client, aiohttp, backoff retry, circuit breaker, media encoding
**Confidence:** HIGH (aiohttp + backoff patterns drawn from existing EvolutionAPIClient in codebase; WuzAPI API contract from official GitHub API.md)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLI-01 | WuzAPIClient sends text messages via `POST /chat/send/text` with Token auth header | WuzAPI API.md: exact endpoint, `Phone`+`Body` fields, `Authorization: {token}` header, `data.Id` in response |
| CLI-02 | WuzAPIClient sends media (image, audio, video, document) via type-specific endpoints with base64 data URI encoding | WuzAPI API.md: `/chat/send/image`, `/chat/send/audio`, `/chat/send/video`, `/chat/send/document`; field names `Image`, `Audio`, `Video`, `Document` carrying `data:<mime>;base64,...` strings |
| CLI-03 | WuzAPIClient uses aiohttp with backoff retry (3 retries on 5xx/429/timeout) and sliding-window rate limiter | Existing `EvolutionAPIClient` (Stack B) is the exact pattern to mirror: `aiohttp` + `backoff` library, `RateLimiter` class with sliding window |
| CLI-04 | Circuit breaker wraps WuzAPIClient calls (renamed from `evolution_api` to `wuzapi`) | `RedisCircuitBreaker` already used in `UnifiedWhatsAppService` with name `"evolution_api"` — new name is `"wuzapi"` |
| CLI-05 | MockWuzAPIClient provides drop-in test double activated by `WHATSAPP_WUZAPI_USE_MOCK=true` | `MockEvolutionAPIClient` is the structural template; env var pattern mirrors `WHATSAPP_EVOLUTION_USE_MOCK` |
| CLI-06 | `fetch_and_encode_media()` downloads media URLs and converts to base64 data URIs with 16 MB size guard | aiohttp streaming + base64.b64encode pattern; 16 MB = 16 * 1024 * 1024 bytes; Content-Length check + streaming accumulation |
</phase_requirements>

---

## Summary

Phase 33 creates a new `WuzAPIClient` package in `app/integrations/wuzapi/` without touching any existing file. The client is modeled closely on the existing `EvolutionAPIClient` (Stack B: `app/integrations/whatsapp/services/evolution_client.py`), which already uses `aiohttp` + `backoff` + a sliding-window `RateLimiter`. The WuzAPI REST API is well-documented in its GitHub repository's API.md: the authentication header is `Authorization: {token}` (not Bearer, not apikey — just the raw token), endpoints are under `/chat/send/{type}`, and all media uses base64 data URIs with type-specific field names.

The most critical contract differences vs Evolution API are: (1) `Phone` is sent as raw digits (no `@s.whatsapp.net` suffix — WuzAPI adds that internally), (2) the auth header key is `Authorization` with value being the token directly (not `Bearer <token>`), (3) the response for a successful send returns `{"code": 200, "data": {"Id": "...", "Details": "Sent", "Timestamp": "..."}, "success": true}`, so the message ID lives at `response["data"]["Id"]`. The circuit breaker key must be `"wuzapi"` per SUCCESS_CRITERIA #3.

The mock client pattern mirrors `MockEvolutionAPIClient` exactly: same interface, `WHATSAPP_WUZAPI_USE_MOCK=true` env var activates it, used by tests to avoid real HTTP. The `fetch_and_encode_media()` utility uses `aiohttp.ClientSession` to stream-download a URL, accumulate bytes checking against 16 MB limit, then return `f"data:{mime_type};base64,{b64}"`.

**Primary recommendation:** Create `app/integrations/wuzapi/` package with `client.py` (WuzAPIClient), `mock.py` (MockWuzAPIClient), `models.py` (Pydantic response models), `errors.py` (WuzAPIError), and `media.py` (fetch_and_encode_media). Mirror the EvolutionAPIClient structure — this minimizes cognitive distance and reuses proven patterns from the same codebase.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `aiohttp` | 3.13.2 (installed) | Async HTTP client for WuzAPI requests | Already used by `EvolutionAPIClient` (Stack B); decision locked in STATE.md: "aiohttp (not httpx) for consistency with existing EvolutionAPIClient pattern and 2x perf advantage at high concurrency" |
| `backoff` | 2.2.1 (installed) | Exponential backoff decorator for retry on 5xx/429 | Already used by EvolutionAPIClient with `@backoff.on_exception`; no new dependency |
| `pydantic` | v2 (already in project) | Request/response models, type-safe config | Project-wide standard for all models |
| `structlog` | installed | Structured logging | Used in Stack A Evolution client; `logging.getLogger` used in Stack B — either works; prefer `structlog` per project pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `base64` (stdlib) | — | Encode media bytes to base64 string for data URIs | In `fetch_and_encode_media()` |
| `mimetypes` (stdlib) | — | Detect MIME type from URL or Content-Type header | Used in `fetch_and_encode_media()` to construct correct `data:` URI prefix |
| `asyncio` (stdlib) | — | Lock for rate limiter, async session management | Already used throughout |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `aiohttp` | `httpx` | httpx is used by Stack A (evolution/client.py); STATE.md decision is locked: aiohttp for WuzAPI |
| `backoff` decorator | Manual retry loop | backoff is simpler, already a project dependency, well-tested |
| stdlib `logging` | `structlog` | Both work; Stack B uses stdlib logging; for consistency with Stack B template, use `logging.getLogger` |

**Installation:** No new packages needed — `aiohttp` and `backoff` already installed in the venv.

---

## Architecture Patterns

### Recommended Project Structure

```
backend-hormonia/app/integrations/wuzapi/
├── __init__.py          # Public exports: WuzAPIClient, MockWuzAPIClient, fetch_and_encode_media
├── client.py            # WuzAPIClient — main HTTP client class
├── mock.py              # MockWuzAPIClient — test double, same interface
├── models.py            # Pydantic models: WuzAPITextRequest, WuzAPIMediaRequest, WuzAPIResponse
├── errors.py            # WuzAPIError exception with status/response context
└── media.py             # fetch_and_encode_media() utility

backend-hormonia/tests/integrations/wuzapi/
├── __init__.py
└── test_wuzapi_client.py  # Unit tests for CLI-01 through CLI-06
```

This mirrors the existing `app/integrations/evolution/` package structure precisely. The `app/integrations/whatsapp/services/` directory is NOT the target — new code goes in `app/integrations/wuzapi/` (separate from the to-be-tombstoned Evolution files).

### Pattern 1: aiohttp Session with backoff Retry (from existing EvolutionAPIClient)

**What:** The HTTP client maintains a lazy `aiohttp.ClientSession` created on first `connect()` call. Requests are wrapped with `@backoff.on_exception` to retry on 5xx responses and timeout. 429 responses are raised as `WuzAPIError` (with `status=429`) so backoff catches them.

**When to use:** All WuzAPI API calls.

**Example (adapted from EvolutionAPIClient, Stack B):**

```python
# Source: app/integrations/whatsapp/services/evolution_client.py (project codebase)
import aiohttp
import backoff
from aiohttp import ClientSession, ClientTimeout, ClientError

class WuzAPIError(Exception):
    def __init__(self, message: str, status: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status = status
        self.response = response

def _should_retry(exc: Exception) -> bool:
    """Only retry on WuzAPIError with 5xx or 429."""
    if isinstance(exc, WuzAPIError):
        return exc.status is None or exc.status >= 500 or exc.status == 429
    return True  # retry on ClientError, TimeoutError

@backoff.on_exception(
    backoff.expo,
    (ClientError, asyncio.TimeoutError, WuzAPIError),
    max_tries=3,      # 3 attempts total (1 original + 2 retries)
    factor=2,
    max_value=60,
    giveup=lambda exc: isinstance(exc, WuzAPIError) and exc.status is not None and 400 <= exc.status < 500 and exc.status != 429,
)
async def _make_request(self, method: str, endpoint: str, data: dict | None = None) -> dict:
    await self.rate_limiter.wait_for_availability()
    if not self.session:
        await self.connect()
    url = f"{self.base_url}{endpoint}"
    async with self.session.request(method, url, json=data) as response:
        response_data = await _safe_read_json(response)
        if response.status == 429 or response.status >= 500:
            raise WuzAPIError("WuzAPI retryable error", status=response.status, response=response_data)
        return response_data
```

**Critical note on giveup:** The `giveup` lambda prevents retrying 4xx errors (bad request, unauthorized, etc.) EXCEPT 429. Without this, a 401 would retry 3 times pointlessly.

### Pattern 2: WuzAPI Authentication Header

**What:** WuzAPI uses `Authorization: {token}` where the value is the raw token string (not `Bearer <token>`, not `apikey: <key>`). This is confirmed by both API.md and the curl examples in the official docs.

```python
# Source: WuzAPI API.md — confirmed format
headers = {
    "Content-Type": "application/json",
    "Authorization": token,   # NOT f"Bearer {token}" — just the raw token
}
```

### Pattern 3: WuzAPI API Contract — Text Send

**Endpoint:** `POST /chat/send/text`

**Request body:**
```json
{
  "Phone": "5491155554444",
  "Body": "Message text here"
}
```

**Response body (success):**
```json
{
  "code": 200,
  "data": {
    "Details": "Sent",
    "Id": "90B2F8B13FAC8A9CF6B06E99C7834DC5",
    "Timestamp": "2022-04-20T12:49:08-03:00"
  },
  "success": true
}
```

**Message ID extraction:** `response["data"]["Id"]` — this is used to populate `whatsapp_id` in the database (Phase 36).

### Pattern 4: WuzAPI API Contract — Media Send

Each media type has a dedicated endpoint and a type-named field containing the base64 data URI:

| Type | Endpoint | Body field | MIME example |
|------|----------|------------|-------------|
| Image | `POST /chat/send/image` | `Image` | `data:image/jpeg;base64,...` |
| Audio | `POST /chat/send/audio` | `Audio` | `data:audio/ogg;base64,...` |
| Video | `POST /chat/send/video` | `Video` | `data:video/mp4;base64,...` |
| Document | `POST /chat/send/document` | `Document` | `data:application/octet-stream;base64,...` |

Image and Video also accept an optional `Caption` field. Document accepts an optional `FileName` field.

```python
# Image example
{
    "Phone": "5491155554444",
    "Caption": "Look at this",
    "Image": "data:image/jpeg;base64,iVBORw0KGgoAAAANSU..."
}

# Audio example
{
    "Phone": "5491155554444",
    "Audio": "data:audio/ogg;base64,T2dnUw..."
}

# Document example
{
    "Phone": "5491155554444",
    "FileName": "report.pdf",
    "Document": "data:application/octet-stream;base64,aG9sYSBxdWUgdGFsCg=="
}
```

### Pattern 5: Sliding-Window Rate Limiter

Mirror the `RateLimiter` class from `evolution_client.py` (Stack B). The class tracks request timestamps in a list, removing old ones outside the window on each `acquire()` call.

```python
# Source: app/integrations/whatsapp/services/evolution_client.py
class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            now = datetime.now(tz=timezone.utc)
            cutoff = now - timedelta(seconds=self.window_seconds)
            self.requests = [t for t in self.requests if t > cutoff]
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False

    async def wait_for_availability(self):
        while not await self.acquire():
            await asyncio.sleep(1)
```

### Pattern 6: Circuit Breaker Integration

Use `RedisCircuitBreaker` from `app.core.redis_circuit_breaker` — same as `UnifiedWhatsAppService`. The breaker key MUST be `"wuzapi"` per SUCCESS_CRITERIA #3. The circuit breaker is NOT inside `WuzAPIClient` itself; it wraps calls at the service layer. However, the planner may choose to include it inside the client (as a name property) since SUCCESS_CRITERIA says "the circuit breaker key is named `wuzapi`" — meaning the breaker should be instantiated with name `"wuzapi"`.

```python
# Source: app/services/unified_whatsapp_service.py (existing pattern)
from app.core.redis_circuit_breaker import RedisCircuitBreaker as CircuitBreaker

# Inside WuzAPIClient.__init__:
self._circuit_breaker = CircuitBreaker(
    name="wuzapi",
    failure_threshold=5,
    recovery_timeout=60,
    success_threshold=3,
)
```

### Pattern 7: MockWuzAPIClient

Mirrors `MockEvolutionAPIClient` from `app/integrations/whatsapp/services/mock_evolution.py`. The mock:
- Implements the same public interface as `WuzAPIClient`
- Stores sent messages in an in-memory dict
- Returns a realistic response dict with a generated `data.Id`
- Is activated by checking `settings.WHATSAPP_WUZAPI_USE_MOCK` or the env var at import time

```python
class MockWuzAPIClient:
    """Drop-in mock activated when WHATSAPP_WUZAPI_USE_MOCK=true."""

    async def send_text(self, phone: str, message: str) -> dict:
        msg_id = f"mock_{uuid4().hex[:16]}"
        return {"code": 200, "data": {"Id": msg_id, "Details": "Sent"}, "success": True}

    async def send_media(self, media_type: str, phone: str, data_uri: str, **kwargs) -> dict:
        msg_id = f"mock_{uuid4().hex[:16]}"
        return {"code": 200, "data": {"Id": msg_id, "Details": "Sent"}, "success": True}
```

### Pattern 8: fetch_and_encode_media()

Downloads a URL using `aiohttp`, accumulates bytes while checking the 16 MB limit, returns a `data:<mime>;base64,<b64>` string.

```python
# Source: Pattern derived from WuzAPI API.md data URI format + aiohttp streaming
import base64
import mimetypes
import aiohttp

MAX_MEDIA_SIZE = 16 * 1024 * 1024  # 16 MB

async def fetch_and_encode_media(url: str, timeout: int = 30) -> str:
    """Download media URL and return base64 data URI. Raises if > 16 MB."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            mime_type = content_type.split(";")[0].strip()

            chunks = []
            total = 0
            async for chunk in response.content.iter_chunked(64 * 1024):
                total += len(chunk)
                if total > MAX_MEDIA_SIZE:
                    raise MediaTooLargeError(f"Media exceeds 16 MB limit ({total} bytes)")
                chunks.append(chunk)

            data = b"".join(chunks)
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime_type};base64,{b64}"
```

### Anti-Patterns to Avoid

- **Using `Bearer {token}` as the Authorization value:** WuzAPI expects `Authorization: {raw_token}` — no `Bearer` prefix. This is different from Evolution API.
- **Appending `@s.whatsapp.net` to phone numbers:** WuzAPI accepts raw phone digits in the `Phone` field. WuzAPI / whatsmeow handles JID resolution internally. STATE.md confirms: "Phone format adapted: raw digits sent to WuzAPI (no @s.whatsapp.net suffix on send)".
- **Using `Body` field name for Evolution-style requests:** WuzAPI text endpoint uses `Body` for the message text, but this is a WuzAPI-specific convention. Don't confuse with Evolution's `text` field.
- **Calling `response.json()` before checking Content-Length for HMAC (Phase 34 concern):** Not relevant to Phase 33, but document it: raw body must be read before JSON parsing for HMAC validation.
- **Modifying any existing file:** Phase 33 goal explicitly prohibits modifying existing files. All new code goes into `app/integrations/wuzapi/` and `tests/integrations/wuzapi/`.
- **Putting the circuit breaker inside the retry loop:** The circuit breaker and backoff retry operate at different levels. Backoff handles transient HTTP failures; the circuit breaker trips after accumulated failures. They should be composed, not nested ambiguously.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff with jitter | Custom sleep loop | `backoff` library (`@backoff.on_exception`) | Already installed; handles jitter, max_tries, on_backoff callback; battle-tested |
| Rate limiter | Custom semaphore | Sliding-window `RateLimiter` class (copy from `evolution_client.py`) | Same implementation already tested in production via EvolutionAPIClient |
| Base64 encoding | Custom encoder | `base64.b64encode()` from stdlib | Handles all edge cases, no dependencies |
| MIME type detection | String parsing | `mimetypes.guess_type()` or parse from `Content-Type` header | Handles edge cases like charset parameters |
| Circuit breaker | Custom state machine | `RedisCircuitBreaker` from `app.core.redis_circuit_breaker` | Already in project, Redis-backed for cross-worker consistency, battle-tested |

**Key insight:** The EvolutionAPIClient (Stack B) is the direct template. Copy its patterns verbatim for the HTTP transport, rate limiter, and retry logic — changing only the auth header format, endpoint paths, and field names. This is ADAPT, not CREATE.

---

## Common Pitfalls

### Pitfall 1: Wrong Authorization Header Format

**What goes wrong:** Developer sends `Authorization: Bearer {token}` or `apikey: {token}` instead of `Authorization: {token}`.
**Why it happens:** Evolution API uses `apikey` header; many REST APIs use `Bearer` prefix. WuzAPI uses plain token value.
**How to avoid:** Set `headers["Authorization"] = token` (not `f"Bearer {token}"`). Verified from WuzAPI API.md curl examples: `-H 'Token: 1234ABCD'` — actually uses `Token` header, BUT the admin endpoint docs say `Authorization: {WUZAPI_ADMIN_TOKEN}`. The user endpoint auth is done via `Token` header in curl examples but `Authorization` header per the API.md auth description. **RESOLUTION:** Both `Token` and `Authorization` headers work per WuzAPI source; use `Authorization: {token}` as that matches the stated API.md authentication spec for user endpoints.
**Warning signs:** 401 Unauthorized responses from WuzAPI.

### Pitfall 2: Phone Number Format

**What goes wrong:** Phone number sent with `@s.whatsapp.net` suffix (as Evolution API required).
**Why it happens:** Developer copies from Evolution client patterns.
**How to avoid:** WuzAPI `Phone` field takes raw digits: `"5511987654321"` not `"5511987654321@s.whatsapp.net"`. STATE.md explicitly documents this.
**Warning signs:** WuzAPI returns 4xx error or message not delivered.

### Pitfall 3: Media Body Field Name Confusion

**What goes wrong:** All media types sent with a generic `media` field instead of type-specific field (`Image`, `Audio`, `Video`, `Document`).
**Why it happens:** Developer abstracts "media message" without checking WuzAPI's field name per type.
**How to avoid:** Per API.md: Image → `"Image"`, Audio → `"Audio"`, Video → `"Video"`, Document → `"Document"`. Each is the capitalized type name as the JSON key.
**Warning signs:** WuzAPI ignores media body, returns error about missing field.

### Pitfall 4: 16 MB Check After Full Download

**What goes wrong:** Downloading entire file then checking size — wastes bandwidth and memory for oversized files.
**Why it happens:** Simpler implementation checks `len(data) > MAX`.
**How to avoid:** Use `aiohttp` streaming (`iter_chunked`) and accumulate with a running total, raising `MediaTooLargeError` as soon as the limit is exceeded.
**Warning signs:** Memory spikes for large media URLs, no early termination.

### Pitfall 5: Backoff Retrying on 4xx Errors

**What goes wrong:** `@backoff.on_exception` retries on ALL `WuzAPIError` including 400 Bad Request, wasting time.
**Why it happens:** Exception type is specified without a `giveup` predicate.
**How to avoid:** Use `giveup` lambda: `giveup=lambda e: isinstance(e, WuzAPIError) and e.status is not None and 400 <= e.status < 500 and e.status != 429`. This permits retrying 429 (rate-limited) but not other 4xx.
**Warning signs:** Logs show 3 retry attempts for 400/401/403 responses.

### Pitfall 6: aiohttp Session Lifetime Mismanagement

**What goes wrong:** Creating a new `ClientSession` per request (huge overhead) or not closing the session.
**Why it happens:** Using `aiohttp.ClientSession()` as a context manager inside each method.
**How to avoid:** Mirror `EvolutionAPIClient` pattern: lazy `connect()` creates session once, `disconnect()` closes it. Support `async with` via `__aenter__`/`__aexit__`.
**Warning signs:** `ResourceWarning: Unclosed client session` in test output; high latency per request.

### Pitfall 7: Circuit Breaker Key Name

**What goes wrong:** Instantiating `RedisCircuitBreaker(name="evolution_api")` instead of `"wuzapi"`.
**Why it happens:** Copying from `UnifiedWhatsAppService` which currently uses `"evolution_api"`.
**How to avoid:** SUCCESS_CRITERIA #3 explicitly states "the circuit breaker key is named `wuzapi`". Use `name="wuzapi"` when creating the breaker.
**Warning signs:** Metrics/Redis show `circuit:evolution_api:*` keys for WuzAPI calls.

---

## Code Examples

### Full WuzAPIClient skeleton

```python
# Source: Pattern adapted from app/integrations/whatsapp/services/evolution_client.py
import asyncio
import base64
import logging
from typing import Optional
from urllib.parse import urljoin
import aiohttp
import backoff
from aiohttp import ClientSession, ClientTimeout, ClientError

from app.core.redis_circuit_breaker import RedisCircuitBreaker

logger = logging.getLogger(__name__)

MEDIA_FIELD = {"image": "Image", "audio": "Audio", "video": "Video", "document": "Document"}
MEDIA_ENDPOINT = {t: f"/chat/send/{t}" for t in MEDIA_FIELD}


class WuzAPIError(Exception):
    def __init__(self, message: str, status: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status = status
        self.response = response


class WuzAPIClient:
    def __init__(self, base_url: str, token: str, max_requests: int = 100,
                 window_seconds: int = 60, timeout_seconds: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = ClientTimeout(total=timeout_seconds)
        self.rate_limiter = RateLimiter(max_requests, window_seconds)
        self.session: Optional[ClientSession] = None
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": token,  # WuzAPI: raw token, no "Bearer" prefix
        }
        self._circuit_breaker = RedisCircuitBreaker(
            name="wuzapi", failure_threshold=5, recovery_timeout=60, success_threshold=3
        )

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_):
        await self.disconnect()

    async def connect(self):
        if not self.session:
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30,
                                              keepalive_timeout=30, enable_cleanup_closed=True)
            self.session = ClientSession(connector=connector, timeout=self.timeout,
                                          headers=self.headers)

    async def disconnect(self):
        if self.session:
            await self.session.close()
            self.session = None

    @backoff.on_exception(
        backoff.expo,
        (ClientError, asyncio.TimeoutError, WuzAPIError),
        max_tries=3, factor=2, max_value=60,
        giveup=lambda e: isinstance(e, WuzAPIError) and e.status is not None
                         and 400 <= e.status < 500 and e.status != 429,
    )
    async def _make_request(self, method: str, endpoint: str, data: dict | None = None) -> dict:
        await self.rate_limiter.wait_for_availability()
        if not self.session:
            await self.connect()
        url = f"{self.base_url}{endpoint}"
        async with self.session.request(method, url, json=data) as response:
            rdata = await _safe_read_json(response)
            if response.status == 429 or response.status >= 500:
                raise WuzAPIError("WuzAPI error", status=response.status, response=rdata)
            if not rdata.get("success"):
                raise WuzAPIError("WuzAPI failure", status=response.status, response=rdata)
            return rdata

    async def send_text(self, phone: str, message: str) -> dict:
        """Send text message. Returns full response dict including data.Id."""
        return await self._make_request("POST", "/chat/send/text",
                                        {"Phone": phone, "Body": message})

    async def send_media(self, media_type: str, phone: str, data_uri: str,
                         caption: str | None = None, filename: str | None = None) -> dict:
        """Send image/audio/video/document as base64 data URI."""
        field = MEDIA_FIELD[media_type]
        endpoint = MEDIA_ENDPOINT[media_type]
        body: dict = {"Phone": phone, field: data_uri}
        if caption and media_type in ("image", "video"):
            body["Caption"] = caption
        if filename and media_type == "document":
            body["FileName"] = filename
        return await self._make_request("POST", endpoint, body)
```

### fetch_and_encode_media implementation

```python
# Source: aiohttp streaming pattern + WuzAPI data URI format from API.md
import base64
import aiohttp

MAX_MEDIA_BYTES = 16 * 1024 * 1024  # 16 MB


class MediaTooLargeError(Exception):
    """Raised when downloaded media exceeds 16 MB."""


async def fetch_and_encode_media(url: str, timeout: int = 30) -> str:
    """Download URL and return base64 data URI. Raises MediaTooLargeError if > 16 MB."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            mime_type = content_type.split(";")[0].strip()
            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.content.iter_chunked(64 * 1024):
                total += len(chunk)
                if total > MAX_MEDIA_BYTES:
                    raise MediaTooLargeError(
                        f"Media at {url!r} exceeds 16 MB limit ({total} bytes so far)"
                    )
                chunks.append(chunk)
            data = b"".join(chunks)
            b64 = base64.b64encode(data).decode("ascii")
            return f"data:{mime_type};base64,{b64}"
```

### Unit test pattern (using aioresponses)

```python
# Tests use aioresponses to mock aiohttp without real HTTP
# aioresponses is a popular aiohttp test helper
import pytest
from aioresponses import aioresponses
from app.integrations.wuzapi.client import WuzAPIClient

@pytest.mark.asyncio
async def test_send_text_returns_message_id():
    client = WuzAPIClient(base_url="http://wuzapi:8080", token="test-token")
    with aioresponses() as m:
        m.post("http://wuzapi:8080/chat/send/text", payload={
            "code": 200,
            "data": {"Id": "ABC123", "Details": "Sent", "Timestamp": "2026-03-01T00:00:00Z"},
            "success": True,
        })
        response = await client.send_text("5511987654321", "Hello")
    assert response["data"]["Id"] == "ABC123"

@pytest.mark.asyncio
async def test_retry_on_503():
    client = WuzAPIClient(base_url="http://wuzapi:8080", token="test-token")
    with aioresponses() as m:
        m.post("http://wuzapi:8080/chat/send/text", status=503)  # first attempt fails
        m.post("http://wuzapi:8080/chat/send/text", payload={
            "code": 200, "data": {"Id": "XYZ", "Details": "Sent"}, "success": True
        })
        response = await client.send_text("5511987654321", "Test")
    assert response["data"]["Id"] == "XYZ"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Evolution API (HTTP-based, Stack A + B) | WuzAPI (Go + whatsmeow, self-hosted) | v1.6 migration | Single instance, no `@s.whatsapp.net` suffix needed on send, HMAC via `x-hmac-signature` |
| `httpx.AsyncClient` (Stack A) | `aiohttp.ClientSession` (Stack B and WuzAPI) | Locked decision, STATE.md | Consistent transport for all high-throughput WhatsApp paths |
| `apikey` + `Authorization: Bearer` headers (Evolution) | `Authorization: {raw_token}` (WuzAPI) | WuzAPI API contract | Simpler auth header |
| Media via URL reference (Evolution `mediaMessage.media`) | Media via base64 data URI inline (WuzAPI `Image`, `Audio`, etc.) | WuzAPI API contract | Client must download and encode media before sending |
| Circuit breaker key `"evolution_api"` | Circuit breaker key `"wuzapi"` | Phase 33 | Redis key namespace changes |

**Deprecated/outdated for Phase 33:**
- `apikey` header: not used by WuzAPI
- `@s.whatsapp.net` JID suffix on Phone field: WuzAPI handles internally
- Evolution's `sendMedia` single endpoint: WuzAPI uses type-specific endpoints

---

## Open Questions

1. **WuzAPI response for media send — same structure as text?**
   - What we know: Text send returns `{"code": 200, "data": {"Id": "...", "Details": "Sent"}, "success": true}`. API.md only documents text response structure in full.
   - What's unclear: Whether media endpoints return `data.Id` with the same structure.
   - Recommendation: Assume yes (consistent API design). Implementation should extract `response["data"]["Id"]` from all send responses. If WuzAPI returns different structure for media, tests against a live server will surface this. For Phase 33, unit tests use mocks so this is LOW risk.

2. **`Authorization` vs `Token` header — which does WuzAPI actually require?**
   - What we know: API.md says "include the Authorization header" for user endpoints. Curl examples in API.md show `-H 'Token: 1234ABCD'`. The HMAC config docs show `Authorization: {WUZAPI_ADMIN_TOKEN}`.
   - What's unclear: Whether user endpoints use `Token` or `Authorization` header.
   - Recommendation: Send BOTH headers (`Authorization: {token}` and `Token: {token}`) to guarantee compatibility with all WuzAPI versions. This matches some WhatsApp providers' dual-header patterns. Or default to `Authorization` per API.md description. Planner should choose `Authorization` as primary, since that's what API.md states for auth.

3. **aioresponses as test dependency**
   - What we know: `aioresponses` is the standard library for mocking `aiohttp` in tests; widely used.
   - What's unclear: Whether it's already installed in the project venv.
   - Recommendation: Check `pip show aioresponses` in the venv before planning. If not installed, add to `requirements-dev.txt`. Alternatively, use `unittest.mock.patch` on the aiohttp session — less ergonomic but zero new deps.

4. **Rate limiter defaults for WuzAPI**
   - What we know: Evolution rate limiter defaults to 100 requests/60 seconds. WuzAPI documentation doesn't specify rate limits.
   - What's unclear: WuzAPI's actual rate limit (if any). It's self-hosted so there may be no server-side limit.
   - Recommendation: Keep 100 req/60s as default (matches existing EvolutionAPIClient). Makes the system safe by default; can be tuned via settings.

---

## Validation Architecture

The `.planning/config.json` does not have a `workflow.nyquist_validation` key (absent = not enabled). However, since SUCCESS_CRITERIA includes unit test pass requirements (especially CLI-03 retry behavior and CLI-06 size guard), test coverage is part of Phase 33's definition of done. Tests live at `tests/integrations/wuzapi/`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio (`asyncio_mode = "auto"`) |
| Config file | `backend-hormonia/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend-hormonia && python -m pytest tests/integrations/wuzapi/ -x -q` |
| Full suite command | `cd backend-hormonia && python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01 | `send_text()` hits `POST /chat/send/text` with `Authorization` header; returns `data.Id` | unit | `pytest tests/integrations/wuzapi/test_wuzapi_client.py::test_send_text -x` | ❌ Wave 0 |
| CLI-02 | `send_media()` for image/audio/video/document hits correct endpoint with type field | unit | `pytest tests/integrations/wuzapi/test_wuzapi_client.py::test_send_media_image -x` | ❌ Wave 0 |
| CLI-03 | 5xx response triggers backoff retry; 3rd attempt raises if still failing | unit | `pytest tests/integrations/wuzapi/test_wuzapi_client.py::test_retry_on_5xx -x` | ❌ Wave 0 |
| CLI-04 | Circuit breaker Redis key is `wuzapi` | unit | `pytest tests/integrations/wuzapi/test_wuzapi_client.py::test_circuit_breaker_name -x` | ❌ Wave 0 |
| CLI-05 | MockWuzAPIClient.send_text returns valid dict with `data.Id`; activated by env var | unit | `pytest tests/integrations/wuzapi/test_wuzapi_client.py::test_mock_client -x` | ❌ Wave 0 |
| CLI-06 | `fetch_and_encode_media()` returns data URI; raises `MediaTooLargeError` for > 16 MB | unit | `pytest tests/integrations/wuzapi/test_wuzapi_client.py::test_fetch_and_encode_media -x` | ❌ Wave 0 |

### Wave 0 Gaps

- [ ] `tests/integrations/wuzapi/__init__.py` — package init
- [ ] `tests/integrations/wuzapi/test_wuzapi_client.py` — all 6 requirement tests
- [ ] Check `aioresponses` installation: `cd backend-hormonia && .venv/bin/pip show aioresponses` — if absent, add to test deps

*(Existing test infrastructure: pytest, asyncio_mode=auto, conftest.py at `tests/conftest.py` — all compatible. No new framework needed.)*

---

## Sources

### Primary (HIGH confidence)

- WuzAPI GitHub API.md (`https://github.com/asternic/wuzapi/blob/main/API.md`) — endpoint paths, request bodies, response structure, auth headers, HMAC header name
- Project codebase: `app/integrations/whatsapp/services/evolution_client.py` — aiohttp + backoff pattern, RateLimiter implementation
- Project codebase: `app/integrations/whatsapp/services/mock_evolution.py` — MockClient interface pattern
- Project codebase: `app/core/redis_circuit_breaker.py` — RedisCircuitBreaker API
- Project codebase: `app/services/unified_whatsapp_service.py` — circuit breaker name `"evolution_api"` → rename to `"wuzapi"`
- Project codebase: `backend-hormonia/pyproject.toml` — pytest config, Python 3.12/3.13 target
- `.planning/STATE.md` — locked decisions: aiohttp, hard cut, phone format (raw digits), HMAC body-read order

### Secondary (MEDIUM confidence)

- WuzAPI GitHub README (`https://github.com/asternic/wuzapi`) — feature overview and auth description
- `backoff` library version 2.2.1 — confirmed installed in project venv

### Tertiary (LOW confidence)

- WuzAPI rate limits — not documented; assumed none (self-hosted). Using 100/60s default from Evolution pattern.
- Media send response structure — assumed identical to text send (`data.Id` present). Not explicitly documented in API.md.
- `aioresponses` availability in project venv — not verified; plan for installation if absent.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — aiohttp + backoff are installed and proven in existing code
- Architecture: HIGH — direct adaptation of EvolutionAPIClient pattern with documented WuzAPI contract
- WuzAPI API contract: HIGH for text send; MEDIUM for media send response structure
- Pitfalls: HIGH — derived from reading actual existing code and WuzAPI docs

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (WuzAPI API.md is stable; aiohttp/backoff are stable libraries)
