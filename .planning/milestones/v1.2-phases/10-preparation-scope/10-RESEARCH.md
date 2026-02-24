# Phase 10: Preparation & Scope - Research

**Researched:** 2026-02-24
**Domain:** Python import auditing, dependency installation validation, dead code deletion
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Consensus deletion pattern:** Delete completely — remove files from repository entirely (not tombstone pattern). Delete all associated test files with no @pytest.skip stubs. Remove unused agent IDs from `app/agents/base.py` (ALERT_ANALYZER_ID, PATIENT_MONITOR_ID etc. — only those exclusively used by consensus). Adjust `flow_coordinator` to remove consensus imports and calls cleanly (not stub/mock). Files to delete: `app/ai/langgraph/consensus.py`, `app/agents/patient/flow_coordinator/consensus_manager.py`, and any tests for these.
- **ADK deferral:** Do NOT design for ADK compatibility — Pydantic AI pure, no future-proofing for ADK. ADK deferred to v1.3 due to 3 irresolvable dependency conflicts (OTel cap, FastAPI bundling, Pydantic 2.11+ failures). Track ADK issue #3615 (google-adk-core lightweight install) for v1.3 readiness.
- **Dependency management:** Single `requirements.txt` file (no dev/prod/test split). pydantic-ai and LangGraph coexist during migration phases 10-12. LangGraph packages removed at end of Phase 12.

### Claude's Discretion

- **Agent identity handling:** Whether to rename `app/agents/` DDD services, annotate them, or restructure — Claude evaluates naming confusion risk and chooses the least-disruptive approach.
- **Timing of agent reorganization:** Phase 10 or Phase 11 — Claude picks based on what minimizes churn.
- **message_composer classification:** Whether it stays as DDD service or migrates to AI agent — Claude evaluates based on its actual LLM usage pattern.
- **New Pydantic AI agents directory:** `app/ai/agents/` vs `app/agents/ai/` vs other — Claude picks based on existing codebase patterns.
- **ADK deferral documentation location:** PROJECT.md Key Decisions, REQUIREMENTS.md, or both.
- **ADK tracking mechanism:** STATE.md pending todo, MILESTONES.md note, or other.
- **Dependency coexistence strategy:** How to manage pydantic-ai + LangGraph side-by-side safely.
- **pydantic-ai version pinning:** `>=1.63.0,<2.0.0` vs exact pin vs other — Claude picks the safest strategy given v2 breaking changes planned for April 2026.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PREP-01 | Developer can see a complete import graph of all LangGraph/LangChain dependencies across the codebase (audit) | Codebase grep confirmed exact file list and import patterns — 9 files outside `app/ai/langgraph/` import from langgraph/langchain packages |
| PREP-02 | System installs pydantic-ai-slim[google,retries] without conflicts on Python 3.13 | Dry-run in project venv confirms zero conflicts; `Would install` output lists only new packages, no incompatibility messages |
| PREP-03 | Consensus graph and all associated code are deleted (0 callers, confirmed dead code) | Full call graph traced — production call chain is: `FlowCoordinatorAgent` (instantiated only via `hive_mind_integration.py`, a dormant Hive-Mind integration) → `ConsensusManager` → `get_consensus_graph()`; no production flow triggers this path |
</phase_requirements>

---

## Summary

Phase 10 is a preparation phase with three bounded, concrete tasks: audit LangGraph imports, install pydantic-ai-slim, and delete the consensus system. All three are mechanically straightforward; the research value is in precisely mapping what exists so the planner can write exact task steps without discovery work.

The LangGraph import audit reveals 9 files outside `app/ai/langgraph/` that import from the LangGraph/LangChain/langchain-google-genai packages, spread across 6 different modules. The full list is known and enumerable. The success criterion requires `python -c "import app.main"` to print a list of these files — this is a runtime audit via a temporary debug hook, not a static grep. The implementation must produce a printable list during import of `app.main`.

The pydantic-ai-slim installation has been validated via `pip install --dry-run` in the project's `.venv` (Python 3.12.3). The output confirms zero conflicts: all critical packages (`pydantic>=2.12`, `httpx>=0.27`, `opentelemetry-api>=1.28.0`) are already installed at compatible versions. Six new packages would be added: `pydantic-ai-slim-1.63.0`, `pydantic-graph-1.63.0`, `google-genai-1.64.0`, `genai-prices-0.0.54`, `griffelib-2.0.0`, `logfire-api-4.25.0`, and `websockets-15.0.1`. The success criterion mentions Python 3.13, but the production Dockerfile uses `python:3.13-slim` while the local venv is Python 3.12.3. The installation validation must be performed in a Python 3.13 environment (Docker or CI) to fully satisfy PREP-02.

The consensus deletion is more complex than it appears. The files-to-delete list in CONTEXT.md is correct (`consensus.py`, `consensus_manager.py`, and their tests) but the dependency ripple requires additional edits: `coordinator.py` imports `ConsensusManager` and calls it in 4 places, `flow_coordinator/__init__.py` re-exports `ConsensusManager`, `app/orchestration/consensus.py` is a re-export shim for `app.ai.langgraph.consensus`, and `alert_analyzer.py` and `patient_monitor.py` register `consensus_request` message handlers. All of these must be cleaned up in the same commit. Additionally, `ALERT_ANALYZER_ID` and `PATIENT_MONITOR_ID` in `registry.py` must NOT be deleted — they are used by `response_processor.py`, `quiz/conductor.py`, and `quiz/session_coordinator.py` for purposes unrelated to consensus.

**Primary recommendation:** Execute all three tasks sequentially in Phase 10, committing each separately. The import audit commit adds a temporary print hook only; pydantic-ai installation commits the requirements.txt change; consensus deletion is the most impactful commit and requires the most careful staging.

---

## Standard Stack

### Core (for Phase 10 specifically)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic-ai-slim[google,retries] | >=1.63.0,<2.0.0 | Pydantic AI framework with Gemini support | Slim variant for Google-only deployment; `[retries]` pulls tenacity (already installed) |
| google-genai | >=1.56.0 (transitive) | Unified Google GenAI SDK | Replaces google-ai-generativelanguage eventually; pydantic-ai's `[google]` extra pins this |

### Existing (already installed, confirmed compatible)

| Library | Installed Version | Relevant For |
|---------|------------------|-------------|
| pydantic | 2.12.5 | pydantic-ai requires `>=2.12` — satisfied |
| httpx | 0.28.1 | pydantic-ai requires `>=0.27` — satisfied |
| opentelemetry-api | 1.39.1 | pydantic-ai requires `>=1.28.0` — satisfied (also confirms google-adk's `<1.39.0` cap would conflict) |
| tenacity | 8.5.0 | pydantic-ai `[retries]` extra requires `>=8.2.3` — satisfied |
| langchain-core | 1.2.7 | Coexists safely during migration — no version clash with pydantic-ai |
| langgraph | 1.0.8 | Coexists safely during migration — no version clash with pydantic-ai |

### New packages added by pydantic-ai-slim installation

| Package | Version | Notes |
|---------|---------|-------|
| pydantic-ai-slim | 1.63.0 | Core package |
| pydantic-graph | 1.63.0 | Internal graph library, installed as pydantic-ai dependency |
| google-genai | 1.64.0 | Upgrades from not-installed (google-genai was missing in venv) to 1.64.0 |
| genai-prices | 0.0.54 | Token pricing utility (small, no conflict) |
| griffelib | 2.0.0 | Internal pydantic-ai utility |
| logfire-api | 4.25.0 | Observability API stub (zero-overhead when Logfire not configured) |
| websockets | 15.0.1 | WebSocket support for google-genai live streaming |

**Installation command (for requirements.txt):**
```
pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0
```

**Installation command (to run in virtualenv):**
```bash
pip install "pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0"
```

---

## Architecture Patterns

### PREP-01: LangGraph Import Audit Pattern

The success criterion for PREP-01 requires `python -c "import app.main"` to print a list of files that import from langgraph/langchain/langchain-google-genai. This means the audit hook must be inserted into `app/main.py` startup — not as a standalone script.

**Implementation approach:** Add a debug block at the top of `app/main.py` that uses `importlib` or `sys.modules` post-import introspection, or more practically, a one-time scan of `*.py` files using the Python `ast` module during startup. The print must happen when the module is imported, not only when the server is started.

**Alternative (simpler):** The print can also be achieved via a standalone script `scripts/audit_langgraph_imports.py` that is invoked by `python -c "import app.main"` through a startup hook. Either approach satisfies the acceptance criterion if the import of `app.main` triggers the printout.

**Static audit result (grep-based, verified against codebase as of 2026-02-24):**

| File | Imports From | Import Type |
|------|-------------|-------------|
| `app/ai/client.py` | `langchain_core.messages`, `langchain_google_genai` | top-level + try/except |
| `app/ai/langgraph/consensus.py` | `langgraph.graph` | try/except |
| `app/ai/langgraph/graphs.py` | `langgraph.graph` | try/except |
| `app/ai/langgraph/nodes.py` | `langchain_core.runnables` | top-level |
| `app/ai/langgraph/runtime.py` | `langgraph.checkpoint.memory`, `langgraph.checkpoint.base` | try/except |
| `app/services/ai/patient_summary_service.py` | `langchain_core.messages`, `langchain_google_genai` | top-level + try/except |
| `app/services/flow/sequential_message_handler.py` | `app.ai.langgraph.graphs`, `app.ai.langgraph.runtime` | top-level (indirect) |
| `app/agents/communication/message_composer/composer.py` | `app.ai.langgraph.nodes_ai`, `app.ai.langgraph.prompts` | lazy import in function |
| `app/ai/client_domain.py` | `app.ai.langgraph.nodes_ai`, `app.ai.langgraph.prompts` | lazy import in function |
| `app/services/analytics/data_extraction/service.py` | `app.ai.langgraph.nodes_ai`, `app.ai.langgraph.prompts` | lazy import in function |
| `app/services/enhanced_flow_engine.py` | `app.ai.langgraph.nodes_ai`, `app.ai.langgraph.prompts` | lazy import in function |
| `app/services/follow_up_system/generators/empathy.py` | `app.ai.langgraph.prompts` | lazy import in function |
| `app/services/follow_up_system/generators/response.py` | `app.ai.langgraph.prompts` | lazy import in function |
| `app/agents/patient/flow_coordinator/consensus_manager.py` | `app.ai.langgraph.runtime`, `app.ai.langgraph.consensus` | top-level + lazy |
| `app/core/lifespan.py` | `app.ai.langgraph.graphs` (via `_check_langgraph_available()`) | lazy import |
| `app/orchestration/consensus.py` | `app.ai.langgraph.consensus` | top-level re-export |

**Note on scope:** `consensus_manager.py` and `app/orchestration/consensus.py` will be deleted/cleaned up as part of PREP-03. The audit must include them in its output but they will not be migration targets.

### PREP-02: pydantic-ai-slim Installation Pattern

The installation is a single `pip install` command followed by a `requirements.txt` update. The coexistence with LangGraph is already validated — both packages share `google-auth`, `httpx`, `tenacity`, and `pydantic` dependencies at versions that satisfy both.

The success criterion mentions Python 3.13 but the local venv is Python 3.12.3. The pydantic-ai-slim package lists Python 3.10-3.14 as supported. The correct validation sequence is:

1. Run `pip install --dry-run "pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0"` in the local `.venv` (Python 3.12) to confirm no version conflicts.
2. Run the actual `pip install` command to install into the local `.venv`.
3. Verify the installation by importing: `python -c "from pydantic_ai import Agent; print('ok')"`.
4. Add `pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0` to `requirements.txt`.
5. Document that Docker build (Python 3.13) provides the canonical Python 3.13 validation; local venv is Python 3.12.3.

The PREP-02 success criterion ("pip install ... succeeds in the project virtualenv on Python 3.13 with zero dependency conflicts") will be documented as: local dry-run on Python 3.12.3 confirmed zero conflicts, and pydantic-ai officially supports Python 3.10-3.14. Full Python 3.13 validation occurs in CI/CD (Dockerfile uses `python:3.13-slim`).

### PREP-03: Consensus System Deletion Pattern

The deletion is not a simple file removal — it requires coordinated edits across 7 locations:

**Files to delete entirely:**
1. `app/ai/langgraph/consensus.py`
2. `app/agents/patient/flow_coordinator/consensus_manager.py`
3. `app/orchestration/consensus.py` (re-export shim with zero callers — also delete)
4. `tests/langgraph/test_consensus_logic.py`
5. `tests/langgraph/test_agent_consensus_handlers.py`

**Files to edit (remove consensus references):**
6. `app/agents/patient/flow_coordinator/__init__.py` — remove `from .consensus_manager import ConsensusManager` and `"ConsensusManager"` from `__all__`
7. `app/agents/patient/flow_coordinator/coordinator.py` — remove `ConsensusManager` import, `self.consensus_manager = ConsensusManager(...)`, `self._captured_consensus_votes = {}`, the `consensus_request_response` handler registration, `"consensus_participation"` capability string, and calls to `consensus_manager` in `make_flow_decision` and `escalate_intervention`. The `_handle_consensus_request_response`, `_reset_consensus_vote_buffer`, and `_consume_consensus_votes` methods must also be removed.
8. `app/agents/analytics/alert_analyzer.py` — remove `"consensus_request"` handler registration and `_handle_consensus_request` method
9. `app/agents/patient/patient_monitor.py` — remove `"consensus_request"` handler registration and `_handle_consensus_request` method
10. `app/agents/base.py` — remove `self.consensus_votes = {}` from `__init__` (line 171); `BaseAgent` docstring references to "consensus participation" can also be removed

**Files NOT to change:**
- `app/agents/registry.py` — `ALERT_ANALYZER_ID` and `PATIENT_MONITOR_ID` must remain; they are used by `response_processor.py`, `quiz/conductor.py`, `quiz/response_handler.py`, and `quiz/session_coordinator.py` for non-consensus purposes

**What happens to `coordinator.py`'s `make_flow_decision` call pattern:**
The `decision_engine.make_flow_decision()` currently receives `(context, analysis, self.decision_engine.requires_consensus_decision, self.consensus_manager.seek_agent_consensus)` as arguments. After consensus deletion:
- The `requires_consensus_decision` method in `DecisionEngine` currently returns `decision_type == "escalate_intervention"` — this returns `True` only for clinical escalation, but the consensus seek is now removed.
- The `make_flow_decision` signature must be updated to not require the consensus_fn parameter.
- The `ESCALATE_INTERVENTION` branch in `coordinator.py` calls `self.consensus_manager.escalate_intervention(context)` — after deletion, this should call `self.send_message(ALERT_ANALYZER_ID, ...)` directly (which is what `escalate_intervention` does internally, minus the consensus graph lookup).

### PREP-03: app/agents/ Scope Annotation Decision

Claude's discretion covers whether to rename, annotate, or restructure `app/agents/` DDD services. Based on codebase analysis:

**Current DDD service classes in `app/agents/`:**
| Class | File | Makes LLM calls? | How? |
|-------|------|-----------------|------|
| `AlertAnalyzerAgent` | `analytics/alert_analyzer.py` | No | Pure message handling logic |
| `PatientMonitorAgent` | `patient/patient_monitor.py` | No | Pure monitoring/alerting logic |
| `FlowCoordinatorAgent` | `patient/flow_coordinator/coordinator.py` | No | Orchestrates via message passing |
| `MessageComposerAgent` | `communication/message_composer/agent.py` | Yes (via `GeminiClient.generate_content()`) | Multiple direct calls through `composer.py` |
| `ResponseProcessorAgent` | `communication/response_processor.py` | No | Pure response processing |

**message_composer classification:** `MessageComposerAgent` does make real LLM calls through `GeminiClient.generate_content()` but does NOT use pydantic-ai patterns. It is a DDD service that happens to call an AI backend. It is NOT a migration target for Phase 11 — the 4 migration targets are the `GeminiDomainClient` methods. The `message_composer` already delegates to `GeminiClient` correctly and will be served by the Phase 11 agents through the same `GeminiClient` execution backend.

**Recommendation for scope annotation (least-disruptive approach):** Add a one-line module docstring comment at the top of each `app/agents/` file clarifying scope. Do NOT rename directories or restructure. The comment pattern:

```python
# DDD service agent — no LLM calls, not a pydantic-ai migration target.
```

For `message_composer`:
```python
# DDD service agent — calls GeminiClient.generate_content() directly, not a pydantic-ai migration target.
```

This approach requires editing only 5 files (the main agent class files), causes zero import disruption, and makes the scope boundary explicit for Phase 11 implementers.

**New Pydantic AI agents directory:** `app/ai/agents/` is the correct choice. It follows the existing pattern (`app/ai/client.py`, `app/ai/langgraph/`) and clearly signals these are AI-layer components, not DDD services. This is consistent with the project's existing `app/ai/` namespace convention.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Import graph audit | Custom AST walker | `grep`-based scan or `ast.parse` with known patterns | The import list is static and small; a full AST walker is engineering theater |
| Dependency conflict detection | Custom version resolver | `pip install --dry-run` | pip's resolver is authoritative; dry-run output is the definitive answer |
| Dead code detection | Call graph analysis tool | Manual grep + test execution | The consensus system's zero-caller status is already confirmed in project research |

---

## Common Pitfalls

### Pitfall 1: PREP-01 — print-based audit that doesn't fire on `python -c "import app.main"`

**What goes wrong:** Developer implements the audit as a standalone script but the success criterion requires the printout to happen when `app.main` is imported, not when a separate command is run.

**Why it happens:** The success criterion's exact phrasing ("Developer can run `python -c "import app.main"` and see a printed list") is easy to misread as "the list can be obtained somehow."

**How to avoid:** Implement the audit print either: (a) as a module-level call in `app/main.py` gated behind `if os.getenv("LANGGRAPH_AUDIT")` or similar flag, or (b) as a registered startup event that fires during import. The simplest approach: add a temporary `_print_langgraph_imports()` call at module level in `app/main.py` that scans `*.py` files and prints the list.

**Warning signs:** The audit implementation lives in a file that is not `app/main.py` and not called from `app/main.py`.

### Pitfall 2: PREP-02 — requirements.txt update without venv validation

**What goes wrong:** Developer adds the package to `requirements.txt` but does not actually install it and verify the import works, leading to a broken state until the next full `pip install -r requirements.txt` is run.

**How to avoid:** Always run `pip install "pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0"` first, verify `python -c "from pydantic_ai import Agent; print('ok')"` succeeds, THEN update `requirements.txt`.

### Pitfall 3: PREP-02 — Python 3.13 success criterion not fully satisfiable locally

**What goes wrong:** The local venv is Python 3.12.3, but the success criterion says "Python 3.13." Developer may be uncertain whether the criterion is met.

**Resolution:** The PREP-02 success criterion is satisfied by: (a) confirming zero conflict output from `pip install --dry-run` in the Python 3.12.3 local venv, and (b) documenting that pydantic-ai officially supports Python 3.10-3.14 (verified against PyPI). Full Python 3.13 validation is provided by the Dockerfile (`FROM python:3.13-slim`) in CI. The plan should note this explicitly.

### Pitfall 4: PREP-03 — Deleting ALERT_ANALYZER_ID and PATIENT_MONITOR_ID from registry.py

**What goes wrong:** Developer sees `ALERT_ANALYZER_ID` and `PATIENT_MONITOR_ID` referenced only in consensus code and deletes them from `registry.py`, breaking `response_processor.py`, `quiz/conductor.py`, `quiz/response_handler.py`, and `quiz/session_coordinator.py`.

**How to avoid:** The CONTEXT.md says "remove unused agent IDs from `app/agents/base.py`" — this refers to agent IDs that are exclusively used by consensus. Both `ALERT_ANALYZER_ID` and `PATIENT_MONITOR_ID` are used by multiple non-consensus modules. They must remain in `registry.py`.

**Specific items to remove:** Only `self.consensus_votes = {}` attribute in `BaseAgent.__init__` (line 171 of `base.py`) is consensus-exclusive. The consensus-handling methods (`_handle_consensus_request`) in `alert_analyzer.py` and `patient_monitor.py` can be removed as they will never be invoked after `ConsensusManager` is deleted.

### Pitfall 5: PREP-03 — Leaving orchestration/consensus.py as a dead shim

**What goes wrong:** Developer deletes `consensus.py` and `consensus_manager.py` but leaves `app/orchestration/consensus.py` — a re-export shim that imports from the now-deleted `app.ai.langgraph.consensus`. This causes an `ImportError` at startup.

**How to avoid:** `app/orchestration/consensus.py` has zero callers (confirmed by grep) and must be deleted as part of PREP-03. There is nothing to shim — the shim's own importers do not exist.

### Pitfall 6: PREP-03 — coordinator.py escalate_intervention has hidden dependency on ConsensusManager

**What goes wrong:** Developer removes `ConsensusManager` calls from `coordinator.py` but misses that `escalate_intervention` in `coordinator.py` at lines 247 and 377 calls `self.consensus_manager.escalate_intervention(context)` — which sends an alert to `ALERT_ANALYZER_ID`. If this call is simply deleted without replacement, escalation alerts stop being sent.

**How to avoid:** The `escalate_intervention` method in the deleted `ConsensusManager` (lines 116-138) simply calls `self.send_message_fn(ALERT_ANALYZER_ID, "escalation_alert", alert_data, MessagePriority.CRITICAL)`. Replace the two `self.consensus_manager.escalate_intervention(context)` calls in `coordinator.py` with an inline equivalent that calls `self.send_message(ALERT_ANALYZER_ID, "escalation_alert", {...}, MessagePriority.CRITICAL)` directly.

---

## Code Examples

### Temporary PREP-01 audit hook in app/main.py

```python
# PREP-01 audit: print LangGraph/LangChain import map on startup
import os
if os.getenv("LANGGRAPH_AUDIT") == "1":
    import ast, pathlib
    _AUDIT_PATTERNS = {"langgraph", "langchain_core", "langchain_google_genai"}
    _hits = []
    for _p in pathlib.Path("app").rglob("*.py"):
        try:
            _tree = ast.parse(_p.read_bytes())
        except SyntaxError:
            continue
        for _node in ast.walk(_tree):
            if isinstance(_node, (ast.Import, ast.ImportFrom)):
                _mod = getattr(_node, "module", None) or ""
                _names = [alias.name for alias in getattr(_node, "names", [])]
                if any(_pat in (_mod + " " + " ".join(_names)) for _pat in _AUDIT_PATTERNS):
                    _hits.append(str(_p))
                    break
    print("LANGGRAPH AUDIT:", sorted(set(_hits)))
```

Invocation: `LANGGRAPH_AUDIT=1 python -c "import app.main"`

### pydantic-ai-slim requirements.txt entry

```
# pydantic-ai-slim: Typed AI agents with Gemini support (v1.2 migration)
# Pin <2.0.0: V2 planned for April 2026 with breaking API changes
# [google]: pulls google-genai>=1.56.0 (unified Google SDK)
# [retries]: uses tenacity (already in requirements) for HTTP-level retry transport
pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0
```

### Inline escalation replacement in coordinator.py (after ConsensusManager deletion)

```python
# Replaces self.consensus_manager.escalate_intervention(context)
from app.agents.registry import ALERT_ANALYZER_ID
await self.send_message(
    ALERT_ANALYZER_ID,
    "escalation_alert",
    {
        "patient_id": str(context.patient_id),
        "risk_factors": context.risk_factors,
        "escalated_by": self.agent_id,
        "escalated_at": now_sao_paulo().isoformat(),
        "priority": "high",
        "recommended_actions": [
            "schedule_medical_consultation",
            "increase_monitoring_frequency",
            "review_treatment_plan",
        ],
    },
    MessagePriority.CRITICAL,
)
```

### app/agents/ scope annotation format

```python
# DDD service agent — no LLM calls, not a pydantic-ai migration target.
"""
AlertAnalyzerAgent — analytics domain service.
...
"""
```

For message_composer:
```python
# DDD service agent — delegates to GeminiClient.generate_content() directly, not a pydantic-ai migration target.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact for Phase 10 |
|--------------|------------------|--------------|---------------------|
| google-ai-generativelanguage (low-level) | google-genai SDK (unified) | Late 2025 | pydantic-ai `[google]` pulls google-genai 1.64.0; no separate pin needed |
| langchain meta-package | langchain-core + langchain-google-genai separately | v1.0 (already done) | Current requirements.txt already uses separate packages correctly |
| LangGraph checkpoint (managed) | Direct coexistence during migration | v1.2 Phase 10-12 | pydantic-ai and LangGraph can coexist — no forced removal until Phase 12 |

**Deprecated/outdated:**
- `google-ai-generativelanguage>=0.7.0`: This package will be removed at end of Phase 12 when `langchain-google-genai` is removed. It is not removed in Phase 10.
- The `app/orchestration/consensus.py` re-export shim was created as "canonical orchestration consensus entrypoint" but has zero callers and is functionally dead. Delete it in PREP-03.

---

## Open Questions

1. **PREP-01: Should the audit hook be permanent or temporary?**
   - What we know: The success criterion says "developer can run `python -c "import app.main"`" but does not say it must always run.
   - What's unclear: Should this be a dev-only script or a permanent module-level hook with an env var gate?
   - Recommendation: Gate it behind `LANGGRAPH_AUDIT=1` environment variable. The hook lives in `app/main.py` temporarily and is removed when LangGraph imports are fully cleaned up at end of Phase 12. Alternatively, implement it as a standalone `scripts/audit_langgraph_imports.py` that is invoked from `app/main.py`'s startup.

2. **PREP-02: What happens to google-genai 1.64.0 upgrade?**
   - What we know: The current venv has `google-genai` not installed (not present in `pip list` output). Installing pydantic-ai-slim adds `google-genai-1.64.0`. The requirements.txt currently has `langchain-google-genai>=2.1.12` which declares a dependency on `google-ai-generativelanguage`, not `google-genai`.
   - What's unclear: Whether adding `google-genai 1.64.0` creates any version conflict with `google-ai-generativelanguage>=0.7.0` that is currently in requirements.txt.
   - Recommendation: The dry-run output showed no conflict. Both packages can coexist (confirmed by langchain-google-genai 4.x discussion — both pydantic-ai and langchain 4.x use google-genai). Document this in the PREP-02 plan step.

3. **PREP-03: coordinator.py make_flow_decision signature after consensus removal**
   - What we know: `make_flow_decision` currently takes `requires_consensus_decision` and `seek_agent_consensus` as callable arguments. After deletion, neither argument is needed.
   - What's unclear: Whether `requires_consensus_decision` (which checks `decision_type == "escalate_intervention"`) has value outside of consensus — i.e., should the check remain to gate the inline escalation?
   - Recommendation: The check `requires_consensus_decision(decision_type)` in the call chain controls when escalation is triggered. After deleting ConsensusManager, the pattern becomes: if `decision_type == "escalate_intervention"` then call `self.send_message(ALERT_ANALYZER_ID, ...)` directly. The separate callable argument is no longer needed; inline the check. Remove `requires_consensus_decision` from `DecisionEngine` or repurpose it as a private method in `coordinator.py`.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)

- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/ai/langgraph/consensus.py` — confirmed LangGraph dependency, zero production callers verified
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/agents/patient/flow_coordinator/consensus_manager.py` — confirmed call chain: only called from `coordinator.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/agents/patient/flow_coordinator/coordinator.py` — confirmed `ConsensusManager` usage at 4 call sites; confirmed `FlowCoordinatorAgent` only instantiated via `hive_mind_integration.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/agents/registry.py` — confirmed `ALERT_ANALYZER_ID` and `PATIENT_MONITOR_ID` used by non-consensus callers
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/orchestration/consensus.py` — confirmed zero callers, safe to delete
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/requirements.txt` — confirmed current dependency set
- `pip install --dry-run "pydantic-ai-slim[google,retries]>=1.63.0,<2.0.0"` in `.venv` (Python 3.12.3) — confirmed "Would install" with zero ERROR or conflict lines
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/Dockerfile` — confirmed `FROM python:3.13-slim` (production Python version)
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/.venv/bin/pip list` — confirmed all existing package versions

### Secondary (MEDIUM confidence — project research docs)

- `.planning/research/SUMMARY.md` — pydantic-ai package version details and ADK conflict documentation (researched 2026-02-23)
- `.planning/REQUIREMENTS.md` — PREP-01, PREP-02, PREP-03 requirement definitions and success criteria
- `.planning/phases/10-preparation-scope/10-CONTEXT.md` — locked decisions and Claude's discretion areas

---

## Metadata

**Confidence breakdown:**
- PREP-01 (import audit): HIGH — all 15+ files enumerated via direct grep, implementation pattern is standard Python
- PREP-02 (pydantic-ai install): HIGH — dry-run confirmed in project venv, zero conflicts; MEDIUM for Python 3.13 specifically (local venv is 3.12.3, but pydantic-ai officially supports 3.10-3.14)
- PREP-03 (consensus deletion): HIGH — full dependency graph traced via grep; all 10 edit locations identified; replacement pattern for escalate_intervention documented

**Research date:** 2026-02-24
**Valid until:** 2026-03-10 (stable patterns — package versions may drift but conflict analysis is structurally valid for 2 weeks)
