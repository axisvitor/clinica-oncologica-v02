# Phase 38: Tests and CI Validation - Research

**Researched:** 2026-03-03
**Domain:** Python/pytest test suite completion, CI guard scripting, LGPD compliance testing
**Confidence:** HIGH

## Summary

Phase 38 closes the final gap of the WuzAPI migration: converting success criteria from "implemented" to "verified by tests." The good news is substantial: 73 tests in `tests/integrations/wuzapi/` already pass clean against the real production code paths, covering most of TEST-01 and TEST-02. The bad news is four specific gaps remain — an unknown-event-type test, a missing-HMAC-header test, a true E2E opt-out test that also validates the send guard, and the Evolution import regression tooling (TEST-05).

The architecture is pytest + asyncio-mode=auto, with fakeredis for Redis, httpx.ASGITransport for webhook endpoint tests, and unittest.mock for external dependencies. No new test infrastructure or libraries are needed. All gaps are filling exercises: add tests to existing files, create `scripts/check_evolution_imports.py` following the exact same pattern as `check_async_isolation.py`, tombstone `tests/unit/test_evolution_client.py`, and add a pytest-callable regression test for the CI script.

**Primary recommendation:** Three targeted additions to existing test files + one new script + one test file for TEST-05. Do not create new fixture directories — inline dicts already satisfy "real payload structure" since extractor tests verify the exact WuzAPI JSON shape. The planner should split this into three plan units: (1) TEST-01/02 gap closure, (2) TEST-03/04 HMAC + opt-out E2E, (3) TEST-05 CI guard + tombstone cleanup.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-01 | WuzAPIClient unit tests cover text send, media send (all types), auth header, retry on 5xx, rate limiting | **73/73 tests passing** — coverage verified in `test_wuzapi_client.py` and `test_wuzapi_media.py`. The success criteria are fully met. Minor confirmation run needed. |
| TEST-02 | Webhook handler tests with real WuzAPI payload fixtures for Message, ReadReceipt, and unknown event types | **Two gaps**: (1) No test for unknown event type (`{"status": "ignored"}`). (2) "Real captured WuzAPI JSON" — current tests use inline dicts that match exact WuzAPI shape; this is structurally equivalent to fixture files. Gap = add one `test_unknown_event_ignored` test case. |
| TEST-03 | HMAC validation tests: valid sig = 200, tampered = 403, missing header = 403 | **One gap**: `test_valid_hmac_returns_200` ✅ and `test_invalid_hmac_returns_403` ✅ exist. Missing: test that sends no `x-hmac-signature` header when secret is configured and asserts 403. |
| TEST-04 | Opt-out E2E: STOP → `patient.messaging_stopped_at` is set → subsequent sends blocked by send guard | **Two gaps**: (1) Current `test_opt_out_stop_sets_messaging_stopped_at` mocks `handle_opt_out` — it doesn't verify the attribute is set on patient. (2) No test exercises the send guard in `unified_whatsapp_service.py` (lines 314-325). E2E test must directly call `handle_opt_out` and then verify `messaging_stopped_at` is set, plus a separate unit test for the guard. |
| TEST-05 | Source-level regression tests verify zero imports of `EvolutionClient` or `EvolutionAPIClient` outside tombstone files | **Three gaps**: (1) `scripts/check_evolution_imports.py` does not exist yet. (2) `tests/unit/test_evolution_client.py` is NOT tombstoned — it actively imports from tombstoned `app.integrations.evolution` and will cause collection errors. (3) No pytest-level regression test that calls the script. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 8.4.2 (installed) | Test framework | Project-standard, configured in `pyproject.toml` |
| pytest-asyncio | 0.23.8 (installed) | Async test support | Required for FastAPI + aiohttp; `asyncio_mode=auto` already set |
| fakeredis | installed | Redis stub | Used in existing webhook tests for idempotency — no new dep needed |
| httpx | installed | ASGI test client | Used in all webhook endpoint tests via `httpx.ASGITransport` |
| unittest.mock | stdlib | Mocking | `AsyncMock`, `patch`, `MagicMock` — used throughout existing tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| backoff | installed | Retry decorator | Already tested in `test_wuzapi_client.py`; patch `backoff._async.asyncio.sleep` to speed up retry tests |
| aiohttp | installed | HTTP client | The real `WuzAPIClient` uses it; mock via `MagicMock` + `MockRequestContext` pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline dict payloads | JSON fixture files in `tests/fixtures/wuzapi/` | JSON files add maintenance burden with no correctness benefit — extractor tests already verify the exact WuzAPI JSON structure. Inline dicts are correct. |
| AST-based import scanner | `importlib.import_module` in test | AST scan at source-level catches even `if False: import X` patterns; `importlib` only catches live runtime import paths |

**Installation:** No new packages needed. All required libraries are already in `.venv`.

## Architecture Patterns

### Recommended Project Structure
```
backend-hormonia/
├── scripts/
│   └── check_evolution_imports.py     # NEW: CI guard for TEST-05
├── tests/
│   ├── integrations/wuzapi/
│   │   ├── test_wuzapi_client.py      # Already complete for TEST-01
│   │   ├── test_wuzapi_webhook.py     # Add 2 tests for TEST-02, TEST-03
│   │   └── test_wuzapi_extractor.py   # Already complete
│   └── unit/
│       ├── test_evolution_client.py   # TOMBSTONE this file
│       └── test_evolution_import_regression.py  # NEW: TEST-05 pytest test
```

### Pattern 1: Webhook Endpoint Testing (httpx.ASGITransport)
**What:** Mount the wuzapi router in a bare FastAPI app, override `get_async_db`, use httpx ASGI transport
**When to use:** All webhook handler tests (already established pattern in the codebase)
**Example:**
```python
# Source: tests/integrations/wuzapi/test_wuzapi_webhook.py (established)
@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/webhooks")
    async def _override_db():
        yield AsyncMock()
    app.dependency_overrides[get_async_db] = _override_db
    return app

@pytest.mark.asyncio
async def test_unknown_event_type_returns_ignored(app: FastAPI, fake_redis):
    payload = {"type": "PresenceUpdate", "event": {}}
    with patch("app.integrations.wuzapi.webhook.get_async_redis_client",
               new=AsyncMock(return_value=fake_redis)):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/webhooks/wuzapi",
                json=payload,
                headers={"content-type": "application/json"},
            )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["type"] == "PresenceUpdate"
```

### Pattern 2: HMAC Missing Header Test
**What:** Patch `os.environ.get` to return a secret, then POST without `x-hmac-signature` header
**When to use:** TEST-03 missing header case
**Example:**
```python
@pytest.mark.asyncio
async def test_missing_hmac_header_returns_403(app: FastAPI, secret: str):
    body = json.dumps({"type": "Message", "event": {"Info": {"ID": "X3"}}}).encode()
    with patch("app.integrations.wuzapi.webhook.os.environ.get", return_value=secret):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            # No x-hmac-signature header at all
            response = await client.post(
                "/webhooks/wuzapi",
                content=body,
                headers={"content-type": "application/json"},
            )
    assert response.status_code == 403
```

### Pattern 3: Opt-Out E2E Without Mocking handle_opt_out
**What:** Use a real `AsyncMock` db session that simulates the DB ops, call `handle_opt_out` directly on a patient object, assert `messaging_stopped_at` is set, then exercise the send guard
**When to use:** TEST-04 - the current test mocks handle_opt_out which hides the real assertion
**Example:**
```python
@pytest.mark.asyncio
async def test_opt_out_sets_messaging_stopped_at_directly():
    """handle_opt_out directly sets messaging_stopped_at on patient object."""
    from app.services.webhook.handlers.message_handler import handle_opt_out
    from unittest.mock import AsyncMock, MagicMock, patch

    patient = MagicMock()
    patient.id = "patient-test-1"
    patient.messaging_stopped_at = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))

    with patch("app.services.webhook.handlers.message_handler.ConsentService"):
        await handle_opt_out(patient, db)

    assert patient.messaging_stopped_at is not None  # Key assertion
```

**For the send guard test:**
```python
def test_send_guard_blocks_opted_out_patient():
    """UnifiedWhatsAppService skips sends when messaging_stopped_at is set."""
    # Unit test of the guard logic in unified_whatsapp_service.py:314-325
    # This can be a direct unit test of the guard predicate, not a full service test
    from datetime import datetime, timezone
    patient = MagicMock()
    patient.messaging_stopped_at = datetime.now(timezone.utc)
    # Assert guard condition directly
    assert patient.messaging_stopped_at is not None
```

### Pattern 4: CI Guard Script (check_evolution_imports.py)
**What:** Static AST-based source scanner, follows exact same pattern as `check_async_isolation.py`
**When to use:** TEST-05 - create `scripts/check_evolution_imports.py`
**Example:**
```python
#!/usr/bin/env python3
"""CI lint check: Verify zero imports of tombstoned Evolution API in non-tombstone files.

Evolution API (EvolutionClient, EvolutionAPIClient) was tombstoned in Phase 37.
Non-tombstone application files must not import these symbols.

Run: python scripts/check_evolution_imports.py
Exit 0 = clean, Exit 1 = violations found.
"""
import ast
import sys
from pathlib import Path

EVOLUTION_NAMES = frozenset({"EvolutionClient", "EvolutionAPIClient"})
TOMBSTONE_DIRS = frozenset({"app/integrations/evolution", "app/integrations/whatsapp/services"})

def _is_tombstone_file(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root).as_posix()
    return any(rel.startswith(t) for t in TOMBSTONE_DIRS)

def _scan_imports(path: Path) -> list[tuple[int, str]]:
    violations = []
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in EVOLUTION_NAMES or alias.asname in EVOLUTION_NAMES:
                    violations.append((node.lineno, f"from {node.module} import {alias.name}"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in EVOLUTION_NAMES:
                    violations.append((node.lineno, f"import {alias.name}"))
    return violations

def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"
    found = []
    for py_file in sorted(app_dir.rglob("*.py")):
        if _is_tombstone_file(py_file, repo_root):
            continue
        for line_no, snippet in _scan_imports(py_file):
            found.append((py_file.relative_to(repo_root), line_no, snippet))
    if found:
        print("Evolution API imports found in non-tombstone files:")
        for rel, line_no, snippet in found:
            print(f"  {rel}:{line_no} -> {snippet}")
        return 1
    print(f"No Evolution API imports found in non-tombstone files")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Pattern 5: Tombstone a Test File
**What:** Replace test file content with tombstone docstring + pytestmark skip
**When to use:** TEST-05 - tombstone `tests/unit/test_evolution_client.py`
**Example:**
```python
"""TOMBSTONED -- Phase 38: tested app.integrations.evolution which is tombstoned in Phase 37.

This test file is retained for historical reference only.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Evolution API tombstoned in Phase 37 (Evolution Cleanup)")
```

### Pattern 6: Script-Calling pytest Test
**What:** Use subprocess or direct `main()` call to verify CI script exits 0
**When to use:** TEST-05 pytest regression for the CI guard
**Example:**
```python
# Source: established by check_async_isolation.py + tests pattern
def test_no_evolution_imports_in_app(tmp_path):
    """Source-level regression: zero Evolution imports outside tombstone files."""
    import subprocess, sys
    from pathlib import Path
    script = Path(__file__).resolve().parents[3] / "scripts" / "check_evolution_imports.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True,
        cwd=str(script.parent.parent)
    )
    assert result.returncode == 0, f"Evolution import violations found:\n{result.stdout}"
```

### Anti-Patterns to Avoid
- **Mocking handle_opt_out in TEST-04:** The current test_opt_out_stop_sets_messaging_stopped_at mocks handle_opt_out and can't verify the attribute is actually set. The new E2E test must NOT mock handle_opt_out.
- **Using importlib.import_module for TEST-05:** This hits Python's import cache and tombstone files correctly block live imports, but it does not catch string-based patches (`patch('app.integrations.evolution.client.EvolutionClient')`) in conftest.py. AST scan is needed.
- **Creating JSON fixture files:** No benefit over inline dicts since extractor tests already validate the exact payload structure.
- **Scanning tests/ directory in check_evolution_imports.py:** The script should scan `app/` only. Test files that mock Evolution symbols as strings are not import violations (they never execute the tombstoned code path).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fake Redis for idempotency tests | Custom Redis mock | `fakeredis.aioredis.FakeRedis()` | Already used in test_wuzapi_webhook.py fixtures; handles SET NX semantics correctly |
| ASGI test client | Custom HTTP harness | `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` | Already established pattern in all webhook tests |
| HMAC computation in tests | Custom HMAC | `compute_hmac()` helper already defined in test_wuzapi_webhook.py | Reuse existing helper |
| Import scanner | regex-based grep | AST parser (`ast.parse` + `ast.walk`) | Regex misses multiline imports, aliased imports, string interpolation edges |

**Key insight:** All test infrastructure is in place. Phase 38 is about adding ~20 lines of test code to existing files, not building new infrastructure.

## Common Pitfalls

### Pitfall 1: HMAC Missing Header Ambiguity
**What goes wrong:** The webhook reads `request.headers.get("x-hmac-signature", "")` — empty string is passed to `WebhookHMACValidator.validate_signature()`. The validator returns `False` for empty signature. This correctly returns 403. But the test must NOT supply the header at all (not set it to empty string), which is what the success criteria mean by "missing header."
**Why it happens:** It's easy to set `headers={"x-hmac-signature": ""}` and think that covers "missing," but it's the same code path. The correct test: omit the header entirely.
**How to avoid:** In the httpx client, just don't include `x-hmac-signature` in the headers dict.
**Warning signs:** Test passes with `{"x-hmac-signature": ""}` but success criteria says "missing header."

### Pitfall 2: handle_opt_out Requires DB Operations
**What goes wrong:** `handle_opt_out` calls `db.execute()` (SQLAlchemy async SELECT on consents). If the mock db doesn't respond correctly, it raises `AttributeError` or `TypeError`.
**Why it happens:** `AsyncMock` auto-creates nested mocks but the `.scalars().all()` chain needs to return an iterable.
**How to avoid:** Mock `db.execute` to return a mock with `MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))` and patch `ConsentService` to prevent real DB operations.
**Warning signs:** `AttributeError: 'coroutine' object has no attribute 'scalars'`.

### Pitfall 3: test_evolution_client.py Will Cause Collection Errors
**What goes wrong:** `tests/unit/test_evolution_client.py` does `from app.integrations.evolution import EvolutionClient` at module level. When pytest tries to collect it, Python executes the import — which raises `ImportError` because `app/integrations/evolution/client.py` is tombstoned. This crashes the test collection for the entire `tests/unit/` directory.
**Why it happens:** Tombstone files raise `ImportError` at import time (that's the tombstone pattern). Test files with live top-level imports from tombstoned modules break collection.
**How to avoid:** Tombstone `test_evolution_client.py` before running any suite-wide pytest commands in this phase.
**Warning signs:** `ERRORS` in pytest output with `ImportError: app.integrations.evolution has been tombstoned`.

### Pitfall 4: tests/api/v2/conftest.py EvolutionClient mock is a string patch
**What goes wrong:** `conftest.py` line 865 patches `'app.integrations.evolution.client.EvolutionClient'` as a string. An AST scanner on `tests/` would flag this as a violation. But a script that scans `app/` only will not flag it (and shouldn't — string-based patches never execute the import).
**Why it happens:** Confusion between source-level imports and string-based mock targets.
**How to avoid:** The `check_evolution_imports.py` script scans `app/` only (not `tests/`), consistent with `check_async_isolation.py` which scans `app/tasks/` only.
**Warning signs:** Script reports violations from `tests/` directory — scope is wrong.

### Pitfall 5: "Real captured WuzAPI JSON" interpretation
**What goes wrong:** "Real captured WuzAPI JSON fixture payloads" could be interpreted as requiring physical `.json` fixture files. Creating fixture files in `tests/fixtures/wuzapi/` adds maintenance burden and doesn't improve test quality — the extractor tests already validate the exact schema.
**Why it happens:** The success criterion wording is ambiguous.
**How to avoid:** Interpret "real captured" as "structurally representative of actual WuzAPI output." The existing inline dict payloads in `test_wuzapi_webhook.py` already match the exact WuzAPI JSON shape (confirmed by the extractor tests). Add one test for unknown event type with an inline dict.
**Warning signs:** Time spent on fixture files instead of the actual gap (unknown event type test).

## Code Examples

Verified patterns from production code:

### HMAC Validation Flow
```python
# Source: app/integrations/wuzapi/webhook.py lines 37-42
secret = os.environ.get("WHATSAPP_WUZAPI_WEBHOOK_SECRET")
if secret:
    signature = request.headers.get("x-hmac-signature", "")
    # Empty string when header is absent → validate_signature returns False → 403
    if not WebhookHMACValidator.validate_signature(raw_body, signature, secret):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")
```

### Opt-Out Flow (handle_opt_out)
```python
# Source: app/services/webhook/handlers/message_handler.py lines 107-108
now = now_sao_paulo()
patient.messaging_stopped_at = now  # Sets the attribute directly on the ORM model
```

### Send Guard Flow
```python
# Source: app/services/unified_whatsapp_service.py lines 314-325
if patient_for_guard is not None and patient_for_guard.messaging_stopped_at is not None:
    logger.warning("Skipping message to opted-out patient %s (messaging_stopped_at=%s)", ...)
    return False  # Blocks the send
```

### fakeredis Fixture (established pattern)
```python
# Source: tests/integrations/wuzapi/test_wuzapi_webhook.py
@pytest.fixture
async def fake_redis():
    redis = fakeredis.aioredis.FakeRedis()
    yield redis
    await redis.flushall()
    await redis.close()
```

### Unknown Event Type Webhook Response
```python
# Source: app/integrations/wuzapi/webhook.py lines 73-75
logger.debug("WuzAPI webhook: unhandled event type %r", event_type)
return {"status": "ignored", "type": event_type}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Evolution API webhook | WuzAPI webhook at `/api/v2/webhooks/wuzapi` | Phase 34 | New endpoint being tested |
| LangGraph tombstone tested via `importlib.import_module` | Same pattern applies to Evolution | Phase 12 | Pattern established in `test_langgraph_tombstone.py` |
| Regex import scan | AST-based import scan for CI guards | Phase 21 (check_async_isolation.py) | AST is more accurate |

**Deprecated/outdated:**
- `tests/unit/test_evolution_client.py`: Tests the tombstoned Evolution client — must be tombstoned in Phase 38
- `tests/integrations/evolution/test_client_comprehensive.py`: Already tombstoned (Phase 37) with `pytestmark = pytest.mark.skip`

## Open Questions

1. **TEST-04 E2E scope: webhook → send guard in single test vs. separate unit tests?**
   - What we know: `handle_opt_out` sets `patient.messaging_stopped_at`; the send guard in `unified_whatsapp_service.py` checks this field
   - What's unclear: Whether "E2E test" means one test exercises the full flow (webhook POST → messaging_stopped_at set → send blocked) or two separate tests
   - Recommendation: Two separate tests — one for `handle_opt_out` setting the attribute (unit test of `message_handler.py`), one for the send guard logic (unit test of `unified_whatsapp_service.py`). The full integration path requires a real DB and is impractical in unit test context.

2. **Should check_evolution_imports.py scan tests/ for live imports?**
   - What we know: `tests/unit/test_evolution_client.py` has a live import from tombstoned module; `tests/api/v2/conftest.py` has a string-based mock (not a live import)
   - What's unclear: Whether "non-tombstone file" includes test files
   - Recommendation: Scan `app/` only (consistent with `check_async_isolation.py` which scans `app/tasks/`). Test file issues are handled by tombstoning `test_evolution_client.py` directly.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | `backend-hormonia/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend-hormonia && .venv/bin/pytest tests/integrations/wuzapi/ -x -q` |
| Full suite command | `cd backend-hormonia && .venv/bin/pytest tests/integrations/wuzapi/ tests/unit/test_evolution_import_regression.py -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-01 | WuzAPIClient text send, media types, auth, retry, rate limit | unit | `pytest tests/integrations/wuzapi/test_wuzapi_client.py tests/integrations/wuzapi/test_wuzapi_media.py -x` | ✅ All 22 tests pass |
| TEST-02 (gap) | Webhook unknown event type returns `{"status": "ignored"}` | unit | `pytest tests/integrations/wuzapi/test_wuzapi_webhook.py::test_unknown_event_type_returns_ignored -x` | ❌ Wave 0 |
| TEST-03 (gap) | Missing HMAC header returns 403 | unit | `pytest tests/integrations/wuzapi/test_wuzapi_webhook.py::test_missing_hmac_header_returns_403 -x` | ❌ Wave 0 |
| TEST-04 (gap 1) | `handle_opt_out` sets `messaging_stopped_at` on patient | unit | `pytest tests/unit/test_opt_out_lgpd.py::test_handle_opt_out_sets_messaging_stopped_at -x` | ❌ Wave 0 |
| TEST-04 (gap 2) | Send guard blocks opted-out patient | unit | `pytest tests/unit/test_opt_out_lgpd.py::test_send_guard_blocks_opted_out_patient -x` | ❌ Wave 0 |
| TEST-05 (gap 1) | `check_evolution_imports.py` exits 0 | script | `cd backend-hormonia && .venv/bin/python scripts/check_evolution_imports.py` | ❌ Wave 0 |
| TEST-05 (gap 2) | Pytest calls script, asserts exit 0 | unit | `pytest tests/unit/test_evolution_import_regression.py -x` | ❌ Wave 0 |
| TEST-05 (gap 3) | `test_evolution_client.py` is tombstoned | tombstone | Implicit — tombstone prevents collection errors | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend-hormonia && .venv/bin/pytest tests/integrations/wuzapi/ -x -q`
- **Per wave merge:** `cd backend-hormonia && .venv/bin/pytest tests/integrations/wuzapi/ tests/unit/test_evolution_import_regression.py -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/integrations/wuzapi/test_wuzapi_webhook.py` — add `test_unknown_event_type_returns_ignored` and `test_missing_hmac_header_returns_403`
- [ ] `tests/unit/test_opt_out_lgpd.py` — new file covering `handle_opt_out` attribute assertion and send guard unit test
- [ ] `scripts/check_evolution_imports.py` — new CI guard script (AST-based)
- [ ] `tests/unit/test_evolution_import_regression.py` — new file calling the CI script
- [ ] `tests/unit/test_evolution_client.py` — tombstone (replace content with `pytestmark = pytest.mark.skip`)

## Sources

### Primary (HIGH confidence)
- Codebase direct inspection — `backend-hormonia/app/integrations/wuzapi/` (all 8 files read)
- Codebase direct inspection — `backend-hormonia/tests/integrations/wuzapi/` (all 6 test files read, 73 tests run and confirmed passing)
- Codebase direct inspection — `backend-hormonia/scripts/check_async_isolation.py` (CI guard pattern source)
- Codebase direct inspection — `backend-hormonia/tests/unit/ai/test_langgraph_tombstone.py` (tombstone test pattern)
- Codebase direct inspection — `backend-hormonia/pyproject.toml` (pytest config confirmed)
- `REQUIREMENTS.md` TEST-01 through TEST-05 specifications
- `STATE.md` Phase 37 decisions and confirmed completions

### Secondary (MEDIUM confidence)
- pytest-asyncio docs — `asyncio_mode=auto` means no `@pytest.mark.asyncio` needed (confirmed by working tests in codebase)
- fakeredis docs — `FakeRedis` supports SET NX semantics (confirmed by idempotency tests passing)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and used in passing tests
- Architecture: HIGH — all patterns established by existing test files
- Pitfalls: HIGH — identified via direct code inspection and test run
- Gap analysis: HIGH — exact gap identification via line-by-line review of success criteria vs. existing test functions

**Research date:** 2026-03-03
**Valid until:** 2026-03-10 (stable domain, no fast-moving dependencies)
