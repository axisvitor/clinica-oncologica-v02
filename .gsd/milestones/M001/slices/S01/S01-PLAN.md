# S01: Pipeline Reliability

**Goal:** Fix silent patient stall when sequential gate encounters a context mismatch.
**Demo:** Fix silent patient stall when sequential gate encounters a context mismatch.

## Must-Haves


## Tasks

- [x] **T01: Sequential gate context mismatch recovery** `est:25m`
  - Fix silent patient stall when sequential gate encounters a context mismatch.

Purpose: Currently, when `load_response_context` detects a mismatch between the inbound response context and the pending flow state (e.g., wrong flow_day, wrong message_index), it returns `status: "waiting"` with `reason: "context_mismatch"`. The patient stays stuck forever because no recovery mechanism exists. This plan adds a counter-based recovery: after a configurable number of consecutive mismatches, the flow resets `awaiting_response=False` so the daily flow processor can re-send the prompt on the next cycle.

Output: Modified `_flow_response_flow.py` with mismatch counting and auto-reset, helper in `sequential_response_gate.py`, and comprehensive unit tests.
- [x] **T02: Outbound message send retry via Celery** `est:12m`
  - Add automatic Celery-based retry with exponential backoff for failed outbound WhatsApp flow messages.

Purpose: Currently, when `_send_flow_message` in `sequencing.py` calls `whatsapp_service.send_message()` and it fails, the method just returns `False`, causing the flow to return `status: "error"`. The patient's flow stalls with no retry. This plan creates a dedicated Celery task `retry_failed_flow_send` that re-attempts delivery with exponential backoff (max 3 attempts), and modifies `_send_flow_message` to enqueue this task on failure instead of silently giving up.

Output: New Celery task `send_retry.py`, modified `sequencing.py`, and tests.
- [x] **T03: Deferred follow-up retry and atomic day advancement** `est:20m`
  - Ensure deferred follow-up sends are retried on failure and day advancement is atomic and verified.

Purpose: Two related silent-failure paths are fixed: (1) When the follow-up system's MessageExecutor fails to send a deferred message, the failure is swallowed and the follow-up is silently dropped. This plan adds a Celery retry task for follow-up sends. (2) When a flow day completes and the day advancement step fails, the flow can end up in a broken state where day_complete=True but current_step was never incremented. This plan makes day advancement atomic with a verification flag.

Output: New Celery task `followup_retry.py`, modified MessageExecutor, atomic day advancement in sequencing, and tests for both.
- [x] **T04: Template day_config validation** `est:12m`
  - Validate template day_config at flow start so malformed configs fail fast with clear errors.

Purpose: Currently, `load_flow_context` in `_flow_message_flow.py` does minimal validation of the day_config returned by `handler._get_day_config()`. It checks if it is a dict, if messages is a list, and if send_mode is valid. But it does not validate the structure of individual messages (e.g., missing `content` field, invalid `expects_response` type) or detect completely empty configs that should not silently skip. This plan creates a dedicated `validate_day_config` function that performs thorough validation and is called early in `load_flow_context`, failing fast with a `DayConfigValidationError` that includes specific details about what is wrong.

Output: New `config_validation.py` module, modified `_flow_message_flow.py` with early validation, and comprehensive tests.

## Files Likely Touched

- `backend-hormonia/app/services/flow/_flow_response_flow.py`
- `backend-hormonia/app/services/flow/sequential_response_gate.py`
- `backend-hormonia/app/services/flow/_flow_orchestration_utils.py`
- `backend-hormonia/tests/unit/services/flow/test_sequential_gate_mismatch_recovery.py`
- `backend-hormonia/app/tasks/flows/send_retry.py`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py`
- `backend-hormonia/tests/unit/tasks/test_send_retry_task.py`
- `backend-hormonia/app/tasks/flows/followup_retry.py`
- `backend-hormonia/app/services/follow_up_system/execution/message.py`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py`
- `backend-hormonia/app/services/flow/management/advancement.py`
- `backend-hormonia/tests/unit/tasks/test_followup_retry_task.py`
- `backend-hormonia/tests/unit/services/test_day_advancement_atomic.py`
- `backend-hormonia/app/services/flow/config_validation.py`
- `backend-hormonia/app/services/flow/_flow_message_flow.py`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py`
- `backend-hormonia/tests/unit/services/flow/test_day_config_validation.py`
