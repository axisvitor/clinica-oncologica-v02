---
id: M001
provides:
  - Bounded sequential-gate mismatch recovery, retryable outbound and deferred follow-up delivery, atomic day advancement, and fail-fast template day_config validation
  - Periodic stalled-flow detection and auto-recovery plus admin reset/advance/unstick/failed-ops tooling
  - Flow health and stall alert APIs, AI fallback Prometheus metrics, correlation tracing, and end-to-end pipeline/recovery integration coverage
key_decisions:
  - "Kept mismatch recovery bounded via context_mismatch_count and reset semantics instead of clearing awaiting_response on the first mismatch."
  - "Reused Redis idempotency plus existing resend/day-advance services for stalled-flow recovery instead of introducing a separate transport."
  - "Derived operator visibility from live PatientFlowState and step_data markers rather than adding a new failure table."
  - "Verified the pipeline through the real seams that exist today: direct WuzAPI ingress, sequential handler continuation, and Celery task .run() entry points."
patterns_established:
  - "Pipeline failures now converge into explicit retry, reset, skip, or terminal-failure markers instead of silent stalls."
  - "Admin flow observability and recovery surfaces follow the existing admin_extensions pattern: auth, rate limits, response schemas, and audit logging."
  - "Phase-level verification favors real database-backed integration tests and task entry points over mocked orchestration seams."
observability_surfaces:
  - "/admin-ext/flow-health/"
  - "/admin-ext/flow-health/check-stalls"
  - "/admin-ext/flow-ops/*"
  - "ai_personalization_fallback_total"
  - "structured stall/reset/correlation logs and PatientFlowState.step_data failure markers"
requirement_outcomes:
  - id: FLOW-01
    from_status: active
    to_status: validated
    proof: "S01 added bounded context mismatch recovery in sequential_response_gate/_flow_response_flow with passing unit coverage in backend-hormonia/tests/unit/services/flow/test_sequential_gate_mismatch_recovery.py."
  - id: FLOW-02
    from_status: active
    to_status: validated
    proof: "S01 added retry_failed_flow_send plus enqueue wiring, with unit coverage in backend-hormonia/tests/unit/tasks/test_send_retry_task.py and integration coverage in tests/integration/test_flow_recovery_retry_e2e.py."
  - id: FLOW-03
    from_status: active
    to_status: validated
    proof: "S01 added retry_failed_followup_send and scheduler-backed retry enqueueing, covered by backend-hormonia/tests/unit/tasks/test_followup_retry_task.py and test_flow_recovery_retry_e2e.py."
  - id: FLOW-04
    from_status: active
    to_status: validated
    proof: "S01 routed day completion through advance_day_atomic() with verification metadata, covered by backend-hormonia/tests/unit/services/test_day_advancement_atomic.py and pipeline integration assertions."
  - id: FLOW-05
    from_status: active
    to_status: validated
    proof: "S01 introduced validate_day_config()/DayConfigValidationError and fail-fast flow start behavior, covered by backend-hormonia/tests/unit/services/flow/test_day_config_validation.py and test_flow_pipeline_e2e.py."
  - id: RECV-01
    from_status: active
    to_status: validated
    proof: "S02 added the detect_stuck_flows periodic Celery task, settings, and 900-second beat schedule with focused tests in backend-hormonia/tests/unit/tasks/test_stuck_detection.py."
  - id: RECV-02
    from_status: active
    to_status: validated
    proof: "S02 implemented bounded resend/day-advance auto-recovery in app/services/flow/recovery.py with unit coverage in test_flow_recovery.py and task-level integration coverage in test_flow_recovery_retry_e2e.py."
  - id: RECV-03
    from_status: active
    to_status: validated
    proof: "S02 added admin reset, advance, and unstick endpoints under /admin-ext/flow-ops with unit coverage in backend-hormonia/tests/unit/api/test_admin_flow_ops.py."
  - id: RECV-04
    from_status: active
    to_status: validated
    proof: "S02 exposed failed flow operations from persisted PatientFlowState.step_data markers via the /admin-ext/flow-ops/failed endpoint and covered pagination/mapping in test_admin_flow_ops.py."
  - id: OBS-01
    from_status: active
    to_status: validated
    proof: "S03 added FlowHealthService plus /admin-ext/flow-health/ with active/stalled/failed/completed counts, covered by test_flow_health.py and test_admin_flow_health.py."
  - id: OBS-02
    from_status: active
    to_status: validated
    proof: "S03 added structured stalled-flow alerts and optional webhook fan-out via /admin-ext/flow-health/check-stalls, covered by backend-hormonia/tests/unit/services/flow/test_flow_health.py."
  - id: OBS-03
    from_status: active
    to_status: validated
    proof: "S03 added ai_personalization_fallback_total with reason labels and covered it in backend-hormonia/tests/unit/services/flow/test_flow_metrics.py."
  - id: OBS-04
    from_status: active
    to_status: validated
    proof: "S03 propagated correlation IDs from WuzAPI ingress through webhook handling, continuation, and send logs, covered by backend-hormonia/tests/unit/integrations/test_wuzapi_correlation_id.py and tests/integrations/wuzapi/test_wuzapi_webhook.py."
  - id: TEST-01
    from_status: active
    to_status: validated
    proof: "S04 added backend-hormonia/tests/integration/test_flow_pipeline_e2e.py and verified it with WHATSAPP_WUZAPI_TOKEN=test-token ./.venv/bin/python -m pytest tests/integration/test_flow_pipeline_e2e.py -q."
  - id: TEST-02
    from_status: active
    to_status: validated
    proof: "S04 added stuck-flow detection and auto-recovery integration coverage in backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py and verified it with the focused pytest command recorded in the slice summary."
  - id: TEST-03
    from_status: active
    to_status: validated
    proof: "S04 covered outbound send retry and deferred follow-up retry success/backoff/exhaustion in backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py, plus a combined run with test_flow_pipeline_e2e.py."
duration: 83m
verification_result: passed
completed_at: 2026-03-06
---

# M001: Bulletproof Flow Pipeline

**Patient flow execution is now resilient, recoverable, observable, and end-to-end verified from webhook ingress through retries and stalled-flow recovery.**

## What Happened

M001 closed the main reliability gap in the oncology follow-up pipeline: patients could previously get stuck silently when response correlation, outbound delivery, deferred follow-ups, or day advancement failed. S01 hardened the core delivery path with bounded sequential-gate mismatch recovery, Celery-backed retry tasks for failed sends, atomic verified day advancement, and fail-fast day_config validation. That converted previously silent failure modes into explicit retry, reset, or terminal-failure states.

S02 then added continuous recovery on top of that hardened pipeline. A periodic Celery Beat detector now finds stale awaiting-response flows, re-reads state under Redis-backed idempotency, and attempts bounded resend or day-advance recovery. Operators also gained direct admin tools to reset, advance, unstick, and inspect failed flows without touching the database manually.

S03 made the whole path observable. Flow health counts and stalled-flow alerting now expose active, stalled, failed, and completed flow counts in real time, while AI personalization fallbacks emit Prometheus reason metrics and WuzAPI correlation IDs propagate from ingress through continuation and outbound send logs. Operators can now see both aggregate health and individual broken-flow markers.

S04 proved the milestone at the integration layer. The project now has selectable end-to-end coverage for WuzAPI ingress, sequential continuation, mismatch reset, config validation, atomic day completion, stuck-flow detection and recovery, outbound retry, and deferred follow-up retry. Together, the four slices turned the flow pipeline from best-effort into an operationally recoverable system with evidence-backed coverage.

## Cross-Slice Verification

- **Success criterion: sequential gate context mismatches recover via bounded retry/reset instead of silently stalling patients.** Verified by S01 unit coverage in `backend-hormonia/tests/unit/services/flow/test_sequential_gate_mismatch_recovery.py`, plus S04 integration regression coverage in `backend-hormonia/tests/integration/test_flow_pipeline_e2e.py` for the mismatch reset path.
- **Success criterion: failed outbound sends and deferred follow-ups retry automatically, and day advancement is atomic and verified.** Verified by S01 focused tests in `backend-hormonia/tests/unit/tasks/test_send_retry_task.py`, `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py`, and `backend-hormonia/tests/unit/services/test_day_advancement_atomic.py`, plus S04 retry integration coverage in `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py`.
- **Success criterion: stalled flows are detected/recovered automatically, while operators can inspect and intervene through admin APIs.** Verified by S02 service/task coverage in `backend-hormonia/tests/unit/services/flow/test_flow_recovery.py` and `backend-hormonia/tests/unit/tasks/test_stuck_detection.py`, plus admin endpoint coverage in `backend-hormonia/tests/unit/api/test_admin_flow_ops.py`.
- **Success criterion: flow health, stall alerts, AI fallback metrics, and correlation IDs make the pipeline observable end-to-end.** Verified by S03 coverage in `backend-hormonia/tests/unit/services/flow/test_flow_health.py`, `backend-hormonia/tests/unit/api/test_admin_flow_health.py`, `backend-hormonia/tests/unit/services/flow/test_flow_metrics.py`, `backend-hormonia/tests/unit/integrations/test_wuzapi_correlation_id.py`, and `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py`.
- **Success criterion: integration tests prove the webhook -> gate -> continuation -> send pipeline plus recovery/retry paths.** Verified by S04 commands: `WHATSAPP_WUZAPI_TOKEN=test-token ./.venv/bin/python -m pytest tests/integration/test_flow_pipeline_e2e.py -q`, `WHATSAPP_WUZAPI_TOKEN=test-token ./.venv/bin/python -m pytest tests/integration/test_flow_recovery_retry_e2e.py -q`, and the combined run of both integration files.
- **Definition of done check:** The roadmap showed all slices complete (`S01`-`S04` marked `[x]` in the preloaded roadmap context), `ls` confirmed all four slice summary files exist under `.gsd/milestones/M001/slices/`, and the cross-slice integration points are covered by the two passing integration suites in `backend-hormonia/tests/integration/`.
- **Unmet criteria:** None.

## Requirement Changes

- FLOW-01: active → validated — Bounded context mismatch recovery shipped in S01 with passing unit and integration regression coverage.
- FLOW-02: active → validated — Failed outbound sends now enqueue Celery retries with backoff; covered by unit and integration tests.
- FLOW-03: active → validated — Deferred follow-up send failures now retry via task queue; covered by unit and integration tests.
- FLOW-04: active → validated — Day completion now uses `advance_day_atomic()` with verification metadata; covered by focused unit tests and pipeline integration assertions.
- FLOW-05: active → validated — Malformed `day_config` now fails fast with explicit validation errors; covered by unit and integration tests.
- RECV-01: active → validated — Periodic stuck-flow detection task and beat schedule shipped in S02.
- RECV-02: active → validated — Automatic resend/day-advance recovery logic shipped in S02 with unit and integration evidence.
- RECV-03: active → validated — Admin reset/advance/unstick APIs shipped in S02 with router tests.
- RECV-04: active → validated — Failed flow operations are now visible through admin APIs backed by persisted `step_data` markers.
- OBS-01: active → validated — Flow health summary endpoint shipped in S03 with service and router tests.
- OBS-02: active → validated — Stalled-flow alerting with structured logs and optional webhook shipped in S03.
- OBS-03: active → validated — AI fallback rate is now observable via `ai_personalization_fallback_total`.
- OBS-04: active → validated — Correlation IDs now propagate from WuzAPI ingress through continuation and send logs.
- TEST-01: active → validated — End-to-end pipeline coverage shipped in `backend-hormonia/tests/integration/test_flow_pipeline_e2e.py`.
- TEST-02: active → validated — Stuck-flow detection and auto-recovery coverage shipped in `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py`.
- TEST-03: active → validated — Retry mechanics for outbound and deferred follow-up sends are covered by the same integration suite.

## Forward Intelligence

### What the next milestone should know
- The real production seams are split: `wuzapi_webhook()` validates ingress and correlation, while continuation/day advancement happens elsewhere. Future work should test and instrument those seams directly instead of assuming a single route owns the full flow.

### What's fragile
- `PatientFlowState.step_data` now carries multiple recovery and observability markers (`context_mismatch_count`, delivery failures, mismatch reset timestamps, recovery attempts). Any schema drift here can break recovery, health counts, and admin failed-op visibility at once.

### Authoritative diagnostics
- Start with `backend-hormonia/tests/integration/test_flow_pipeline_e2e.py` and `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py` for behavioral truth, then use `/admin-ext/flow-health/` and `/admin-ext/flow-ops/failed` for live-state inspection because they surface the exact markers the recovery pipeline writes.

### What assumptions changed
- The original assumption was that webhook ingress could be verified as a single end-to-end path. In practice, the current codebase splits webhook normalization from sequential continuation, so the correct verification strategy is two real-surface integration tests rather than one artificially coupled route test.

## Files Created/Modified

- `backend-hormonia/app/tasks/flows/send_retry.py` — Added Celery retry orchestration for failed outbound flow sends with bounded backoff and permanent-failure recording.
- `backend-hormonia/app/tasks/flows/followup_retry.py` — Added deferred follow-up retry execution and terminal failure bookkeeping.
- `backend-hormonia/app/services/flow/recovery.py` — Added stalled-flow detection, bounded recovery decisions, Redis idempotency, and manual-escalation markers.
- `backend-hormonia/app/services/flow/health.py` — Added real-time flow health counts and structured stalled-flow alert fan-out.
- `backend-hormonia/app/api/v2/routers/admin_extensions/flow_ops.py` — Added operator reset/advance/unstick/failed-flow APIs.
- `backend-hormonia/app/api/v2/routers/admin_extensions/flow_health.py` — Added operator flow health summary and stall-check APIs.
- `backend-hormonia/tests/integration/test_flow_pipeline_e2e.py` — Added end-to-end pipeline coverage for ingress, continuation, mismatch reset, validation failure, and day completion.
- `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py` — Added integration coverage for stuck-flow recovery and send/follow-up retry paths.
