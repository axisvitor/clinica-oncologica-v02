---
id: T01
parent: S01
milestone: M007
provides:
  - test suite isolating expects_response sequencing behavior per send_mode
  - confirmed bug diagnosis: _send_all_sequential ignores per-message expects_response
key_files:
  - backend-hormonia/tests/unit/services/flow/test_sequencing_expects_response.py
key_decisions:
  - Reused existing shim pattern from test_sequential_message_handler.py for module isolation
  - Globally patched advance_day_atomic via autouse fixture to avoid DB dependency in all tests
  - Stubbed _send_flow_message, _personalize_message_ai, _await_inter_message_delay at handler level for pure logic testing
patterns_established:
  - _make_messages() helper builds message dicts from boolean expects_response flags
  - autouse patch_advance_day_atomic fixture prevents DB calls in sequencing tests
observability_surfaces:
  - none (test-only task)
duration: 45m
verification_result: partial — tests written and structurally valid, execution blocked by environment issue
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Criar suite de testes focada em expects_response e diagnosticar o bug de bulk

**Created 7-test suite reproducing the bulk-send bug in `_send_all_sequential` and validating correct behavior in `_send_remaining_after_response` and `_send_wait_each_with_auto_advance`.**

## What Happened

Read the existing test patterns in `test_sequential_message_handler.py` (610 lines, 20 tests) and the production code in `sequencing.py`. Confirmed the bug via code analysis:

**Bug root cause:** `_send_all_sequential` iterates ALL messages in a `for` loop with no early exit. After the loop, it only checks `messages[-1].get("expects_response", False)` — the LAST message. If a message in the middle has `expects_response=true`, it is sent but the system does not stop to wait for a response. All subsequent messages fire immediately (bulk-send).

Created `test_sequencing_expects_response.py` with 7 tests across 5 classes:

1. `TestSequentialAutoStopsAtExpectsResponse::test_sequential_auto_stops_at_expects_response` — **BUG REPRO**: 3 msgs [F,T,F], expects only 2 sends. Will FAIL pre-fix (current code sends all 3).
2. `TestSequentialAutoAllFalseSendsAll::test_sequential_auto_all_false_sends_all` — 3 msgs all false, all sent, day advances. Should PASS pre-fix.
3. `TestSequentialAutoLastExpectsResponse::test_sequential_auto_last_expects_response` — 3 msgs [F,F,T], all sent, awaiting_response on last. Should PASS pre-fix (current code handles this case).
4. `TestContinuationAfterResponseRespectsExpectsResponse::test_continuation_after_response_respects_expects_response` — `_send_remaining_after_response` with expects_response=true at start_index. Should PASS pre-fix.
5. `TestContinuationAfterResponseRespectsExpectsResponse::test_continuation_all_false_completes_day` — continuation with all false completes day. Should PASS pre-fix.
6. `TestWaitEachStopsAtFirstExpectsResponse::test_wait_each_stops_at_expects_response` — wait_each mode stops at expects_response=true. Should PASS pre-fix.
7. `TestWaitEachStopsAtFirstExpectsResponse::test_wait_each_completes_when_all_false` — wait_each with all false completes. Should PASS pre-fix.

## Verification

- **Test file structure**: Confirmed valid — 7 tests in 5 classes, all using the established fixture pattern.
- **pytest execution**: BLOCKED — WSL filesystem I/O became unresponsive during test runs, causing all Python subprocess invocations (including trivial `python -c "print('hello')"`) to hang. This is an environment issue, not a code issue. The earlier run of existing tests (20/20 passed in 2.8s) confirms the conftest and venv work when the filesystem is responsive.
- **Bug diagnosis**: CONFIRMED via static analysis of `sequencing.py` lines 60-97. The `for i, msg in enumerate(messages)` loop sends every message. The `expects_response` check at line 86 only examines `messages[-1]`, not the current `msg` in the loop.

### Resume verification command

When the environment recovers, run:
```bash
cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py -vv
```

Expected results:
- `test_sequential_auto_stops_at_expects_response` → **FAIL** (bug reproduction)
- All other 6 tests → **PASS**

## Diagnostics

None — test-only task. The bug is in `_send_all_sequential` (sequencing.py:60-97), specifically the loop structure that sends all messages without checking per-message `expects_response`.

## Deviations

- Added `patch_advance_day_atomic` as autouse fixture (not in plan) — necessary because `advance_day_atomic` makes real DB calls with optimistic locking that can't run with mock DB.
- Could not execute tests due to WSL environment degradation — file written and structurally validated but not runtime-verified.

## Known Issues

- WSL filesystem I/O hangs prevented test execution. This is transient — the same venv/conftest worked at the start of the session (20 existing tests passed). Resume by re-running the verification command.

## Files Created/Modified

- `backend-hormonia/tests/unit/services/flow/test_sequencing_expects_response.py` — new test suite with 7 tests covering expects_response sequencing across send modes
