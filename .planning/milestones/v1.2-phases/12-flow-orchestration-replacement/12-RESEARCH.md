# Phase 12: Flow Orchestration Replacement - Research

**Researched:** 2026-02-24
**Domain:** LangGraph removal, async Python refactor, Redis PHI purge, LGPD compliance
**Confidence:** HIGH

## Summary

Phase 12 has three clearly separated workstreams. The first is a code replacement: the two `StateGraph`-backed orchestrators (`flow_message_graph`, `flow_response_graph`) in `sequential_message_handler.py` are each 10-15 lines of graph invocation that can be replaced by direct `async def` functions calling the same four underlying node functions (`load_flow_context`, `dispatch_send_mode`, `load_response_context`, `dispatch_response_continuation`) already present in `nodes.py`. No logic changes are needed — only the invocation layer changes. The `AI_FLOW_FRAMEWORK` feature flag (a new setting, extending the existing `AI_FRAMEWORK` pattern from Phase 11) must gate the two paths so the legacy graph path can coexist until verified.

The second workstream is package removal: three lines in `requirements.txt` (`langchain-core`, `langchain-google-genai`, `google-ai-generativelanguage`, `langgraph`) are removed after all callers in `app/` are either redirected through the `helpers.py` shim or the prompts/nodes_ai content is relocated. This is primarily a dependency of plan 12-01 completing first.

The third workstream is LGPD compliance: all `langgraph:checkpoint:*` keys in Dragonfly DB 0 (the Celery broker database) must be purged via a `scan_iter` loop, the purge count logged as a data deletion event using `log_event(event_type="lgpd_data_deleted", ...)`, and the `app/ai/langgraph/` directory converted to a directory of tombstone files (each raising `ImportError` with a migration message on import).

A critical discovery: **`helpers.py` already acts as a re-export shim designed for Phase 12** — it contains `# When Phase 12 tombstones app/ai/langgraph/, only this file needs updating`. However, **multiple callers in `client_domain.py`, `composer.py`, `analytics/data_extraction/service.py`, `enhanced_flow_engine.py`, and `follow_up_system/generators/` still import directly from `app.ai.langgraph.*` instead of going through `helpers.py`**. These must be migrated to `helpers.py` before tombstoning can succeed.

**Primary recommendation:** Do the three workstreams in dependency order: (12-01) replace graph invocations with direct async functions + migrate all `app.ai.langgraph.*` callers to `helpers.py`; (12-02) remove LangGraph packages from requirements.txt + verify with `pip check`; (12-03) purge Redis checkpoint PHI keys + tombstone the directory.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FLOW-01 | `flow_message_graph` callers invoke a direct async Python function that executes `load_flow_context → dispatch_send_mode` with no LangGraph runtime involved — `AI_FLOW_FRAMEWORK` flag routes between old and new paths | `sequential_message_handler.py` lines 127-156 contain the only production caller; nodes exist in `nodes.py`; `AI_FRAMEWORK` pattern from Phase 11 provides the exact flag design to replicate |
| FLOW-02 | `flow_response_graph` callers invoke a direct async Python function that executes `load_response_context → dispatch_response_continuation` — same behavior, zero graph overhead | `sequential_message_handler.py` lines 176-201 contain the only production caller; same nodes.py functions used |
| FLOW-03 | `requirements.txt` no longer contains `langgraph`, `langchain-core`, `langchain-google-genai`, or `google-ai-generativelanguage` — confirmed by a single clean `pip check` run | All 4 packages identified at lines 42-45 in `requirements.txt`; removal must follow FLOW-01 completion so app/ callers already don't depend on them |
| FLOW-04 | `scan_iter` on Dragonfly DB 0 returns zero results for `langgraph:checkpoint:*` keys — purge executed, purge count logged as a LGPD data deletion event in the audit record | Key prefix is `langgraph:checkpoint:{graph_name}:` from `runtime.py:156`; audit uses `log_event(event_type="lgpd_data_deleted", ...)` from `quiz_audit.py:308-323` |
| FLOW-05 | Every file in `app/ai/langgraph/` raises `ImportError` with a migration message when imported — directory tombstoned, not deleted | Files to tombstone: `runtime.py`, `nodes.py`, `state.py`, `graphs.py`, `_invoke.py`, `prompts.py`, `nodes_ai.py`, `ai_state.py`, `__init__.py` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python asyncio | stdlib | Direct async function execution | Replaces graph overhead with zero dependencies |
| redis-py (sync) | already pinned | Redis scan_iter for checkpoint purge | Already the project's canonical Redis client via `get_sync_redis_client()` |
| app.services.audit.quiz_audit | internal | LGPD data deletion event logging | `log_data_deletion()` already implements `lgpd_data_deleted` event type, 7-year retention |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-ai-slim | already installed | New agent framework | Already active from Phase 11; not directly used in Phase 12 |
| app.ai.agents.helpers | internal shim | Bridge during tombstoning | All `app.ai.langgraph.prompts` and `nodes_ai` imports must go through this shim before tombstone |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct `async def` functions | ADK SequentialAgent | ADK deferred to v1.3 (3 irresolvable conflicts documented in STATE.md); direct Python is simpler and has zero new dependencies |
| `log_data_deletion()` wrapper | raw `log_event()` | Either works; `log_data_deletion()` already has the right event_type, severity, legal_basis, and 7-year retention — prefer it |

## Architecture Patterns

### Recommended Project Structure (after Phase 12)

```
app/ai/
├── langgraph/           # TOMBSTONED — every .py raises ImportError
│   ├── __init__.py      # tombstone
│   ├── graphs.py        # tombstone
│   ├── nodes.py         # tombstone
│   ├── nodes_ai.py      # tombstone
│   ├── prompts.py       # tombstone
│   ├── runtime.py       # tombstone
│   ├── state.py         # tombstone
│   ├── ai_state.py      # tombstone
│   └── _invoke.py       # tombstone
├── agents/
│   ├── helpers.py       # NOW owns prompts + node helpers (moved from langgraph/)
│   ├── ...
└── ...
app/services/flow/
├── sequential_message_handler.py   # NOW calls run_flow_message() / run_flow_response()
└── _flow_functions.py              # NEW — houses the two direct async functions
```

### Pattern 1: Direct Async Function Replacing Graph

**What:** Two pure `async def` functions that replicate the graph's two-node linear execution without any LangGraph runtime.

**When to use:** Any replacement of a linear StateGraph where nodes pass state forward — no branching, no cycles, no checkpointing needed.

**Example (flow_message_graph replacement):**
```python
# app/services/flow/_flow_functions.py
from __future__ import annotations
import logging
from typing import Any, Dict
from uuid import UUID
from app.ai.langgraph.nodes import (
    load_flow_context,
    dispatch_send_mode,
)

logger = logging.getLogger(__name__)


async def run_flow_message(
    *,
    patient_id: UUID,
    day_number: int,
    flow_kind: str,
    handler: Any,
) -> Dict[str, Any]:
    """Direct async replacement for flow_message_graph.ainvoke()."""
    state: Dict[str, Any] = {
        "patient_id": patient_id,
        "day_number": day_number,
        "flow_kind": flow_kind,
        "result": None,
        "error": None,
    }
    # Mimic config dict that nodes previously received from LangGraph
    config = {"configurable": {"thread_id": f"flow_message:{patient_id}:{flow_kind}:{day_number}", "handler": handler}}

    state.update(await load_flow_context(state, config=config))
    if state.get("result"):
        return state["result"]
    state.update(await dispatch_send_mode(state, config=config))
    result = state.get("result")
    if not isinstance(result, dict):
        raise ValueError("Direct flow function did not return a result payload")
    return result
```

**Note:** The `config` dict structure must exactly match what `_require_handler(config)` and `require_configurable_thread_id(config)` expect in `nodes.py` — they both read `config["configurable"]["handler"]` and `config["configurable"]["thread_id"]`. No LangGraph `RunnableConfig` type is required; these functions accept `Optional[Any]`.

### Pattern 2: AI_FLOW_FRAMEWORK Feature Flag in settings

**What:** Extend the existing `AI_FRAMEWORK` pattern from Phase 11 to add `AI_FLOW_FRAMEWORK`.

**Where to add:**
- `app/config/settings/integrations.py` — add `AI_FLOW_FRAMEWORK: str = Field(default="legacy", ...)`
- `.env.example` — add `AI_FLOW_FRAMEWORK=legacy  # 'legacy' or 'direct' - toggles graph vs direct async`

**Usage in `sequential_message_handler.py`:**
```python
def _use_direct_flow_functions(self) -> bool:
    from app.config import settings
    return getattr(settings, "AI_FLOW_FRAMEWORK", "legacy") == "direct"

async def send_day_messages(self, patient_id, day_number, flow_kind="onboarding"):
    if self._use_direct_flow_functions():
        from app.services.flow._flow_functions import run_flow_message
        return await run_flow_message(patient_id=patient_id, day_number=day_number, flow_kind=flow_kind, handler=self)
    # legacy graph path unchanged
    graph = get_flow_message_graph()
    ...
```

### Pattern 3: Redis Checkpoint Purge Script

**What:** A standalone Python script (or Celery task) that iterates all `langgraph:checkpoint:*` keys in Dragonfly DB 0 and deletes them, logging the count as LGPD event.

**Key prefix from `runtime.py`:**
```
langgraph:checkpoint:{graph_name}:ckpt:{thread_id}:{checkpoint_ns}:{checkpoint_id}
langgraph:checkpoint:{graph_name}:latest:{thread_id}:{checkpoint_ns}
langgraph:checkpoint:{graph_name}:index:{thread_id}:{checkpoint_ns}
langgraph:checkpoint:{graph_name}:writes:{thread_id}:{checkpoint_ns}:{checkpoint_id}
```
All four sub-key types share the `langgraph:checkpoint:` prefix, so a single `scan_iter(match="langgraph:checkpoint:*", count=100)` covers all variants.

**Purge pattern (from `runtime.py` `delete_thread()` and project Redis conventions):**
```python
from app.core.redis_manager import get_sync_redis_client

def purge_langgraph_checkpoints() -> int:
    redis = get_sync_redis_client()
    keys = list(redis.scan_iter(match="langgraph:checkpoint:*", count=100))
    if keys:
        redis.delete(*keys)
    return len(keys)
```

**LGPD audit logging pattern (from `quiz_audit.py`):**
```python
from app.services.audit.service import AuditService

# log_data_deletion needs a DB session; for a standalone script, use log_event directly
audit_service = AuditService(db=db_session)
audit_service.log_event(
    event_type="lgpd_data_deleted",
    event_category="data_change",
    severity="warning",
    actor_id=SYSTEM_ACTOR_UUID,
    subject_id=None,
    event_data={
        "deletion_scope": "redis_langgraph_checkpoints",
        "reason": "LGPD Art. 46 — PHI ephemeral data purge during LangGraph decommission",
        "keys_deleted": purge_count,
        "key_pattern": "langgraph:checkpoint:*",
    },
    result="success",
    legal_basis="legal_obligation",
    retention_days=2555,
)
```

### Pattern 4: Tombstone File Format

**What:** Replace each file in `app/ai/langgraph/` with a docstring and a module-level `ImportError` raise. This is the project's established tombstone pattern.

**Tombstone template (inferred from MEMORY.md and project patterns):**
```python
"""
TOMBSTONED — Phase 12 (Flow Orchestration Replacement)

This module has been decommissioned.  All prompt builders and node helpers
have moved to ``app.ai.agents.helpers``.  Flow orchestration has moved to
``app.services.flow._flow_functions``.

Do not import from this module.  Update your import to:
  - Prompts/node helpers: ``from app.ai.agents.helpers import <name>``
  - Flow state types: ``from app.services.flow._flow_functions import <name>``
"""
raise ImportError(
    "app.ai.langgraph has been tombstoned in Phase 12 (Flow Orchestration Replacement). "
    "Import from app.ai.agents.helpers for prompt builders and node helpers."
)
```

### Pattern 5: helpers.py Content Migration

**What:** Before tombstoning `prompts.py` and `nodes_ai.py`, the content they export must either be moved inline to `helpers.py` or `helpers.py` re-exports from new permanent homes.

**Recommended approach:** Move the actual function bodies from `prompts.py` and `nodes_ai.py` into `helpers.py` (or a new `app/ai/prompts.py` and `app/ai/node_utils.py`). The helpers.py shim comment already says "only this file needs updating" — make it the actual owner.

**Callers that bypass helpers.py and still import directly (ALL must be fixed before tombstoning):**
- `app/agents/communication/message_composer/composer.py` (lines 316-317)
- `app/ai/client_domain.py` (lines 84-85, 151-158, 213-214, 270)
- `app/services/analytics/data_extraction/service.py` (lines 428-429)
- `app/services/enhanced_flow_engine.py` (lines 420-421, 558-559)
- `app/services/follow_up_system/generators/empathy.py` (line 126)
- `app/services/follow_up_system/generators/response.py` (line 113)
- `app/core/lifespan.py` (line 229) — imports `_LANGGRAPH_IMPORT_ERROR`; must be removed entirely since lifespan check is no longer meaningful post-tombstone

### Anti-Patterns to Avoid
- **Deleting the `langgraph/` directory:** The project uses tombstone-not-delete. Keep files, replace content with `raise ImportError`.
- **Removing the `AI_FLOW_FRAMEWORK` flag before validating production:** The flag must default to `"legacy"` so production is unchanged until explicit opt-in.
- **Purging Redis before tombstoning:** The purge script depends only on having `get_sync_redis_client()` — it can run at any time, but logically belongs in 12-03 after the graph code is gone.
- **Using `redis.keys("langgraph:checkpoint:*")`:** The project rule is `scan_iter(match=pattern, count=100)` — never `keys()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LGPD audit record for purge | Custom DB insert | `AuditService.log_event(event_type="lgpd_data_deleted")` | Already implements 7-year retention, legal_basis, correct event schema |
| Redis key enumeration | `redis.keys("*")` | `scan_iter(match=pattern, count=100)` | Project convention; avoids blocking Redis on large keyset |
| Feature flag | Custom config parsing | Pydantic `Field` in `IntegrationsSettings` | Existing pattern from Phase 11 `AI_FRAMEWORK` |

**Key insight:** The project's existing patterns cover every technical requirement. This phase is a refactor that connects existing pieces, not a build.

## Common Pitfalls

### Pitfall 1: nodes.py uses `RunnableConfig` type from langchain-core
**What goes wrong:** `nodes.py` imports `from langchain_core.runnables import RunnableConfig` at the top level (line 9). When `langchain-core` is removed from requirements.txt (FLOW-03), importing nodes.py will fail at `ImportError: No module named 'langchain_core'`.
**Why it happens:** The type annotation `config: Optional[RunnableConfig]` is used in all four node functions, but the actual runtime behavior only needs `config` to be a dict (it's passed to `require_configurable_thread_id(config)` which reads `config.get("configurable")`).
**How to avoid:** The new direct async functions in `_flow_functions.py` accept `config: dict` — they don't need `RunnableConfig`. Since `nodes.py` is tombstoned in plan 12-03 anyway, the tombstone replaces the import. But during plan 12-01, `_flow_functions.py` must avoid importing from `nodes.py` directly if `langchain-core` is still installed — or more precisely, plan 12-02 (package removal) must happen AFTER plan 12-01 ensures `_flow_functions.py` owns the logic independently. **The safest approach is to inline the four node functions into `_flow_functions.py` rather than calling `nodes.py`.**

### Pitfall 2: The _check_langgraph_available() check in lifespan.py will fail after tombstone
**What goes wrong:** `app/core/lifespan.py` line 229 imports `_LANGGRAPH_IMPORT_ERROR` from `graphs.py`. After tombstoning, this import raises `ImportError` at app startup.
**Why it happens:** lifespan.py uses this to check whether LangGraph loaded successfully in production — a check that becomes meaningless once LangGraph is intentionally removed.
**How to avoid:** Remove the `_check_langgraph_available()` function from `lifespan.py` entirely in plan 12-01. The call to it is at line 90 of lifespan.py.

### Pitfall 3: Tests in `tests/langgraph/` and `tests/unit/` import from `app.ai.langgraph.*`
**What goes wrong:** After tombstoning, the following test files will fail to import:
- `tests/langgraph/test_langgraph_real_flows.py` — imports `build_flow_message_graph`, `build_flow_response_graph`
- `tests/langgraph/test_prompts_pii_redaction.py` — imports from `app.ai.langgraph.prompts`
- `tests/langgraph/test_runtime_checkpointer_fallback.py` — imports `runtime`
- `tests/langgraph/test_state_validation.py` — imports `validate_ai_state`, `validate_flow_message_state`, nodes functions
- `tests/unit/ai/test_nodes_question_variation.py` — imports `nodes_ai`
- `tests/unit/ai/test_runtime.py` — imports `runtime`
- `tests/unit/services/flow/test_sequential_message_handler.py` — imports from `app.ai.langgraph.nodes`
**Why it happens:** Tests were written against LangGraph internals. After tombstone, those imports fail.
**How to avoid:** All tests that exercise LangGraph-specific internals must be deleted or converted. Tests that exercise node logic should be rewritten to call `_flow_functions.py` directly. The `tests/langgraph/` directory should be removed.

### Pitfall 4: `AI_FLOW_FRAMEWORK` (the new flag name) does not yet exist in settings
**What goes wrong:** The phase description says `AI_FLOW_FRAMEWORK` but the current codebase only has `AI_FRAMEWORK` (for agent delegation in Phase 11). There is currently no `AI_FLOW_FRAMEWORK` setting — the planner must create it.
**Why it happens:** The phase spec uses a different flag name than the existing one.
**How to avoid:** Add `AI_FLOW_FRAMEWORK: str = Field(default="legacy", ...)` to `IntegrationsSettings` in the same file that already has `AI_FRAMEWORK`. The two flags are independent: `AI_FRAMEWORK` routes agent (AI calls), `AI_FLOW_FRAMEWORK` routes orchestration (graph vs direct function).

### Pitfall 5: `lru_cache` on graph constructors persists stale compiled graphs across invocations
**What goes wrong:** `get_flow_message_graph()` and `get_flow_response_graph()` use `@lru_cache(maxsize=1)`. If the legacy path is still active but the graph code has been made inactive, the cached object from a previous call would be returned. This is not an issue for the replacement (the new `_flow_functions.py` path doesn't use caches), but the legacy path must remain intact if `AI_FLOW_FRAMEWORK=legacy`.
**How to avoid:** Leave the `@lru_cache` and graph builder functions fully intact in `sequential_message_handler.py`'s legacy branch. Only add the new direct-function branch; don't modify the legacy branch.

### Pitfall 6: Redis checkpoint keys are in DB 0 (Celery broker), not DB 1 (cache)
**What goes wrong:** The purge script connects to the wrong Redis database and finds zero keys, or the `get_sync_redis_client()` call connects to DB 1 (cache) by default.
**Why it happens:** Project uses Dragonfly with 4 DBs: DB 0 = broker (Celery + LangGraph checkpoints), DB 1 = cache, DB 2 = sessions, DB 3 = ratelimit. The `RedisCheckpointer` in `runtime.py` connects to Dragonfly DB 0 via `get_sync_redis_client()`. The BROKER_DB_NUMBER is 0 per `.env.example:133`.
**How to avoid:** Verify that `get_sync_redis_client()` defaults to DB 0 before running the purge. If it defaults to another DB, explicitly pass `db=0`. Confirm via `redis-cli -n 0 SCAN 0 MATCH "langgraph:checkpoint:*"` before and after.

## Code Examples

### Direct async function signature (verified from nodes.py analysis)

```python
# The four node functions have these signatures:
async def load_flow_context(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
) -> FlowMessageState: ...

async def dispatch_send_mode(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
) -> FlowMessageState: ...

async def load_response_context(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
) -> FlowMessageState: ...

async def dispatch_response_continuation(
    state: FlowMessageState, config: Optional[RunnableConfig] = None
) -> FlowMessageState: ...
```

The functions accept `Optional[Any]` for config; `RunnableConfig` is just a type alias. They call `_require_handler(config)` which does:
```python
def _require_handler(config: Optional[RunnableConfig]) -> Any:
    require_configurable_thread_id(config)  # checks config["configurable"]["thread_id"]
    handler = (config or {}).get("configurable", {}).get("handler")
    if handler is None:
        raise RuntimeError("Flow handler missing.")
    return handler
```

So the config dict must be: `{"configurable": {"thread_id": "...", "handler": self}}`

### The two existing caller sites in sequential_message_handler.py

```python
# FLOW-01 caller (lines 127-156):
graph = get_flow_message_graph()
state = await graph.ainvoke(
    {"patient_id": patient_id, "day_number": day_number, "flow_kind": flow_kind, "result": None, "error": None},
    config=build_graph_config(
        thread_id=self._build_flow_message_thread_id(patient_id=patient_id, flow_kind=flow_kind, day_number=day_number),
        handler=self,
    ),
)
result = state.get("result")

# FLOW-02 caller (lines 177-201):
graph = get_flow_response_graph()
graph_state: Dict[str, Any] = {"patient_id": patient_id, "result": None, "error": None}
if response_context is not None:
    graph_state["response_context"] = response_context
state = await graph.ainvoke(
    graph_state,
    config=build_graph_config(
        thread_id=self._build_flow_response_thread_id(patient_id),
        handler=self,
    ),
)
result = state.get("result")
```

The replacement functions have identical input/output contracts. `build_graph_config()` in `runtime.py` simply produces `{"configurable": {**kwargs}}`.

### Requirements.txt lines to remove (verified)

```
# Line 42: langchain-core>=1.2.7,<2.0.0
# Line 43: langchain-google-genai>=2.1.12,<4.0.0
# Line 44: google-ai-generativelanguage>=0.7.0,<1.0.0
# Line 45: langgraph>=1.0.7,<2.0.0
# Line 39-40: two comment lines explaining the removals
```

After removal, run: `pip check` — should produce no dependency errors.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangGraph `StateGraph` with Redis checkpointing | Direct `async def` Python functions | Phase 12 | Zero overhead, no checkpoint PHI leak surface |
| `MemorySaver`/`RedisCheckpointer` for state between invocations | Stateless single-call functions | Phase 12 | State lives in PostgreSQL `step_data` column, not Redis |
| `_LANGGRAPH_IMPORT_ERROR` check in lifespan | Removed (LangGraph intentionally absent) | Phase 12 | Startup check no longer needed |
| `langchain_core.runnables.RunnableConfig` type annotation | Plain `dict` | Phase 12 | No langchain-core import needed |

**Deprecated/outdated after Phase 12:**
- `app.ai.langgraph.*`: Entire package tombstoned
- `langchain-core`, `langchain-google-genai`, `google-ai-generativelanguage`, `langgraph`: All removed from requirements.txt
- `tests/langgraph/`: Entire test directory removed (tests LangGraph internals that no longer exist)
- `_check_langgraph_available()` in lifespan.py: Removed (meaningful only when LangGraph might be missing at startup)

## Open Questions

1. **Does `get_sync_redis_client()` default to DB 0 or DB 1?**
   - What we know: DB 0 is the broker per `.env.example:133 (REDIS_BROKER_DB_NUMBER=0)`. `runtime.py:148` calls `get_sync_redis_client()` without a db parameter for the `RedisCheckpointer`.
   - What's unclear: Whether `get_sync_redis_client()` defaults to DB 0 or another database.
   - Recommendation: Read `app/core/redis_manager/sync_client.py:18` (function body) before writing the purge script. If it defaults to DB 1, the purge script must explicitly pass `db=0` (or the `REDIS_BROKER_DB_NUMBER` setting).

2. **Does the purge script need a database session (SQLAlchemy) for the audit log, or can it write directly?**
   - What we know: `AuditService.log_event()` typically uses a DB session for ORM writes. The purge script is standalone (not an HTTP request handler).
   - What's unclear: Whether there's a standalone session factory available for scripts.
   - Recommendation: Check `app/db/session.py` for a `get_db_session()` context manager. If none, use `log_event` with a minimal direct DB write, or emit a structured log entry at CRITICAL level as the LGPD audit record (same information, different storage).

3. **Should the `AI_FLOW_FRAMEWORK` flag be the same env var as `AI_FRAMEWORK` or a new one?**
   - What we know: Phase spec says `AI_FLOW_FRAMEWORK`. `AI_FRAMEWORK` controls agent delegation (Phase 11). These are independent concerns.
   - What's unclear: Whether a single unified flag would be simpler.
   - Recommendation: Use a separate `AI_FLOW_FRAMEWORK` as specified. Adding it as a new field in `IntegrationsSettings` is a one-line addition.

## Validation Architecture

> `workflow.nyquist_validation` is not present in `.planning/config.json` — section included based on test infrastructure detection.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `backend-hormonia/pyproject.toml` ([tool.pytest.ini_options]) |
| Quick run command | `cd backend-hormonia && pytest tests/unit/services/flow/test_sequential_message_handler.py -q` |
| Full suite command | `cd backend-hormonia && pytest tests/ -q --ignore=tests/langgraph` |
| Estimated runtime | ~30 seconds (unit tests, no external services) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FLOW-01 | `send_day_messages()` invokes `run_flow_message()` when `AI_FLOW_FRAMEWORK=direct` | unit | `pytest tests/unit/services/flow/test_sequential_message_handler.py -k "test_flow_message" -x` | Existing file must be updated; new test added |
| FLOW-02 | `handle_response_and_continue()` invokes `run_flow_response()` when `AI_FLOW_FRAMEWORK=direct` | unit | `pytest tests/unit/services/flow/test_sequential_message_handler.py -k "test_response" -x` | Existing file must be updated; new test added |
| FLOW-03 | No langgraph/langchain imports resolved | smoke | `python -c "import app.services.flow.sequential_message_handler"` (after pip uninstall) | No — manual verification or new smoke test |
| FLOW-04 | Redis `langgraph:checkpoint:*` key count is 0 after purge | integration | `pytest tests/unit/ai/test_checkpoint_purge.py -x` | No — Wave 0 gap |
| FLOW-05 | `from app.ai.langgraph.graphs import get_flow_message_graph` raises `ImportError` | unit | `pytest tests/unit/ai/test_langgraph_tombstone.py -x` | No — Wave 0 gap |

### Nyquist Sampling Rate
- **Minimum sample interval:** After each committed task → run: `cd backend-hormonia && pytest tests/unit/services/flow/test_sequential_message_handler.py -q`
- **Full suite trigger:** Before merging final task of any plan wave
- **Phase-complete gate:** Full suite green (excluding `tests/langgraph/` which is deleted) before `/gsd:verify-work` runs
- **Estimated feedback latency per task:** ~15 seconds

### Wave 0 Gaps (must be created before implementation tasks reference them)
- [ ] `tests/unit/ai/test_checkpoint_purge.py` — covers FLOW-04 (mock Redis scan_iter/delete, verify purge count and audit log call)
- [ ] `tests/unit/ai/test_langgraph_tombstone.py` — covers FLOW-05 (verify `ImportError` raised for each tombstoned file)
- [ ] Update `tests/unit/services/flow/test_sequential_message_handler.py` — add test cases for `AI_FLOW_FRAMEWORK=direct` path in both `send_day_messages` and `handle_response_and_continue`

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis — `backend-hormonia/app/ai/langgraph/graphs.py`, `nodes.py`, `runtime.py`, `state.py`, `_invoke.py`, `nodes_ai.py`, `prompts.py`, `ai_state.py`
- Direct codebase analysis — `backend-hormonia/app/services/flow/sequential_message_handler.py` (only production caller of both graphs)
- Direct codebase analysis — `backend-hormonia/app/ai/agents/helpers.py` (Phase 12 migration shim, already designed for this)
- Direct codebase analysis — `backend-hormonia/app/ai/client_domain.py` (AI_FRAMEWORK pattern from Phase 11)
- Direct codebase analysis — `backend-hormonia/app/services/audit/quiz_audit.py:308-323` (log_data_deletion pattern)
- Direct codebase analysis — `backend-hormonia/requirements.txt:42-45` (packages to remove)
- Direct codebase analysis — `backend-hormonia/.env.example:133` (REDIS_BROKER_DB_NUMBER=0)
- `.planning/STATE.md` — key decisions, phase history, `AI_FLOW_FRAMEWORK` flag name specified

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — FLOW-01 through FLOW-05 requirement definitions
- `.planning/phases/11-agent-implementation/11-04-SUMMARY.md` — confirmed Phase 11 completion state and helpers.py shim design

### Tertiary (LOW confidence)
- None — all findings are from primary codebase analysis

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all tools already in the codebase
- Architecture: HIGH — four node functions exist and work; direct async pattern is trivial; audit log API verified
- Pitfalls: HIGH — all pitfalls verified against actual code (not theoretical)

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable codebase; 30-day window)
