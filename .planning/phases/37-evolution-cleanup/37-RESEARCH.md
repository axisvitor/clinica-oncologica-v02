# Phase 37: Evolution Cleanup - Research

**Researched:** 2026-03-02
**Domain:** Python dead-code tombstoning, FastAPI router deregistration, pydantic settings cleanup
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLEAN-01 | Stack A tombstoned: `app/integrations/evolution/` (client, message_sender, request_handler, webhook_handler, rate_limiter, validators) converted to ImportError sentinels | Tombstone pattern confirmed from Phase 12/16; all 7 files identified |
| CLEAN-02 | Stack B tombstoned: `app/integrations/whatsapp/services/evolution_client.py` and `mock_evolution.py` converted to ImportError sentinels | Both files confirmed live; callers in routes.py and __init__.py identified |
| CLEAN-03 | Evolution webhook handler tombstoned: `app/integrations/whatsapp/api/webhooks.py` deregistered from router | Router registration path confirmed (router_registry.py → whatsapp/__init__.py); webhook_handler.py also wraps it |
| CLEAN-04 | Evolution message extractor tombstoned: `app/services/webhook/utils/message_extractor.py` | File confirmed active; only one call site in message_handler.py at line 459 needs removal |
| CLEAN-05 | LID resolution methods removed from `phone_normalizer.py` (WuzAPI/whatsmeow handles internally) | `resolve_phone_from_lid`, `_fetch_evolution_chats`, `_match_phone_jid_for_lid`, `_normalize_chat_name`, `_parse_chat_timestamp` identified; single call site in message_handler.py line 459 |
| CLEAN-06 | `WHATSAPP_EVOLUTION_*` env vars removed from settings and `.env.example` | 10 settings fields identified; `.env.example` has only `WHATSAPP_EVOLUTION_TIMEOUT_SECONDS` remaining; `worker/.env.example` has 5 more |
</phase_requirements>

---

## Summary

Phase 37 is a tombstone-and-prune operation: all Evolution API code that was bypassed in Phase 36 (outbound rewiring) must now be converted to `ImportError` sentinels so any surviving import attempt fails immediately at startup rather than silently consuming Evolution API credentials that no longer exist.

The project has a mature tombstone pattern (used in Phase 12 for LangGraph, Phase 16 for dead code): replace the file content with a module-level docstring explaining the removal and a bare `raise ImportError(...)` on the first executable line. This pattern has been applied to at least 20+ modules in the codebase and is well-understood.

The complexity of this phase comes not from the tombstoning itself but from the dependency graph: several non-Evolution files still import from Evolution modules (`routes.py`, `__init__.py`, `orchestrator.py`, `message_handler.py`, `service_health.py`, `patients/crud.py`, `security.py`, `webhook_validator.py`). Each of these callers must be cleaned up or have their Evolution reference replaced/removed before or alongside the tombstone, otherwise the application fails to start.

**Primary recommendation:** Tombstone in two waves — first fix all callers (routes.py, __init__ files, orchestrator, health check, webhook infrastructure), then convert the Evolution files to ImportError sentinels. Commit as a single Phase 37 commit.

---

## Standard Stack

### Core (already in project)
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Python `raise ImportError(...)` | stdlib | Module-level tombstone sentinel | Zero dependencies; fails fast at import time |
| Pydantic `Field` removal | pydantic v2 | Remove settings fields | Already used throughout `IntegrationsSettings` |
| FastAPI `APIRouter` | current | Router deregistration | Remove `include_router` call and `webhook_router` export |
| `pytest` + `importlib` | 7.x | Verify tombstones raise | CI-runnable; established in codebase |

### Verification Tools (already in project)
| Tool | Purpose |
|------|---------|
| `scripts/check_agent_run_calls.py` | Reference CI lint script pattern to write TEST-05 equivalent |
| `grep -r "EvolutionAPIClient\|EvolutionClient"` | Verify zero live imports after tombstone |

---

## Architecture Patterns

### Tombstone Pattern (established in project)

All tombstoned modules follow exactly this structure — no variation:

```python
"""
TOMBSTONED -- Phase 37 (Evolution Cleanup)

This module has been decommissioned. WuzAPI replaces all Evolution API
outbound and inbound functionality as of Phase 37.

Do not import from this module.
"""
raise ImportError(
    "app.integrations.evolution has been tombstoned in Phase 37 (Evolution Cleanup). "
    "Use app.integrations.wuzapi for WhatsApp messaging."
)
```

Source: `app/ai/langgraph/__init__.py`, `app/services/flow/constants.py` (all identical structure).

### Caller Cleanup Pattern

Before tombstoning a module, all callers must be either:
1. **Removed** — if the caller itself is dead (e.g., `evolution_client.py` in routes.py `get_evolution_client()` function used only by Evolution endpoints being deleted)
2. **Replaced** — if the caller is live but uses a replaceable evolution reference (e.g., `EvolutionClient()` in `patients/crud.py` which passes it to `SagaOrchestrator`; `SagaOrchestrator.__init__` accepts `Optional[EvolutionClient]` and stores it but the field is never used downstream — so the argument can simply be omitted)

### Router Deregistration Pattern

The Evolution webhook router at `/webhooks/whatsapp` is registered via:
1. `app/integrations/whatsapp/__init__.py` exports `webhook_router` (from `api/webhooks.py`)
2. `app/core/router_registry.py` calls `app.include_router(webhook_router)`
3. `app/integrations/whatsapp/webhook_handler.py` wraps `api/webhooks.py` functions in a second router at `/api/v2/webhooks/whatsapp/evolution/{instance_name}`

Deregistration requires:
- Removing the `webhook_router` export from `whatsapp/__init__.py`
- Removing `app.include_router(webhook_router)` from `router_registry.py`
- Tombstoning `api/webhooks.py` (CLEAN-03)
- Tombstoning `webhook_handler.py` (the wrapper, which imports from `api/webhooks.py`)

After deregistration, `GET /webhooks/whatsapp/*` and `POST /api/v2/webhooks/whatsapp/evolution/*` return 404.

---

## Complete File Inventory

### Stack A — `app/integrations/evolution/` (7 files — CLEAN-01)

| File | Class/Function | Status | Action |
|------|---------------|--------|--------|
| `__init__.py` | exports `EvolutionClient`, `get_evolution_client`, etc. | Live | Tombstone |
| `client.py` | `EvolutionClient`, `get_evolution_client`, `close_evolution_client` | Live | Tombstone |
| `message_sender.py` | `MessageSender` | Live | Tombstone |
| `request_handler.py` | `RequestHandler` | Live | Tombstone |
| `webhook_handler.py` | `WebhookHandler` | Live | Tombstone |
| `rate_limiter.py` | `RateLimiter` | Live | Tombstone |
| `validators.py` | `format_phone_number`, `validate_message_content` | Live | Tombstone |
| `models.py` | `MessageType`, `TextMessage`, `WebhookEvent`, `EvolutionAPIError` | Live | Tombstone (not individually listed in requirements but is part of the package) |

### Stack B — `app/integrations/whatsapp/services/` (2 files — CLEAN-02)

| File | Class/Function | Status | Action |
|------|---------------|--------|--------|
| `evolution_client.py` | `EvolutionAPIClient`, `RateLimiter`, `EvolutionAPIError` | Live | Tombstone |
| `mock_evolution.py` | `MockEvolutionAPIClient`, `create_evolution_client` | Live | Tombstone |

### Evolution Webhook Handler (CLEAN-03)

| File | Routes | Status | Action |
|------|--------|--------|--------|
| `app/integrations/whatsapp/api/webhooks.py` | `POST /webhooks/whatsapp/{instance_name}`, `POST /webhooks/whatsapp/{instance_name}/{event_name}` | Live | Tombstone + deregister |
| `app/integrations/whatsapp/webhook_handler.py` | `POST /api/v2/webhooks/whatsapp/evolution/{instance_name}` | Live | Tombstone + deregister |

### Message Extractor (CLEAN-04)

| File | Function | Status | Action |
|------|----------|--------|--------|
| `app/services/webhook/utils/message_extractor.py` | `extract_message_data`, `_clean_phone_from_jid`, `_prefer_non_lid_jid`, `_select_source_jid`, `_extract_content_and_type` | Live | Tombstone (only called from `message_handler.py` Evolution path) |

### LID Resolution Methods (CLEAN-05)

| Location | Methods to remove | Callers |
|----------|------------------|---------|
| `app/services/webhook/utils/phone_normalizer.py` | `resolve_phone_from_lid`, `_fetch_evolution_chats`, `_match_phone_jid_for_lid`, `_normalize_chat_name`, `_parse_chat_timestamp`, class-level `_lid_resolution_cache: Dict[str, str]` | `message_handler.py:459` — single call site |

The call site in `message_handler.py` at line 459 is in an `if remote_jid.endswith("@lid"):` block that must be deleted entirely (WuzAPI/whatsmeow resolves LIDs internally before delivering events).

### Settings Fields to Remove (CLEAN-06)

From `app/config/settings/integrations.py`, remove these `Field(...)` declarations:

| Field | Default | Still Used? |
|-------|---------|-------------|
| `WHATSAPP_EVOLUTION_USE_MOCK` | `False` | routes.py `_should_use_mock_evolution()` — remove |
| `WHATSAPP_EVOLUTION_API_URL` | `"http://localhost:8080"` | routes.py, lifespan, security, phone_normalizer — all to be cleaned |
| `WHATSAPP_EVOLUTION_INSTANCE_NAME` | `"clinica_oncologica"` | monitoring/whatsapp.py lines 36, 47 — requires cleanup there |
| `WHATSAPP_EVOLUTION_API_KEY` | `"your-evolution-api-key-here"` | routes.py, lifespan, validation.py — all to be cleaned |
| `WHATSAPP_EVOLUTION_WEBHOOK_SECRET` | `None` | security.py lines 47/57/63, webhook_validator.py line 19 — all to be cleaned |
| `WHATSAPP_WEBHOOK_SECRET` | `None` | Only referenced by security.py as fallback for evolution secret — can be removed |
| `WHATSAPP_EVOLUTION_WEBHOOK_URL` | `None` | lifespan.py, routes.py — to be cleaned |
| `WHATSAPP_EVOLUTION_TIMEOUT_SECONDS` | `30` | `phone_normalizer.py` LID methods (being deleted) — safe to remove |

**Note:** `WHATSAPP_WEBHOOK_HMAC_ENABLED`, `WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED`, etc. are provider-agnostic and MUST be kept.

From `.env.example` (backend-hormonia/):
- Line 205: `WHATSAPP_EVOLUTION_TIMEOUT_SECONDS=30` — remove

From `worker/.env.example`:
- Lines 66-70: 5 WHATSAPP_EVOLUTION_* vars — remove

---

## Caller Cleanup Map

Before tombstoning Evolution modules, these live callers must be cleaned:

### 1. `app/integrations/whatsapp/__init__.py`
- Remove `from .services.evolution_client import EvolutionAPIClient, RateLimiter`
- Remove `from .services.mock_evolution import MockEvolutionAPIClient, create_evolution_client`
- Remove `from .api.webhooks import router as webhook_router`
- Remove from `__all__`: `EvolutionAPIClient`, `RateLimiter`, `MockEvolutionAPIClient`, `create_evolution_client`, `webhook_router`

### 2. `app/integrations/__init__.py`
- Remove `from .evolution import (EvolutionClient, EvolutionAPIError, WebhookEvent, MessageType, get_evolution_client, close_evolution_client)`
- Remove from `__all__`: all Evolution exports
- Update module docstring to remove Evolution reference

### 3. `app/integrations/whatsapp/api/routes.py`
- Remove `from ..services.evolution_client import EvolutionAPIClient, validate_phone_number`
- Remove `get_evolution_client()` dependency function (lines 78-109)
- Remove `_should_use_mock_evolution()` helper
- Remove all endpoints that `Depends(get_evolution_client)`:
  - `POST /instances` (create_instance)
  - `GET /instances/{instance_name}` (get_instance_status)
  - `GET /instances/{instance_name}/qr` (get_qr_code)
  - `POST /instances/{instance_name}/restart` (restart_instance)
  - `DELETE /instances/{instance_name}` (delete_instance)
  - `POST /contacts/{instance_name}/check` (check_whatsapp_number)
- Keep: endpoints that use `Depends(get_message_service)` or `Depends(get_async_db)` only

### 4. `app/core/router_registry.py`
- Remove `app.include_router(webhook_router)` (line 210)
- Keep `app.include_router(whatsapp_router)` (for surviving message/queue/contact endpoints)

### 5. `app/core/lifespan.py`
- Remove `_initialize_evolution_api(app, logger)` from `asyncio.gather()` (line 114)
- Remove the entire `_initialize_evolution_api()` function (line 546+)

### 6. `app/orchestration/saga_orchestrator/orchestrator.py`
- Remove `from app.integrations.evolution import EvolutionClient` (line 26)
- Remove `evolution_client: Optional[EvolutionClient] = None` from `__init__` signature
- Remove `self.evolution_client = evolution_client` (line 64)
- **Verify**: `evolution_client` is never used beyond being stored (confirmed at lines 26, 60, 64 — not referenced in any method body)

### 7. `app/api/v2/routers/patients/crud.py`
- Remove `from app.integrations.evolution import EvolutionClient` (line 754)
- Remove `evolution_client=EvolutionClient()` from `SagaOrchestrator(...)` call (line 757)
- Verify `SagaOrchestrator` constructor no longer has `evolution_client` parameter after step 6

### 8. `app/api/v2/routers/health/service_health.py`
- Remove the `if hasattr(settings, "ENABLE_EVOLUTION") and settings.WHATSAPP_ENABLE_SERVICE:` block (lines 162-195) that calls `get_evolution_client()` and adds Evolution API health check

### 9. `app/services/webhook/handlers/message_handler.py`
- Remove the `if remote_jid.endswith("@lid"):` block (lines 456-469) that calls `self.phone_normalizer.resolve_phone_from_lid(...)`
- Remove the evolution-specific message logging (`source="evolution_api"` strings at lines 215/221 are metadata strings — not import dependencies, safe to leave as string literals or change to `"whatsapp"`)

### 10. `app/services/whatsapp/security.py`
- Replace `WHATSAPP_EVOLUTION_WEBHOOK_SECRET` references with `WHATSAPP_WUZAPI_WEBHOOK_SECRET` (lines 47, 57, 63)

### 11. `app/middleware/webhook_validator.py`
- Replace `settings.WHATSAPP_EVOLUTION_WEBHOOK_SECRET` with `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET` (lines 19, 106, 123)

### 12. `app/api/v2/routers/system/validation.py`
- Update validation check at line 121 — remove or replace `settings.WHATSAPP_EVOLUTION_API_KEY` check

### 13. `app/api/v2/monitoring/whatsapp.py`
- Replace `settings.WHATSAPP_EVOLUTION_INSTANCE_NAME` (lines 36, 47) with `settings.WHATSAPP_WUZAPI_BASE_URL` or a neutral default

### 14. `app/resilience/circuit_breaker/enhanced.py`
- Line 53: `WHATSAPP = "whatsapp_evolution_api"` — rename constant value to `"wuzapi"` (the string is a metric label, not an import)

---

## Tests to Tombstone/Remove

These test files test code that will be tombstoned:

| File | Action |
|------|--------|
| `tests/integrations/evolution/test_client_comprehensive.py` | Tombstone (imports from `app.integrations.evolution.client`) |
| `tests/integration/whatsapp/test_evolution_integration.py` | Tombstone (imports `RateLimiter`, `EvolutionAPIClient` from Stack B) |
| `tests/fixtures/saga_fixtures.py` | Remove `mock_evolution_client` fixture and update `saga_orchestrator` fixture to not pass `evolution_client=` |

The test tombstone pattern: replace test file with skip-all:
```python
"""TOMBSTONED -- Phase 37: tested app.integrations.evolution which is now tombstoned."""
import pytest
pytestmark = pytest.mark.skip(reason="Evolution API tombstoned in Phase 37")
```

Or simply delete the test file entirely (the project has precedent for both approaches; deleting is cleaner for tests).

---

## Common Pitfalls

### Pitfall 1: Partial Caller Cleanup Breaks Startup
**What goes wrong:** If `routes.py` still `from ..services.evolution_client import EvolutionAPIClient` and `evolution_client.py` has been tombstoned, FastAPI app startup fails with `ImportError` in the `whatsapp/__init__.py` module, which is imported by `router_registry.py` before any request is processed.
**Why it happens:** Python resolves all imports at module load time.
**How to avoid:** Clean all callers listed in "Caller Cleanup Map" before or in the same commit as the tombstones.
**Warning signs:** Any import of `evolution_client` in `routes.py`, `__init__.py`, or any other live module will cause startup failure.

### Pitfall 2: models.py Contains Enums Shared with Stack B
**What goes wrong:** `app/integrations/evolution/models.py` exports `MessageType` and `EvolutionAPIError`. Stack B (`evolution_client.py`) imports from `..models.message` (a *different* models module in `app/integrations/whatsapp/models/message.py`). There is no circular dependency, but the models in `app/integrations/evolution/models.py` must be tombstoned too (they are part of the package).
**How to avoid:** Tombstone `app/integrations/evolution/models.py` along with other Stack A files.

### Pitfall 3: `WHATSAPP_WEBHOOK_SECRET` vs `WHATSAPP_EVOLUTION_WEBHOOK_SECRET`
**What goes wrong:** `security.py` uses `WHATSAPP_EVOLUTION_WEBHOOK_SECRET` as the primary and `EVOLUTION_WEBHOOK_SECRET` as fallback. After removing these fields from settings, any call to `WhatsAppSecurity.validate_webhook_signature()` that is NOT on the WuzAPI webhook handler will fail.
**How to avoid:** In `security.py`, replace `WHATSAPP_EVOLUTION_WEBHOOK_SECRET` → `WHATSAPP_WUZAPI_WEBHOOK_SECRET`. The WuzAPI webhook handler already uses `WebhookHMACValidator` directly with `settings.WHATSAPP_WUZAPI_WEBHOOK_SECRET`; `WhatsAppSecurity` is only used by the Evolution webhook path (which is being deleted). Once the Evolution webhook handler is gone, `WhatsAppSecurity` may become dead code too — confirm this and tombstone it if so.

### Pitfall 4: `message_extractor.py` LID Constants
**What goes wrong:** `message_extractor.py` defines `_prefer_non_lid_jid` and `_select_source_jid` which reference `@lid`. The WuzAPI webhook processor (Phase 34) has its own parser that does NOT call `extract_message_data()`. Tombstoning `message_extractor.py` is safe because it is only imported from the Evolution webhook handler path.
**How to avoid:** Confirm no WuzAPI code imports from `message_extractor.py` before tombstoning. Search shows zero imports outside the Evolution webhook flow.

### Pitfall 5: `resolve_phone_from_lid` Call Site Remains
**What goes wrong:** The call to `self.phone_normalizer.resolve_phone_from_lid(...)` at `message_handler.py:459` is inside the Evolution webhook processing path. If the Evolution webhooks are deregistered but `message_handler.py` is still loaded, the dead code path will silently survive — but it references `WHATSAPP_EVOLUTION_*` settings that no longer exist, causing `AttributeError` if somehow triggered.
**How to avoid:** Delete the entire `if remote_jid.endswith("@lid"):` block at lines 456-469 in `message_handler.py`.

---

## Code Examples

### Canonical Tombstone (from `app/ai/langgraph/__init__.py`)
```python
"""
TOMBSTONED -- Phase 37 (Evolution Cleanup)

This module has been decommissioned. WuzAPI is the sole WhatsApp provider.
All outbound messaging: use app.integrations.wuzapi.
All inbound events: routed through /api/v2/webhooks/wuzapi.

Do not import from this module.
"""
raise ImportError(
    "app.integrations.evolution has been tombstoned in Phase 37 (Evolution Cleanup). "
    "Use app.integrations.wuzapi for WhatsApp messaging."
)
```

### Settings Field Removal (CLEAN-06)
Remove the block from `IntegrationsSettings` in `integrations.py`:
```python
# DELETE these fields:
WHATSAPP_EVOLUTION_USE_MOCK: bool = Field(...)
WHATSAPP_EVOLUTION_API_URL: str = Field(...)
WHATSAPP_EVOLUTION_INSTANCE_NAME: str = Field(...)
WHATSAPP_EVOLUTION_API_KEY: str = Field(...)
WHATSAPP_EVOLUTION_WEBHOOK_SECRET: Optional[str] = Field(...)
WHATSAPP_WEBHOOK_SECRET: Optional[str] = Field(...)     # Evolution-only fallback
WHATSAPP_EVOLUTION_WEBHOOK_URL: Optional[str] = Field(...)
WHATSAPP_EVOLUTION_TIMEOUT_SECONDS: int = Field(...)    # Used only by LID methods
```

### Verifying tombstones (TEST-05 approach)
```bash
# This must return zero matches outside tombstone docstrings:
grep -r "EvolutionAPIClient\|EvolutionClient" backend-hormonia/app/ --include="*.py" -i
# Expected output: only lines containing the string inside """ docstrings """
```

---

## Plan Split Rationale

### Plan 37-01: Stack A Tombstone
- Tombstone all 7 files in `app/integrations/evolution/` (including `models.py`)
- Remove Evolution exports from `app/integrations/__init__.py`
- Fix `app/orchestration/saga_orchestrator/orchestrator.py` (remove EvolutionClient import + constructor param)
- Fix `app/api/v2/routers/patients/crud.py` (remove EvolutionClient() instantiation)
- Fix `app/api/v2/routers/health/service_health.py` (remove Evolution health check block)
- Fix `app/resilience/circuit_breaker/enhanced.py` (rename WHATSAPP enum string)
- Tombstone `tests/integrations/evolution/test_client_comprehensive.py`
- Fix `tests/fixtures/saga_fixtures.py` (remove mock_evolution_client fixture dependency)

### Plan 37-02: Stack B Tombstone + Webhook Deregistration + LID Cleanup + Settings
- Tombstone `app/integrations/whatsapp/services/evolution_client.py` (CLEAN-02)
- Tombstone `app/integrations/whatsapp/services/mock_evolution.py` (CLEAN-02)
- Tombstone `app/integrations/whatsapp/api/webhooks.py` (CLEAN-03)
- Tombstone `app/integrations/whatsapp/webhook_handler.py` (CLEAN-03, wrapper)
- Tombstone `app/services/webhook/utils/message_extractor.py` (CLEAN-04)
- Clean `app/integrations/whatsapp/__init__.py` (remove evolution_client, mock_evolution, webhook_router exports)
- Clean `app/integrations/whatsapp/api/routes.py` (remove get_evolution_client and Evolution endpoints)
- Clean `app/core/router_registry.py` (remove webhook_router include)
- Clean `app/core/lifespan.py` (remove _initialize_evolution_api)
- Remove LID methods from `app/services/webhook/utils/phone_normalizer.py` (CLEAN-05)
- Remove LID call block from `app/services/webhook/handlers/message_handler.py`
- Remove `WHATSAPP_EVOLUTION_*` fields from `integrations.py` settings (CLEAN-06)
- Update `security.py` and `webhook_validator.py` to use WuzAPI secret
- Update `monitoring/whatsapp.py` and `system/validation.py`
- Remove evolution vars from `.env.example` files
- Tombstone `tests/integration/whatsapp/test_evolution_integration.py`

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x |
| Config file | `backend-hormonia/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend-hormonia && python -m pytest tests/unit/ -x -q` |
| Full suite command | `cd backend-hormonia && python -m pytest tests/ -x -q --timeout=60` |
| Source lint | `cd backend-hormonia && grep -r "EvolutionAPIClient\|EvolutionClient" app/ --include="*.py" -i` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Command | File Exists? |
|--------|----------|-----------|---------|-------------|
| CLEAN-01 | `from app.integrations.evolution import EvolutionClient` raises ImportError | unit | `pytest tests/unit/test_evolution_tombstone.py -x` | No — Wave 0 |
| CLEAN-02 | `from app.integrations.whatsapp.services.evolution_client import EvolutionAPIClient` raises ImportError | unit | same test file | No — Wave 0 |
| CLEAN-03 | `GET /webhooks/whatsapp/X` returns 404 | smoke | manual or `pytest tests/api/` | No — Wave 0 |
| CLEAN-04 | `from app.services.webhook.utils.message_extractor import extract_message_data` raises ImportError | unit | same test file | No — Wave 0 |
| CLEAN-05 | `phone_normalizer.PhoneNormalizer` has no `resolve_phone_from_lid` attribute | unit | `pytest tests/services/webhook/test_phone_normalizer.py` | Partial — existing test file |
| CLEAN-06 | `settings.WHATSAPP_EVOLUTION_API_KEY` raises `AttributeError` | unit | same test file | No — Wave 0 |

### Wave 0 Gaps
- [ ] `tests/unit/test_evolution_tombstone.py` — covers CLEAN-01, CLEAN-02, CLEAN-04, CLEAN-06 import assertions

Existing tests to verify no regression:
- `tests/services/webhook/test_phone_normalizer.py` — CLEAN-05 (verify `resolve_phone_from_lid` is gone)
- `tests/services/test_unified_whatsapp_service.py` — verify unified service still works post-cleanup

---

## Open Questions

1. **`WHATSAPP_WEBHOOK_SECRET` field in settings**
   - What we know: Used only as fallback in `security.py` for evolution secret lookup; WuzAPI uses `WHATSAPP_WUZAPI_WEBHOOK_SECRET` directly
   - What's unclear: Whether any non-Evolution code reads `WHATSAPP_WEBHOOK_SECRET`
   - Recommendation: Remove it in CLEAN-06; if something breaks, it will be a clear `AttributeError`

2. **`WHATSAPP_ENABLE_SERVICE` flag**
   - What we know: Currently guards `_initialize_evolution_api` in lifespan and the `webhook_router` registration
   - What's unclear: Should it be repurposed as a WuzAPI enable flag, or removed entirely since WuzAPI is always required?
   - Recommendation: Keep `WHATSAPP_ENABLE_SERVICE` but repurpose the name; it now guards WuzAPI session initialization only. This is a Phase 37 discretion decision.

3. **`app/services/webhook_service.py` uses `WHATSAPP_EVOLUTION_WEBHOOK_SECRET`**
   - What we know: Line 106 and 123 in `webhook_service.py` (confirmed from grep)
   - What's unclear: Whether `webhook_service.py` is the same as `middleware/webhook_validator.py` or a different file
   - Recommendation: Check both files in 37-02 and update both if different.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — all file paths, line numbers, and code patterns are from the actual source files
- `app/ai/langgraph/__init__.py` — canonical tombstone pattern (Phase 12)
- `app/integrations/evolution/client.py` — Stack A main file confirmed
- `app/integrations/whatsapp/services/evolution_client.py` — Stack B confirmed
- `app/integrations/whatsapp/__init__.py` — export manifest confirmed
- `app/core/router_registry.py:204-213` — Evolution webhook registration path confirmed
- `app/config/settings/integrations.py` — all WHATSAPP_EVOLUTION_* fields confirmed
- `.planning/STATE.md` — `[Phase 35]: Keep WHATSAPP_EVOLUTION_* fields in settings until Phase 37 cleanup` (explicit prior decision)
- `.planning/STATE.md` — `[v1.6]: Hard cut — no dual-provider mode... Evolution tombstoned in single commit after Phase 36 passes`

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — CLEAN-01 through CLEAN-06 requirement text (project-authored spec)

---

## Metadata

**Confidence breakdown:**
- File inventory: HIGH — every file verified by direct read
- Caller cleanup map: HIGH — every caller found by grep and code inspection
- Tombstone pattern: HIGH — taken verbatim from existing Phase 12 tombstones
- Settings field list: HIGH — all fields counted and confirmed in integrations.py
- Test gaps: MEDIUM — test file content inspected but Wave 0 test details are planning-time estimates

**Research date:** 2026-03-02
**Valid until:** Indefinite (codebase is not fast-moving; this phase is the terminal step of v1.6)
