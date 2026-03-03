# Phase 39: WuzAPI Integration Polish - Research

**Researched:** 2026-03-03
**Domain:** FastAPI/Python — settings consistency, HTTP 501 endpoints, dead code removal
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WH-04 | HMAC validation uses `x-hmac-signature` header with SHA-256 on raw request body bytes | Fix confirmed: `webhook.py:37` reads secret from `os.environ.get()` — must change to `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET` |
| CFG-01 | New env vars added: `WHATSAPP_WUZAPI_BASE_URL`, `WHATSAPP_WUZAPI_TOKEN`, `WHATSAPP_WUZAPI_WEBHOOK_SECRET` | `WHATSAPP_WUZAPI_WEBHOOK_SECRET` already exists on `IntegrationsSettings` — webhook.py just needs to import and use it |
| OUT-02 | WhatsAppMessageService queue pipeline wired to WuzAPIClient | The `sync_contacts` endpoint is part of this pipeline — returning 501 (or removing the route) closes the misleading 200/NotImplementedError gap |
</phase_requirements>

---

## Summary

Phase 39 closes three integration polish items flagged in the v1.6 milestone audit (M-1, M-2, and the orphaned models tech debt). All three are small, targeted code changes — no new libraries, no new architecture, no schema changes.

**Gap 1 (M-1, severity: LOW):** `app/integrations/wuzapi/webhook.py` line 37 reads `WHATSAPP_WUZAPI_WEBHOOK_SECRET` from `os.environ.get()` instead of `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET`. Every other consumer of this env var (`webhook_validator.py`, `webhook_service.py`, `whatsapp/security.py`) uses `settings`. This inconsistency bypasses Pydantic validation and field documentation. The fix is a one-line change: replace `os.environ.get("WHATSAPP_WUZAPI_WEBHOOK_SECRET")` with `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET` and drop the `import os` if it becomes unused.

**Gap 2 (M-2, severity: MEDIUM):** `POST /whatsapp/contacts/{instance_name}/sync` in `routes.py` schedules `message_service.sync_contacts()` as a background task, but that method raises `NotImplementedError`. The endpoint returns HTTP 200 ("sync_started") while the background silently crashes. The correct fix is to remove the background scheduling entirely and return HTTP 501 with a clear "WuzAPI does not support contacts sync" message directly from the handler — eliminating the misleading success response.

**Gap 3 (orphaned models, severity: LOW):** `WuzAPIWebhookEvent` and `WuzAPIMessageInfo` in `app/integrations/wuzapi/models.py` are defined but never imported or used by any runtime code. Grep confirms zero consumers in `app/` and `tests/`. These can be removed, or if kept they need a clear docstring noting they are reference-only types reserved for future structured parsing.

**Primary recommendation:** Treat all three gaps as one compact plan. Fix M-1 (settings import), replace M-2 (sync_contacts endpoint to 501), and remove the orphaned models. Update tests for webhook.py to patch `settings` instead of `os.environ.get`. Total impact: 3-4 files modified, zero new dependencies.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `app.config.settings` (Pydantic Settings) | existing | Centralized env var access with type validation | All other WuzAPI consumers already use it |
| `fastapi.HTTPException` | existing | Return structured error responses | Already used throughout routes.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` + `httpx` | existing | Test HMAC path with settings patch | Same pattern as test_wuzapi_webhook.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Remove sync_contacts route | Keep route + return 501 inline | Removing is cleaner (dead code); returning 501 is more explicit. Prefer 501 in-place since the route may be in client code or documentation — the 501 signals "not implemented" clearly |
| Remove orphaned models | Add docstring + keep them | Removing is the correct IDS pattern (REUSE > ADAPT > CREATE, dead types accumulate); removal wins unless another consumer is planned |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure

No structural changes. Changes are in-place within existing files:

```
backend-hormonia/app/integrations/wuzapi/
├── webhook.py      # Fix: os.environ.get -> settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET
└── models.py       # Fix: remove WuzAPIWebhookEvent and WuzAPIMessageInfo

backend-hormonia/app/integrations/whatsapp/api/
└── routes.py       # Fix: sync_contacts handler -> HTTP 501 directly

backend-hormonia/tests/integrations/wuzapi/
└── test_wuzapi_webhook.py  # Fix: patch target -> settings attribute
```

### Pattern 1: Settings-based config access (all other WuzAPI callers)

**What:** Access env vars through the Pydantic Settings object, never via `os.environ` directly.
**When to use:** Every env var access in application code.

```python
# Source: app/middleware/webhook_validator.py:19
# Source: app/services/webhook_service.py:106,123
# Source: app/services/whatsapp/security.py:46

from app.config import settings

# CORRECT (all other callers do this):
secret = settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET

# WRONG (current webhook.py line 37 — the bug):
# secret = os.environ.get("WHATSAPP_WUZAPI_WEBHOOK_SECRET")
```

The settings object is a global singleton (`settings = Settings()`) in `app/config/settings/__init__.py`. It is safe to import at module level in webhook.py.

### Pattern 2: HTTP 501 for unimplemented provider features

**What:** Return 501 Not Implemented immediately when a route calls an operation the current provider does not support.
**When to use:** Any endpoint whose underlying service method raises `NotImplementedError` due to provider capability gap.

```python
# Pattern used elsewhere (routes.py line 76-80, WuzAPI token missing):
raise HTTPException(
    status_code=501,
    detail="WuzAPI does not support contacts sync. "
           "This endpoint has been retained for API compatibility but will not perform any sync.",
)
```

The sync_contacts handler should be rewritten to raise HTTPException(501) immediately without scheduling any background task. The `background_tasks` parameter can be removed since it is no longer needed.

### Pattern 3: Removing dead/orphaned Pydantic models

**What:** Remove model classes that have zero runtime consumers.
**When to use:** After confirming with Grep that no `import` statement references the class names outside of the defining module.

```python
# Confirmed by grep: WuzAPIWebhookEvent and WuzAPIMessageInfo have ZERO consumers
# in app/ and tests/ directories.
# The extractor (extractor.py) uses raw dict access, not these models.
# The webhook router (webhook.py) uses raw dict access, not these models.
# Safe to remove both classes from models.py entirely.
```

### Anti-Patterns to Avoid

- **`os.environ.get()` in application code:** Bypasses Pydantic validation, type coercion, and field documentation. All env var access must go through `settings`.
- **Background tasks that raise NotImplementedError:** Creates silent errors and misleads clients. Return an HTTP error synchronously instead.
- **Keeping dead model classes indefinitely:** Orphaned types add cognitive load and imply future usage that never comes. Remove or explicitly document them as tombstoned.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Settings access | Custom env reader | `from app.config import settings` | Already validated and type-safe |
| "Not implemented" HTTP response | Custom 200+message | `HTTPException(status_code=501, ...)` | Standard REST semantics, FastAPI built-in |

**Key insight:** This phase is pure polish — no new infrastructure needed. The fixes are shorter than the original code.

---

## Common Pitfalls

### Pitfall 1: Breaking webhook HMAC tests after settings refactor

**What goes wrong:** Existing `test_wuzapi_webhook.py` patches `app.integrations.wuzapi.webhook.os.environ.get` to inject a test secret. After the fix, this patch no longer intercepts the secret read (it now goes through `settings`). Tests that rely on the old patch target will fail with "HMAC validation skipped" or unexpected 403/200 results.

**Why it happens:** Python `unittest.mock.patch` targets the name as it is used in the module. Patching `os.environ.get` after the module switches to `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET` has no effect.

**How to avoid:** Update test patches to target `app.integrations.wuzapi.webhook.settings` (the settings object imported into webhook.py), or use `monkeypatch.setattr(settings, "WHATSAPP_WUZAPI_WEBHOOK_SECRET", "test-secret")`. The simplest approach: add `from app.config import settings` to webhook.py and then patch `app.integrations.wuzapi.webhook.settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET` in tests.

**Warning signs:** Test output shows `test_valid_hmac_returns_200` or `test_invalid_hmac_returns_403` failing after the fix.

**Affected tests (in test_wuzapi_webhook.py):**
- `test_valid_hmac_returns_200` — patches `os.environ.get` on line 92
- `test_invalid_hmac_returns_403` — patches `os.environ.get` on line 101
- `test_missing_hmac_header_returns_403` — patches `os.environ.get` on line 128

### Pitfall 2: `import os` left dangling after settings migration

**What goes wrong:** After replacing `os.environ.get(...)` with `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET`, the `import os` at the top of webhook.py becomes unused. Linters (flake8, ruff) will flag this as an error in CI.

**Why it happens:** `os` is only used on line 5 (`import os`) and line 37 (`os.environ.get(...)`). After the fix, the only remaining `os` usage is removed.

**How to avoid:** Check if `os` is used anywhere else in webhook.py (it is not, per the current file). Remove `import os` when removing the `os.environ.get()` call.

**Warning signs:** CI lint step fails with `F401 'os' imported but unused`.

### Pitfall 3: sync_contacts BackgroundTasks parameter left in signature

**What goes wrong:** If the handler body is changed to raise 501 but the `background_tasks: BackgroundTasks` parameter is left in the function signature, FastAPI will still inject a BackgroundTasks object (harmless) but the import of `BackgroundTasks` may become unused if it's not referenced elsewhere in routes.py.

**How to avoid:** Remove the `background_tasks: BackgroundTasks` parameter from the `sync_contacts` function signature and verify that `BackgroundTasks` is still imported for other handlers (it is not — confirm with Grep before removing the import).

**Warning signs:** Linter flags `BackgroundTasks` as unused import.

### Pitfall 4: models.py `__init__.py` re-exports broken after removal

**What goes wrong:** If `WuzAPIWebhookEvent` or `WuzAPIMessageInfo` are re-exported from `app/integrations/wuzapi/__init__.py`, removing them from models.py will cause an ImportError at startup.

**How to avoid:** Check `__init__.py` before removing.

```python
# Current __init__.py — confirmed does NOT re-export WuzAPIWebhookEvent or WuzAPIMessageInfo
# (only re-exports get_wuzapi_client, WuzAPIClient, MockWuzAPIClient, etc.)
```

---

## Code Examples

Verified patterns from the codebase:

### Fix M-1: webhook.py settings migration

```python
# Source: app/integrations/wuzapi/webhook.py (current buggy code at line 37)
# BEFORE:
import os
...
secret = os.environ.get("WHATSAPP_WUZAPI_WEBHOOK_SECRET")

# AFTER (matching all other callers):
from app.config import settings
...
secret = settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET
```

### Fix M-1: Updated test patch target

```python
# Source: tests/integrations/wuzapi/test_wuzapi_webhook.py
# BEFORE (current — breaks after fix):
with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
    ...

# AFTER (correct patch target post-fix):
with patch.object(
    __import__("app.integrations.wuzapi.webhook", fromlist=["settings"]).settings,
    "WHATSAPP_WUZAPI_WEBHOOK_SECRET",
    secret,
):
    ...
# OR simpler — patch the module-level settings object:
import app.integrations.wuzapi.webhook as wh_module
with patch.object(wh_module.settings, "WHATSAPP_WUZAPI_WEBHOOK_SECRET", secret):
    ...
```

### Fix M-2: sync_contacts endpoint returning 501

```python
# Source: app/integrations/whatsapp/api/routes.py (lines 205-221)
# BEFORE:
@router.post("/contacts/{instance_name}/sync")
async def sync_contacts(
    instance_name: str,
    background_tasks: BackgroundTasks,
    message_service: WhatsAppMessageService = Depends(get_message_service),
):
    """Synchronize contacts from WhatsApp."""
    try:
        background_tasks.add_task(message_service.sync_contacts, instance_name)
        return {
            "status": "sync_started",
            "instance_name": instance_name,
            "timestamp": now_sao_paulo(),
        }
    except Exception as e:
        logger.error(f"Error starting contact sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start contact sync")

# AFTER:
@router.post("/contacts/{instance_name}/sync")
async def sync_contacts(instance_name: str):
    """Contacts sync is not supported by WuzAPI.

    WuzAPI (whatsmeow-based) does not expose a contacts API equivalent to
    Evolution API. This endpoint is retained for API compatibility and returns
    HTTP 501 to avoid silent failures from the previous stub implementation.
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Contacts sync is not supported by WuzAPI. "
            "WuzAPI does not expose a contacts management API. "
            "Use GET /whatsapp/contacts/{instance_name} to read locally stored contacts."
        ),
    )
```

### Fix Gap 3: Remove orphaned models

```python
# Source: app/integrations/wuzapi/models.py
# Remove these two classes entirely (lines 36-55 in current file):
#   class WuzAPIMessageInfo(BaseModel): ...
#   class WuzAPIWebhookEvent(BaseModel): ...
#
# Confirmed safe: zero imports of these classes in app/ or tests/
# (grep: "WuzAPIWebhookEvent|WuzAPIMessageInfo" -> only models.py itself)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Evolution API env vars via `os.environ` | WuzAPI env vars via Pydantic settings | Phase 35 | Settings-based access is validated at startup |
| sync_contacts returned 200 with background NotImplementedError | Endpoint returns 501 immediately | Phase 39 (this phase) | Clients get correct HTTP semantics |
| Orphaned webhook envelope models in models.py | Removed | Phase 39 (this phase) | Cleaner models.py; no unused types |

**Deprecated/outdated:**
- `os.environ.get("WHATSAPP_WUZAPI_WEBHOOK_SECRET")` in webhook.py: replaced by `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET`
- `background_tasks.add_task(message_service.sync_contacts, ...)`: removed (operation not supported)
- `WuzAPIWebhookEvent`, `WuzAPIMessageInfo` in models.py: removed (orphaned types)

---

## Open Questions

1. **Should sync_contacts route be removed entirely or return 501?**
   - What we know: Phase 36 decision log says "removal deferred to Phase 37" — but Phase 37 didn't remove it, and now Phase 39 is the cleanup phase
   - What's unclear: Whether any external client (frontend-hormonia, quiz interface) calls this endpoint and would benefit from seeing 501 vs a 404 from a removed route
   - Recommendation: Return 501 (not remove). A 501 is self-documenting — it tells the caller "this server understands the request but doesn't implement it." A 404 from a removed route would look like a routing bug.

2. **Should `WuzAPIWebhookEvent` and `WuzAPIMessageInfo` be tombstoned or hard-deleted?**
   - What we know: These are Pydantic models (not async infrastructure), zero consumers confirmed, no tombstone pattern applies to data models in this codebase (tombstones are for service/client classes)
   - What's unclear: None — the IDS principle says dead code should be removed
   - Recommendation: Hard delete. Pydantic models are not services; tombstoning them with an ImportError sentinel would be bizarre. Remove the two class definitions.

---

## Precise File Inventory

Every file that requires a code change in this phase:

### File 1: `backend-hormonia/app/integrations/wuzapi/webhook.py`

**Change:** Replace `os.environ.get("WHATSAPP_WUZAPI_WEBHOOK_SECRET")` with `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET`. Add `from app.config import settings`. Remove `import os` (no longer used elsewhere in file).

**Lines affected:** 4 (import os), 37 (os.environ.get call). Requires adding one new import line.

**Risk:** LOW — settings object is a singleton, already initialized before any request is processed. The value resolves identically at runtime.

### File 2: `backend-hormonia/app/integrations/wuzapi/models.py`

**Change:** Remove `WuzAPIWebhookEvent` class (lines 47-55) and `WuzAPIMessageInfo` class (lines 36-45).

**Lines affected:** Lines 36-55 (20 lines removed). File shrinks from 55 lines to ~35 lines.

**Risk:** LOW — grep confirms zero consumers in entire codebase.

### File 3: `backend-hormonia/app/integrations/whatsapp/api/routes.py`

**Change:** Rewrite `sync_contacts` handler to raise `HTTPException(501, ...)` immediately. Remove `background_tasks: BackgroundTasks` parameter. Remove `message_service` dependency injection from this handler. Check whether `BackgroundTasks` import is still needed elsewhere (it is not — confirm before removing).

**Lines affected:** Lines 205-221 (handler body). Possibly line 8 if `BackgroundTasks` import is removed.

**Risk:** LOW — the previous implementation was already broken at runtime (NotImplementedError). Clients that got a 200 were receiving false information.

### File 4: `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py`

**Change:** Update three tests that patch `app.integrations.wuzapi.webhook.os.environ.get` to instead patch the settings attribute. Tests: `test_valid_hmac_returns_200` (line 92), `test_invalid_hmac_returns_403` (line 101), `test_missing_hmac_header_returns_403` (line 128).

**Patch pattern options:**
- `with patch.object(wh_module.settings, "WHATSAPP_WUZAPI_WEBHOOK_SECRET", secret):`
- `monkeypatch.setattr(settings, "WHATSAPP_WUZAPI_WEBHOOK_SECRET", secret)`

**Risk:** LOW — purely mechanical test update, same behavior being tested.

---

## Sources

### Primary (HIGH confidence)

- Direct code inspection: `app/integrations/wuzapi/webhook.py` — confirmed `os.environ.get` at line 37
- Direct code inspection: `app/integrations/wuzapi/models.py` — confirmed orphaned classes
- Direct code inspection: `app/integrations/whatsapp/api/routes.py` — confirmed 200 + NotImplementedError pattern
- Direct code inspection: `app/integrations/whatsapp/services/message_service.py:753-765` — confirmed `raise NotImplementedError`
- Direct code inspection: `app/config/settings/integrations.py:59-65` — confirmed `WHATSAPP_WUZAPI_WEBHOOK_SECRET` on IntegrationsSettings
- Grep search: `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET` — found 3 correct consumers in `webhook_validator.py`, `webhook_service.py`, `whatsapp/security.py`
- Grep search: `WuzAPIWebhookEvent|WuzAPIMessageInfo` — confirmed zero consumers outside models.py
- Direct code inspection: `.planning/v1.6-MILESTONE-AUDIT.md` — confirmed M-1 (LOW), M-2 (MEDIUM), orphaned models findings
- Direct code inspection: `tests/integrations/wuzapi/test_wuzapi_webhook.py` — confirmed 3 tests use old patch target

### Secondary (MEDIUM confidence)

- HTTP 501 semantics: RFC 7231 §6.6.2 — "The server does not support the functionality required to fulfill the request." This is the canonical response for "this endpoint exists but the operation is not implemented."

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all patterns from existing codebase
- Architecture: HIGH — changes are in-place within existing files, no structural changes
- Pitfalls: HIGH — identified from direct code inspection of test file patch targets and import analysis

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (stable domain — settings and FastAPI patterns don't change rapidly)
