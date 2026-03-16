---
id: T02
parent: S01
milestone: M007
provides:
  - "_send_all_sequential" checks expects_response per message inside the loop, stopping immediately when True
key_files:
  - backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py
key_decisions:
  - Moved expects_response check from post-loop (last-message-only) into per-iteration check, matching the pattern already used by _send_remaining_after_response
  - Added structured log with patient_id, flow_kind, day_number, stopped_at_index when halting mid-sequence
patterns_established:
  - Per-message expects_response check pattern is now consistent across all three send functions (sequential_auto, wait_each, remaining_after_response)
observability_surfaces:
  - "Structured log: 'Sequential send stopped at expects_response message' with patient_id, flow_kind, day_number, stopped_at_index, sent_count"
  - "PatientFlowState.step_data correctly persists awaiting_response and current_day_message_index at the stopping index"
duration: 10m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T02: Corrigir `_send_all_sequential` para respeitar `expects_response` por mensagem

**Fixed bulk-send bug: `_send_all_sequential` now stops at the first message with `expects_response=True` instead of blasting all messages and only checking the last one.**

## What Happened

The root cause was straightforward: `_send_all_sequential` had a for-loop that sent ALL messages, then after the loop checked `messages[-1].get("expects_response", False)`. A message in the middle with `expects_response=True` was completely ignored.

The fix moved the `expects_response` check inside the loop, right after each message is sent. When a message has `expects_response=True`:
1. `_resolve_sent_message_id` is called for the current index
2. `_set_flow_progress` persists `awaiting_response=True` at that index
3. A structured log is emitted with patient_id, flow_kind, day_number, stopped_at_index
4. The method returns `{"status": "waiting", "message_index": i, "awaiting_response": True, "sent_count": sent_count}` immediately

If no message has `expects_response=True`, the day advances normally via `advance_day_atomic` — unchanged behavior.

Confirmed `_send_remaining_after_response` already handles `expects_response` correctly per-message (step 4 of plan) — no changes needed.

## Verification

All three slice-level test suites pass:

- `test_sequencing_expects_response.py` — **7/7 passed** (including `test_sequential_auto_stops_at_expects_response` which previously failed)
- `test_sequential_message_handler.py` — **20/20 passed** (no regressions)
- `test_flow_advance_awaiting_response_block.py` — **5/5 passed** (no regressions)

## Diagnostics

- **Log grep**: `grep "Sequential send stopped at expects_response" <log>` shows every time the sequential send halted mid-sequence
- **DB query**: `SELECT step_data->'awaiting_response', step_data->'current_day_message_index' FROM patient_flow_states WHERE status='active'` — verify no `awaiting_response=true` with `day_complete=true`
- **Failure shape**: If a mid-sequence message fails to send, the method returns `status: "error"` before persisting wait state — no orphaned awaiting flags

## Deviations

None — implementation followed the plan exactly.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` — Fixed `_send_all_sequential` to check `expects_response` per message inside the loop, added structured log
- `.gsd/milestones/M007/slices/S01/tasks/T02-PLAN.md` — Added Observability Impact section (pre-flight fix)
- `.gsd/milestones/M007/slices/S01/S01-PLAN.md` — Marked T02 as done
