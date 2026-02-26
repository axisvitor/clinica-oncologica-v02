# Phase 18: Flow Service Splits - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Split the four oversized flow service files (`sequential_message_handler.py` 1,135 lines, `enhanced_flow_engine.py` 1,141 lines, `flow_dashboard.py` 946 lines, `flow_monitoring.py` 923 lines) into focused modules, each under 500 lines. No behavioral changes — pure structural refactor with re-export shims preserving all existing import paths.

</domain>

<decisions>
## Implementation Decisions

### Module boundaries
- Split by **functional cohesion**: group methods that share the same data dependencies and domain concept
- Each resulting module should have a single responsibility expressible in 1 sentence
- Concrete splits derived from method analysis:
  - `sequential_message_handler.py` (1,135 lines, 1 class 30+ methods):
    - **sequencing.py** — `send_day_messages`, `_send_all_sequential`, `_send_wait_each_with_auto_advance`, `_send_message_and_wait`, `_send_remaining_after_response`, `_send_flow_message` (core message orchestration)
    - **state.py** — `_get_or_create_flow_state`, `_set_flow_progress`, `_mark_last_message_sent`, `_resolve_sent_message_id`, `_get_day_config` (flow state management)
    - **personalization.py** — `_personalize_message_ai`, `_personalize_message_simple`, `_personalization_is_grounded`, `_build_fallback_content`, `_select_template_variation`, `_lightly_rephrase_question` (AI content personalization)
    - **quiz.py** — `_inject_quiz_link_if_needed` and related quiz-link logic (quiz integration)
  - `enhanced_flow_engine.py` (1,141 lines, 2 classes):
    - **context.py** — `FlowContext` dataclass + helpers (flow context model)
    - **orchestration.py** — `generate_flow_message` + prompt construction + few-shot examples (AI message generation)
    - **response_processing.py** — `process_patient_response` + engagement scoring + response normalization (patient response handling)
    - **conversation.py** — `_get_conversation_history`, `_get_recent_interactions`, `health_check` (conversation memory + health)
  - `flow_dashboard.py` (946 lines, 1 class + 2 enums):
    - **models.py** — `DashboardTimeframe`, `TrendDirection` enums + any shared types
    - **analytics.py** — `get_dashboard_overview`, `_get_flow_type_breakdown`, `_get_date_range` (dashboard analytics)
    - **trends.py** — `get_patient_engagement_trends`, `_calculate_trends`, `_get_trend_direction`, `_get_daily_engagement_metrics`, `_get_engagement_distribution`, `_get_peak_engagement_times`, `_generate_engagement_insights` (trend analysis)
    - **risk.py** — `get_at_risk_patient_dashboard`, `_analyze_risk_factors`, `_generate_intervention_recommendations`, `_get_risk_trends` (risk detection)
    - **alerts.py** — `get_real_time_alerts`, `_get_recent_alerts`, `_check_no_response_alerts`, `_check_sentiment_alerts`, `_check_performance_alerts`, `_check_engagement_alerts` (dashboard alerting)
    - **optimization.py** — `get_flow_optimization_recommendations`, `_analyze_message_timing`, `_analyze_content_effectiveness`, `_analyze_flow_dropoffs`, `_generate_optimization_recommendations`, `_prioritize_recommendations` (optimization recommendations)
  - `flow_monitoring.py` (923 lines, 1 class + 3 dataclasses):
    - **models.py** — `HealthStatus`, `PerformanceMetrics`, `SystemAlert` (monitoring data models)
    - **metrics.py** — `collect_performance_metrics`, `_update_flow_metrics`, `_get_average_response_time`, `_calculate_error_rate`, `_get_queue_depth`, `_get_redis_memory_usage`, `_get_database_connection_count`, `_count_stale_flows`, `_calculate_corruption_rate` (metrics collection)
    - **health.py** — `get_system_health`, `run_health_checks`, `_determine_health_status`, `_check_database_connectivity`, `_check_redis_connectivity`, `_check_flow_processing_health`, `_check_message_delivery_health`, `_check_data_integrity`, `_check_external_services`, `_get_component_health` (health checks)
    - **alerting.py** — `check_and_create_alerts`, `get_active_alerts`, `resolve_alert`, `_create_alert`, `_send_critical_alert_notification` (alert lifecycle)
    - **trends.py** — `_get_performance_trends`, `_get_message_volume_trend`, `_get_error_rate_trend`, `_get_response_time_trend` (performance trends)

### Package structure
- Follow established `_pkg` suffix convention: `sequential_message_handler_pkg/`, `enhanced_flow_engine_pkg/`, `flow_dashboard_pkg/`, `flow_monitoring_pkg/`
- Each package gets an `__init__.py` that re-exports all public symbols (matching existing `template_loader_pkg` and `automated_recovery_pkg` patterns)
- Flat files inside each package (no nested sub-packages) — keeps structure simple and grep-friendly
- File naming: lowercase, descriptive of the functional concern (e.g., `sequencing.py`, `orchestration.py`, `health.py`)

### Shim & import strategy
- Original file becomes a thin re-export shim: `from package import *  # noqa: F401,F403`
- Shim includes a deprecation docstring: `"""Shim — canonical code lives in {pkg}/. See Phase 18."""`
- `__init__.py` of each package re-exports every public class, function, and constant that the original file exported
- Cross-module dependencies within a package use relative imports (`from .models import ...`)
- External callers continue importing from the original path — zero caller changes required
- `__all__` explicitly defined in each `__init__.py` (matches existing pattern)

### Split prioritization
- Sequence: `flow_monitoring` → `flow_dashboard` → `enhanced_flow_engine` → `sequential_message_handler`
- Rationale: monitoring/dashboard are standalone services with fewer inbound callers (lower risk), engine/handler have more cross-dependencies (benefit from lessons learned)
- Each file is one plan (4 plans total, matching roadmap: 18-01 through 18-04)
- Each plan is independently deployable and testable

### Claude's Discretion
- Exact method grouping adjustments if line counts don't balance well (target: each module 150-400 lines)
- Whether to extract shared utility functions into a `_utils.py` within each package
- Import ordering and organization within `__init__.py` files
- Whether `FlowContext` stays in the engine package or gets promoted to `flow/types.py`
- Handling of any private helper methods that straddle two functional concerns

</decisions>

<specifics>
## Specific Ideas

- Follow the exact same pattern as `template_loader_pkg/`, `automated_recovery_pkg/`, and `critical_error_escalation_pkg/` — these are the established split convention in this codebase
- The `_pkg` suffix distinguishes split packages from original shim files
- Re-export `__all__` in `__init__.py` must be exhaustive — downstream code must not break
- Test imports after each split to verify shim integrity

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-flow-service-splits*
*Context gathered: 2026-02-26*
