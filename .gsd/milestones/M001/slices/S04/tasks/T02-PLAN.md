# T02: Recovery and retry integration tests

**Slice:** S04 — **Milestone:** M001

## Description

Create integration tests that exercise stuck flow detection and auto-recovery, failed outbound send retry mechanics, and deferred follow-up retry behavior.

Purpose: Prove that the recovery and retry infrastructure built in Phases 50-51 works as integrated chains -- stuck flows get detected and recovered, failed sends get retried with backoff, and exhausted retries surface permanent failures.
Output: `tests/integration/test_flow_recovery_retry_e2e.py` with focused integration tests for recovery and retry paths.

## Must-Haves

- [ ] "Integration test exercises stuck flow detection identifying a flow stuck in awaiting_response beyond the threshold"
- [ ] "Integration test exercises auto-recovery attempting prompt resend for a stuck flow and verifying the flow progresses"
- [ ] "Integration test exercises auto-recovery selecting day advancement when day_complete is true but unverified"
- [ ] "Integration test exercises failed outbound send triggering the Celery retry task and verifying eventual delivery on retry success"
- [ ] "Integration test exercises retry exhaustion marking the send as permanently failed with failure metadata in flow state"
- [ ] "Integration test exercises deferred follow-up retry after initial execution failure"
- [ ] "All recovery and retry integration tests pass in a single pytest run"

## Files

- `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py`
