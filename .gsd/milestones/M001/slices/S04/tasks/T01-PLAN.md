# T01: End-to-end pipeline integration tests

**Slice:** S04 — **Milestone:** M001

## Description

Create integration tests that exercise the full pipeline from webhook arrival through sequential gate, continuation dispatch, and next question send.

Purpose: Prove the pipeline built in Phases 50-52 works as an integrated chain under both happy-path and failure conditions, catching integration bugs that unit tests with mocks cannot.
Output: `tests/integration/test_flow_pipeline_e2e.py` with focused integration tests for the pipeline chain.

## Must-Haves

- [ ] "Integration test exercises webhook arrival through sequential gate evaluation to continuation dispatch"
- [ ] "Integration test exercises continuation dispatch through next question send via sequential message handler"
- [ ] "Integration test verifies correlation ID propagates from webhook entry through all processing stages"
- [ ] "Integration test verifies day config validation rejects malformed config at flow start"
- [ ] "All pipeline integration tests pass in a single pytest run"

## Files

- `backend-hormonia/tests/integration/test_flow_pipeline_e2e.py`
- `backend-hormonia/pyproject.toml`
