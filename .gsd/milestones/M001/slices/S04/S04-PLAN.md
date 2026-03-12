# S04: Pipeline Verification

**Goal:** Create integration tests that exercise the full pipeline from webhook arrival through sequential gate, continuation dispatch, and next question send.
**Demo:** Create integration tests that exercise the full pipeline from webhook arrival through sequential gate, continuation dispatch, and next question send.

## Must-Haves


## Tasks

- [x] **T01: End-to-end pipeline integration tests** `est:55m`
  - Create integration tests that exercise the full pipeline from webhook arrival through sequential gate, continuation dispatch, and next question send.

Purpose: Prove the pipeline built in Phases 50-52 works as an integrated chain under both happy-path and failure conditions, catching integration bugs that unit tests with mocks cannot.
Output: `tests/integration/test_flow_pipeline_e2e.py` with focused integration tests for the pipeline chain.
- [x] **T02: Recovery and retry integration tests** `est:45m`
  - Create integration tests that exercise stuck flow detection and auto-recovery, failed outbound send retry mechanics, and deferred follow-up retry behavior.

Purpose: Prove that the recovery and retry infrastructure built in Phases 50-51 works as integrated chains -- stuck flows get detected and recovered, failed sends get retried with backoff, and exhausted retries surface permanent failures.
Output: `tests/integration/test_flow_recovery_retry_e2e.py` with focused integration tests for recovery and retry paths.

## Files Likely Touched

- `backend-hormonia/tests/integration/test_flow_pipeline_e2e.py`
- `backend-hormonia/pyproject.toml`
- `backend-hormonia/tests/integration/test_flow_recovery_retry_e2e.py`
