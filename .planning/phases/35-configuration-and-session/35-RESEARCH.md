# Phase 35: Configuration and Session - Research

**Researched:** 2026-03-02
**Domain:** Pydantic-settings startup validation + WuzAPI session management endpoints + FastAPI lifespan integration
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CFG-01 | New env vars added: `WHATSAPP_WUZAPI_BASE_URL`, `WHATSAPP_WUZAPI_TOKEN`, `WHATSAPP_WUZAPI_WEBHOOK_SECRET` | `IntegrationsSettings` in `app/config/settings/integrations.py` is the correct file; pattern for adding fields is identical to existing `WHATSAPP_EVOLUTION_*` fields |
| CFG-02 | Startup validation refuses to start if `WHATSAPP_WUZAPI_TOKEN` is missing (hard fail) | `@model_validator(mode="after")` in `SecuritySettings.validate_required_environment_variables` is the exact pattern to replicate in `IntegrationsSettings` |
| CFG-03 | `.env.example` updated with all WuzAPI env vars and removed Evolution API vars | Evolution API block in `.env.example` is lines 181-195; must be replaced with WuzAPI block |
| SESS-01 | Application startup calls `POST /session/connect` and verifies session is connected before accepting sends | WuzAPI `POST /session/connect` returns `{"data": {"details": "Connected!"}, "success": true}`; lifespan `_initialize_evolution_api` is the pattern to adapt as `_initialize_wuzapi_session` |
| SESS-02 | Session status endpoint (`GET /session/status`) exposes connection state via monitoring API | WuzAPI `GET /session/status` returns `{"data": {"Connected": bool, "LoggedIn": bool}}`; new router mounted under `/api/v2/monitoring/whatsapp` or new `/api/v2/monitoring/wuzapi` |
| SESS-03 | QR code endpoint (`GET /session/qr`) returns base64 QR for WhatsApp pairing | WuzAPI `GET /session/qr` returns a base64-encoded PNG image data URI; endpoint proxies through `WuzAPIClient._make_request` |
</phase_requirements>

---

## Summary

Phase 35 has two tightly coupled concerns: (1) embedding the three WuzAPI environment variables (`WHATSAPP_WUZAPI_BASE_URL`, `WHATSAPP_WUZAPI_TOKEN`, `WHATSAPP_WUZAPI_WEBHOOK_SECRET`) into the existing pydantic-settings `IntegrationsSettings` class with a hard-fail validator for the token, and (2) adding two new monitoring API endpoints (`GET /session/status`, `GET /session/qr`) plus a startup-time session connect call wired into the lifespan manager.

Every pattern needed already exists in the codebase and can be replicated directly. The `IntegrationsSettings` class already holds `WHATSAPP_EVOLUTION_*` fields with the same shape. The `SecuritySettings.validate_required_environment_variables` validator shows exactly how to produce a hard-fail `ValueError` for a missing required string field. The `_initialize_evolution_api` function in `lifespan.py` shows exactly how to call an external API at startup with guard checks and graceful logging. The monitoring router in `app/api/v2/monitoring/whatsapp.py` shows exactly how to wire a new endpoint into the monitoring namespace.

The WuzAPI session endpoints are: `POST /session/connect` (subscribes + connects), `GET /session/status` (returns `Connected`/`LoggedIn` booleans), and `GET /session/qr` (returns base64 PNG data URI). All three use the same `Authorization: {token}` header that `WuzAPIClient` already sends by default.

**Primary recommendation:** Add three fields to `IntegrationsSettings` with a `@model_validator(mode="after")` that raises `ValueError` when token is blank. Add `get_session_status()` and `get_qr()` methods to `WuzAPIClient`. Create a `app/api/v2/monitoring/wuzapi.py` router with two endpoints. Add `_initialize_wuzapi_session` to `lifespan.py`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic-settings | 2.x (project standard) | Settings class with env var parsing and `@model_validator` | Already used for all settings; `BaseAppSettings` is the base class |
| FastAPI | 0.100+ (project standard) | Router for monitoring endpoints | Already used; monitoring router pattern is established |
| aiohttp | 3.x (project standard) | HTTP client for WuzAPIClient session calls | Already used in `WuzAPIClient`; session endpoints use same transport |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic `Field` | 2.x | Field definitions with `default`, `description` | Required for every new settings field |
| pydantic `model_validator` | 2.x | Cross-field validation at init time | For the hard-fail token presence check |
| Python `typing.Optional` | stdlib | Optional field type for `WHATSAPP_WUZAPI_WEBHOOK_SECRET` | Webhook secret may be absent in dev |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@model_validator(mode="after")` in `IntegrationsSettings` | Validator in global `Settings.__init__` | Both work; `IntegrationsSettings` keeps the rule co-located with its fields — prefer this |
| Separate router `wuzapi.py` under monitoring | Add endpoints to existing `whatsapp.py` | `whatsapp.py` imports Evolution-specific services; a new file avoids coupling |

**Installation:** No new dependencies. All libraries already present.

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── config/settings/integrations.py        # CFG-01, CFG-02: add 3 new fields + validator
├── api/v2/monitoring/
│   ├── __init__.py                         # add wuzapi_monitoring_router export
│   ├── whatsapp.py                         # existing — no changes (Evolution still present)
│   └── wuzapi.py                           # new: GET /session/status, GET /session/qr
├── integrations/wuzapi/
│   ├── client.py                           # add get_session_status(), get_qr() methods
│   └── mock.py                             # add matching mock methods
└── core/lifespan.py                        # add _initialize_wuzapi_session() to Phase 1
```

### Pattern 1: Adding WuzAPI fields to IntegrationsSettings (CFG-01 + CFG-02)

**What:** Three new `Field` declarations in `IntegrationsSettings`, plus a `@model_validator(mode="after")` that hard-fails when `WHATSAPP_WUZAPI_TOKEN` is absent or empty.
**When to use:** Whenever a new external API credential must be validated at startup.

```python
# Source: app/config/settings/integrations.py (existing file, add below Evolution block)

from pydantic import Field, model_validator
from typing import Optional

class IntegrationsSettings(BaseAppSettings):
    # ... existing fields ...

    # ============================================================================
    # WhatsApp / WuzAPI - Direct ENV names
    # ============================================================================
    WHATSAPP_WUZAPI_BASE_URL: str = Field(
        default="http://localhost:8080",
        description="WuzAPI base URL (e.g. http://wuzapi:8080)"
    )
    WHATSAPP_WUZAPI_TOKEN: Optional[str] = Field(
        default=None,
        description=(
            "WuzAPI API token — REQUIRED. "
            "Set via Authorization header on every request. "
            "Application refuses to start if absent."
        )
    )
    WHATSAPP_WUZAPI_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description=(
            "HMAC-SHA256 secret for WuzAPI webhook signature validation. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    )

    @model_validator(mode="after")
    def validate_wuzapi_token(self) -> "IntegrationsSettings":
        """Hard-fail at startup if WHATSAPP_WUZAPI_TOKEN is missing.

        CFG-02: application must refuse to start without the token.
        Silent fallback is explicitly prohibited.
        """
        import logging
        logger = logging.getLogger(__name__)

        if not self.WHATSAPP_WUZAPI_TOKEN or not self.WHATSAPP_WUZAPI_TOKEN.strip():
            env = self.APP_ENVIRONMENT.lower()
            # Allow absence in test environments to avoid breaking existing test suites
            if env in ("test", "testing"):
                logger.warning(
                    "WHATSAPP_WUZAPI_TOKEN not set — allowed in test environment only."
                )
                return self
            raise ValueError(
                "\n" + "=" * 70 + "\n"
                "STARTUP VALIDATION FAILED: WHATSAPP_WUZAPI_TOKEN is required.\n"
                "=" * 70 + "\n"
                "Set WHATSAPP_WUZAPI_TOKEN in your .env file or environment.\n"
                "This token authenticates all WuzAPI API calls.\n"
                "Obtain it from your WuzAPI instance configuration.\n"
                "=" * 70 + "\n"
            )
        return self
```

**Critical:** The `Settings` composite class in `__init__.py` also maintains a `boolean_fields` list in `parse_env_values`. Add `"WHATSAPP_WUZAPI_USE_MOCK"` there if a mock flag is added. The three new fields do not need entries in that list (they are strings/Optional[str], not booleans).

### Pattern 2: WuzAPIClient session methods (SESS-01, SESS-02, SESS-03)

**What:** Three new async methods on `WuzAPIClient` that call WuzAPI session endpoints.
**When to use:** Any time the monitoring API or lifespan needs to observe/control the WhatsApp session.

```python
# Source: app/integrations/wuzapi/client.py (add to WuzAPIClient class)

async def session_connect(
    self,
    subscribe: list[str] | None = None,
    immediate: bool = False,
) -> dict[str, Any]:
    """POST /session/connect — connect to WhatsApp servers."""
    payload: dict[str, Any] = {}
    if subscribe:
        payload["Subscribe"] = subscribe
    payload["Immediate"] = immediate
    return await self._make_request("POST", "/session/connect", data=payload)

async def get_session_status(self) -> dict[str, Any]:
    """GET /session/status — returns Connected and LoggedIn booleans."""
    return await self._make_request("GET", "/session/status")

async def get_qr(self) -> dict[str, Any]:
    """GET /session/qr — returns base64 QR code data URI for pairing."""
    return await self._make_request("GET", "/session/qr")
```

**WuzAPI response shapes (verified from official API.md):**

```json
// POST /session/connect response
{
  "code": 200,
  "data": {
    "details": "Connected!",
    "events": "Message",
    "jid": "5491155554444.0:52@s.whatsapp.net",
    "webhook": "http://some.site/webhook?token=123456"
  },
  "success": true
}

// GET /session/status response
{
  "code": 200,
  "data": {
    "Connected": true,
    "LoggedIn": true
  },
  "success": true
}

// GET /session/qr response (base64 PNG data URI)
{
  "code": 200,
  "data": "data:image/png;base64,...",
  "success": true
}
```

### Pattern 3: Startup session initialization in lifespan (SESS-01)

**What:** New `_initialize_wuzapi_session()` function added to `lifespan.py`, called from Phase 1 of `_startup()` in parallel with other services.
**When to use:** Startup actions for external services follow this exact pattern.

```python
# Source: app/core/lifespan.py (add alongside _initialize_evolution_api)

async def _initialize_wuzapi_session(app: FastAPI, logger) -> None:
    """Connect WuzAPI session at startup (SESS-01).

    Non-blocking: logs warning and continues if WuzAPI is unreachable.
    WuzAPI may not be available in all environments (tests, dev without WuzAPI).
    """
    import time
    start = time.time()

    if not settings.WHATSAPP_ENABLE_SERVICE:
        logger.info("WuzAPI: WHATSAPP_ENABLE_SERVICE=False — skipping session connect")
        return

    token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
    base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", None)

    if not token or not base_url:
        logger.warning("WuzAPI: token or base_url not configured — skipping session connect")
        return

    try:
        from app.integrations.wuzapi import get_wuzapi_client
        client = get_wuzapi_client(base_url=base_url, token=token)
        await client.connect()
        try:
            result = await client.session_connect(subscribe=["Message"])
            elapsed = time.time() - start
            logger.info(
                f"WuzAPI session connected ({elapsed:.2f}s)",
                extra={"details": result.get("data", {}).get("details")}
            )
        finally:
            await client.disconnect()
    except Exception as exc:
        elapsed = time.time() - start
        logger.warning(
            f"WuzAPI session connect failed ({elapsed:.2f}s): {exc}. "
            "WhatsApp sends will fail until session is connected manually."
        )
```

**Then in `_startup` Phase 1 gather block:**
```python
await asyncio.gather(
    _initialize_monitoring(app, logger),
    _initialize_redis_websocket_events(app, logger),
    _initialize_ai_services(app, logger),
    _initialize_enum_validation(app, logger),
    _initialize_evolution_api(app, logger),   # existing — will be removed in Phase 37
    _initialize_wuzapi_session(app, logger),  # new
    return_exceptions=True
)
```

### Pattern 4: Monitoring endpoints for session (SESS-02, SESS-03)

**What:** New `app/api/v2/monitoring/wuzapi.py` router with two GET endpoints that proxy to WuzAPI session API.
**When to use:** Any monitoring endpoint that surfaces external service state to operators.

```python
# Source: app/api/v2/monitoring/wuzapi.py (new file)

from fastapi import APIRouter
from app.config import settings
from app.integrations.wuzapi import get_wuzapi_client
from app.utils.timezone import now_sao_paulo

router = APIRouter()


@router.get("/session/status")
async def get_wuzapi_session_status():
    """SESS-02: Expose WuzAPI session connection state for operators."""
    token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
    base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
    if not token:
        return {"connected": False, "logged_in": False, "error": "WHATSAPP_WUZAPI_TOKEN not configured"}
    try:
        client = get_wuzapi_client(base_url=base_url, token=token)
        await client.connect()
        try:
            result = await client.get_session_status()
            data = result.get("data", {})
            return {
                "connected": data.get("Connected", False),
                "logged_in": data.get("LoggedIn", False),
                "timestamp": now_sao_paulo().isoformat(),
            }
        finally:
            await client.disconnect()
    except Exception as exc:
        return {"connected": False, "logged_in": False, "error": str(exc)}


@router.get("/session/qr")
async def get_wuzapi_qr():
    """SESS-03: Return base64 QR code for WhatsApp pairing."""
    token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
    base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
    if not token:
        return {"qr": None, "error": "WHATSAPP_WUZAPI_TOKEN not configured"}
    try:
        client = get_wuzapi_client(base_url=base_url, token=token)
        await client.connect()
        try:
            result = await client.get_qr()
            return {"qr": result.get("data"), "timestamp": now_sao_paulo().isoformat()}
        finally:
            await client.disconnect()
    except Exception as exc:
        return {"qr": None, "error": str(exc)}
```

**Wire into `app/api/v2/monitoring/__init__.py`:**
```python
from .whatsapp import router as whatsapp_monitoring_router
from .wuzapi import router as wuzapi_monitoring_router

__all__ = ["whatsapp_monitoring_router", "wuzapi_monitoring_router"]
```

**Wire into `app/api/v2/router.py`:**
```python
from app.api.v2.monitoring import wuzapi_monitoring_router

api_v2_router.include_router(
    wuzapi_monitoring_router,
    prefix="/monitoring/wuzapi",
    tags=["wuzapi-monitoring-v2"],
)
```

### Pattern 5: MockWuzAPIClient session methods

**What:** Add matching stub methods to `MockWuzAPIClient` so tests don't break when the interface is expanded.
**When to use:** Every time WuzAPIClient gains a new method, MockWuzAPIClient must match.

```python
# Source: app/integrations/wuzapi/mock.py (add to MockWuzAPIClient)

async def session_connect(self, subscribe=None, immediate=False) -> dict:
    _ = subscribe, immediate
    return {"code": 200, "data": {"details": "Connected (mock)"}, "success": True}

async def get_session_status(self) -> dict:
    return {
        "code": 200,
        "data": {"Connected": self.connected, "LoggedIn": self.connected},
        "success": True,
    }

async def get_qr(self) -> dict:
    return {"code": 200, "data": "data:image/png;base64,mockQRcode==", "success": True}
```

### Pattern 6: .env.example update (CFG-03)

**What:** Replace the Evolution API block (lines 181-195) with a WuzAPI block. Keep `WHATSAPP_ENABLE_SERVICE` and other generic WhatsApp settings.
**When to use:** Any time env vars are added/removed.

```bash
# ============================================================================
# WHATSAPP - WUZAPI (replaces EVOLUTION API block)
# ============================================================================
WHATSAPP_ENABLE_SERVICE=true
# true => use mock client; false => real WuzAPI
WHATSAPP_WUZAPI_USE_MOCK=false
WHATSAPP_WUZAPI_BASE_URL=http://localhost:8080
# REQUIRED: Application refuses to start without this value
WHATSAPP_WUZAPI_TOKEN=CHANGE_THIS_TO_YOUR_WUZAPI_TOKEN
# Optional: HMAC-SHA256 secret for webhook signature validation
# Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'
WHATSAPP_WUZAPI_WEBHOOK_SECRET=CHANGE_THIS_TO_A_SECURE_RANDOM_VALUE
```

**Remove these lines from .env.example:**
```
WHATSAPP_EVOLUTION_USE_MOCK=...
WHATSAPP_EVOLUTION_API_URL=...
WHATSAPP_EVOLUTION_INSTANCE_NAME=...
WHATSAPP_EVOLUTION_API_KEY=...
WHATSAPP_EVOLUTION_WEBHOOK_SECRET=...
WHATSAPP_EVOLUTION_WEBHOOK_URL=...
```

Note: `WHATSAPP_WEBHOOK_HMAC_ENABLED`, `WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED`, `WHATSAPP_WEBHOOK_MAX_TIMESTAMP_AGE_SECONDS`, `WHATSAPP_WEBHOOK_IP_WHITELIST` are kept — they are shared webhook settings, not Evolution-specific.

### Anti-Patterns to Avoid

- **Silent fallback on missing token:** The requirement is explicit — no default value that lets the app start without a token. `Optional[str] = Field(default=None)` with a validator is correct; `str = Field(default="")` would allow silent empty-string startup.
- **Removing `WHATSAPP_EVOLUTION_*` fields from settings:** Do NOT remove Evolution settings from `IntegrationsSettings` in this phase. They are still used by `lifespan.py (_initialize_evolution_api)` and `whatsapp.py monitoring router`. Evolution cleanup is Phase 37.
- **Creating a WuzAPIClient singleton at module import time:** Construct clients on demand with `get_wuzapi_client(base_url=settings.WHATSAPP_WUZAPI_BASE_URL, token=settings.WHATSAPP_WUZAPI_TOKEN)`. The settings object is guaranteed to be populated by the time the factory is called.
- **Calling `settings.WHATSAPP_WUZAPI_TOKEN` directly in the validator before `__init__` completes:** Use `self.WHATSAPP_WUZAPI_TOKEN` inside the `@model_validator(mode="after")` — `self` is fully populated at that point.
- **Opening a persistent aiohttp session in a monitoring endpoint:** The monitoring endpoints have low traffic. Open and close `aiohttp.ClientSession` per request (via `client.connect()` / `client.disconnect()`) to avoid resource leaks in a short-lived endpoint handler.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Startup validation for missing env var | Custom check in `lifespan.py` | `@model_validator(mode="after")` in settings class | Validators run before the app boots — fail before lifespan runs at all |
| HTTP client for session endpoints | Separate aiohttp session | `WuzAPIClient._make_request()` | Reuses rate limiter, circuit breaker, retry policy, and auth headers |
| QR code decoding | PIL/Pillow base64 parsing | Return base64 data URI as-is to caller | The endpoint contract is to return the base64 string; rendering is the frontend's job |
| Mock session methods | A separate mock module | Add methods to `MockWuzAPIClient` | One mock class, one truth — the existing mock pattern |

---

## Common Pitfalls

### Pitfall 1: Validator runs in all environments including test
**What goes wrong:** If the hard-fail validator runs in test environments where `WHATSAPP_WUZAPI_TOKEN` is not set, every pytest session fails at import time of `settings`.
**Why it happens:** pydantic-settings validators run when the `Settings()` singleton is instantiated, which happens at `from app.config import settings`.
**How to avoid:** Guard the hard-fail with an env check: allow absence when `APP_ENVIRONMENT in ("test", "testing")` and when `PYTEST_CURRENT_TEST` is set. Look at `_is_test_environment()` in `lifespan.py` for the existing pattern.
**Warning signs:** All tests fail with `ValueError: STARTUP VALIDATION FAILED: WHATSAPP_WUZAPI_TOKEN is required` in `conftest.py`.

### Pitfall 2: IntegrationsSettings fields missing from Settings boolean parse list
**What goes wrong:** If `WHATSAPP_WUZAPI_USE_MOCK` (a bool) is added to `IntegrationsSettings` but not to the `boolean_fields` list in `Settings.parse_env_values`, then `WHATSAPP_WUZAPI_USE_MOCK=true` in `.env` may not be correctly parsed.
**Why it happens:** The `Settings.__init__.py` `parse_env_values` maintains a centralized boolean parse list that supplements individual class validators.
**How to avoid:** For any new `bool` field in `IntegrationsSettings`, add the env var name to the `boolean_fields` list in `Settings.parse_env_values`. For the three fields in CFG-01, only `WHATSAPP_WUZAPI_USE_MOCK` (if added) would be boolean — the others are string/Optional[str].

### Pitfall 3: Removing Evolution settings breaks the monitoring whatsapp router
**What goes wrong:** `app/api/v2/monitoring/whatsapp.py` calls `settings.WHATSAPP_EVOLUTION_INSTANCE_NAME` and `settings.WHATSAPP_EVOLUTION_API_URL`. Removing these fields causes `AttributeError` at import.
**Why it happens:** Phase 35 is NOT the cleanup phase. Evolution cleanup is Phase 37.
**How to avoid:** Add WuzAPI fields only. Leave all `WHATSAPP_EVOLUTION_*` fields in settings and `.env.example` for now (marked as "to be removed in Phase 37").

### Pitfall 4: WuzAPI GET endpoints use query params not body
**What goes wrong:** WuzAPIClient `_make_request` sends JSON body by default. For `GET /session/status` and `GET /session/qr`, no body should be sent.
**Why it happens:** The `_do_request` method passes `json=data` to aiohttp. For GET with `data=None` this is safe (aiohttp does not send a Content-Type or body when `json=None`).
**How to avoid:** Pass `data=None` (default) for GET calls. The current `_make_request` signature already supports `data=None`.

### Pitfall 5: `get_wuzapi_client()` factory ignores base_url/token when USE_MOCK=true
**What goes wrong:** If `WHATSAPP_WUZAPI_USE_MOCK=true` and the monitoring endpoint calls `get_wuzapi_client(base_url=..., token=...)`, the mock client is returned — which is correct for testing. But if a developer forgets to set the env var and doesn't notice the mock is active, status checks return fake data.
**Why it happens:** `get_wuzapi_client` checks the env var at call time.
**How to avoid:** Log clearly in the monitoring endpoints when mock is active. The mock `get_session_status()` returns `connected=True` which would be misleading. Consider returning an explicit `mock: true` flag in the response.

---

## Code Examples

### Adding a field to IntegrationsSettings with validator

```python
# Source: app/config/settings/integrations.py — existing validated field pattern
# (comparison: WHATSAPP_EVOLUTION_WEBHOOK_SECRET uses Optional[str] with None default)

WHATSAPP_WUZAPI_TOKEN: Optional[str] = Field(
    default=None,
    description="WuzAPI API token — REQUIRED at startup"
)

@model_validator(mode="after")
def validate_wuzapi_token(self) -> "IntegrationsSettings":
    import os
    is_test = (
        os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("TESTING") == "1"
        or self.APP_ENVIRONMENT.lower() in ("test", "testing")
    )
    if not is_test and not (self.WHATSAPP_WUZAPI_TOKEN or "").strip():
        raise ValueError(
            "WHATSAPP_WUZAPI_TOKEN is required. "
            "Application cannot start without a WuzAPI token."
        )
    return self
```

### Making a GET request with WuzAPIClient

```python
# Source: app/integrations/wuzapi/client.py — _make_request pattern
# GET with no body — data=None (default) is correct

async def get_session_status(self) -> dict[str, Any]:
    return await self._make_request("GET", "/session/status")
```

### Monitoring endpoint with per-request client lifecycle

```python
# Source: app/api/v2/monitoring/wuzapi.py — per-request connect/disconnect pattern
# (mirrors how lifespan _initialize_evolution_api handles client lifecycle)

client = get_wuzapi_client(base_url=base_url, token=token)
await client.connect()
try:
    result = await client.get_session_status()
finally:
    await client.disconnect()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Evolution API for WhatsApp | WuzAPI (whatsmeow-based) | v1.6 (Phase 33) | New client, new session lifecycle, new token auth header |
| `WHATSAPP_EVOLUTION_API_KEY` | `WHATSAPP_WUZAPI_TOKEN` | Phase 35 | Token goes directly in `Authorization` header, no instance name needed |
| Evolution instance status check at startup | WuzAPI `POST /session/connect` | Phase 35 | Simpler — no instance creation flow, just connect |

**Deprecated/outdated:**
- `WHATSAPP_EVOLUTION_*` env vars: to be removed from settings and `.env.example` in **Phase 37**. In Phase 35 they are still present.
- `_initialize_evolution_api` lifespan function: to be removed in Phase 37.

---

## Open Questions

1. **Should `WHATSAPP_WUZAPI_WEBHOOK_SECRET` also be a hard-fail validator?**
   - What we know: CFG-02 specifies only `WHATSAPP_WUZAPI_TOKEN` as required. The webhook secret is needed for HMAC validation (WH-04 in Phase 34).
   - What's unclear: Phase 34 webhook HMAC validation already reads the secret from settings — but Phase 34 is already complete. If the secret is absent, HMAC will fail at runtime.
   - Recommendation: Make `WHATSAPP_WUZAPI_WEBHOOK_SECRET` a warning-only (log) in dev, hard-fail in production only. Mirrors how `WHATSAPP_EVOLUTION_WEBHOOK_SECRET` behaved.

2. **How should the startup connect handle "already connected" state?**
   - What we know: WuzAPI `POST /session/connect` is idempotent — calling it when already connected returns success.
   - What's unclear: If the session is already connected (e.g., restart after crash), connecting again may re-subscribe to events.
   - Recommendation: Call `GET /session/status` first; if already connected, skip `POST /session/connect`. Prevents unnecessary re-subscription.

3. **Should the monitoring endpoints require authentication?**
   - What we know: The existing `GET /monitoring/whatsapp/health` in `whatsapp.py` uses `Depends(get_db)` but no auth dependency.
   - What's unclear: Whether QR code exposure (which is sensitive — it authenticates a WhatsApp session) should be gated.
   - Recommendation: Add `Depends(get_current_user)` or admin-only auth to `GET /session/qr` since it's operationally sensitive. `GET /session/status` can remain open (it's read-only connection state).

---

## Sources

### Primary (HIGH confidence)
- `backend-hormonia/app/config/settings/integrations.py` — Field definition patterns for `WHATSAPP_EVOLUTION_*` fields
- `backend-hormonia/app/config/settings/security.py` — `validate_required_environment_variables` pattern for hard-fail startup validator
- `backend-hormonia/app/config/settings/__init__.py` — `Settings` composite class, `parse_env_values` boolean list, test environment guard
- `backend-hormonia/app/core/lifespan.py` — `_initialize_evolution_api` as the canonical startup service init pattern
- `backend-hormonia/app/api/v2/monitoring/whatsapp.py` — Monitoring router endpoint pattern
- `backend-hormonia/app/integrations/wuzapi/client.py` — `WuzAPIClient._make_request` method signature
- `backend-hormonia/app/integrations/wuzapi/mock.py` — `MockWuzAPIClient` method shape
- `backend-hormonia/app/integrations/wuzapi/__init__.py` — `get_wuzapi_client` factory signature
- `backend-hormonia/.env.example` — Current Evolution API env var block (lines 181-195 to replace)
- [WuzAPI API.md (official)](https://github.com/asternic/wuzapi/blob/main/API.md) — Session endpoint shapes, HTTP methods, response schemas

### Secondary (MEDIUM confidence)
- [WuzAPI GitHub README](https://github.com/asternic/wuzapi/blob/main/README.md) — Authentication model (Token header), multi-session concept
- [WuzAPI web search results 2024-2025](https://www.blog.brightcoding.dev/2025/11/23/the-ultimate-guide-to-whatsapp-rest-api-service-in-go-build-scalable-multi-device-solutions-with-wuzapi-%F0%9F%9A%80/) — Community usage patterns confirming endpoint names

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are existing project dependencies, no new deps required
- Architecture: HIGH — every pattern (validator, lifespan function, monitoring router) has a direct precedent in the codebase
- WuzAPI session endpoint shapes: HIGH — verified from official `API.md` in the asternic/wuzapi repo
- Pitfalls: HIGH — derived from reading the actual settings validator code, lifespan code, and understanding test environment behavior

**Research date:** 2026-03-02
**Valid until:** 2026-06-01 (stable domain — pydantic-settings and WuzAPI session API are unlikely to change)
