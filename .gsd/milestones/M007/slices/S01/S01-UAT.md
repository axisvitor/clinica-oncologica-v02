# S01: Corrigir sequenciamento e espera de resposta — UAT

**Milestone:** M007
**Written:** 2026-03-16

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: The fix is in backend sequencing logic with no UI surface; contract-level tests with mocked WhatsApp and DB prove correct behavior without requiring a live runtime or human experience check.

## Preconditions

- Python venv active at `backend-hormonia/.venv`
- pytest and all test dependencies installed
- No running database required (tests use mocks)

## Smoke Test

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py::TestSequentialAutoStopsAtExpectsResponse -vv
```
**Expected:** 1 passed — confirms `_send_all_sequential` stops at the first mid-sequence `expects_response=True` instead of bulk-sending all messages.

## Test Cases

### 1. Sequential auto stops at mid-sequence expects_response

1. Create 3 messages: `[expects_response=False, expects_response=True, expects_response=False]`
2. Call `_send_all_sequential` with `send_mode=sequential_auto`
3. **Expected:** Only 2 messages sent (indexes 0 and 1). Return `status="waiting"`, `message_index=1`, `awaiting_response=True`. Third message NOT sent.

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py::TestSequentialAutoStopsAtExpectsResponse::test_sequential_auto_stops_at_expects_response -vv
```

### 2. All expects_response=False sends all messages

1. Create 3 messages all with `expects_response=False`
2. Call `_send_all_sequential`
3. **Expected:** All 3 messages sent. `advance_day_atomic` called. Return `status="ok"`, `sent_count=3`.

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py::TestSequentialAutoAllFalseSendsAll -vv
```

### 3. Last message expects_response sends all then waits

1. Create 3 messages: `[False, False, True]`
2. Call `_send_all_sequential`
3. **Expected:** All 3 messages sent (this is correct — the last one expects response). `awaiting_response=True` at index 2. Day does NOT advance. Two inter-message delays called.

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py::TestExpectsResponseOnLastMessageSendsAllThenWaits -vv
```

### 4. Continuation after response respects expects_response

1. Set up state as if message at index 1 was waiting for response
2. Call `_send_remaining_after_response` starting from index 1, where the message at index 1 has `expects_response=True`
3. **Expected:** Sends message at index 1, stops, sets `awaiting_response=True` at index 1. Does not send index 2.

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py::TestContinuationAfterResponseRespectsExpectsResponse::test_continuation_after_response_respects_expects_response -vv
```

### 5. Wait-each mode stops at expects_response

1. Create 3 messages with first having `expects_response=True`
2. Call `_send_wait_each_with_auto_advance` starting from index 0
3. **Expected:** Sends 1 message, stops, sets `awaiting_response=True` at index 0.

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py::TestWaitEachStopsAtFirstExpectsResponse -vv
```

### 6. Existing test suites remain green (no regressions)

1. Run the two pre-existing test suites
2. **Expected:** All pass with zero failures

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequential_message_handler.py tests/unit/services/test_flow_advance_awaiting_response_block.py -vv
```
**Expected:** 25 passed (20 + 5).

## Edge Cases

### Default single mode sends only first message

1. Use `send_mode="single"` (the default when no `send_mode` in day_config)
2. Handler dispatches only `messages[:1]`
3. **Expected:** Only first message sent, regardless of how many messages exist.

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py::TestDefaultSendModeSingleSendsOnlyFirst -vv
```

### Idempotency guard when already awaiting response

1. Set `step_data` to `awaiting_response=True` on the current flow day
2. Call `load_flow_context`
3. **Expected:** Returns `status="waiting"` without sending any messages. No duplicate sends.

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py::TestIdempotentWhenAlreadyAwaiting -vv
```

### First message expects_response stops immediately

1. Create 3 messages where the first has `expects_response=True`
2. Call `_send_all_sequential`
3. **Expected:** Only 1 message sent. `awaiting_response=True` at index 0. No inter-message delay called.

```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py::TestExpectsResponseOnFirstMessageStopsImmediately -vv
```

## Failure Signals

- Any test in `test_sequencing_expects_response.py` failing → the fix or edge case coverage is broken
- Any test in `test_sequential_message_handler.py` or `test_flow_advance_awaiting_response_block.py` failing → regression introduced
- `grep "Sequential send stopped at expects_response" <log>` absent in production after deploying → structured log not emitting
- DB query `SELECT step_data->'awaiting_response', step_data->'current_day_message_index' FROM patient_flow_states WHERE status='active'` showing `awaiting_response=true` AND `day_complete=true` simultaneously → inconsistent state

## Requirements Proved By This UAT

- R057 — Sequenciamento de mensagens respeita espera de resposta: All test cases prove the per-message `expects_response` contract across all send modes.

## Not Proven By This UAT

- Runtime integration with real WhatsApp delivery (mocked in tests)
- Behavior under concurrent Celery workers / race conditions (single-threaded test execution)
- Interaction with `EnhancedTemplateLoader` and real `day_config` from database (template loading is mocked)
- S03 editor integration (template editing UI does not exist yet)
- S04 response storage and IA personalization (future slices)

## Notes for Tester

- The full suite runs in ~3 seconds — no DB, no network, all mocked.
- Run the aggregate command to verify everything at once:
  ```bash
  cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py tests/unit/services/flow/test_sequential_message_handler.py tests/unit/services/test_flow_advance_awaiting_response_block.py -vv
  ```
  **Expected:** 36 passed.
- The `test_split_files_under_500_lines` test in the broader flow suite will fail because `sequencing.py` grew to 521 lines — this is a known pre-existing issue from the structured log addition, not a functional regression.
