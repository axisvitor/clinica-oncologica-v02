# T02: Outbound message send retry via Celery

**Slice:** S01 — **Milestone:** M001

## Description

Add automatic Celery-based retry with exponential backoff for failed outbound WhatsApp flow messages.

Purpose: Currently, when `_send_flow_message` in `sequencing.py` calls `whatsapp_service.send_message()` and it fails, the method just returns `False`, causing the flow to return `status: "error"`. The patient's flow stalls with no retry. This plan creates a dedicated Celery task `retry_failed_flow_send` that re-attempts delivery with exponential backoff (max 3 attempts), and modifies `_send_flow_message` to enqueue this task on failure instead of silently giving up.

Output: New Celery task `send_retry.py`, modified `sequencing.py`, and tests.

## Must-Haves

- [ ] "When an outbound WhatsApp flow message send fails, a Celery retry task is enqueued automatically"
- [ ] "The retry task uses exponential backoff with jitter (base 60s, factor 2, max 3 attempts)"
- [ ] "After 3 failed attempts, the message is marked as permanently_failed with a structured log and the flow step records the failure"
- [ ] "Successful retry delivers the message and the flow continues normally"

## Files

- `backend-hormonia/app/tasks/flows/send_retry.py`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py`
- `backend-hormonia/tests/unit/tasks/test_send_retry_task.py`
