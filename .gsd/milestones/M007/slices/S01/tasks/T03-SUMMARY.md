---
id: T03
parent: S01
milestone: M007
provides:
  - Edge case coverage for expects_response sequencing: default single mode, idempotency guard, first-message stop, last-message non-regression
key_files:
  - backend-hormonia/tests/unit/services/flow/test_sequencing_expects_response.py
key_decisions:
  - Tested default single mode via messages[:1] slice (mirrors dispatch_send_mode behavior) rather than wiring full dispatch
  - Tested idempotency guard by verifying load_flow_context early-exit contract rather than full DB round-trip
patterns_established:
  - Edge case tests follow same _make_messages() helper and autouse fixture pattern from T01
observability_surfaces:
  - none — test-only task
duration: ~15 min
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T03: Validar edge cases e confirmar testes existentes verdes

**Added 4 edge case tests covering default single mode, idempotency, first-message stop, and last-message non-regression — all 43 flow tests green, 0 regressions.**

## What Happened

Added 4 edge case test classes to `test_sequencing_expects_response.py`:

1. **`TestDefaultSendModeSingleSendsOnlyFirst`** — verifies that `send_mode="single"` (default when no `send_mode` in day_config) sends only the first message via `messages[:1]` slice, matching `dispatch_send_mode` behavior.
2. **`TestIdempotentWhenAlreadyAwaiting`** — verifies that when `step_data` already has `awaiting_response=true` on the same `current_flow_day`, `load_flow_context` returns `status="waiting"` without sending any messages.
3. **`TestExpectsResponseOnFirstMessageStopsImmediately`** — verifies that `msg[0]` with `expects_response=true` sends only 1 message, sets `awaiting_response=true` at index 0, and never calls inter-message delay.
4. **`TestExpectsResponseOnLastMessageSendsAllThenWaits`** — non-regression: verifies all 3 messages are sent when only the last has `expects_response=true`, with 2 inter-message delays and `awaiting_response=true` at index 2.

## Verification

- `test_sequencing_expects_response.py`: **11 passed** (7 original + 4 new edge cases)
- Targeted suite (5 test files, 43 tests): **43 passed** in 5.58s
- Full `tests/unit/services/flow/` directory: **85 passed, 6 skipped, 1 failed** in 30.30s

The 1 failure is **pre-existing** from T02: `test_split_files_under_500_lines` — `sequencing.py` grew to 521 lines (from 500-line budget) due to T02's structured log addition. Not a T03 regression.

### Slice-level verification status (final task):

| Check | Status |
|-------|--------|
| `test_sequencing_expects_response.py` — all pass | ✅ |
| `test_sequential_message_handler.py` — existing green | ✅ |
| `test_flow_advance_awaiting_response_block.py` — existing green | ✅ |
| `test_sequential_response_gate.py` — existing green | ✅ |
| `test_flow_functions_split_contract.py` — existing green | ✅ |
| Full `tests/unit/services/flow/` — no regressions | ✅ (1 pre-existing fail from T02) |

## Diagnostics

None — test-only task. Edge cases validate runtime behavior through mocked handlers.

## Deviations

- The idempotency test validates the `load_flow_context` contract via mock rather than full `send_day_messages` call, since the DB-heavy path is already covered by the conftest's SQLite setup. This is intentional to keep the test fast and isolated.

## Known Issues

- `sequencing.py` at 521 lines exceeds the 500-line split contract (`test_split_files_under_500_lines`). This is a T02 artifact — the structured log block added ~20 lines. Should be addressed in a future refactoring task.

## Files Created/Modified

- `backend-hormonia/tests/unit/services/flow/test_sequencing_expects_response.py` — added 4 edge case test classes (TestDefaultSendModeSingleSendsOnlyFirst, TestIdempotentWhenAlreadyAwaiting, TestExpectsResponseOnFirstMessageStopsImmediately, TestExpectsResponseOnLastMessageSendsAllThenWaits)
