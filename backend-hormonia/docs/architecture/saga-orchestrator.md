# Saga Orchestrator

This document describes the patient onboarding saga architecture, with a focus
on phone normalization and transaction timing.

## Phone Normalization Strategy

- All entry points normalize phone numbers using `PhoneValidationMode.BR_TO_E164`.
- Accepted inputs: Brazilian digits (e.g. `11987654321`), formatted (`(11) 98765-4321`),
  and already E.164 (`+5511987654321`).
- Stored format: E.164 only, used for duplicate detection and phone hashing.
- Duplicate detection uses normalized phones to prevent variants of the same
  number from creating multiple patients.

## Transaction Optimization

- Step 3 (welcome message) is asynchronous and does not block the transaction.
- The saga only schedules the message (status `PENDING`) in the database.
- A Celery worker sends the message after commit, with a 5 second countdown
  to avoid race conditions where the message row is not yet visible.
- Expected transaction duration is below 2 seconds under normal load.

## Monitoring and Alerts

Metrics exposed for observability:
- `saga_transaction_duration_seconds` (step=complete)
- `saga_step_duration_seconds` (step_name=create_patient|initialize_flow|schedule_message)
- `saga_phone_normalization_total` (format_detected=brazilian|e164|other)
- `saga_onboarding_starts_total`, `saga_onboarding_completions_total`,
  `saga_onboarding_failures_total`
- `saga_compensations_total`

Recommended alerts:
- Compensation failures (rate > threshold)
- High saga failure rate
- Transaction duration p95 > 2s
