# Requirements

## Active

None currently assigned.

## Validated

### FLOW-01 — Sequential gate recovers context mismatch with retry/reset instead of silent wait

- Status: validated
- Class: core-capability
- Source: milestone M001
- Primary Slice: S01

Sequential gate recovers context mismatches via bounded retry/reset behavior instead of leaving patients silently stuck.

### FLOW-02 — Failed outbound sends retry automatically via Celery with exponential backoff

- Status: validated
- Class: core-capability
- Source: milestone M001
- Primary Slice: S01

Failed outbound flow sends automatically retry in the background with bounded backoff and permanent-failure recording.

### FLOW-03 — Failed deferred follow-up sends retry via task queue

- Status: validated
- Class: core-capability
- Source: milestone M001
- Primary Slice: S01

Deferred follow-up send failures are re-queued and retried instead of being silently dropped.

### FLOW-04 — Day advancement after day_complete is atomic and verified

- Status: validated
- Class: core-capability
- Source: milestone M001
- Primary Slice: S01

Day completion uses atomic verified advancement semantics so next-day progression cannot skip silently.

### FLOW-05 — Template day_config validates at flow start and fails fast when malformed

- Status: validated
- Class: core-capability
- Source: milestone M001
- Primary Slice: S01

Malformed day configuration payloads fail fast with explicit validation errors during flow startup/send-day entry.

### RECV-01 — Stuck-flow detector runs periodically for awaiting_response flows

- Status: validated
- Class: core-capability
- Source: milestone M001
- Primary Slice: S02

A periodic Celery Beat task detects stalled awaiting-response flows using bounded thresholds.

### RECV-02 — Automatic recovery attempts resend or day advance based on stalled state

- Status: validated
- Class: core-capability
- Source: milestone M001
- Primary Slice: S02

Detected stalled flows attempt bounded resend/day-advance recovery with idempotency protection.

### RECV-03 — Admins can reset, advance, and unstick patient flows via API

- Status: validated
- Class: operator-capability
- Source: milestone M001
- Primary Slice: S02

Operators can intervene through admin endpoints to reset, advance, or unstick patient flows.

### RECV-04 — Failed flow operations are visible to operators

- Status: validated
- Class: operator-capability
- Source: milestone M001
- Primary Slice: S02

Failed flow operations are queryable through admin APIs using persisted flow-state markers.

### OBS-01 — Flow health endpoint shows active, stalled, failed, and completed counts

- Status: validated
- Class: observability
- Source: milestone M001
- Primary Slice: S03

Operators can query real-time flow health counts through a dedicated admin API.

### OBS-02 — Stalled-flow alert fires when patients do not progress within threshold

- Status: validated
- Class: observability
- Source: milestone M001
- Primary Slice: S03

Structured stalled-flow alerts and optional webhook fan-out fire when configured stall thresholds are crossed.

### OBS-03 — AI personalization fallback rate is tracked via metric

- Status: validated
- Class: observability
- Source: milestone M001
- Primary Slice: S03

Deterministic personalization fallbacks increment a reason-labeled Prometheus counter.

### OBS-04 — Correlation ID propagates from webhook through the full flow chain

- Status: validated
- Class: observability
- Source: milestone M001
- Primary Slice: S03

Correlation IDs are created or reused at WuzAPI ingress and propagated through continuation and send logs.

### TEST-01 — Integration tests cover full pipeline: webhook arrival -> sequential gate -> continuation -> next question send

- Status: validated
- Class: core-capability
- Source: inferred
- Primary Slice: S04

Integration tests cover full pipeline: webhook arrival -> sequential gate -> continuation -> next question send

### TEST-02 — Integration tests cover stuck flow detection -> auto-recovery path

- Status: validated
- Class: core-capability
- Source: inferred
- Primary Slice: S04

Integration tests cover stuck flow detection -> auto-recovery path

### TEST-03 — Integration tests cover retry mechanics for failed outbound sends

- Status: validated
- Class: core-capability
- Source: inferred
- Primary Slice: S04

Integration tests cover retry mechanics for failed outbound sends

## Deferred

## Out of Scope
