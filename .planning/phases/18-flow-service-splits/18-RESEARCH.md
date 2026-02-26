# Phase 18: Flow Service Splits - Research

**Researched:** 2026-02-26
**Domain:** Python module refactoring — monolithic service files split into focused subpackages with backward-compatible re-export shims
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Module boundaries — split by functional cohesion:**
- `sequential_message_handler.py` (1,135 lines):
  - `sequencing.py` — send_day_messages, _send_all_sequential, _send_wait_each_with_auto_advance, _send_message_and_wait, _send_remaining_after_response, _send_flow_message
  - `state.py` — _get_or_create_flow_state, _set_flow_progress, _mark_last_message_sent, _resolve_sent_message_id, _get_day_config
  - `personalization.py` — _personalize_message_ai, _personalize_message_simple, _personalization_is_grounded, _build_fallback_content, _select_template_variation, _lightly_rephrase_question
  - `quiz.py` — _inject_quiz_link_if_needed and related quiz-link logic

- `enhanced_flow_engine.py` (1,141 lines):
  - `context.py` — FlowContext dataclass + helpers
  - `orchestration.py` — generate_flow_message + prompt construction + few-shot examples
  - `response_processing.py` — process_patient_response + engagement scoring + response normalization
  - `conversation.py` — _get_conversation_history, _get_recent_interactions, health_check

- `flow_dashboard.py` (946 lines):
  - `models.py` — DashboardTimeframe, TrendDirection enums + shared types
  - `analytics.py` — get_dashboard_overview, _get_flow_type_breakdown, _get_date_range
  - `trends.py` — get_patient_engagement_trends, _calculate_trends, _get_trend_direction, _get_daily_engagement_metrics, _get_engagement_distribution, _get_peak_engagement_times, _generate_engagement_insights
  - `risk.py` — get_at_risk_patient_dashboard, _analyze_risk_factors, _generate_intervention_recommendations, _get_risk_trends
  - `alerts.py` — get_real_time_alerts, _get_recent_alerts, _check_no_response_alerts, _check_sentiment_alerts, _check_performance_alerts, _check_engagement_alerts
  - `optimization.py` — get_flow_optimization_recommendations, _analyze_message_timing, _analyze_content_effectiveness, _analyze_flow_dropoffs, _generate_optimization_recommendations, _prioritize_recommendations

- `flow_monitoring.py` (923 lines):
  - `models.py` — HealthStatus, PerformanceMetrics, SystemAlert
  - `metrics.py` — collect_performance_metrics, _update_flow_metrics, _get_average_response_time, _calculate_error_rate, _get_queue_depth, _get_redis_memory_usage, _get_database_connection_count, _count_stale_flows, _calculate_corruption_rate
  - `health.py` — get_system_health, run_health_checks, _determine_health_status, _check_database_connectivity, _check_redis_connectivity, _check_flow_processing_health, _check_message_delivery_health, _check_data_integrity, _check_external_services, _get_component_health
  - `alerting.py` — check_and_create_alerts, get_active_alerts, resolve_alert, _create_alert, _send_critical_alert_notification
  - `trends.py` — _get_performance_trends, _get_message_volume_trend, _get_error_rate_trend, _get_response_time_trend

**Package structure:**
- `_pkg` suffix convention: `sequential_message_handler_pkg/`, `enhanced_flow_engine_pkg/`, `flow_dashboard_pkg/`, `flow_monitoring_pkg/`
- Each package gets `__init__.py` re-exporting all public symbols
- Flat files inside each package (no nested sub-packages)
- File naming: lowercase, descriptive functional concern

**Shim & import strategy:**
- Original file becomes thin re-export shim: `from package import *  # noqa: F401,F403`
- Shim includes deprecation docstring: `"""Shim — canonical code lives in {pkg}/. See Phase 18."""`
- `__init__.py` re-exports every public class, function, and constant from the original
- Cross-module deps within package use relative imports (`from .models import ...`)
- `__all__` explicitly defined in each `__init__.py`

**Split prioritization (sequence):**
- `flow_monitoring` → `flow_dashboard` → `enhanced_flow_engine` → `sequential_message_handler`
- Rationale: monitoring/dashboard standalone with fewer callers; engine/handler benefit from lessons learned

### Claude's Discretion

- Exact method grouping adjustments if line counts don't balance (target: each module 150-400 lines)
- Whether to extract shared utility functions into `_utils.py` within each package
- Import ordering and organization within `__init__.py` files
- Whether `FlowContext` stays in engine package or gets promoted to `flow/types.py`
- Handling of private helper methods straddling two functional concerns

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPLIT-01 | `sequential_message_handler.py` (1,135 LOC) split into focused modules | Module boundaries locked in CONTEXT.md; 4 sub-modules identified; shim pattern confirmed |
| SPLIT-02 | `enhanced_flow_engine.py` (1,141 LOC) split into AI orchestration + conversation memory + response processing | Module boundaries locked; 4 sub-modules identified; FlowContext placement decision delegated |
| SPLIT-03 | `flow_dashboard.py` (946 LOC) split into dashboard analytics + trend analysis + risk detection | Module boundaries locked; 6 sub-modules identified; `get_flow_dashboard_service` factory must be shimmed |
| SPLIT-04 | `flow_monitoring.py` (923 LOC) split into metrics + health checks + recovery | Module boundaries locked; 5 sub-modules identified; `AlertSeverity` re-export required for callers in `critical_error_escalation_pkg` |
</phase_requirements>

---

## Summary

Phase 18 is a pure structural refactor: four oversized Python service files are split into focused subpackages with backward-compatible shims at the original import paths. No behavioral changes are permitted. The project already has three completed examples of this exact pattern (`template_loader_pkg/`, `automated_recovery_pkg/`, `critical_error_escalation_pkg/`) plus two Phase 17 subdirectory-within-flow splits (`flow/core/`, `flow/management/`). The research confirms the locked decisions in CONTEXT.md are fully implementable and prescribes exact conventions from existing code.

The key architectural insight is that Phase 18 targets files in `app/services/` (not `app/services/flow/`): `enhanced_flow_engine.py`, `flow_dashboard.py`, and `flow_monitoring.py` live in `app/services/`; only `sequential_message_handler.py` lives in `app/services/flow/`. The `_pkg` suffix convention established for `template_loader_pkg/` etc. applies to the three files in `app/services/`. For `sequential_message_handler.py` in `app/services/flow/`, the appropriate structure is a subdirectory `app/services/flow/sequential_message_handler/` matching the `flow/core/` and `flow/management/` patterns from Phase 17 — or alternatively a `_pkg` directory alongside the existing file. Either works; the CONTEXT.md decision says `_pkg` suffix for all four, so use `app/services/flow/sequential_message_handler_pkg/` with the shim at `app/services/flow/sequential_message_handler.py`.

The split sequence (monitoring → dashboard → engine → handler) is well-chosen: `flow_monitoring` has the narrowest inbound caller surface (tasks/monitoring.py, automated_recovery_pkg, critical_error_escalation_pkg), and `sequential_message_handler` has the widest (5 direct callers plus a task import).

**Primary recommendation:** Follow the `template_loader_pkg` shim-and-package pattern exactly. Create `{name}_pkg/` directory in the same directory as the original file, populate it with focused modules, write exhaustive `__init__.py` with `__all__`, then convert the original file to a one-liner re-export shim.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.12 | Module system, `__init__.py`, `__all__` | Built-in — no external deps needed for structural splits |
| sqlalchemy | 2.x (AsyncSession) | Retained in split modules that own DB queries | Already in use across all four files |
| prometheus_client | existing | Prometheus metrics in flow_monitoring | Already imported at module level in flow_monitoring.py |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| redis | existing | Redis client in flow_monitoring metrics/health | Retained as-is in split modules that need it |
| google-genai / GeminiClient | existing | AI calls in enhanced_flow_engine orchestration module | Stays in orchestration.py |
| ConversationMemory | internal | Conversation history in enhanced_flow_engine | Stays in conversation.py |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `_pkg` suffix convention | Subdirectory without suffix (`flow/sequential_message_handler/`) | Phase 17 used bare subdirectory for `core/` and `management/`; `_pkg` suffix is the explicit convention for `app/services/` level splits to distinguish pkg from shim |
| `from package import *` shim | Explicit named imports in shim | Explicit named imports (used in flow_core.py, flow_management.py) are preferred — they make `__all__` visible and avoid wildcard ambiguity |

**Installation:** No new packages required. This is a pure structural refactor using existing dependencies.

---

## Architecture Patterns

### Recommended Project Structure

For `app/services/` level files (enhanced_flow_engine, flow_dashboard, flow_monitoring):

```
app/services/
├── enhanced_flow_engine.py          # Shim: "from enhanced_flow_engine_pkg import *"
├── enhanced_flow_engine_pkg/
│   ├── __init__.py                  # Exhaustive re-export + __all__
│   ├── context.py                   # FlowContext class + to_dict + _calculate_treatment_day
│   ├── orchestration.py             # generate_flow_message + _get_few_shot_examples + prompts
│   ├── response_processing.py       # process_patient_response + engagement scoring
│   └── conversation.py              # _get_conversation_history + _get_recent_interactions + health_check
│
├── flow_dashboard.py                # Shim
├── flow_dashboard_pkg/
│   ├── __init__.py
│   ├── models.py                    # DashboardTimeframe, TrendDirection enums
│   ├── analytics.py                 # get_dashboard_overview, _get_flow_type_breakdown, _get_date_range
│   ├── trends.py                    # get_patient_engagement_trends + sub-methods
│   ├── risk.py                      # get_at_risk_patient_dashboard + sub-methods
│   ├── alerts.py                    # get_real_time_alerts + _check_* methods
│   └── optimization.py             # get_flow_optimization_recommendations + sub-methods
│
├── flow_monitoring.py               # Shim
└── flow_monitoring_pkg/
    ├── __init__.py
    ├── models.py                    # HealthStatus, PerformanceMetrics, SystemAlert
    ├── metrics.py                   # collect_performance_metrics + metric sub-methods
    ├── health.py                    # get_system_health, run_health_checks, _check_* methods
    ├── alerting.py                  # check_and_create_alerts, get_active_alerts, resolve_alert
    └── trends.py                    # _get_performance_trends + trend sub-methods
```

For `app/services/flow/` level (sequential_message_handler):

```
app/services/flow/
├── sequential_message_handler.py    # Shim
└── sequential_message_handler_pkg/
    ├── __init__.py
    ├── sequencing.py                # Core send orchestration
    ├── state.py                     # Flow state get/create/update
    ├── personalization.py           # AI content personalization
    └── quiz.py                      # Quiz link injection
```

### Pattern 1: Package `__init__.py` — Exhaustive Re-export

**What:** Every public symbol from the original file is imported and listed in `__all__`. Callers importing from the original path continue to work unchanged.

**When to use:** Always for every split package in this phase.

**Example (from `template_loader_pkg/__init__.py`, confirmed existing pattern):**

```python
"""
FlowDashboard package.

Replaces the monolithic ``flow_dashboard.py`` module.
Every public symbol that the old module exported is re-exported here.
"""

from app.services.flow_dashboard_pkg.models import DashboardTimeframe, TrendDirection
from app.services.flow_dashboard_pkg.analytics import FlowDashboardService
from app.services.flow_dashboard_pkg.analytics import get_flow_dashboard_service

__all__ = [
    "DashboardTimeframe",
    "TrendDirection",
    "FlowDashboardService",
    "get_flow_dashboard_service",
]
```

Note: `FlowDashboardService` is a class that aggregates methods from multiple sub-modules — see Pattern 3.

### Pattern 2: Shim File — Explicit Named Re-export

**What:** The original file becomes a thin shim with explicit imports (not wildcard) and a deprecation docstring.

**When to use:** Always for the original `.py` file after extracting the package.

**Example (matches `flow_core.py` and `flow_management.py` shim style — confirmed existing pattern):**

```python
"""Shim — canonical code lives in flow_monitoring_pkg/. See Phase 18."""

from app.services.flow_monitoring_pkg import (
    FlowMonitoringService,
    HealthStatus,
    PerformanceMetrics,
    SystemAlert,
    AlertSeverity,  # re-exported for callers in critical_error_escalation_pkg
)

__all__ = [
    "FlowMonitoringService",
    "HealthStatus",
    "PerformanceMetrics",
    "SystemAlert",
    "AlertSeverity",
]
```

### Pattern 3: Composed Service Class

**What:** When a large class's methods are split across multiple mixin modules, use Python multiple inheritance or a thin composer class in `service.py`.

**When to use:** When the original class has too many methods to keep in one file but callers reference the class by name (not individual mixins).

**Example (matches `flow/core/service.py` and `flow/management/service.py` — confirmed existing pattern):**

```python
# enhanced_flow_engine_pkg/service.py
from .context import FlowContextMixin
from .orchestration import FlowOrchestrationMixin
from .response_processing import FlowResponseMixin
from .conversation import FlowConversationMixin

class EnhancedFlowEngine(
    FlowOrchestrationMixin,
    FlowResponseMixin,
    FlowConversationMixin,
    FlowContextMixin,
    FlowCore,  # preserved base class
):
    """Composed engine preserving legacy contract."""
```

**DECISION POINT:** `EnhancedFlowEngine` inherits from `FlowCore` — the mixin pattern is the right approach to preserve the inheritance chain. For `sequential_message_handler`, `FlowDashboardService`, and `FlowMonitoringService` (which do NOT use inheritance), the split can use standalone modules with the service class reassembled in `service.py` or directly in `__init__.py`.

### Pattern 4: Cross-Module Relative Imports Within Package

**What:** Modules within the same `_pkg` package use relative imports to reference each other.

**When to use:** When a module in the split package needs a type or constant from a sibling module.

```python
# In flow_monitoring_pkg/health.py
from .models import HealthStatus, PerformanceMetrics
from .metrics import collect_performance_metrics_impl  # if extracted to helper
```

**Critical:** Never use absolute imports (`from app.services.flow_monitoring_pkg.models import ...`) inside the package itself — always use relative imports (`from .models import ...`).

### Pattern 5: Contract Test — Shim Identity + Line Count Guard

**What:** A contract test verifying (1) the shim resolves to the same object as the canonical module, (2) all split files stay under 500 lines.

**When to use:** One contract test file per split, following `test_flow_core_split_contract.py` and `test_flow_management_split_contract.py` patterns.

**Example:**

```python
# tests/unit/services/test_flow_monitoring_split_contract.py
from pathlib import Path
from app.services.flow_monitoring_pkg.service import FlowMonitoringService as CanonicalService
from app.services.flow_monitoring import FlowMonitoringService as ShimService

def test_shim_resolves_to_canonical():
    assert ShimService is CanonicalService

def test_split_files_under_500_lines():
    root = Path(__file__).resolve().parents[3]
    files = [
        root / "app/services/flow_monitoring_pkg/models.py",
        root / "app/services/flow_monitoring_pkg/metrics.py",
        root / "app/services/flow_monitoring_pkg/health.py",
        root / "app/services/flow_monitoring_pkg/alerting.py",
        root / "app/services/flow_monitoring_pkg/trends.py",
    ]
    for f in files:
        lines = len(f.read_text(encoding="utf-8").splitlines())
        assert lines < 500, f"{f} has {lines} lines"
```

### Anti-Patterns to Avoid

- **Wildcard shim (`from pkg import *`):** The existing `flow_core.py` and `flow_management.py` shims use explicit named imports — follow that precedent. Wildcard imports hide what is exported and break IDE navigation.
- **Circular imports:** `enhanced_flow_engine` is already imported by `flow_management/service.py` and multiple callers. When splitting, the `context.py` module must NOT import from the service module — keep `FlowContext` independent.
- **Absolute imports inside the package:** Modules inside `*_pkg/` must use `from .module import X`, not `from app.services.*_pkg.module import X`.
- **Forgetting to re-export factory functions:** `flow_dashboard.py` has `get_flow_dashboard_service()`, `enhanced_flow_engine.py` has `get_enhanced_flow_engine()` and `test_enhanced_flow_engine()`. These MUST appear in both the `__init__.py` and the shim `__all__`.
- **Forgetting `AlertSeverity` in `flow_monitoring` shim:** `critical_error_escalation_pkg` imports `AlertSeverity` from `app.services.flow_monitoring` (not from `app.models.alert` directly). The shim must re-export it.
- **Breaking the `FlowType` re-export from `enhanced_flow_engine`:** `transition_handler.py` and `manual_correction.py` do `from app.services.enhanced_flow_engine import FlowType`. `FlowType` is imported (not defined) in the original file — the shim must pass it through.
- **Prometheus module-level globals:** `flow_monitoring.py` defines four Prometheus metrics at module level (`Gauge`, `Counter`, `Histogram`). These must be defined in `metrics.py` and re-exported via `__init__.py` and the shim — they cannot be duplicated or they will register twice.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Import compatibility after split | Custom import hooks or `sys.modules` patching | Re-export shim with explicit `__all__` | The project's established pattern; no runtime magic needed |
| Checking shim integrity | Manual testing | Contract test with `assert ShimClass is CanonicalClass` | Automated, runs in CI, already established in `test_flow_core_split_contract.py` |
| Cross-module method resolution | Copy-paste method bodies | Mixin inheritance or composition in `service.py` | Keeps behavior identical, no duplication |

**Key insight:** Python's import system makes the shim pattern trivially reliable — `from pkg.module import X` and `from shim_file import X` both return the same object if the shim imports from the package. No custom infrastructure needed.

---

## Common Pitfalls

### Pitfall 1: Prometheus Double-Registration

**What goes wrong:** `flow_monitoring.py` defines `Gauge` and `Counter` at module level. If these definitions appear in two places (e.g., both `metrics.py` and the shim), Prometheus raises `ValueError: Duplicated timeseries` at import time.

**Why it happens:** Prometheus metrics are registered globally on first definition. Importing the same variable name twice from different modules creates two registration attempts.

**How to avoid:** Define Prometheus metrics exactly once in `flow_monitoring_pkg/metrics.py`. Re-export via `__init__.py` and shim as variable references — never redefine.

**Warning signs:** `ValueError: Duplicated timeseries` at test collection time or service startup.

### Pitfall 2: Missed Re-export Breaks Caller at Import Time

**What goes wrong:** A caller does `from app.services.flow_monitoring import AlertSeverity` — if `AlertSeverity` is not in the shim's `__all__` and not explicitly imported, the caller gets `ImportError` immediately.

**Why it happens:** `flow_monitoring.py` currently re-exports `AlertSeverity` implicitly (it's imported as a name in the module). The shim must explicitly import and re-export it.

**How to avoid:** Audit every name imported by external callers from each file before creating the shim. In this phase, the critical ones are:
- `flow_monitoring.py` → `AlertSeverity`, `FlowMonitoringService`, `HealthStatus`, `PerformanceMetrics`, `SystemAlert`
- `flow_dashboard.py` → `FlowDashboardService`, `DashboardTimeframe`, `TrendDirection`, `get_flow_dashboard_service`
- `enhanced_flow_engine.py` → `EnhancedFlowEngine`, `FlowContext`, `FlowType` (re-exported from `flow.types`), `get_enhanced_flow_engine`, `test_enhanced_flow_engine`
- `flow/sequential_message_handler.py` → `SequentialMessageHandler`, `get_sequential_message_handler`

**Warning signs:** `ImportError: cannot import name 'X' from 'app.services.Y'` in test output.

### Pitfall 3: `FlowContext` Name Collision

**What goes wrong:** There are THREE `FlowContext` classes in this codebase:
1. `app.services.enhanced_flow_engine.FlowContext` (the one being split) — a plain Python class
2. `app.services.flow.types.FlowContext` (Pydantic BaseModel)
3. `app.agents.patient.flow_coordinator.models.FlowContext` (coordinator-specific)

**Why it happens:** Multiple independent abstractions use the same name. External callers reference `from app.services.enhanced_flow_engine import FlowContext` — this must remain stable.

**How to avoid:** Keep `FlowContext` (the engine version) in `context.py` within `enhanced_flow_engine_pkg/`. Do NOT promote it to `flow/types.py` (that would merge two distinct types). The shim must re-export it explicitly.

**Warning signs:** `AttributeError` or wrong type being used where callers expect `enhanced_flow_engine.FlowContext`.

### Pitfall 4: `EnhancedFlowEngine` Inheritance Chain Breaks

**What goes wrong:** `EnhancedFlowEngine` inherits from `FlowCore`. When split into mixins, if the mixin classes don't all call `super().__init__()` correctly (or the composition order is wrong), `FlowCore.__init__` may not be called.

**Why it happens:** Python MRO with multiple mixins requires cooperative `super()` calls.

**How to avoid:** If using the mixin pattern, keep `__init__` only in the leaf composer class (`service.py`), not in mixins. Each mixin should only define methods that don't need `__init__`. The composer `EnhancedFlowEngine` in `service.py` inherits from mixins AND `FlowCore` and calls `super().__init__()` once.

**Warning signs:** `TypeError: __init__() got unexpected keyword argument` or attributes not set on `self`.

### Pitfall 5: Circular Import in Sequencing Split

**What goes wrong:** `sequential_message_handler.py` has a `TYPE_CHECKING` guard for `EnhancedFlowEngine` and a lazy `_get_ai_engine()` method. If `sequencing.py` imports from `personalization.py` and `personalization.py` imports from `sequencing.py`, circular import occurs.

**Why it happens:** The original class has all methods in one scope — splitting by concern can create implicit data dependencies.

**How to avoid:** `SequentialMessageHandler` is a single class. Keep it as a single class in `service.py` (or keep `__init__` and shared attributes there). Extract method implementations to mixins. Alternatively, since the handler methods are mostly independent, each split module can define a mixin that the composer in `service.py` assembles.

**Warning signs:** `ImportError: cannot import name 'X'` with circular import traceback.

---

## Code Examples

Verified patterns from existing codebase:

### Shim File Pattern (source: `app/services/flow_core.py`)

```python
"""Compatibility shim for FlowCore split modules."""

from app.services.flow.core.service import (
    FLOW_ADVANCE_BLOCKED_CODE,
    FLOW_ADVANCE_BLOCKED_MESSAGE,
    FLOW_ADVANCE_BLOCKED_REASON,
    FlowCore,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "FLOW_ADVANCE_BLOCKED_CODE",
    "FLOW_ADVANCE_BLOCKED_MESSAGE",
    "FLOW_ADVANCE_BLOCKED_REASON",
    "FlowCore",
    "NotFoundError",
    "ValidationError",
]
```

### Package `__init__.py` Pattern (source: `app/services/template_loader_pkg/__init__.py`)

```python
"""
DB-only template loader package with versioning support.

This package replaces the monolithic ``template_loader.py`` module.
Every public symbol that the old module exported is re-exported here so
that ``from app.services.template_loader_pkg import X`` works identically.
"""

from app.services.template_loader_pkg.models import (
    MessageType, MessageTemplate, ...
)
from app.services.template_loader_pkg.loader import EnhancedTemplateLoader

__all__ = [
    "MessageType",
    "MessageTemplate",
    ...
    "EnhancedTemplateLoader",
]
```

### Contract Test Pattern (source: `tests/unit/services/test_flow_core_split_contract.py`)

```python
from pathlib import Path
from app.services.flow.core.service import FlowCore as CanonicalFlowCore
from app.services.flow_core import FlowCore as ShimFlowCore

def test_legacy_flow_core_import_points_to_canonical_service() -> None:
    assert ShimFlowCore is CanonicalFlowCore

def test_flow_core_split_files_stay_under_500_lines() -> None:
    root = Path(__file__).resolve().parents[3]
    files = [
        root / "app/services/flow/core/operations.py",
        ...
    ]
    for file_path in files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 500, f"{file_path} has {line_count} lines"
```

### Mixin Composer Pattern (source: `app/services/flow/core/service.py`)

```python
from .operations import FlowCoreOperationsMixin
from .template_binding import FlowCoreTemplateBindingMixin
from .transitions import FlowCoreTransitionsMixin

class FlowCore(
    FlowCoreTransitionsMixin,
    FlowCoreTemplateBindingMixin,
    FlowCoreOperationsMixin,
):
    """Composed flow core service preserving legacy contract."""

__all__ = ["FlowCore", ...]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monolithic `template_loader.py` | `template_loader_pkg/` + shim | Phase pre-17 | Established `_pkg` pattern |
| Monolithic `automated_recovery.py` | `automated_recovery_pkg/` + shim | Phase pre-17 | Same pattern |
| Monolithic `flow_core.py` | `flow/core/` subdirectory + shim | Phase 17 | Confirms subdirectory approach works too |
| Monolithic `flow_management.py` | `flow/management/` subdirectory + shim | Phase 17 | Mixin composer pattern established |

**Phase 18 adds:** Four more splits following the same patterns. The `_pkg` suffix convention (not bare subdirectory) is specified by CONTEXT.md for all four.

---

## Caller Surface Analysis

### `sequential_message_handler.py` callers (WIDE — highest risk)

| Caller | Import Style | Risk |
|--------|-------------|------|
| `app/tasks/flow_automation.py` | Top-level: `from app.services.flow.sequential_message_handler import SequentialMessageHandler` | Must work via shim |
| `app/agents/patient/flow_coordinator/coordinator.py` | Lazy: inside method | Shim works |
| `app/services/hive_mind_integration.py` | Lazy: inside method | Shim works |
| `app/services/response_processor/processor.py` | Lazy: inside method | Shim works |
| `app/services/webhook/handlers/message_handler.py` | Lazy: inside method | Shim works |

### `enhanced_flow_engine.py` callers (WIDE — many importers)

| Caller | What They Import | Risk |
|--------|-----------------|------|
| `app/api/v2/flows/advanced.py` | `EnhancedFlowEngine` | High — top-level import |
| `app/api/v2/routers/flows.py` | `EnhancedFlowEngine`, `get_flow_dashboard_service` | High |
| `app/api/v2/routers/patients/flow.py` | `get_enhanced_flow_engine` | High |
| `app/agents/patient/flow_coordinator/transition_handler.py` | `FlowType` (re-exported) | Critical — wrong FlowType would be silent |
| `app/services/manual_correction.py` | `FlowType` | Must re-export |
| `app/services/flow_management.py` (shim) | `EnhancedFlowEngine` | Must work |
| `app/service_provider.py` | `EnhancedFlowEngine` | Top-level |
| `app/services/flow/management/service.py` | `EnhancedFlowEngine` | Top-level |
| `app/domain/quizzes/...` | `get_enhanced_flow_engine`, `FlowType` | Multiple |
| `app/tasks/flow_automation.py` | `get_enhanced_flow_engine` | Top-level |

### `flow_dashboard.py` callers (NARROW)

| Caller | What They Import |
|--------|-----------------|
| `app/api/v2/flows/analytics.py` | `DashboardTimeframe`, `get_flow_dashboard_service` |
| `app/api/v2/routers/flows.py` | `get_flow_dashboard_service` |
| `app/services/flow_service.py` | `FlowDashboardService` |

### `flow_monitoring.py` callers (MEDIUM — critical for escalation)

| Caller | What They Import |
|--------|-----------------|
| `app/tasks/monitoring.py` | `FlowMonitoringService` |
| `app/services/automated_recovery_pkg/assessment.py` | `FlowMonitoringService` |
| `app/services/automated_recovery_pkg/service.py` | `FlowMonitoringService` |
| `app/services/critical_error_escalation_pkg/models.py` | `AlertSeverity` |
| `app/services/critical_error_escalation_pkg/serialization.py` | `AlertSeverity` |
| `app/services/critical_error_escalation_pkg/service.py` | `FlowMonitoringService`, `AlertSeverity` |
| `app/services/__init__.py` | `FlowMonitoringService` (lazy registry) |

**Critical finding:** `AlertSeverity` is defined in `app.models.alert` but imported and re-exported by `flow_monitoring.py`. The split must preserve this re-export in `flow_monitoring_pkg/__init__.py` AND in the `flow_monitoring.py` shim.

---

## Open Questions

1. **`FlowContext` placement in `enhanced_flow_engine_pkg`**
   - What we know: CONTEXT.md designates `context.py` inside the package
   - What's unclear: Whether to also register `FlowContext` in `flow/types.py` as a canonical type (CONTEXT.md marks this as Claude's discretion)
   - Recommendation: Keep `FlowContext` only in `enhanced_flow_engine_pkg/context.py` and shim it through `enhanced_flow_engine.py`. Do NOT add to `flow/types.py` — that risks conflating it with `flow.types.FlowContext` (a Pydantic BaseModel).

2. **`EnhancedFlowEngine` split approach: mixin vs. single module**
   - What we know: The class has 2 top-level classes (`FlowContext`, `EnhancedFlowEngine`) and ~20 methods across 4 functional areas
   - What's unclear: Whether methods can cleanly become mixins given `FlowCore` base class
   - Recommendation: Use the mixin pattern matching `flow/core/service.py`. Each split module (`orchestration.py`, `response_processing.py`, `conversation.py`) defines a mixin. `service.py` composes them with `FlowCore` as base. `context.py` is standalone (not a mixin). This exactly mirrors Phase 17.

3. **`_calculate_engagement_score` and `_normalize_response_context` in enhanced_flow_engine**
   - What we know: Both methods are used by `process_patient_response` and `generate_flow_message`
   - What's unclear: Whether they belong in `orchestration.py` or `response_processing.py` or `_utils.py`
   - Recommendation: Put in `response_processing.py` since engagement scoring is an input to response handling; add `_utils.py` only if both orchestration and response_processing need them.

---

## Validation Architecture

Note: `workflow.nyquist_validation` is not set in `.planning/config.json` (absent = false). This section is included for completeness since Phase 17 established contract tests for every split.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.4 |
| Config file | `backend-hormonia/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend-hormonia && python -m pytest tests/unit/services/test_flow_monitoring_split_contract.py -x -q` |
| Full suite command | `cd backend-hormonia && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPLIT-01 | `sequential_message_handler.py` shim resolves to canonical; all split files < 500 lines | unit (contract) | `pytest tests/unit/services/flow/test_sequential_message_handler_split_contract.py -x` | ❌ Wave 0 |
| SPLIT-02 | `enhanced_flow_engine.py` shim resolves to canonical; all split files < 500 lines | unit (contract) | `pytest tests/unit/services/test_enhanced_flow_engine_split_contract.py -x` | ❌ Wave 0 |
| SPLIT-03 | `flow_dashboard.py` shim resolves to canonical; all split files < 500 lines | unit (contract) | `pytest tests/unit/services/test_flow_dashboard_split_contract.py -x` | ❌ Wave 0 |
| SPLIT-04 | `flow_monitoring.py` shim resolves to canonical; all split files < 500 lines | unit (contract) | `pytest tests/unit/services/test_flow_monitoring_split_contract.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** Contract test for the specific split just completed
- **Per wave merge:** All four contract tests green
- **Phase gate:** Full `pytest tests/unit/services/ -q` green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/services/test_flow_monitoring_split_contract.py` — covers SPLIT-04
- [ ] `tests/unit/services/test_flow_dashboard_split_contract.py` — covers SPLIT-03
- [ ] `tests/unit/services/test_enhanced_flow_engine_split_contract.py` — covers SPLIT-02
- [ ] `tests/unit/services/flow/test_sequential_message_handler_split_contract.py` — covers SPLIT-01

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection — `app/services/template_loader_pkg/__init__.py` — `_pkg` shim pattern
- Direct codebase inspection — `app/services/flow_core.py` — explicit-import shim pattern
- Direct codebase inspection — `app/services/flow_management.py` — shim with extra re-exported names
- Direct codebase inspection — `app/services/flow/core/service.py` — mixin composer pattern
- Direct codebase inspection — `app/services/flow/management/service.py` — mixin composer with base class
- Direct codebase inspection — `tests/unit/services/test_flow_core_split_contract.py` — contract test pattern
- Direct codebase inspection — `tests/unit/services/test_flow_management_split_contract.py` — contract test pattern
- Direct codebase inspection — all four target files (actual line counts, method lists, top-level exports)
- Direct codebase inspection — all caller files (grep for import patterns)

### Secondary (MEDIUM confidence)

- Python documentation on `__all__`, module re-exports, and import system — standard language behavior

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all patterns verified from codebase
- Architecture: HIGH — three existing `_pkg` splits and two Phase 17 subdirectory splits provide complete templates
- Pitfalls: HIGH — Prometheus double-registration, AlertSeverity re-export, and FlowType collision all verified by grep of actual imports
- Caller surface: HIGH — grep confirmed all callers and import styles

**Research date:** 2026-02-26
**Valid until:** Stable — no external dependencies; valid until codebase structure changes
