# Corrections Checklist

- [x] Implement saga retry scheduling (implemented in `app/tasks/saga_retry.py`, 60/120/240s)
- [x] Add compensation failure alerts (Sentry + DB alert + email in `app/tasks/saga_retry.py`)
- [x] Align compensation backoff/TTL with spec (1/2/4s, 30 days)
- [ ] Add saga observability metrics (executions, compensations, durations)
- [ ] Fix integration fixtures and model usage in saga tests
- [ ] Add retry/error unit tests for saga orchestrator
- [ ] Configure test DB and rerun coverage + integration tests
