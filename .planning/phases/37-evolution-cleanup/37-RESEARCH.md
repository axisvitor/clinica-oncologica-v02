# Phase 37: Evolution Cleanup - Research

**Researched:** 2026-03-02 (gap-closure re-research)
**Domain:** Python dead-code tombstoning, FastAPI router deregistration, pydantic settings cleanup
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLEAN-01 | Stack A tombstoned: `app/integrations/evolution/` (client, message_sender, request_handler, webhook_handler, rate_limiter, validators) converted to ImportError sentinels | Tombstones exist (37-01); blocked only by runtime import in `message_handler.py:1065` |
| CLEAN-02 | Stack B tombstoned: `app/integrations/whatsapp/services/evolution_client.py` and `mock_evolution.py` converted to ImportError sentinels | Tombstones exist (37-02); blocked only by top-level import of `EvolutionAPIError` in `queue/manager.py:19` |
| CLEAN-03 | Evolution webhook handler tombstoned: `app/integrations/whatsapp/api/webhooks.py` deregistered from router | Tombstone exists (37-02); blocked by `api/__init__.py:6` still importing it + 2 test files importing the tombstoned module |
| CLEAN-04 | Evolution message extractor tombstoned: `app/services/webhook/utils/message_extractor.py` | SATISFIED — tombstoned, zero active handler usage |
| CLEAN-05 | LID resolution methods removed from `phone_normalizer.py` | SATISFIED — confirmed removed |
| CLEAN-06 | `WHATSAPP_EVOLUTION_*` env vars removed from settings and `.env.example` | SATISFIED — confirmed removed (37-03) |
</phase_requirements>

---

## Summary

### Original Research Context (preserved)

Phase 37 is a tombstone-and-prune operation converting all Evolution API code to `ImportError` sentinels. Plans 37-01 and 37-02 completed the bulk of the work (tombstoning all Stack A/B files, webhook handlers, message extractor, LID resolution, env vars). Plan 37-03 closed a second round of gaps (canonical phone validator import in `message_service.py`, residual WHATSAPP_EVOLUTION settings, production env template).

The project's tombstone pattern is established across 20+ modules: module-level docstring + `raise ImportError(...)` as the first executable line. This pattern has been used in Phase 12 (LangGraph), Phase 16 (dead code), Phase 37-01/02 (Evolution Stack A/B).

After 37-03, three gaps remain. All tombstone files exist. The three gaps are all caller-side: active runtime code that still imports from already-tombstoned modules.

**Primary recommendation for gap-closure plan 37-04:** Three file edits — no new tombstones required. All three fixes are caller-side removals/replacements. Two test files also need tombstoning.

---

## Gap Closure Re-Research: 3 Specific Gaps

### Gap 1 — Stack A runtime import (CLEAN-01 blocked)

**File:** `backend-hormonia/app/services/webhook/handlers/message_handler.py`
**Lines:** 1065–1091 (within `_send_unauthorized_response` method, lines 1054–1099)

#### Current code (exact, verified):

```python
    async def _send_unauthorized_response(
        self, phone: str, attempt_count: int = 1
    ) -> None:
        """
        Send escalating unauthorized messages to non-registered numbers.

        Args:
            phone: Phone number
            attempt_count: Number of attempts (1-3)
        """
        try:
            from app.integrations.evolution import get_evolution_client   # LINE 1065 -- TOMBSTONED

            client = await get_evolution_client()                          # LINE 1067
            if not client:
                logger.warning("Evolution client unavailable")
                return

            # Escalating messages based on attempt count
            messages = {
                1: (
                    "Olá! Este número não está cadastrado no sistema de acompanhamento da clínica. "
                    "Para informações sobre cadastro, entre em contato com a recepção pelos telefones oficiais."
                ),
                2: (
                    "ATENÇÃO: Este número não tem autorização para acessar o sistema da clínica. "
                    "Se você é paciente, verifique se está usando o número correto cadastrado."
                ),
                3: (
                    "ALERTA DE SEGURANÇA: Múltiplas tentativas de acesso não autorizado detectadas. "
                    "Este número será temporariamente bloqueado."
                ),
            }

            message = messages.get(attempt_count, messages[3])
            delay = min(1000 * attempt_count, 5000)

            await client.send_text_message(phone, message, delay=delay)   # LINE 1091

            logger.info(
                f"Sent unauthorized response (attempt #{attempt_count})",
                extra={"phone": phone[:6] + "****", "attempt": attempt_count},
            )

        except Exception as e:
            logger.error(f"Failed to send unauthorized response: {e}")
```

#### Only caller:
Line 495: `await self._send_unauthorized_response(message_data["phone"], attempt_count)`

The caller is in the active (WuzAPI-compatible) webhook processing path.

#### Additional Evolution references in this file (non-blocking, string literals):
- Line 2: module docstring mentions "Evolution API integration" — safe to leave or update
- Line 94: comment "Standalone opt-out handler for any webhook endpoint (WuzAPI, Evolution, etc.)"
- Line 157: class docstring "Handler for incoming message webhooks from Evolution API"
- Line 196: method docstring "Process incoming message webhook from Evolution API"
- Lines 214, 220: `source="evolution_api"` string literals — NOT import dependencies
- Line 440: comment "Evolution official payload can include remoteJidAlt for LID addressed chats"

None of the above are import dependencies. Only lines 1065–1091 are the actual blocker.

#### WuzAPI replacement:

The WuzAPI client is at `app.integrations.wuzapi` with `get_wuzapi_client(base_url, token)`. The send method is `send_text(phone: str, message: str) -> dict`. There is no `delay` parameter in WuzAPI's `send_text` — the delay concept was Evolution-specific.

The recommended fix is to replace the Evolution client call with a direct WuzAPI `send_text` call using the same settings pattern used in `unified_whatsapp_service.py:_get_wuzapi_client()`:

```python
    async def _send_unauthorized_response(
        self, phone: str, attempt_count: int = 1
    ) -> None:
        """
        Send escalating unauthorized messages to non-registered numbers.

        Args:
            phone: Phone number
            attempt_count: Number of attempts (1-3)
        """
        try:
            from app.integrations.wuzapi import get_wuzapi_client

            token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
            if not token:
                logger.warning("WuzAPI not configured, skipping unauthorized response")
                return

            base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
            client = get_wuzapi_client(base_url=base_url, token=token)

            # Escalating messages based on attempt count
            messages = {
                1: (
                    "Olá! Este número não está cadastrado no sistema de acompanhamento da clínica. "
                    "Para informações sobre cadastro, entre em contato com a recepção pelos telefones oficiais."
                ),
                2: (
                    "ATENÇÃO: Este número não tem autorização para acessar o sistema da clínica. "
                    "Se você é paciente, verifique se está usando o número correto cadastrado."
                ),
                3: (
                    "ALERTA DE SEGURANÇA: Múltiplas tentativas de acesso não autorizado detectadas. "
                    "Este número será temporariamente bloqueado."
                ),
            }

            message = messages.get(attempt_count, messages[3])

            await client.send_text(phone, message)

            logger.info(
                f"Sent unauthorized response (attempt #{attempt_count})",
                extra={"phone": phone[:6] + "****", "attempt": attempt_count},
            )

        except Exception as e:
            logger.error(f"Failed to send unauthorized response: {e}")
```

**Rationale:** The lazy import pattern is acceptable here because this method has a broad `except Exception` guard — any failure including import errors is already swallowed. However, changing to WuzAPI import is cleaner. The `delay` parameter is dropped because WuzAPI's `send_text` has no delay support; at the volume of unauthorized responses this is not significant. The `client.connect()` step is NOT called here (unlike `_get_wuzapi_client()` in UnifiedWhatsAppService) because `connect()` establishes a WuzAPI session and this is an outbound-only ephemeral call — WuzAPI session is managed globally by the startup lifespan.

**Alternative (simpler):** Disable the unauthorized response path entirely by making the method a no-op with a log. The function is defensive messaging for non-patients; the clinic may prefer to simply not respond to unauthorized numbers rather than send potentially confusing messages via a newly configured provider. The planner should decide between:
1. Replace with WuzAPI send_text (preserves behavior)
2. Disable with logger.warning only (removes behavior, simpler, safer)

---

### Gap 2 — Stack B runtime import (CLEAN-02 blocked)

**File:** `backend-hormonia/app/integrations/whatsapp/queue/manager.py`
**Line:** 19 (top-level import)

#### Current code (exact, verified):

```python
# Line 19 (top-level, module load time):
from app.integrations.whatsapp.services.evolution_client import EvolutionAPIError
```

#### Where it is used (exact, verified):

```python
# Lines 486-489 in _categorize_failure():
    def _categorize_failure(self, error: Exception) -> FailureReason:
        """Categorize failures for DLQ routing."""
        if isinstance(error, asyncio.TimeoutError):
            return FailureReason.TIMEOUT
        if isinstance(error, ValueError) and "phone" in str(error).lower():
            return FailureReason.INVALID_PHONE
        if isinstance(error, EvolutionAPIError) and error.status == 429:  # LINE 486
            return FailureReason.RATE_LIMIT
        if isinstance(error, EvolutionAPIError):                           # LINE 488
            return FailureReason.API_ERROR
        if "rate" in str(error).lower() and "limit" in str(error).lower():
            return FailureReason.RATE_LIMIT
        return FailureReason.API_ERROR
```

#### WuzAPI replacement:

`WuzAPIError` is the direct replacement. It lives at `app.integrations.wuzapi.errors` and is exported from `app.integrations.wuzapi`. It has the same `status` attribute (`status: int | None`). The structure is identical:

```python
# WuzAPIError (from app/integrations/wuzapi/errors.py):
class WuzAPIError(Exception):
    def __init__(self, message: str, status: int | None = None, response: dict | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.response = response
```

**Fix — two changes in manager.py:**

1. Replace line 19 import:
   ```python
   # REMOVE:
   from app.integrations.whatsapp.services.evolution_client import EvolutionAPIError
   # ADD:
   from app.integrations.wuzapi.errors import WuzAPIError
   ```

2. Replace lines 486–489 in `_categorize_failure`:
   ```python
   # REMOVE:
   if isinstance(error, EvolutionAPIError) and error.status == 429:
       return FailureReason.RATE_LIMIT
   if isinstance(error, EvolutionAPIError):
       return FailureReason.API_ERROR
   # ADD:
   if isinstance(error, WuzAPIError) and error.status == 429:
       return FailureReason.RATE_LIMIT
   if isinstance(error, WuzAPIError):
       return FailureReason.API_ERROR
   ```

#### Additional Evolution references in this file (non-blocking):
- Line 4: module docstring "delivery to Evolution instances"
- Line 35: class docstring "Multi-instance Evolution support"
- Line 52: constructor docstring "Default Evolution instance name"

These are string comments only — no import dependency. Safe to update as part of cleanup but not blocking.

---

### Gap 3 — Webhook deregistration incomplete (CLEAN-03 blocked)

**File:** `backend-hormonia/app/integrations/whatsapp/api/__init__.py`
**Lines:** 1–8 (entire file, only 8 lines)

#### Current code (exact, verified):

```python
"""
WhatsApp API package
"""

from .routes import router as whatsapp_router
from .webhooks import router as webhook_router        # LINE 6 -- TOMBSTONED

__all__ = ["whatsapp_router", "webhook_router"]       # LINE 8
```

#### Why this breaks the import chain:

When Python imports `app.integrations.whatsapp` (triggered from `router_registry.py:207` and `app/api/v2/router.py:54`), the following chain runs:

1. `from app.integrations.whatsapp import whatsapp_router` (or `from app.integrations.whatsapp.api.routes import router`)
2. Python initializes `app.integrations.whatsapp.api` package → executes `api/__init__.py`
3. `api/__init__.py` line 6: `from .webhooks import router as webhook_router`
4. `webhooks.py` is tombstoned → raises `ImportError`
5. App startup fails

#### Consumers of `webhook_router` from `api/__init__.py`:

None found. `grep -r "webhook_router"` across `backend-hormonia/app/` shows ZERO consumers outside of `api/__init__.py` itself. The `webhook_router` exported here was previously consumed by `router_registry.py` (removed in 37-02) and possibly `whatsapp/__init__.py` (removed in 37-02).

#### Fix — two changes in `api/__init__.py`:

```python
# BEFORE (entire file):
"""
WhatsApp API package
"""

from .routes import router as whatsapp_router
from .webhooks import router as webhook_router

__all__ = ["whatsapp_router", "webhook_router"]

# AFTER:
"""
WhatsApp API package
"""

from .routes import router as whatsapp_router

__all__ = ["whatsapp_router"]
```

#### Test files that also import the tombstoned `webhooks` module:

Two test files import `from app.integrations.whatsapp.api import webhooks as webhook_module`:

1. `backend-hormonia/tests/integration/whatsapp/test_webhook_scenarios.py` (line 19)
2. `backend-hormonia/tests/integration/whatsapp/test_webhook_fail_closed_and_queue_batch.py` (line 13)

These tests will also fail with ImportError when the package init is fixed (because they import the tombstoned `webhooks` module directly). Both must be tombstoned using the standard test tombstone pattern:

```python
"""TOMBSTONED -- Phase 37: tested app.integrations.whatsapp.api.webhooks which is now tombstoned."""
import pytest
pytestmark = pytest.mark.skip(reason="Evolution webhook API tombstoned in Phase 37")
```

---

## Gap Closure Map

| Gap | File | Lines | Action | Replacement |
|-----|------|-------|--------|-------------|
| 1 (CLEAN-01) | `app/services/webhook/handlers/message_handler.py` | 1065–1091 | Replace import+call | `get_wuzapi_client` + `send_text()` OR disable (log only) |
| 2 (CLEAN-02) | `app/integrations/whatsapp/queue/manager.py` | 19, 486–489 | Replace import+isinstance checks | `WuzAPIError` from `app.integrations.wuzapi.errors` |
| 3 (CLEAN-03) | `app/integrations/whatsapp/api/__init__.py` | 6, 8 | Remove import+export | Nothing (line deletion only) |
| 3 (CLEAN-03) test | `tests/integration/whatsapp/test_webhook_scenarios.py` | whole file | Tombstone | Standard skip pattern |
| 3 (CLEAN-03) test | `tests/integration/whatsapp/test_webhook_fail_closed_and_queue_batch.py` | whole file | Tombstone | Standard skip pattern |

**Total files to touch:** 5 (3 source + 2 tests)
**New tombstone files:** 0 (all existing tombstones are correct)
**New source files:** 0

---

## Standard Stack

### Core (already in project)
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `raise ImportError(...)` | stdlib | Module-level tombstone sentinel | Zero dependencies; fails fast at import time |
| `WuzAPIError` | project | Provider-agnostic WhatsApp error | Replaces `EvolutionAPIError`; identical `status` attribute |
| `get_wuzapi_client` | project | WuzAPI client factory | Same pattern used by `unified_whatsapp_service.py` |
| `pytest.mark.skip` | 7.x | Test tombstone pattern | Established in project for dead-code tests |

---

## Architecture Patterns

### Tombstone Pattern (established in project)

All tombstoned modules follow exactly this structure:

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

### WuzAPI Client Instantiation Pattern (from `unified_whatsapp_service.py:203-215`)

```python
from app.integrations.wuzapi import get_wuzapi_client

token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
if not token:
    # handle missing config
    return
base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
client = get_wuzapi_client(base_url=base_url, token=token)
response = await client.send_text(phone, message)
```

Note: `client.connect()` is used in `UnifiedWhatsAppService` because it manages a persistent session. For the short-lived unauthorized response path in `message_handler.py`, `connect()` is NOT needed — the WuzAPI session is already established by the app startup lifespan.

### Test Tombstone Pattern (established in project)

```python
"""TOMBSTONED -- Phase 37: tested app.integrations.whatsapp.api.webhooks which is now tombstoned."""
import pytest
pytestmark = pytest.mark.skip(reason="Evolution webhook API tombstoned in Phase 37")
```

---

## Common Pitfalls

### Pitfall 1: `send_text_message` vs `send_text`

Evolution client method was `send_text_message(phone, message, delay=delay)`. WuzAPI client method is `send_text(phone, message)` (no `delay` parameter). The planner must NOT pass `delay=delay` to `send_text`.

### Pitfall 2: `client.connect()` in unauthorized response path

`UnifiedWhatsAppService._get_wuzapi_client()` calls `await self._wuzapi_client.connect()` because it manages a long-lived client instance. In `message_handler._send_unauthorized_response`, we create a new ephemeral client — calling `connect()` here would attempt a new WuzAPI session registration, which is unnecessary. The WuzAPI session is already managed by the startup lifespan. The `send_text` call works via aiohttp directly to the already-running WuzAPI server.

### Pitfall 3: `api/__init__.py` fix is NOT sufficient without also tombstoning the test files

After fixing `api/__init__.py`, running `pytest tests/integration/whatsapp/test_webhook_scenarios.py` will still fail because that test file does `from app.integrations.whatsapp.api import webhooks as webhook_module`, which hits the tombstone directly (bypassing `__init__.py`). Both test files must be tombstoned as part of the same plan.

### Pitfall 4: `EvolutionAPIError` isinstance checks use `error.status`

`EvolutionAPIError.status` is an integer field. `WuzAPIError.status` is also `int | None`. The replacement `isinstance(error, WuzAPIError) and error.status == 429` is semantically identical. No attribute mapping needed.

### Pitfall 5: Module docstrings mention "Evolution" — these are NOT blockers

`message_handler.py` docstring says "Message webhook handler for Evolution API integration". These string literals in docstrings/comments are not import dependencies and do not cause ImportError. They should be updated as courtesy cleanup but must NOT be confused with the actual blocker (line 1065 import).

---

## Code Examples

### Gap 1 complete replacement (Option A — WuzAPI send):

```python
    async def _send_unauthorized_response(
        self, phone: str, attempt_count: int = 1
    ) -> None:
        """
        Send escalating unauthorized messages to non-registered numbers.

        Args:
            phone: Phone number
            attempt_count: Number of attempts (1-3)
        """
        try:
            from app.integrations.wuzapi import get_wuzapi_client

            token = getattr(settings, "WHATSAPP_WUZAPI_TOKEN", None)
            if not token:
                logger.warning("WuzAPI not configured, skipping unauthorized response")
                return

            base_url = getattr(settings, "WHATSAPP_WUZAPI_BASE_URL", "")
            client = get_wuzapi_client(base_url=base_url, token=token)

            messages = {
                1: (
                    "Olá! Este número não está cadastrado no sistema de acompanhamento da clínica. "
                    "Para informações sobre cadastro, entre em contato com a recepção pelos telefones oficiais."
                ),
                2: (
                    "ATENÇÃO: Este número não tem autorização para acessar o sistema da clínica. "
                    "Se você é paciente, verifique se está usando o número correto cadastrado."
                ),
                3: (
                    "ALERTA DE SEGURANÇA: Múltiplas tentativas de acesso não autorizado detectadas. "
                    "Este número será temporariamente bloqueado."
                ),
            }

            message = messages.get(attempt_count, messages[3])
            await client.send_text(phone, message)

            logger.info(
                f"Sent unauthorized response (attempt #{attempt_count})",
                extra={"phone": phone[:6] + "****", "attempt": attempt_count},
            )

        except Exception as e:
            logger.error(f"Failed to send unauthorized response: {e}")
```

### Gap 1 complete replacement (Option B — disable flow):

```python
    async def _send_unauthorized_response(
        self, phone: str, attempt_count: int = 1
    ) -> None:
        """
        Unauthorized response disabled — Evolution API removed in Phase 37.

        WuzAPI outbound responses to non-registered numbers are not implemented.
        Unauthorized access attempts are logged only.
        """
        logger.warning(
            "Unauthorized response skipped (Evolution removed, WuzAPI response not configured)",
            extra={"phone": phone[:6] + "****", "attempt": attempt_count},
        )
```

### Gap 2 complete fix (manager.py):

```python
# Line 19 — replace:
from app.integrations.wuzapi.errors import WuzAPIError

# Lines 486-489 in _categorize_failure() — replace:
        if isinstance(error, WuzAPIError) and error.status == 429:
            return FailureReason.RATE_LIMIT
        if isinstance(error, WuzAPIError):
            return FailureReason.API_ERROR
```

### Gap 3 complete fix (api/__init__.py — entire file after edit):

```python
"""
WhatsApp API package
"""

from .routes import router as whatsapp_router

__all__ = ["whatsapp_router"]
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x |
| Config file | `backend-hormonia/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend-hormonia && python -m pytest tests/unit/ -x -q` |
| Boot check | `cd backend-hormonia && TESTING=1 WHATSAPP_WUZAPI_TOKEN=dummy python3 -c "from app.main import app; print(app.title)"` |
| Import check | `cd backend-hormonia && python -c "from app.integrations.whatsapp.api import whatsapp_router; print('OK')"` |

### Phase Requirements → Test Map (gap-closure specific)

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLEAN-01 | `message_handler.py` imports cleanly without Evolution import | smoke | `python -c "from app.services.webhook.handlers.message_handler import MessageHandler; print('OK')"` | implicit |
| CLEAN-02 | `queue/manager.py` imports cleanly without Evolution import | smoke | `python -c "from app.integrations.whatsapp.queue.manager import QueueManager; print('OK')"` | implicit |
| CLEAN-03 | `from app.integrations.whatsapp.api import whatsapp_router` succeeds | smoke | `python -c "from app.integrations.whatsapp.api import whatsapp_router; print('OK')"` | implicit |
| CLEAN-03 | App boots without ImportError | smoke | `TESTING=1 WHATSAPP_WUZAPI_TOKEN=dummy python3 -c "from app.main import app; print(app.title)"` | implicit |

### Wave 0 Gaps
None — existing infrastructure is sufficient. All checks are import-level smoke tests runnable in < 5 seconds.

---

## Open Questions

1. **Gap 1 — WuzAPI send vs disable**
   - Should `_send_unauthorized_response` use WuzAPI to actually send the escalating messages, or should it be disabled (log only)?
   - WuzAPI send preserves existing behavior but adds a new outbound code path for this rarely-triggered function.
   - Disabling is simpler and safer; unauthorized responses were a defensive feature with no clinical impact.
   - **Recommendation:** Disable (Option B). The unauthorized response was an Evolution-era feature; re-implementing it for WuzAPI adds scope and testing surface for a non-critical function. Document it as deferred to a future story if needed.

2. **Docstring cleanup in `message_handler.py`**
   - Multiple docstrings and comments reference "Evolution API" and `source="evolution_api"` strings.
   - These are NOT blockers (no import dependency).
   - **Recommendation:** Update module docstring and class docstring to "WuzAPI" in the same plan for completeness, but keep as separate atomic edit clearly marked as "courtesy cleanup only."

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — all file paths, line numbers, and code patterns verified by reading actual source files
- `backend-hormonia/app/services/webhook/handlers/message_handler.py:1054-1099` — exact current code of `_send_unauthorized_response`
- `backend-hormonia/app/integrations/whatsapp/queue/manager.py:1-25, 480-492` — exact current code of import and `_categorize_failure`
- `backend-hormonia/app/integrations/whatsapp/api/__init__.py:1-8` — exact current 8-line file
- `backend-hormonia/app/integrations/wuzapi/errors.py` — WuzAPIError class structure confirmed
- `backend-hormonia/app/integrations/wuzapi/__init__.py` — `WuzAPIError` and `get_wuzapi_client` exports confirmed
- `backend-hormonia/app/integrations/wuzapi/client.py:177-179` — `send_text(phone, message)` signature confirmed
- `backend-hormonia/tests/integration/whatsapp/test_webhook_scenarios.py:19` — test import of tombstoned webhooks confirmed
- `backend-hormonia/tests/integration/whatsapp/test_webhook_fail_closed_and_queue_batch.py:13` — test import of tombstoned webhooks confirmed
- `.planning/phases/37-evolution-cleanup/37-VERIFICATION.md` — gap definitions confirmed
- `.planning/phases/37-evolution-cleanup/37-03-SUMMARY.md` — 37-03 scope confirmed (did NOT address these 3 gaps)

---

## Metadata

**Confidence breakdown:**
- Gap site identification: HIGH — every line number verified by direct file read
- WuzAPI replacement interface: HIGH — `send_text`, `WuzAPIError`, `get_wuzapi_client` verified from source
- Test file impact: HIGH — both test files confirmed by grep
- Import chain analysis: HIGH — `api/__init__.py` only 8 lines, import chain traced fully

**Research date:** 2026-03-02 (gap-closure re-research after 37-03)
**Valid until:** Indefinite (codebase is not fast-moving; no concurrent changes expected)
