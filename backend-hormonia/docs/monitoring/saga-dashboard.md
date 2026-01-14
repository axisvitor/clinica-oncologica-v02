# Saga Dashboard

Suggested panels for monitoring the patient onboarding saga.

## Transaction Duration
- Histogram: `saga_transaction_duration_seconds`
- Focus: p50, p95, p99 by step=complete

## Phone Normalization
- Counter: `saga_phone_normalization_total`
- Breakdown by `format_detected` (brazilian|e164|other)

## Saga Success Rate
- Counters: `saga_onboarding_starts_total`, `saga_onboarding_completions_total`,
  `saga_onboarding_failures_total`
- Derived: success_rate = completions / starts

## Celery Task Lag
- Track time between message scheduling and send execution.
- Suggested source: message timestamps (scheduled_for vs sent_at) or task runtime metrics.

## Compensation Failures
- Counter: `saga_compensations_total` with `result=failed`
- Alert on spikes or sustained non-zero failure rate.
